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

# Features engineered ajoutees au vecteur de base
# Le vecteur de base est 29-dim (27 + 2 features camera: line_offset, line_detected)
# ou 21-dim si les features Detection (8-15) sont exclues.
# Les features engineered sont toujours ajoutees a la fin.
ENGINEERED_FEATURE_NAMES = [
    'calibrated_error',   # (ir_bot_r - ir_bot_l) - ir_offset
    'line_visible',       # 1.0 si ir_sum < GAP_THRESHOLD (IR)
    'cal_error_norm',     # calibrated_error / (ir_sum + eps)
    'gyro_z_rate',        # delta gyro_z (vitesse angulaire par tick)
    'heading_drift',      # gyro_z_rate * (1 - line_visible)
]

# Indices des features Detection (Haar) dans le vecteur brut 29-dim.
# Ces features sont inutilisees tant que les detecteurs Haar ne sont pas integres
# et peuvent etre exclues de facon reversible (exclude_detection=True).
DETECTION_INDICES = list(range(8, 16))  # 8 features: flag + 3 one-hot + 4 bbox

# Fenetre glissante: 25 pas d'historique (1.25 seconde a 20Hz)
WINDOW_SIZE = 25

# Dimension par pas de fenetre (calculee dynamiquement selon exclude_detection)
# 34 = 29 raw + 5 engineered (detection incluse)
# 26 = 21 raw + 5 engineered (detection exclue)
WINDOW_FEATURE_DIM = 26  # defaut: detection exclue

