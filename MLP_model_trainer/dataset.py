#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dataset PyTorch pour l'entraînement du MLP de contrôle.

Charge les fichiers JSONL générés par le système d'échantillonnage
(captures.jsonl = vecteurs d'état, labels.jsonl = commandes moteur).
"""

import json
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, random_split, WeightedRandomSampler
from pathlib import Path

# ============================================================
# Constantes de feature engineering (source de verite)
# Synchronisees vers ml_controller.py via normalization_stats.json
# ============================================================

# Seuils IR pour la detection de ligne et de surface
IR_OFFSET_DEFAULT = -17.0    # Offset bot_left - bot_right (defaut, remplace par calibration)
GAP_THRESHOLD = 195.0        # ir_sum sous lequel la ligne blanche est visible
OFF_ROAD_THRESHOLD = 120.0   # ir_sum sous lequel on est hors piste (gazon)
GRASS_THRESHOLD = 140.0      # capteurs front sous ce seuil = gazon devant

# Features engineered ajoutees au vecteur de base (27-dim -> 35-dim)
ENGINEERED_FEATURE_NAMES = [
    'calibrated_error',   # 27: (ir_bot_r - ir_bot_l) - ir_offset
    'line_visible',       # 28: 1.0 si ir_sum < GAP_THRESHOLD
    'cal_error_norm',     # 29: calibrated_error / (ir_sum + eps)
    'approaching_line',   # 30: +1 si |cal_error| diminue, -1 sinon
    'on_road',            # 31: 1.0 si ir_sum > OFF_ROAD_THRESHOLD
    'grass_detect',       # 32: 1.0 si min(ir_front_l, ir_front_r) < GRASS_THRESHOLD
    'gyro_z_rate',        # 33: delta gyro_z (vitesse angulaire par tick)
    'heading_drift',      # 34: gyro_z_rate * (1 - line_visible)
]

# Indices des features pour lesquelles calculer des deltas temporels
# Note: indices 27-34 sont les features engineered ajoutees par
# compute_engineered_features() avant l'appel a compute_deltas()
DELTA_FEATURE_INDICES = [
    1,   # IR_bot_R
    3,   # IR_bot_L
    6,   # IR_diff
    7,   # IR_sum
    18,  # gyro_z (heading cumulatif)
    19,  # acc_x
    20,  # acc_y
    27,  # calibrated_error
    29,  # cal_error_norm
    30,  # approaching_line
    33,  # gyro_z_rate
    34,  # heading_drift
]
DELTA_FEATURE_NAMES = [
    'IR_bot_R_delta', 'IR_bot_L_delta', 'IR_diff_delta', 'IR_sum_delta',
    'gyro_z_delta', 'acc_x_delta', 'acc_y_delta',
    'cal_error_delta', 'cal_error_norm_delta', 'approaching_delta',
    'gyro_z_rate_delta', 'heading_drift_delta',
]

# Deltas multi-pas: 5 pas d'historique avec ponderation exponentielle
DELTA_STEPS = 5
DELTA_WEIGHTS = [1.0, 0.7, 0.5, 0.3, 0.15]

# Indice du gyro_z (vitesse angulaire yaw en deg/s) dans le vecteur 27-dim
GYRO_Z_INDEX = 18

# Noms des categories d'actions
ACTION_NAMES = ["Arret", "Tout droit", "Tourne G", "Tourne D", "Recule"]


def classify_actions(captures, labels, gyro_z_index=GYRO_Z_INDEX,
                     rotation_thresh=3.0, stop_thresh=0.02,
                     boundary_thresh=150.0):
    """Categorise les echantillons par action reelle via IMU.

    Utilise le delta du gyroscope (gyro_z[t] - gyro_z[t-1]) pour detecter
    les rotations plutot que les commandes moteur, car celles-ci sont
    biaisees par la correction PID de cap.

    Note: gyro_z (index 18) est l'angle yaw CUMULATIF integre du gyroscope
    (en degres), pas une vitesse angulaire. Il s'accumule au sein d'une
    sequence et est reinitialise entre les sequences. On calcule donc le
    delta entre echantillons consecutifs pour obtenir la vitesse angulaire
    par tick, en mettant a zero les frontieres de sequence (gros sauts).

    Convention Zumi: gyro_z positif = rotation vers la gauche.

    Args:
        captures: array (N, D) avec gyro_z a l'index gyro_z_index
        labels: array (N, 2) commandes moteur normalisees [-1, 1]
        gyro_z_index: indice du gyro_z dans captures (18 pour raw 27-dim)
        rotation_thresh: seuil delta gyro_z en deg/tick pour detecter une rotation
        stop_thresh: seuil commande moteur pour detecter un arret
        boundary_thresh: seuil de saut gyro_z pour detecter une frontiere de sequence

    Returns:
        categories: array int (N,) — 0=arret, 1=forward, 2=turn_left,
                    3=turn_right, 4=reverse
    """
    gyro_z_raw = captures[:, gyro_z_index]

    # Calculer le delta gyro_z (vitesse angulaire par tick)
    gyro_z_delta = np.zeros_like(gyro_z_raw)
    gyro_z_delta[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]

    # Mettre a zero les frontieres de sequence (gros sauts = reset gyro)
    boundaries = np.abs(gyro_z_delta) > boundary_thresh
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
        - captures.jsonl: vecteurs d'état normalisés (dim = 17 + N classes)
        - labels.jsonl: commandes moteur normalisées [left, right] dans [-1, 1]
    """

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Répertoire contenant captures.jsonl et labels.jsonl
        """
        self.data_dir = Path(data_dir)
        self.captures = []
        self.labels = []

        self._load_data()

    def _load_data(self):
        """Charge les fichiers JSONL en mémoire."""
        captures_path = self.data_dir / "captures.jsonl"
        labels_path = self.data_dir / "labels.jsonl"

        if not captures_path.exists():
            raise FileNotFoundError(f"Fichier captures.jsonl non trouvé: {captures_path}")
        if not labels_path.exists():
            raise FileNotFoundError(f"Fichier labels.jsonl non trouvé: {labels_path}")

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

        # Validation
        if len(self.captures) != len(self.labels):
            raise ValueError(
                f"Nombre d'échantillons incohérent: "
                f"{len(self.captures)} captures vs {len(self.labels)} labels"
            )

        # Convertir en tenseurs numpy pour efficacité
        self.captures = np.array(self.captures, dtype=np.float32)
        self.labels = np.array(self.labels, dtype=np.float32)

        print(f"[Dataset] Chargé {len(self)} échantillons")
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

    def deduplicate(self, threshold: float = 1e-4, min_run_length: int = 5):
        """Retire les echantillons consecutifs quasi-identiques.

        Ne retire que les groupes de doublons d'au moins min_run_length
        echantillons consecutifs, en gardant le premier de chaque groupe.
        Les paires courtes (2-3 echantillons similaires) sont normales
        a ~80ms de sampling et representent un signal valide (commande
        maintenue, virage constant).

        Args:
            threshold: Distance L2 minimale entre deux echantillons consecutifs.
            min_run_length: Nombre minimum d'echantillons consecutifs dans un
                           groupe pour qu'il soit considere comme un vrai doublon.
                           Les groupes plus courts sont conserves.
        """
        if len(self.captures) < 2:
            return

        diffs = np.linalg.norm(self.captures[1:] - self.captures[:-1], axis=1)
        is_dup = diffs < threshold

        # Identifier les runs de doublons consecutifs et ne retirer
        # que ceux dont la longueur >= min_run_length
        keep = np.ones(len(self.captures), dtype=bool)
        run_start = None
        n_removed = 0

        for i in range(len(is_dup)):
            if is_dup[i]:
                if run_start is None:
                    run_start = i  # i est le dernier "original", i+1 est le premier doublon
            else:
                if run_start is not None:
                    run_length = (i + 1) - run_start  # nb echantillons dans le groupe
                    if run_length >= min_run_length:
                        # Garder le premier (run_start), retirer le reste
                        keep[run_start + 1 : i + 1] = False
                        n_removed += i - run_start
                    run_start = None

        # Fermer le dernier run s'il se termine a la fin du tableau
        if run_start is not None:
            run_length = len(self.captures) - run_start
            if run_length >= min_run_length:
                keep[run_start + 1 :] = False
                n_removed += len(self.captures) - run_start - 1

        self.captures = self.captures[keep]
        self.labels = self.labels[keep]
        print(f"[Dataset] Deduplication: {n_removed} doublons retires "
              f"(groupes >= {min_run_length} samples, {len(self)} restants)")

    def compute_ir_offset(self) -> float:
        """Estime l'offset IR bottom depuis le dataset (echantillons forward+straight).

        Equivalent de la calibration IR hardware mais calcule a partir des
        donnees d'entrainement. Utilise comme defaut quand pas de calibration.

        Returns:
            float: Offset moyen (ir_bot_left - ir_bot_right) sur les echantillons droits.
        """
        categories = classify_actions(self.captures, self.labels)
        forward_mask = categories == 1  # forward

        if forward_mask.sum() < 10:
            print(f"[Dataset] IR offset: pas assez d'echantillons forward, defaut={IR_OFFSET_DEFAULT}")
            return IR_OFFSET_DEFAULT

        # Parmi les forward, filtrer ceux vraiment droits (delta gyro_z faible)
        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]
        gyro_z_delta = np.zeros_like(gyro_z_raw)
        gyro_z_delta[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]
        gyro_z_delta[np.abs(gyro_z_delta) > 150.0] = 0.0

        fwd_delta = gyro_z_delta[forward_mask]
        straight_mask = np.abs(fwd_delta) < 5.0

        if straight_mask.sum() >= 10:
            ir_diff_straight = self.captures[forward_mask][straight_mask, 6]  # IR_diff = index 6
        else:
            ir_diff_straight = self.captures[forward_mask, 6]

        offset = float(ir_diff_straight.mean())
        print(f"[Dataset] IR offset estime: {offset:.1f} "
              f"(n_straight={int(straight_mask.sum()) if straight_mask.sum() >= 10 else len(ir_diff_straight)})")
        return offset

    def compute_engineered_features(self, ir_offset: float = None):
        """Ajoute 8 features PID-inspired au vecteur de base (27-dim -> 35-dim).

        Features ajoutees (indices 27-34):
          27: calibrated_error  - signal d'erreur PID zero-centre
          28: line_visible      - 1.0 si ligne blanche detectee
          29: cal_error_norm    - erreur normalisee par luminosite
          30: approaching_line  - +1 si on se rapproche de la ligne, -1 sinon
          31: on_road           - 1.0 si sur la route (pas sur gazon)
          32: grass_detect      - 1.0 si gazon detecte devant
          33: gyro_z_rate       - vitesse angulaire (delta gyro_z par tick)
          34: heading_drift     - derive de cap dans les gaps entre tirets

        Doit etre appelee AVANT compute_deltas().

        Args:
            ir_offset: Offset IR bottom (bot_left - bot_right). Si None, estime depuis le dataset.
        """
        if ir_offset is None:
            ir_offset = self.compute_ir_offset()
        self._ir_offset = ir_offset

        n = len(self.captures)
        ir_bot_r = self.captures[:, 1]   # IR_bottom_right
        ir_bot_l = self.captures[:, 3]   # IR_bottom_left
        ir_front_r = self.captures[:, 0] # IR_front_right
        ir_front_l = self.captures[:, 5] # IR_front_left
        ir_sum = (ir_bot_l + ir_bot_r) / 2.0
        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]

        # 27: calibrated_error — signal d'erreur PID zero-centre
        # Convention: positif = robot decale a droite (doit tourner a gauche)
        calibrated_error = (ir_bot_r - ir_bot_l) - (-ir_offset)  # soustrait le biais

        # 28: line_visible — la ligne blanche est sous un capteur
        line_visible = (ir_sum < GAP_THRESHOLD).astype(np.float32)

        # 29: cal_error_norm — invariant a la luminosite ambiante
        cal_error_norm = calibrated_error / (ir_sum + 1e-6)

        # 30: approaching_line — direction de derive (+1 = vers la ligne, -1 = s'eloigne)
        abs_error = np.abs(calibrated_error)
        abs_error_prev = np.zeros_like(abs_error)
        abs_error_prev[1:] = abs_error[:-1]
        approaching = np.where(abs_error < abs_error_prev, 1.0, -1.0).astype(np.float32)
        # Frontieres de sequence: zeroiser
        error_jumps = np.abs(calibrated_error[1:] - calibrated_error[:-1])
        boundaries = np.zeros(n, dtype=bool)
        boundaries[0] = True
        boundaries[1:] = error_jumps > 100.0
        approaching[boundaries] = 0.0

        # 31: on_road — sur la route noire (pas gazon)
        on_road = (ir_sum > OFF_ROAD_THRESHOLD).astype(np.float32)

        # 32: grass_detect — gazon detecte par les capteurs front
        grass_detect = (np.minimum(ir_front_l, ir_front_r) < GRASS_THRESHOLD).astype(np.float32)

        # 33: gyro_z_rate — vitesse angulaire (delta gyro_z cumulatif)
        gyro_z_rate = np.zeros(n, dtype=np.float32)
        gyro_z_rate[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]
        # Zeroiser les frontieres de sequence (gros sauts = reset gyro)
        gyro_boundaries = np.abs(gyro_z_rate) > 150.0
        gyro_z_rate[gyro_boundaries] = 0.0

        # 34: heading_drift — derive de cap active uniquement dans les gaps
        heading_drift = gyro_z_rate * (1.0 - line_visible)

        new_features = np.column_stack([
            calibrated_error, line_visible, cal_error_norm, approaching,
            on_road, grass_detect, gyro_z_rate, heading_drift
        ]).astype(np.float32)

        original_dim = self.captures.shape[1]
        self.captures = np.hstack([self.captures, new_features])

        print(f"[Dataset] Features engineered: {len(ENGINEERED_FEATURE_NAMES)} ajoutees "
              f"({original_dim}-dim -> {self.captures.shape[1]}-dim, ir_offset={ir_offset:.1f})")

    def compute_deltas(self, delta_indices: list = None, n_steps: int = None, weights: list = None):
        """Calcule les features temporelles multi-pas avec ponderation exponentielle.

        Pour chaque pas k (1..n_steps), calcule:
          delta_k[t] = (state[t] - state[t-k]) * weights[k-1]

        Les deltas approximent les derivees temporelles (vitesse de changement)
        et sont appeles AVANT le shuffle pour que les echantillons consecutifs
        soient coherents. Chaque delta est ensuite attache a son echantillon.

        Args:
            delta_indices: Indices des features source dans le vecteur.
                          Par defaut DELTA_FEATURE_INDICES.
            n_steps: Nombre de pas d'historique (defaut: DELTA_STEPS = 3).
            weights: Poids par pas (defaut: DELTA_WEIGHTS = [1.0, 0.5, 0.25]).
        """
        if delta_indices is None:
            delta_indices = DELTA_FEATURE_INDICES
        if n_steps is None:
            n_steps = DELTA_STEPS
        if weights is None:
            weights = DELTA_WEIGHTS

        if len(self.captures) < 2:
            return

        # Detecter les frontieres de sequence AVANT de calculer les deltas
        # On utilise le delta pas-1 sur les features IR seulement (indices bruts 0-7)
        selected_step1 = self.captures[:, delta_indices]
        delta_step1 = np.zeros_like(selected_step1)
        delta_step1[1:] = selected_step1[1:] - selected_step1[:-1]

        ir_delta_cols = [j for j, idx in enumerate(delta_indices) if idx <= 7]
        if ir_delta_cols:
            ir_jumps = np.linalg.norm(delta_step1[:, ir_delta_cols], axis=1)
            boundary_mask = ir_jumps > 150.0
        else:
            boundary_mask = np.zeros(len(self.captures), dtype=bool)
        boundary_mask[0] = True  # premier echantillon = pas de precedent
        n_boundaries = int(np.sum(boundary_mask))

        # Propager les frontieres: pour un delta de pas k, zeroiser si une
        # frontiere existe dans les k echantillons precedents
        boundary_indices = np.where(boundary_mask)[0]

        # Calculer les deltas multi-pas
        original_dim = self.captures.shape[1]
        all_deltas = []
        for step in range(1, n_steps + 1):
            selected = self.captures[:, delta_indices]
            delta = np.zeros_like(selected)
            delta[step:] = (selected[step:] - selected[:-step]) * weights[step - 1]

            # Zeroiser les frontieres: pour le pas k, zeroiser les indices
            # qui ont une frontiere dans [t-k+1, t]
            for bi in boundary_indices:
                start = bi
                end = min(bi + step, len(delta))
                delta[start:end] = 0.0

            all_deltas.append(delta.astype(np.float32))

        self.captures = np.hstack([self.captures] + all_deltas)

        n_total_deltas = len(delta_indices) * n_steps
        print(f"[Dataset] Deltas temporels: {n_total_deltas} features ajoutees "
              f"({original_dim}-dim -> {self.captures.shape[1]}-dim, "
              f"{len(delta_indices)} features x {n_steps} pas)"
              + (f", {n_boundaries} frontieres de sequence detectees" if n_boundaries > 0 else ""))

    def compute_sample_weights(self) -> np.ndarray:
        """Calcule les poids par echantillon pour equilibrer les categories d'actions.

        Utilise le gyroscope (gyro_z) pour categoriser les actions reelles
        plutot que les commandes moteur (biaisees par le PID de cap).

        Returns:
            np.ndarray: Poids par echantillon (shape: [n_samples])
        """
        categories = classify_actions(self.captures, self.labels)

        class_counts = np.bincount(categories, minlength=5).astype(np.float64)
        class_counts[class_counts == 0] = 1.0  # eviter div par zero

        # Utiliser 1/sqrt(count) au lieu de 1/count pour adoucir le reequilibrage.
        # Avec la categorisation IMU, "tout droit" domine (~60%) et 1/count
        # l'ecrase completement (ratio 28:1 vs recule). sqrt donne un ratio
        # plus raisonnable (~5:1) qui booste les actions rares sans empecher
        # le modele d'apprendre a aller droit.
        class_weights = 1.0 / np.sqrt(class_counts)
        sample_weights = class_weights[categories]

        # Afficher le ratio max pour debug
        max_ratio = class_weights.max() / class_weights.min()
        print(f"[Dataset] Poids par categorie (equilibrage sqrt, IMU-based, ratio max: {max_ratio:.1f}x):")
        for i, name in enumerate(ACTION_NAMES):
            count = int(class_counts[i])
            weight = class_weights[i]
            print(f"  {name:15s}: {count:5d} samples, poids {weight:.6f}")

        return sample_weights

    def apply_feature_mask(self, mask: list):
        """Retire les features mortes en ne gardant que les indices du masque.

        Args:
            mask: Liste d'indices de features a conserver (ex: [0,1,2,3,4,5,6,7,16,17,...])
        """
        original_dim = self.captures.shape[1]
        self.captures = self.captures[:, mask]
        print(f"[Dataset] Masque applique: {original_dim}-dim -> {self.captures.shape[1]}-dim "
              f"({original_dim - len(mask)} features mortes retirees)")

    def normalize(self, mean: np.ndarray, std: np.ndarray):
        """Applique la normalisation z-score aux captures.

        Args:
            mean: Moyenne par feature (shape: [input_dim])
            std: Ecart-type par feature (shape: [input_dim])
        """
        safe_std = std.copy()
        safe_std[safe_std < 1e-6] = 1.0  # eviter division par zero pour features mortes
        self.captures = (self.captures - mean) / safe_std

    def get_statistics(self) -> dict:
        """Calcule les statistiques du dataset pour analyse."""
        stats = {
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
        return stats

    def compute_motor_efficiency(self) -> float:
        """Estime l'efficacite du moteur gauche depuis le biais des labels.

        Pendant la collecte, le PID de cap boostait le moteur gauche (plus
        faible) pour maintenir le cap. Pour les echantillons "tout droit"
        (delta gyro_z ~= 0), le ratio mean_right / mean_left donne
        l'efficacite relative du moteur gauche.

        Returns:
            float: Efficacite du moteur gauche dans (0, 1]. 1.0 = pas d'asymetrie.
        """
        categories = classify_actions(self.captures, self.labels)
        forward_mask = categories == 1  # forward

        if forward_mask.sum() < 10:
            print("[Dataset] Motor efficiency: pas assez d'echantillons forward")
            return 1.0

        # Parmi les forward, prendre ceux vraiment droits (delta gyro_z faible)
        # gyro_z est cumulatif -> calculer le delta pour obtenir la vitesse angulaire
        gyro_z_raw = self.captures[:, GYRO_Z_INDEX]
        gyro_z_delta = np.zeros_like(gyro_z_raw)
        gyro_z_delta[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]
        # Zeroiser les frontieres de sequence
        gyro_z_delta[np.abs(gyro_z_delta) > 150.0] = 0.0

        fwd_delta = gyro_z_delta[forward_mask]
        straight_mask = np.abs(fwd_delta) < 5.0  # < 5 deg/tick

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


def create_data_loaders(
    data_dir: str,
    batch_size: int = 32,
    train_ratio: float = 0.8,
    shuffle: bool = True,
    seed: int = 42,
    feature_mask: list = None,
    deduplicate: bool = True,
    balanced_sampling: bool = True
) -> tuple:
    """Crée les DataLoaders pour l'entraînement et la validation.

    Pipeline complet:
      1. Chargement des donnees
      2. Deduplication des echantillons consecutifs quasi-identiques
      3. Features engineered PID-inspired (8 features, 27-dim -> 35-dim)
      4. Deltas temporels multi-pas (12 features x 5 pas = 60 colonnes)
      5. Calcul des poids d'echantillonnage equilibre
      6. Application du masque de features mortes
      7. Split train/validation
      8. Normalisation z-score (stats calculees sur train uniquement)
      9. Creation des DataLoaders

    Args:
        data_dir: Répertoire des données
        batch_size: Taille des mini-batches
        train_ratio: Proportion des données pour l'entraînement (0.8 = 80%)
        shuffle: Mélanger les données d'entraînement (ignore si balanced_sampling=True)
        seed: Graine aléatoire pour reproductibilité
        feature_mask: Liste d'indices de features a conserver (None = toutes)
        deduplicate: Retirer les doublons consecutifs (defaut: True)
        balanced_sampling: Utiliser WeightedRandomSampler pour equilibrer les categories (defaut: True)

    Returns:
        tuple: (train_loader, val_loader, dataset)
    """
    dataset = ZumiControlDataset(data_dir)

    # 1. Deduplication (avant tout traitement)
    if deduplicate:
        dataset.deduplicate()

    # 2. Features engineered (27-dim -> 35-dim)
    dataset.compute_engineered_features()

    # 3. Deltas temporels multi-pas (avant shuffle, sur echantillons consecutifs)
    dataset.compute_deltas()

    # 4. Calculer les poids d'echantillonnage (avant masque, base sur les labels)
    sample_weights = None
    if balanced_sampling:
        sample_weights = dataset.compute_sample_weights()

    # 5. Appliquer le masque de features (retire les features mortes)
    #    Le masque est calcule sur les features originales (27-dim).
    #    Les features engineered et deltas (ajoutees apres) sont toujours actives.
    if feature_mask is not None:
        n_engineered = len(ENGINEERED_FEATURE_NAMES)
        n_deltas = len(DELTA_FEATURE_INDICES) * DELTA_STEPS
        n_extra = n_engineered + n_deltas
        original_dim = dataset.captures.shape[1] - n_extra
        extra_indices = list(range(original_dim, original_dim + n_extra))
        extended_mask = feature_mask + extra_indices
        dataset.apply_feature_mask(extended_mask)
        dataset.feature_mask = extended_mask
    else:
        dataset.feature_mask = None

    # 6. Split train/validation
    n_train = int(len(dataset) * train_ratio)
    n_val = len(dataset) - n_train

    generator = torch.Generator().manual_seed(seed)
    train_dataset, val_dataset = random_split(
        dataset, [n_train, n_val], generator=generator
    )

    # 7. Calculer mean/std sur le train set uniquement (apres masque)
    train_indices = train_dataset.indices
    train_captures = dataset.captures[train_indices]
    feature_mean = train_captures.mean(axis=0)
    feature_std = train_captures.std(axis=0)

    n_dead = np.sum(feature_std < 1e-6)
    n_active = len(feature_std) - n_dead
    print(f"[Dataset] Z-score: {n_active} features actives, {n_dead} features mortes (std < 1e-6)")

    # Normaliser tout le dataset avec les stats du train set
    dataset.normalize(feature_mean, feature_std)

    # Stocker les stats pour export ultérieur
    dataset.feature_mean = feature_mean
    dataset.feature_std = feature_std

    # 8. Creer les DataLoaders
    if balanced_sampling and sample_weights is not None:
        # WeightedRandomSampler pour le train set (equilibre les categories)
        train_weights = torch.from_numpy(sample_weights[train_indices]).double()
        sampler = WeightedRandomSampler(
            weights=train_weights,
            num_samples=len(train_weights),
            replacement=True
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            sampler=sampler,    # sampler remplace shuffle
            num_workers=0,
            pin_memory=True
        )
        print(f"[Dataset] Echantillonnage equilibre active (WeightedRandomSampler)")
    else:
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=0,
            pin_memory=True
        )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True
    )

    print(f"[Dataset] Train: {n_train} samples, Val: {n_val} samples")

    return train_loader, val_loader, dataset


if __name__ == "__main__":
    # Test de chargement
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
