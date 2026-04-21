#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dataset PyTorch pour l'entraînement du MLP de contrôle.

Charge les fichiers JSONL générés par le système d'échantillonnage
(captures.jsonl = vecteurs d'état, labels.jsonl = commandes moteur,
 sequence_ids.jsonl = IDs de séquence pour frontières et split train/val).
"""

import json
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, Subset, WeightedRandomSampler
from pathlib import Path

# ============================================================
# Constantes de feature engineering (source de verite)
# Synchronisees vers ml_controller.py via normalization_stats.json
# ============================================================

# Seuils IR pour la detection de ligne et de surface
# Valeurs mesurees via Sensor Profiler sur zumi_1 (2026-03-28)
IR_OFFSET_DEFAULT = 8.8      # Offset bot_left - bot_right (mesure sur route noire)
GAP_THRESHOLD = 210.8        # ir_sum sous lequel la ligne blanche est visible
OFF_ROAD_THRESHOLD = 165.9   # ir_sum sous lequel on est hors piste (gazon)
GRASS_THRESHOLD = 140.0      # capteurs front sous ce seuil = gazon devant

# Dimensions du vecteur de base
OLD_STATE_DIM = 29           # ancien format (sans zone features)
INTERMEDIATE_STATE_DIM = 36  # format intermediaire (7 zone features, sans dash counts)
NEW_STATE_DIM = 38           # nouveau format (9 zone features, avec dash counts)
ZONE_FEATURES_DIM = 9        # nombre de features de zone ajoutees
ZONE_INSERT_POS = 27         # position d'insertion des zone features (avant camera, pour 29 -> 38)
FRONT_DASH_INSERT_POS = 30   # position d'insertion du front_dash_count_norm (pour 36 -> 38)
CENTER_DASH_INSERT_POS = 35  # position d'insertion du center_dash_count_norm (pour 36 -> 38)

# Features engineered ajoutees au vecteur de base
# Le vecteur de base est 36-dim (nouveau) ou 29-dim (ancien, zero-padde automatiquement)
# ou 28-dim / 21-dim si les features Detection (8-15) sont exclues.
# Les features engineered sont toujours ajoutees a la fin.
ENGINEERED_FEATURE_NAMES = [
    'calibrated_error',   # (ir_bot_r - ir_bot_l) - ir_offset
    'line_visible',       # 1.0 si ir_sum < GAP_THRESHOLD (IR)
    'cal_error_norm',     # calibrated_error / (ir_sum + eps)
    'gyro_z_rate',        # delta gyro_z (vitesse angulaire par tick)
    'heading_drift',      # gyro_z_rate * (1 - line_visible)
    'ir_error_derivative',# delta calibrated_error (vitesse de derive laterale)
    'ir_error_integral',  # moyenne glissante calibrated_error sur 5 pas (biais persistant)
    'gyro_z_accel',       # delta gyro_z_rate (virage qui s'intensifie ou se relache)
    'lookahead_delta',    # (line_camera_offset - cal_error_norm) * line_visible (anticipation)
    'ir_sum_accel',       # d²(ir_sum)/dt² : acceleration du signal IR global (transition ligne)
    'line_lost_duration', # compteur de ticks sans ligne visible, normalise par WINDOW_SIZE
]

INTEGRAL_WINDOW = 5  # Taille de la fenetre pour ir_error_integral

# Indices des features Detection (Haar) dans le vecteur brut 29-dim.
# Ces features sont inutilisees tant que les detecteurs Haar ne sont pas integres
# et peuvent etre exclues de facon reversible (exclude_detection=True).
DETECTION_INDICES = list(range(8, 16))  # 8 features: flag + 3 one-hot + 4 bbox

# Fenetre glissante: 25 pas d'historique (1.25 seconde a 20Hz)
WINDOW_SIZE = 25

# Dimension par pas de fenetre (calculee dynamiquement selon exclude_detection)
# 49 = 38 raw + 11 engineered (detection incluse)
# 41 = 30 raw + 11 engineered (detection exclue)
WINDOW_FEATURE_DIM = 41  # defaut: detection exclue (mis a jour dynamiquement)

# Ponderation temporelle exponentielle de la fenetre glissante.
# Chaque frame t est multiplie par alpha^(window_size - 1 - t):
#   frame le plus recent (t=window_size-1) = 1.0
#   frame le plus ancien (t=0) = alpha^(window_size-1)
# alpha=1.0 desactive le decay. alpha=0.85 avec 25 frames: ancien=0.29, milieu=0.54.
TEMPORAL_DECAY = 0.85

# Indice du gyro_z dans le vecteur de base (29-dim complet)
# Si exclude_detection=True, l'indice effectif est recalcule dynamiquement.
GYRO_Z_INDEX_RAW = 18  # indice dans le vecteur brut 29-dim (toujours valide)
GYRO_Z_INDEX = 18       # indice effectif (mis a jour si detection exclue)

# Noms des categories d'actions
ACTION_NAMES = ["Arret", "Tout droit", "Tourne G", "Tourne D", "Recule"]


def classify_actions(captures, labels, sequence_ids=None, gyro_z_index=None,
                     rotation_thresh=3.0, stop_thresh=0.02):
    """Categorise les echantillons par action reelle via IMU.

    Utilise le delta du gyroscope (gyro_z[t] - gyro_z[t-1]) pour detecter
    les rotations plutot que les commandes moteur, car celles-ci sont
    biaisees par la correction PID de cap.

    Note: gyro_z est l'angle yaw CUMULATIF integre du gyroscope (en degres).
    Il s'accumule au sein d'une sequence et est reinitialise entre les sequences.
    On calcule le delta entre echantillons consecutifs pour obtenir la vitesse
    angulaire par tick, en mettant a zero les frontieres de sequence.

    Les frontieres sont detectees via sequence_ids (changement d'ID).

    Convention Zumi: gyro_z positif = rotation vers la gauche.

    Args:
        captures: array (N, D) avec gyro_z a l'index gyro_z_index
        labels: array (N, 2) commandes moteur normalisees [-1, 1]
        sequence_ids: array (N,) identifiant la sequence de chaque echantillon.
                      Si None, pas de detection de frontiere.
        gyro_z_index: indice du gyro_z dans captures. Si None, utilise GYRO_Z_INDEX.
        rotation_thresh: seuil delta gyro_z en deg/tick pour detecter une rotation
        stop_thresh: seuil commande moteur pour detecter un arret

    Returns:
        categories: array int (N,) — 0=arret, 1=forward, 2=turn_left,
                    3=turn_right, 4=reverse
    """
    # Resoudre l'index gyro_z au runtime (pas au chargement du module)
    # car GYRO_Z_INDEX est modifie dynamiquement par exclude_detection_features()
    if gyro_z_index is None:
        gyro_z_index = GYRO_Z_INDEX

    gyro_z_raw = captures[:, gyro_z_index]

    # Calculer le delta gyro_z (vitesse angulaire par tick)
    gyro_z_delta = np.zeros_like(gyro_z_raw)
    gyro_z_delta[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]

    # Mettre a zero les frontieres de sequence (changement d'ID de sequence)
    if sequence_ids is not None:
        boundaries = np.zeros(len(captures), dtype=bool)
        boundaries[0] = True
        boundaries[1:] = sequence_ids[1:] != sequence_ids[:-1]
        gyro_z_delta[boundaries] = 0.0
    else:
        # Fallback: gros sauts gyro = frontiere (cas sans sequence_ids)
        boundaries = np.abs(gyro_z_delta) > 150.0
        gyro_z_delta[boundaries] = 0.0

    left = labels[:, 0]
    right = labels[:, 1]
    speed_avg = (left + right) / 2.0

    is_stop = (np.abs(left) < stop_thresh) & (np.abs(right) < stop_thresh)
    is_rotating_left = (gyro_z_delta > rotation_thresh) & ~is_stop
    is_rotating_right = (gyro_z_delta < -rotation_thresh) & ~is_stop
    is_reverse = (speed_avg < -stop_thresh) & ~is_stop & ~is_rotating_left & ~is_rotating_right
    is_forward = ~is_stop & ~is_rotating_left & ~is_rotating_right & ~is_reverse

    categories = np.zeros(len(labels), dtype=np.int64)
    categories[is_stop] = 0
    categories[is_forward] = 1
    categories[is_rotating_left] = 2
    categories[is_rotating_right] = 3
    categories[is_reverse] = 4

    return categories


class ZumiControlDataset(Dataset):
    """Dataset pour l'apprentissage par imitation du contrôle Zumi.

    Format des données:
        - captures.jsonl: vecteurs d'état bruts (dim = 29, ou 21 si detection exclue)
        - labels.jsonl: commandes moteur normalisées [left, right] dans [-1, 1]
        - sequence_ids.jsonl: ID de séquence par échantillon (généré par aggregate_sequences.py)
    """

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Répertoire contenant captures.jsonl, labels.jsonl et sequence_ids.jsonl
        """
        self.data_dir = Path(data_dir)
        self.captures = []
        self.labels = []
        self.sequence_ids = None

        self._load_data()

    def _load_data(self):
        """Charge les fichiers JSONL en mémoire."""
        captures_path = self.data_dir / "captures.jsonl"
        labels_path = self.data_dir / "labels.jsonl"
        seqids_path = self.data_dir / "sequence_ids.jsonl"

        if not captures_path.exists():
            raise FileNotFoundError(f"Fichier captures.jsonl non trouvé: {captures_path}")
        if not labels_path.exists():
            raise FileNotFoundError(f"Fichier labels.jsonl non trouvé: {labels_path}")
        if not seqids_path.exists():
            raise FileNotFoundError(
                f"Fichier sequence_ids.jsonl non trouvé: {seqids_path}\n"
                f"Relancez aggregate_sequences.py pour le générer."
            )

        # Charger les captures (états)
        # Gere le melange 29-dim (ancien), 36-dim (intermediaire) et 38-dim (nouveau)
        # en zero-paddant aux positions semantiquement correctes.
        with open(captures_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    if len(row) == OLD_STATE_DIM:
                        # 29 -> 38: insere 9 zeros avant camera
                        row = (row[:ZONE_INSERT_POS]
                               + [0.0] * ZONE_FEATURES_DIM
                               + row[ZONE_INSERT_POS:])
                    elif len(row) == INTERMEDIATE_STATE_DIM:
                        # 36 -> 38: insere front_dash_count (pos 30) et center_dash_count (pos 35)
                        row = (row[:30]           # IR+eng+det+IMU+front_{det,conf,off}
                               + [0.0]             # front_dash_count_norm
                               + row[30:34]        # 4 corner features
                               + [0.0]             # center_dash_count_norm
                               + row[34:36])       # camera
                    self.captures.append(row)

        # Charger les labels (commandes)
        with open(labels_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.labels.append(json.loads(line))

        # Charger les IDs de séquence
        seq_ids = []
        with open(seqids_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    seq_ids.append(int(line))

        # Validation
        if len(self.captures) != len(self.labels):
            raise ValueError(
                f"Nombre d'échantillons incohérent: "
                f"{len(self.captures)} captures vs {len(self.labels)} labels"
            )
        if len(seq_ids) != len(self.captures):
            raise ValueError(
                f"sequence_ids.jsonl incompatible: "
                f"{len(seq_ids)} IDs vs {len(self.captures)} captures. "
                f"Relancez aggregate_sequences.py."
            )

        # Convertir en numpy
        self.captures = np.array(self.captures, dtype=np.float32)
        self.labels = np.array(self.labels, dtype=np.float32)
        self.sequence_ids = np.array(seq_ids, dtype=np.int32)

        n_seqs = len(np.unique(self.sequence_ids))
        print(f"[Dataset] Chargé {len(self)} échantillons ({n_seqs} séquences)")
        print(f"[Dataset] Dimension entrée: {self.input_dim}, Dimension sortie: {self.output_dim}")

    @property
    def input_dim(self) -> int:
        """Dimension du vecteur d'entrée."""
        return self.captures.shape[1] if len(self.captures) > 0 else 0

    @property
    def output_dim(self) -> int:
        """Dimension du vecteur de sortie."""
        return self.labels.shape[1] if len(self.labels) > 0 else 0

    def __len__(self) -> int:
        return len(self.captures)

    def __getitem__(self, idx: int):
        """Retourne un tuple (état, commande) en tenseurs PyTorch."""
        state = torch.from_numpy(self.captures[idx])
        command = torch.from_numpy(self.labels[idx])
        return state, command

    def _apply_mask(self, keep: np.ndarray):
        """Applique un masque booleen aux captures, labels et sequence_ids."""
        self.captures = self.captures[keep]
        self.labels = self.labels[keep]
        if self.sequence_ids is not None:
            self.sequence_ids = self.sequence_ids[keep]

    def deduplicate(self, threshold: float = 1e-4, min_run_length: int = 5):
        """Retire les echantillons consecutifs quasi-identiques.

        Ne retire que les groupes de doublons d'au moins min_run_length
        echantillons consecutifs ET qui sont dans la meme sequence.

        Args:
            threshold: Distance L2 minimale entre deux echantillons consecutifs.
            min_run_length: Nombre minimum d'echantillons consecutifs dans un
                           groupe pour qu'il soit considere comme un vrai doublon.
        """
        if len(self.captures) < 2:
            return

        diffs = np.linalg.norm(self.captures[1:] - self.captures[:-1], axis=1)
        is_dup = diffs < threshold

        # Ne pas considerer comme doublon si les echantillons sont de sequences differentes
        if self.sequence_ids is not None:
            seq_boundary = self.sequence_ids[1:] != self.sequence_ids[:-1]
            is_dup[seq_boundary] = False

        keep = np.ones(len(self.captures), dtype=bool)
        run_start = None
        n_removed = 0

        for i in range(len(is_dup)):
            if is_dup[i]:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None:
                    run_length = (i + 1) - run_start
                    if run_length >= min_run_length:
                        keep[run_start + 1 : i + 1] = False
                        n_removed += i - run_start
                    run_start = None

        if run_start is not None:
            run_length = len(self.captures) - run_start
            if run_length >= min_run_length:
                keep[run_start + 1 :] = False
                n_removed += len(self.captures) - run_start - 1

        self._apply_mask(keep)
        print(f"[Dataset] Deduplication: {n_removed} doublons retires "
              f"(groupes >= {min_run_length} samples, {len(self)} restants)")

    def remove_pwm_stops(self, stop_thresh: float = 0.02):
        """Retire les arrets PWM intercales dans les virages sur place.

        Le controle manuel utilise un PWM logiciel (duty 2/3) pour ralentir
        les rotations sur place : 2 ticks actifs suivis de 1 tick a (0,0).
        Ces arrets isoles sont des artefacts de l'interface humaine — le modele
        ML qui infere a 20 Hz n'en a pas besoin.

        Detection: un sample (0,0) est un arret PWM si le sample avant ET
        le sample apres (dans la meme sequence) ne sont PAS des arrets.
        Les vrais arrets (2+ consecutifs) ne sont pas touches.

        Args:
            stop_thresh: Seuil de commande moteur pour detecter un arret.
        """
        if len(self.labels) < 3:
            return

        n = len(self.labels)
        left = self.labels[:, 0]
        right = self.labels[:, 1]
        is_stop = (np.abs(left) < stop_thresh) & (np.abs(right) < stop_thresh)

        keep = np.ones(n, dtype=bool)
        n_removed = 0

        for i in range(1, n - 1):
            if not is_stop[i]:
                continue

            # Verifier que c'est dans la meme sequence
            if self.sequence_ids is not None:
                if (self.sequence_ids[i] != self.sequence_ids[i - 1] or
                        self.sequence_ids[i] != self.sequence_ids[i + 1]):
                    continue

            # Arret isole entre deux commandes non-nulles = artefact PWM
            if not is_stop[i - 1] and not is_stop[i + 1]:
                keep[i] = False
                n_removed += 1

        self._apply_mask(keep)
        print(f"[Dataset] PWM stops: {n_removed} arrets PWM isoles retires "
              f"({len(self)} restants)")

    def trim_stops(self, max_consecutive: int = 5, stop_thresh: float = 0.02):
        """Retire les sequences d'arret excessives (temps morts de collecte).

        Respecte les frontieres de sequence: un changement de sequence remet
        le compteur d'arret a zero.

        Args:
            max_consecutive: Nombre max d'echantillons d'arret consecutifs a garder.
            stop_thresh: Seuil de commande moteur pour detecter un arret.
        """
        if len(self.labels) < 2:
            return

        left = self.labels[:, 0]
        right = self.labels[:, 1]
        is_stop = (np.abs(left) < stop_thresh) & (np.abs(right) < stop_thresh)

        keep = np.ones(len(self.labels), dtype=bool)
        run_length = 0
        n_removed = 0
        prev_seq_id = -1

        for i in range(len(is_stop)):
            # Reset compteur aux frontieres de sequence
            if self.sequence_ids is not None and self.sequence_ids[i] != prev_seq_id:
                run_length = 0
                prev_seq_id = self.sequence_ids[i]

            if is_stop[i]:
                run_length += 1
                if run_length > max_consecutive:
                    keep[i] = False
                    n_removed += 1
            else:
                run_length = 0

        n_stops_remaining = int(is_stop[keep].sum())
        self._apply_mask(keep)
        print(f"[Dataset] Trim stops: {n_removed} arrets excessifs retires "
              f"(max {max_consecutive} consecutifs, {n_stops_remaining} arrets restants, "
              f"{len(self)} total)")

    def compute_ir_offset(self) -> float:
        """Estime l'offset IR bottom depuis le dataset (echantillons forward+straight)."""
        categories = classify_actions(self.captures, self.labels,
                                      sequence_ids=self.sequence_ids)
        forward_mask = categories == 1

        if forward_mask.sum() < 10:
            print(f"[Dataset] IR offset: pas assez d'echantillons forward, defaut={IR_OFFSET_DEFAULT}")
            return IR_OFFSET_DEFAULT

        # Parmi les forward, filtrer ceux vraiment droits (delta gyro_z faible)
        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]
        gyro_z_delta = np.zeros_like(gyro_z_raw)
        gyro_z_delta[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]

        # Mettre a zero les frontieres de sequence
        if self.sequence_ids is not None:
            boundaries = np.zeros(len(self.captures), dtype=bool)
            boundaries[0] = True
            boundaries[1:] = self.sequence_ids[1:] != self.sequence_ids[:-1]
            gyro_z_delta[boundaries] = 0.0

        fwd_delta = gyro_z_delta[forward_mask]
        straight_mask = np.abs(fwd_delta) < 5.0

        if straight_mask.sum() >= 10:
            ir_diff_straight = self.captures[forward_mask][straight_mask, 6]
        else:
            ir_diff_straight = self.captures[forward_mask, 6]

        offset = float(ir_diff_straight.mean())
        print(f"[Dataset] IR offset estime: {offset:.1f} "
              f"(n_straight={int(straight_mask.sum()) if straight_mask.sum() >= 10 else len(ir_diff_straight)})")
        return offset

    def pad_to_new_format(self):
        """Zero-pad les vecteurs aux formats anciens vers le nouveau format (38-dim).

        Gere 3 cas:
          - 29-dim (ancien): pas de zone features, pas de dash counts
              -> insere 9 zeros a position 27 (avant camera)
          - 36-dim (intermediaire): 7 zone features sans dash counts
              -> insere 2 zeros aux positions 30 (front_dash) et 35 (center_dash)
              pour preserver l'alignement semantique avec les features existantes
          - 38-dim (nouveau): no-op

        Doit etre appelee AVANT exclude_detection_features().
        """
        current_dim = self.captures.shape[1]
        n = len(self.captures)

        if current_dim == NEW_STATE_DIM:
            return  # deja au nouveau format

        if current_dim == OLD_STATE_DIM:
            zeros = np.zeros((n, ZONE_FEATURES_DIM), dtype=np.float32)
            self.captures = np.hstack([
                self.captures[:, :ZONE_INSERT_POS],   # IR + Detection + IMU
                zeros,                                 # 9 zone features (zero-filled)
                self.captures[:, ZONE_INSERT_POS:],    # camera features (2)
            ])
            print(f"[Dataset] Zero-pad: {OLD_STATE_DIM}-dim -> {NEW_STATE_DIM}-dim "
                  f"({ZONE_FEATURES_DIM} zone features inserees a pos {ZONE_INSERT_POS})")

        elif current_dim == INTERMEDIATE_STATE_DIM:
            # Format 36-dim: zone OK mais dash counts manquants.
            # Inserer 2 zeros aux bonnes positions semantiques:
            #   - position 30: front_dash_count_norm (apres front_offset_norm)
            #   - position 35: center_dash_count_norm (juste avant camera)
            # Layout 36-dim: [0..29, cL_det, cR_det, cL_area, cR_area, cam_off, cam_det]
            # Layout 38-dim: [0..29, front_dash, cL_det, cR_det, cL_area, cR_area, center_dash, cam_off, cam_det]
            zero_col = np.zeros((n, 1), dtype=np.float32)
            self.captures = np.hstack([
                self.captures[:, :30],       # IR + eng + detection + IMU + front_{det,conf,off}
                zero_col,                     # front_dash_count_norm (NEW)
                self.captures[:, 30:34],      # 4 corner features
                zero_col,                     # center_dash_count_norm (NEW)
                self.captures[:, 34:36],      # camera (2)
            ])
            print(f"[Dataset] Zero-pad dash counts: {INTERMEDIATE_STATE_DIM}-dim -> {NEW_STATE_DIM}-dim "
                  f"(2 zeros inseres aux positions {FRONT_DASH_INSERT_POS}, {CENTER_DASH_INSERT_POS})")

        else:
            print(f"[Dataset] WARNING: dimension inattendue ({current_dim}), "
                  f"attendu {OLD_STATE_DIM}, {INTERMEDIATE_STATE_DIM} ou {NEW_STATE_DIM}")

    def exclude_detection_features(self):
        """Retire les features Detection (indices 8-15) du vecteur brut.

        Doit etre appelee AVANT compute_engineered_features().
        Re-mappe les indices pour que les features suivantes gardent
        leur semantique (IR 0-7 inchanges, IMU decale, zones decalees, camera en fin).

        Reversible: ne pas appeler cette methode pour garder toutes les features.
        """
        global GYRO_Z_INDEX, WINDOW_FEATURE_DIM

        original_dim = self.captures.shape[1]
        keep_mask = [i for i in range(original_dim) if i not in DETECTION_INDICES]
        self.captures = self.captures[:, keep_mask]
        self._detection_excluded = True
        self._detection_keep_mask = keep_mask

        GYRO_Z_INDEX = GYRO_Z_INDEX_RAW - len(DETECTION_INDICES)

        new_raw_dim = self.captures.shape[1]
        WINDOW_FEATURE_DIM = new_raw_dim + len(ENGINEERED_FEATURE_NAMES)

        print(f"[Dataset] Detection exclue: {original_dim}-dim -> {new_raw_dim}-dim "
              f"(indices {DETECTION_INDICES[0]}-{DETECTION_INDICES[-1]} retires, "
              f"gyro_z_index={GYRO_Z_INDEX})")

    def compute_engineered_features(self, ir_offset: float = None):
        """Ajoute 9 features PID-inspired au vecteur de base.

        Features originales (5):
            calibrated_error, line_visible, cal_error_norm, gyro_z_rate, heading_drift
        Nouvelles features (4):
            ir_error_derivative, ir_error_integral, gyro_z_accel, lookahead_delta

        Doit etre appelee AVANT compute_sliding_windows().
        Fonctionne que Detection soit exclue ou non (utilise GYRO_Z_INDEX dynamique).
        """
        if ir_offset is None:
            ir_offset = self.compute_ir_offset()
        self._ir_offset = ir_offset

        n = len(self.captures)
        raw_dim = self.captures.shape[1]
        ir_bot_r = self.captures[:, 1]
        ir_bot_l = self.captures[:, 3]
        ir_sum = (ir_bot_l + ir_bot_r) / 2.0
        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]

        # Camera features: toujours les 2 derniers indices du vecteur brut
        line_camera_offset = self.captures[:, raw_dim - 2]

        # --- Features originales ---
        calibrated_error = (ir_bot_r - ir_bot_l) - (-ir_offset)
        line_visible = (ir_sum < GAP_THRESHOLD).astype(np.float32)
        cal_error_norm = calibrated_error / (ir_sum + 1e-6)

        gyro_z_rate = np.zeros(n, dtype=np.float32)
        gyro_z_rate[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]

        # Detecter les frontieres de sequence
        boundaries = np.zeros(n, dtype=bool)
        boundaries[0] = True
        if self.sequence_ids is not None:
            boundaries[1:] = self.sequence_ids[1:] != self.sequence_ids[:-1]
        gyro_z_rate[boundaries] = 0.0

        heading_drift = gyro_z_rate * (1.0 - line_visible)

        # --- Nouvelles features ---

        # ir_error_derivative: delta calibrated_error (vitesse de derive laterale)
        ir_error_derivative = np.zeros(n, dtype=np.float32)
        ir_error_derivative[1:] = calibrated_error[1:] - calibrated_error[:-1]
        ir_error_derivative[boundaries] = 0.0

        # ir_error_integral: moyenne glissante de calibrated_error sur INTEGRAL_WINDOW pas
        ir_error_integral = np.zeros(n, dtype=np.float32)
        # Trouver les debuts de chaque segment de sequence
        seg_starts = np.where(boundaries)[0]
        seg_ends = np.concatenate([seg_starts[1:], [n]])
        for s, e in zip(seg_starts, seg_ends):
            seg = calibrated_error[s:e]
            cumsum = np.cumsum(seg)
            padded = np.concatenate([[0.0], cumsum])
            idx = np.arange(len(seg))
            starts = np.maximum(0, idx - INTEGRAL_WINDOW + 1)
            counts = (idx - starts + 1).astype(np.float32)
            ir_error_integral[s:e] = (padded[idx + 1] - padded[starts]) / counts

        # gyro_z_accel: delta gyro_z_rate (virage qui s'intensifie ou se relache)
        gyro_z_accel = np.zeros(n, dtype=np.float32)
        gyro_z_accel[1:] = gyro_z_rate[1:] - gyro_z_rate[:-1]
        gyro_z_accel[boundaries] = 0.0
        # Aussi zero au pas juste apres une frontiere (gyro_z_rate[boundary]=0 est artificiel)
        boundary_plus1 = np.zeros(n, dtype=bool)
        boundary_plus1[1:] = boundaries[:-1]
        gyro_z_accel[boundary_plus1] = 0.0

        # lookahead_delta: discordance entre camera (ligne devant) et IR (ligne dessous)
        lookahead_delta = (line_camera_offset - cal_error_norm) * line_visible

        # --- Features DSP ---

        # ir_sum_accel: 2eme derivee de ir_sum (acceleration du signal IR global)
        # Detecte les transitions rapides entree/sortie de ligne (front montant/descendant)
        ir_sum_delta = np.zeros(n, dtype=np.float32)
        ir_sum_delta[1:] = ir_sum[1:] - ir_sum[:-1]
        ir_sum_delta[boundaries] = 0.0

        ir_sum_accel = np.zeros(n, dtype=np.float32)
        ir_sum_accel[1:] = ir_sum_delta[1:] - ir_sum_delta[:-1]
        ir_sum_accel[boundaries] = 0.0
        ir_sum_accel[boundary_plus1] = 0.0

        # line_lost_duration: compteur de ticks consecutifs sans ligne visible
        # Normalise par WINDOW_SIZE pour rester dans [0, 1]
        line_lost_duration = np.zeros(n, dtype=np.float32)
        for s, e in zip(seg_starts, seg_ends):
            counter = 0
            for i in range(s, e):
                if line_visible[i] > 0.5:
                    counter = 0
                else:
                    counter += 1
                line_lost_duration[i] = counter / WINDOW_SIZE

        new_features = np.column_stack([
            calibrated_error, line_visible, cal_error_norm,
            gyro_z_rate, heading_drift,
            ir_error_derivative, ir_error_integral, gyro_z_accel, lookahead_delta,
            ir_sum_accel, line_lost_duration
        ]).astype(np.float32)

        original_dim = self.captures.shape[1]
        self.captures = np.hstack([self.captures, new_features])

        print(f"[Dataset] Features engineered: {len(ENGINEERED_FEATURE_NAMES)} ajoutees "
              f"({original_dim}-dim -> {self.captures.shape[1]}-dim, ir_offset={ir_offset:.1f})")

    def compute_sliding_windows(self, window_size: int = None, temporal_decay: float = None):
        """Construit des fenetres glissantes a partir des vecteurs d'etat.

        Les frontieres de sequence sont detectees via sequence_ids (changement d'ID).
        Les pas avant une frontiere sont remplaces par des zeros (zero-padding).

        Doit etre appelee APRES compute_engineered_features() et AVANT le shuffle.
        """
        if window_size is None:
            window_size = WINDOW_SIZE
        if temporal_decay is None:
            temporal_decay = TEMPORAL_DECAY

        n_samples = len(self.captures)
        feature_dim = self.captures.shape[1]

        if n_samples < 2:
            return

        # Precalculer les poids temporels
        if temporal_decay < 1.0:
            decay_weights = np.array([
                temporal_decay ** (window_size - 1 - w) for w in range(window_size)
            ], dtype=np.float32)
        else:
            decay_weights = None

        # Detecter les frontieres de sequence via sequence_ids
        if self.sequence_ids is not None:
            seq_id = self.sequence_ids
            n_boundaries = int(np.sum(seq_id[1:] != seq_id[:-1])) + 1
        else:
            raise ValueError("sequence_ids requis pour compute_sliding_windows. "
                             "Relancez aggregate_sequences.py.")

        # Construire les fenetres de facon vectorisee
        windowed = np.zeros((n_samples, window_size * feature_dim), dtype=np.float32)

        for w in range(window_size):
            offset = window_size - 1 - w
            col_start = w * feature_dim
            col_end = (w + 1) * feature_dim

            weight = decay_weights[w] if decay_weights is not None else 1.0

            if offset == 0:
                windowed[:, col_start:col_end] = self.captures * weight
            else:
                valid_dst = slice(offset, n_samples)
                valid_src = slice(0, n_samples - offset)

                same_seq = seq_id[valid_dst] == seq_id[valid_src]

                temp = np.zeros((n_samples, feature_dim), dtype=np.float32)
                temp_dst = np.arange(offset, n_samples)
                temp[temp_dst[same_seq]] = self.captures[:n_samples - offset][same_seq] * weight
                windowed[:, col_start:col_end] = temp

        self.captures = windowed

        decay_str = f", decay={temporal_decay}" if temporal_decay < 1.0 else ""
        print(f"[Dataset] Fenetre glissante: {window_size} pas x {feature_dim} features = "
              f"{window_size * feature_dim}-dim "
              f"({n_boundaries} sequences{decay_str})")

    def compute_sample_weights(self) -> np.ndarray:
        """Calcule les poids par echantillon pour equilibrer les categories d'actions."""
        categories = classify_actions(self.captures, self.labels,
                                      sequence_ids=self.sequence_ids)

        class_counts = np.bincount(categories, minlength=5).astype(np.float64)
        class_counts[class_counts == 0] = 1.0

        class_weights = 1.0 / np.sqrt(class_counts)
        sample_weights = class_weights[categories]

        max_ratio = class_weights.max() / class_weights.min()
        print(f"[Dataset] Poids par categorie (equilibrage sqrt, IMU-based, ratio max: {max_ratio:.1f}x):")
        for i, name in enumerate(ACTION_NAMES):
            count = int(class_counts[i])
            weight = class_weights[i]
            print(f"  {name:15s}: {count:5d} samples, poids {weight:.6f}")

        return sample_weights

    def apply_feature_mask(self, mask: list):
        """Retire les features mortes en ne gardant que les indices du masque."""
        original_dim = self.captures.shape[1]
        self.captures = self.captures[:, mask]
        print(f"[Dataset] Masque applique: {original_dim}-dim -> {self.captures.shape[1]}-dim "
              f"({original_dim - len(mask)} features mortes retirees)")

    def normalize(self, mean: np.ndarray, std: np.ndarray):
        """Applique la normalisation z-score aux captures."""
        safe_std = std.copy()
        safe_std[safe_std < 1e-6] = 1.0
        self.captures = (self.captures - mean) / safe_std

    def get_statistics(self) -> dict:
        """Calcule les statistiques du dataset pour analyse."""
        return {
            "n_samples": len(self),
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "state_mean": self.captures.mean(axis=0).tolist(),
            "state_std": self.captures.std(axis=0).tolist(),
            "label_mean": self.labels.mean(axis=0).tolist(),
            "label_std": self.labels.std(axis=0).tolist(),
            "label_min": self.labels.min(axis=0).tolist(),
            "label_max": self.labels.max(axis=0).tolist(),
        }

    def compute_motor_efficiency(self) -> float:
        """Estime l'efficacite du moteur gauche depuis le biais des labels."""
        categories = classify_actions(self.captures, self.labels,
                                      sequence_ids=self.sequence_ids)
        forward_mask = categories == 1

        if forward_mask.sum() < 10:
            print("[Dataset] Motor efficiency: pas assez d'echantillons forward")
            return 1.0

        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]
        gyro_z_delta = np.zeros_like(gyro_z_raw)
        gyro_z_delta[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]

        if self.sequence_ids is not None:
            boundaries = np.zeros(len(self.captures), dtype=bool)
            boundaries[0] = True
            boundaries[1:] = self.sequence_ids[1:] != self.sequence_ids[:-1]
            gyro_z_delta[boundaries] = 0.0

        fwd_delta = gyro_z_delta[forward_mask]
        straight_mask = np.abs(fwd_delta) < 5.0

        fwd_labels = self.labels[forward_mask]
        if straight_mask.sum() >= 10:
            straight_labels = fwd_labels[straight_mask]
        else:
            straight_labels = fwd_labels

        mean_l = straight_labels[:, 0].mean()
        mean_r = straight_labels[:, 1].mean()

        if mean_l < 1e-6:
            return 1.0

        efficiency = float(mean_r / mean_l)
        efficiency = max(0.80, min(1.0, efficiency))

        print(f"[Dataset] Motor efficiency: left={efficiency:.3f} "
              f"(mean_L={mean_l:.4f}, mean_R={mean_r:.4f}, "
              f"n_straight={int(straight_mask.sum()) if straight_mask.sum() >= 10 else len(straight_labels)})")

        return efficiency


def _prepare_dataset(dataset, deduplicate, trim_stops, exclude_detection,
                     window_size, temporal_decay, balanced_sampling):
    """Pipeline complet de preparation d'un dataset (train ou val).

    Nettoyage -> exclusion detection -> features -> poids -> sliding windows.
    Retourne aussi les sample_weights si balanced_sampling=True.
    """
    if deduplicate:
        dataset.deduplicate()
    dataset.remove_pwm_stops()
    if trim_stops is not None:
        dataset.trim_stops(max_consecutive=trim_stops)

    # Zero-pad ancien format 29-dim -> 36-dim (avant exclusion detection)
    dataset.pad_to_new_format()

    if exclude_detection:
        dataset.exclude_detection_features()

    dataset.compute_engineered_features()

    sample_weights = None
    if balanced_sampling:
        sample_weights = dataset.compute_sample_weights()

    dataset.compute_sliding_windows(window_size=window_size, temporal_decay=temporal_decay)

    return sample_weights


def create_data_loaders(
    train_dir: str,
    val_dir: str,
    batch_size: int = 32,
    shuffle: bool = True,
    seed: int = 42,
    deduplicate: bool = True,
    balanced_sampling: bool = True,
    window_size: int = None,
    trim_stops: int = None,
    exclude_detection: bool = True,
    temporal_decay: float = None,
    num_workers: int = None
) -> tuple:
    """Crée les DataLoaders pour l'entraînement et la validation.

    Le split train/val est fait en amont par aggregate_sequences.py.
    L'augmentation est faite en amont par augment.py sur data/train/ uniquement.
    Le val set est garanti 100% donnees reelles.

    Pipeline (applique independamment sur train et val):
      1. Chargement (captures + labels + sequence_ids)
      2. Nettoyage: dedup, PWM stops, trim stops
      3. Exclusion features Detection
      4. Features engineered
      5. Poids d'echantillonnage (train seulement)
      6. Fenetre glissante avec decay temporel
      7. Normalisation z-score (stats du train, appliquees aux deux)

    Args:
        train_dir: Repertoire data/train/ (donnees reelles + augmentees)
        val_dir: Repertoire data/val/ (donnees reelles pures)

    Returns:
        tuple: (train_loader, val_loader, ds_train)
    """
    import os
    import sys

    if num_workers is None:
        if sys.platform == 'win32':
            num_workers = 0
        else:
            num_workers = min(4, os.cpu_count() or 0)

    ws = window_size or WINDOW_SIZE
    td = temporal_decay or TEMPORAL_DECAY

    # === Charger et preparer le TRAIN set ===
    ds_train = ZumiControlDataset(train_dir)
    train_weights = _prepare_dataset(
        ds_train, deduplicate, trim_stops, exclude_detection, ws, td, balanced_sampling
    )

    # === Charger et preparer le VAL set (donnees reelles pures) ===
    ds_val = ZumiControlDataset(val_dir)
    _prepare_dataset(
        ds_val, deduplicate, trim_stops, exclude_detection, ws, td, False
    )

    # Stocker les metadonnees
    ds_train.window_size = ws
    ds_train.temporal_decay = td
    ds_train.exclude_detection = exclude_detection
    ds_train.feature_mask = None

    # === Z-score (stats du train, appliquees aux deux) ===
    feature_mean = ds_train.captures.mean(axis=0)
    feature_std = ds_train.captures.std(axis=0)

    n_dead = np.sum(feature_std < 1e-6)
    n_active = len(feature_std) - n_dead
    print(f"[Dataset] Z-score: {n_active} features actives, {n_dead} features mortes (std < 1e-6)")

    ds_train.normalize(feature_mean, feature_std)
    ds_val.normalize(feature_mean, feature_std)

    ds_train.feature_mean = feature_mean
    ds_train.feature_std = feature_std

    # === DataLoaders ===
    # Note: WeightedRandomSampler tire aleatoirement selon les poids,
    # donc il fait un shuffle implicite. Mais avec 1.5M+ echantillons
    # et des fenetres chevauchantes (96% de recouvrement), un shuffle
    # pur est preferable pour casser la redondance spatiale.
    # On privilegie shuffle=True sans sampler.
    train_loader = DataLoader(
        ds_train, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=False, drop_last=True
    )

    val_loader = DataLoader(
        ds_val, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=False
    )

    print(f"[Dataset] Train: {len(ds_train)} samples, "
          f"Val: {len(ds_val)} samples (reel pur) "
          f"(num_workers={num_workers})")

    return train_loader, val_loader, ds_train


if __name__ == "__main__":
    import sys

    data_dir = Path(__file__).parent / "data"
    if not data_dir.exists():
        print(f"Répertoire de données non trouvé: {data_dir}")
        sys.exit(1)

    dataset = ZumiControlDataset(str(data_dir))
    stats = dataset.get_statistics()

    print("\n=== Statistiques du Dataset ===")
    print(f"Nombre d'échantillons: {stats['n_samples']}")
    print(f"Dimension entrée: {stats['input_dim']}")
    print(f"Dimension sortie: {stats['output_dim']}")
    print(f"\nLabel (commandes moteur):")
    print(f"  Min: {stats['label_min']}")
    print(f"  Max: {stats['label_max']}")
    print(f"  Mean: {[f'{m:.3f}' for m in stats['label_mean']]}")
    print(f"  Std: {[f'{s:.3f}' for s in stats['label_std']]}")

    # Test DataLoaders
    train_loader, val_loader, _ = create_data_loaders(str(data_dir), batch_size=16)

    print(f"\nTest batch:")
    for states, commands in train_loader:
        print(f"  States shape: {states.shape}")
        print(f"  Commands shape: {commands.shape}")
        break