# Ponderation temporelle exponentielle de la fenetre glissante.
# Chaque frame t est multiplie par alpha^(window_size - 1 - t):
#   frame le plus recent (t=window_size-1) = 1.0
#   frame le plus ancien (t=0) = alpha^(window_size-1)
# alpha=1.0 desactive le decay. alpha=0.95 avec 25 frames: ancien=0.29, milieu=0.54.
TEMPORAL_DECAY = 0.95

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
        - captures.jsonl: vecteurs d'état (dim = 29)
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
        with open(captures_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.captures.append(json.loads(line))

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

    def exclude_detection_features(self):
        """Retire les features Detection (indices 8-15) du vecteur brut.

        Doit etre appelee AVANT compute_engineered_features().
        Re-mappe les indices pour que les features suivantes gardent
        leur semantique (IR 0-7 inchanges, IMU 16-26 -> 8-18, Camera 27-28 -> 19-20).

        Reversible: ne pas appeler cette methode pour garder les 29 features.
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
        """Ajoute 5 features PID-inspired au vecteur de base.

        Doit etre appelee AVANT compute_sliding_windows().
        Fonctionne que Detection soit exclue ou non (utilise GYRO_Z_INDEX dynamique).
        """
        if ir_offset is None:
            ir_offset = self.compute_ir_offset()
        self._ir_offset = ir_offset

        n = len(self.captures)
        ir_bot_r = self.captures[:, 1]
        ir_bot_l = self.captures[:, 3]
        ir_sum = (ir_bot_l + ir_bot_r) / 2.0
        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]

        calibrated_error = (ir_bot_r - ir_bot_l) - (-ir_offset)
        line_visible = (ir_sum < GAP_THRESHOLD).astype(np.float32)
        cal_error_norm = calibrated_error / (ir_sum + 1e-6)

        gyro_z_rate = np.zeros(n, dtype=np.float32)
        gyro_z_rate[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]

        # Mettre a zero les frontieres de sequence
        if self.sequence_ids is not None:
            boundaries = np.zeros(n, dtype=bool)
            boundaries[0] = True
            boundaries[1:] = self.sequence_ids[1:] != self.sequence_ids[:-1]
            gyro_z_rate[boundaries] = 0.0

        heading_drift = gyro_z_rate * (1.0 - line_visible)

        new_features = np.column_stack([
            calibrated_error, line_visible, cal_error_norm,
            gyro_z_rate, heading_drift
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


def _split_by_sequence(dataset, train_ratio: float, seed: int) -> tuple:
    """Split le dataset par sequence entiere (pas par sample).

    Toutes les samples d'une meme sequence vont soit dans train soit dans val.
    Evite le data leakage entre train et val lors du fine-tuning.

    Charge l'historique precedent si disponible pour garantir la stabilite
    du split entre les runs de fine-tuning.

    Args:
        dataset: ZumiControlDataset avec sequence_ids charges
        train_ratio: Proportion cible pour le train set
        seed: Graine pour la permutation aleatoire des sequences

    Returns:
        (train_indices, val_indices, split_history)
    """
    data_dir = dataset.data_dir
    history_path = data_dir / "split_history.json"

    unique_seqs = np.unique(dataset.sequence_ids)
    n_seqs = len(unique_seqs)

    # Charger l'historique si disponible
    known_train_seqs = set()
    known_val_seqs = set()
    if history_path.exists():
        with open(history_path, 'r') as f:
            history = json.load(f)
        known_train_seqs = set(history.get('train_sequences', []))
        known_val_seqs = set(history.get('val_sequences', []))
        print(f"[Dataset] Historique split charge: {len(known_train_seqs)} train, "
              f"{len(known_val_seqs)} val sequences connues")

    # Classifier les sequences: connues vs nouvelles
    train_seqs = []
    val_seqs = []
    new_seqs = []

    for seq_id in unique_seqs:
        sid = int(seq_id)
        if sid in known_train_seqs:
            train_seqs.append(sid)
        elif sid in known_val_seqs:
            val_seqs.append(sid)
        else:
            new_seqs.append(sid)

    # Repartir les nouvelles sequences pour atteindre le ratio cible
    if new_seqs:
        rng = np.random.RandomState(seed)
        rng.shuffle(new_seqs)

        # Calculer combien de samples sont deja assignes
        train_samples = sum(int((dataset.sequence_ids == s).sum()) for s in train_seqs)
        val_samples = sum(int((dataset.sequence_ids == s).sum()) for s in val_seqs)
        total_assigned = train_samples + val_samples
        total_all = len(dataset)

        # Objectif: train_ratio du total
        target_train = int(total_all * train_ratio)

        for sid in new_seqs:
            n = int((dataset.sequence_ids == sid).sum())
            if train_samples < target_train:
                train_seqs.append(sid)
                train_samples += n
            else:
                val_seqs.append(sid)
                val_samples += n

        print(f"[Dataset] Split: {len(new_seqs)} nouvelles sequences reparties")

    # Construire les indices
    train_set = set(train_seqs)
    train_indices = np.where(np.isin(dataset.sequence_ids, list(train_set)))[0]
    val_indices = np.where(~np.isin(dataset.sequence_ids, list(train_set)))[0]

    # Sauvegarder l'historique
    split_history = {
        'train_sequences': sorted(train_seqs),
        'val_sequences': sorted(val_seqs),
        'n_train_samples': len(train_indices),
        'n_val_samples': len(val_indices),
        'n_sequences': n_seqs,
        'seed': seed,
    }
    with open(history_path, 'w') as f:
        json.dump(split_history, f, indent=2)

    print(f"[Dataset] Split par sequence: {len(train_seqs)} train / {len(val_seqs)} val sequences")
    print(f"[Dataset] -> {len(train_indices)} train / {len(val_indices)} val samples")
    print(f"[Dataset] Historique sauvegarde: {history_path}")

    return train_indices, val_indices, split_history


def create_data_loaders(
    data_dir: str,
    batch_size: int = 32,
    train_ratio: float = 0.8,
    shuffle: bool = True,
    seed: int = 42,
    feature_mask: list = None,
    deduplicate: bool = True,
    balanced_sampling: bool = True,
    window_size: int = None,
    trim_stops: int = None,
    exclude_detection: bool = True,
    temporal_decay: float = None,
    num_workers: int = None
) -> tuple:
    """Crée les DataLoaders pour l'entraînement et la validation.

    Pipeline complet:
      1. Chargement des donnees (captures + labels + sequence_ids)
      2. Deduplication (respecte les frontieres de sequence)
      2b. Trim des arrets excessifs (respecte les frontieres de sequence)
      3. Exclusion des features Detection (indices 8-15) si demande
      4. Features engineered PID-inspired (5 features)
      5. Calcul des poids d'echantillonnage equilibre (avant fenetre glissante)
      6. Fenetre glissante avec decay temporel (frontieres via sequence_ids)
      7. Split train/val PAR SEQUENCE ENTIERE (pas par sample)
      8. Normalisation z-score (stats calculees sur train uniquement)
      9. Creation des DataLoaders

    Returns:
        tuple: (train_loader, val_loader, dataset)
    """
    import os
    import sys

    if num_workers is None:
        if sys.platform == 'win32':
            num_workers = 0
        else:
            num_workers = min(4, os.cpu_count() or 0)

    dataset = ZumiControlDataset(data_dir)

    # 1. Deduplication (respecte les frontieres de sequence)
    if deduplicate:
        dataset.deduplicate()

    # 1b. Trim des arrets excessifs
    if trim_stops is not None:
        dataset.trim_stops(max_consecutive=trim_stops)

    # 2. Exclure les features Detection si demande
    if exclude_detection:
        dataset.exclude_detection_features()

    # 3. Features engineered
    dataset.compute_engineered_features()

    # 4. Calculer les poids d'echantillonnage AVANT la fenetre glissante
    sample_weights = None
    if balanced_sampling:
        sample_weights = dataset.compute_sample_weights()

    # 5. Fenetre glissante avec decay temporel (frontieres via sequence_ids)
    dataset.compute_sliding_windows(window_size=window_size, temporal_decay=temporal_decay)
    dataset.window_size = window_size or WINDOW_SIZE
    dataset.temporal_decay = temporal_decay or TEMPORAL_DECAY
    dataset.exclude_detection = exclude_detection
    dataset.feature_mask = None

    # 6. Split train/val PAR SEQUENCE ENTIERE
    train_indices, val_indices, _ = _split_by_sequence(dataset, train_ratio, seed)
    train_dataset = Subset(dataset, train_indices)
    val_dataset = Subset(dataset, val_indices)

    # 7. Calculer mean/std sur le train set uniquement
    train_captures = dataset.captures[train_indices]
    feature_mean = train_captures.mean(axis=0)
    feature_std = train_captures.std(axis=0)

    n_dead = np.sum(feature_std < 1e-6)
    n_active = len(feature_std) - n_dead
    print(f"[Dataset] Z-score: {n_active} features actives, {n_dead} features mortes (std < 1e-6)")

    # Normaliser tout le dataset avec les stats du train set
    dataset.normalize(feature_mean, feature_std)

    dataset.feature_mean = feature_mean
    dataset.feature_std = feature_std

    # 8. Creer les DataLoaders
    if balanced_sampling and sample_weights is not None:
        train_weights = torch.from_numpy(sample_weights[train_indices]).double()
        sampler = WeightedRandomSampler(
            weights=train_weights,
            num_samples=len(train_weights),
            replacement=True
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            sampler=sampler,
            num_workers=num_workers,
            pin_memory=True
        )
        print(f"[Dataset] Echantillonnage equilibre active (WeightedRandomSampler)")
    else:
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=True
        )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )

    print(f"[Dataset] Train: {len(train_indices)} samples, Val: {len(val_indices)} samples "
          f"(num_workers={num_workers})")

    return train_loader, val_loader, dataset


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
