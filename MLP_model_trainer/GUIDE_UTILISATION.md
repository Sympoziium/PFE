# Guide d'utilisation : Pipeline MLP PyTorch → TFLite

**Objectif** : Guide pratique pour entraîner un modèle MLP de contrôle sur PC et le déployer sur le robot Zumi (Pi Zero 2W).

**Flux global** :
```
1. Collecter les données (pilotage manuel sur le robot)
   ↓
2. Agréger et augmenter les données
   ↓
3. Analyser le dataset (stats, distributions)
   ↓
4. Entraîner le modèle (PyTorch, profil adaptatif)
   ↓
5. Évaluer les résultats (métriques, simulateur 2D)
   ↓
6. Convertir en TFLite (pour embarqué)
   ↓
7. Déployer sur le Zumi (MLController)
```

---

## 1. Installation et configuration

### 1.1 Prérequis

- **Python 3.11 ou 3.12** (pas 3.13 — dépendances incompatibles)
- GPU optionnel (CUDA) — accélère l'entraînement mais pas requis

### 1.2 Environnement virtuel

```bash
# Créer et activer
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# Installer les dépendances
cd MLP_model_trainer/
pip install -r requirements.txt
```

**Dépendances principales** :
| Package | Version | Rôle |
|---------|---------|------|
| `torch` | >= 2.0.0 | Entraînement PyTorch |
| `tensorflow` | >= 2.13.0 | Conversion vers TFLite |
| `numpy` | <= 1.26.4 | Calcul numérique |
| `matplotlib` | >= 3.7.0 | Visualisation |
| `pygame` | >= 2.6.0 | Simulateur 2D |
| `scipy` | >= 1.10.0 | Corrélations (Spearman) |
| `scikit-learn` | >= 1.2.0 | Importance des features |

### 1.3 Valider l'environnement

```bash
python validate_env.py
```

Détecte le GPU, recommande une configuration optimale (batch size, threads) et génère `environment_config.json`.

---

## 2. Structure des fichiers

```
MLP_model_trainer/
├── train.py                    ← Point d'entrée principal (menu interactif)
├── dataset.py                  ← Chargement, feature engineering, fenêtre glissante
├── model.py                    ← Architecture ZumiMLP (configurable + BatchNorm)
├── augment.py                  ← Augmentation de données (bruit IR, scaling, dropout)
├── aggregate_sequences.py      ← Consolidation des séquences par scénario
├── analyze_dataset.py          ← Analyse statistique du dataset
├── evaluate.py                 ← Évaluation par séquence + importance des features
├── simulator_2d.py             ← Simulateur 2D temps réel (pygame)
├── convert_to_tflite.py        ← Conversion PyTorch → Keras → TFLite
├── validate_env.py             ← Détection environnement + recommandations
├── requirements.txt            ← Dépendances Python
│
├── sequences/                  ← Données brutes par scénario
│   ├── baseline/               ← Suivi de ligne standard
│   ├── pieton/                 ← Interactions piéton
│   └── stop_sign/              ← Arrêts aux panneaux
│
├── data/                       ← Dataset consolidé (prêt pour l'entraînement)
│   ├── captures.jsonl          ← Vecteurs d'état (1 par ligne)
│   ├── labels.jsonl            ← Commandes moteur (1 par ligne)
│   └── sequence_ids.jsonl      ← Identifiants de séquence
│
├── checkpoints/                ← Modèles entraînés + rapports
│   ├── best_model.pt           ← Meilleur modèle PyTorch
│   ├── training_report.json    ← Rapport complet (métriques, config)
│   ├── training_loss.png       ← Courbe d'apprentissage
│   ├── learning_rate.png       ← Évolution du LR
│   ├── predictions.png         ← Scatter prédictions vs cibles
│   └── residuals.png           ← Analyse des résidus
│
└── export/                     ← Modèle converti pour déploiement
    ├── zumi_mlp.tflite         ← Modèle TFLite final
    └── normalization_stats.json← Stats z-score + config fenêtre
```

---

## 3. Collecte de données

La collecte s'effectue directement sur le robot via l'interface web en mode `ManualController`. À chaque cycle (20 Hz), le système enregistre une paire (état capteurs, commande moteur).

### 3.1 Format des données

**`captures.jsonl`** — un vecteur JSON de 29 dimensions par ligne (état brut du robot) :

| Index | Donnée | Plage | Description |
|-------|--------|-------|-------------|
| 0-5 | IR sensors [6] | 0-255 | Capteurs infrarouges bruts |
| 6 | IR_diff | -255..255 | Position latérale (bottom_L - bottom_R) |
| 7 | IR_sum | 0-255 | Confiance ligne (bottom_L + bottom_R) / 2 |
| 8 | detect_flag | {0, 1} | Drapeau détection vision |
| 9-11 | class [3] | {0, 1} | Classes détectées (one-hot) |
| 12-15 | bbox [4] | [0, 1] | Boîte englobante relative (cx, cy, w, h) |
| 16-26 | IMU [11] | degrés | Gyro(3) + Acc(2) + Comp(2) + Rot(3) + Tilt(1) |
| 27 | line_offset | [-1, 1] | Décalage latéral de la ligne (caméra) |
| 28 | line_detected | {0, 1} | Ligne visible par la caméra |

**`labels.jsonl`** — un vecteur de 2 dimensions par ligne :
```json
[0.4, 0.35]
```
Valeurs normalisées dans [-1, 1] : `-1` = full reverse, `0` = arrêt, `1` = full forward.

### 3.2 Organisation par scénarios

Les sessions de collecte sont rangées dans `sequences/` par type de scénario. Le script `aggregate_sequences.py` les consolide en un dataset unique dans `data/`.

---

## 4. Pipeline de features

Le pipeline transforme le vecteur brut de 29 dimensions en un vecteur de **750 dimensions** prêt pour l'entraînement. Voici les étapes dans l'ordre :

### 4.1 Exclusion des features de détection

Les features de détection vision (indices 8-15) sont exclues par défaut, car le module Haar n'est pas intégré au pipeline d'entraînement actuel. Cela réduit le vecteur brut de 29 à **21 dimensions**.

### 4.2 Features ingéniérées (+9 dimensions)

Neuf caractéristiques dérivées sont calculées, portant le vecteur à **30 dimensions par pas de temps** :

| Feature | Description |
|---------|-------------|
| `calibrated_error` | Erreur latérale calibrée (IR_diff − offset capteurs) |
| `line_visible` | 1 si IR_sum < `GAP_THRESHOLD`, 0 sinon |
| `cal_error_norm` | Erreur normalisée : error / (IR_sum + epsilon) |
| `gyro_z_rate` | Vitesse de rotation en lacet (dérivée gyro_z) |
| `heading_drift` | Dérive de cap quand la ligne est invisible |
| `ir_error_derivative` | Dérivée de l'erreur calibrée (variation entre 2 pas) |
| `ir_error_integral` | Moyenne glissante de l'erreur sur 5 pas |
| `gyro_z_accel` | Accélération angulaire (dérivée seconde gyro_z) |
| `lookahead_delta` | Écart entre offset caméra et erreur IR normalisée |

### 4.3 Fenêtre glissante (30 × 25 = 750 dimensions)

Les 25 derniers vecteurs de 30 dimensions sont concaténés en un seul vecteur aplati. Une pondération exponentielle (`alpha = 0.85`) donne plus de poids aux pas récents :

```
Poids du pas le plus ancien (t-24) : 0.85^24 ≈ 0.019
Poids du pas actuel (t)           : 0.85^0  = 1.0
```

Cette fenêtre de 25 pas représente ~1.25 seconde d'historique à 20 Hz.

### 4.4 Normalisation z-score

Chaque dimension est centrée et réduite selon les statistiques calculées **exclusivement sur l'ensemble d'entraînement**. Les statistiques sont exportées dans `normalization_stats.json` pour être réutilisées à l'identique lors de l'inférence.

### Résumé du pipeline

```
29-dim (brut VisionAdapter)
  ↓ Exclusion détection (indices 8-15)
21-dim (IR[8] + IMU[11] + Cam[2])
  ↓ Features ingéniérées (+9)
30-dim par pas de temps
  ↓ Fenêtre glissante (25 pas × 0.85 decay)
750-dim aplati
  ↓ Z-score normalization
750-dim normalisé → entrée du modèle
```

---

## 5. Utilisation du menu principal

```bash
python train.py
```

Le script affiche un menu interactif :

```
[1] Agréger les séquences    → Consolide sequences/ → data/
[2] Analyser le dataset      → Statistiques + graphiques
[3] Entraîner un modèle      → Profil adaptatif + entraînement
[Q] Quitter
```

### 5.1 Agréger les séquences (option 1)

Consolide toutes les séquences dans `sequences/` en un dataset unifié dans `data/`. Applique automatiquement :
- Concaténation des captures et labels de tous les scénarios
- Génération des identifiants de séquence (`sequence_ids.jsonl`)

### 5.2 Analyser le dataset (option 2)

Lance `analyze_dataset.py` qui produit :
- Distribution des catégories d'action (arrêt, avance, virage G/D, recul)
- Statistiques par feature (moyenne, écart-type, min/max)
- Matrice de corrélation de Spearman
- Calibration automatique (IR offset, gap threshold, motor efficiency)
- Graphiques sauvegardés dans `evaluation_results/`

### 5.3 Entraîner un modèle (option 3)

Le script analyse le dataset et propose un **profil adaptatif** :

```
PROFIL D'ENTRAÎNEMENT SUGGÉRÉ
  Dataset: 311 627 échantillons
  Features actives: 30 (détection exclue)
  Fenêtre: 25 pas × 30 features = 750-dim

  Architectures candidates:
  ┌─────────────────────────┬────────────┬───────────┐
  │ Architecture            │ Paramètres │ Ratio     │
  ├─────────────────────────┼────────────┼───────────┤
  │ [64, 32]                │   49 698   │  6.3 : 1  │
  │ [128, 64, 32]           │  107 170   │  2.9 : 1  │
  │ [256, 128, 64]          │  226 498   │  1.4 : 1  │
  └─────────────────────────┴────────────┴───────────┘

  1) Accepter le profil suggéré
  2) Custom (modifier manuellement)
```

Le profil cible un ratio **échantillons / paramètres >= 5**.

---

## 6. Entraînement

### 6.1 Prétraitement automatique du dataset

Avant l'entraînement, le pipeline applique automatiquement :

1. **Déduplication** — supprime les échantillons quasi-identiques consécutifs
2. **Suppression des arrêts PWM** — retire les arrêts isolés dans les virages (artefacts du PWM logiciel)
3. **Trim des arrêts** — limite les séquences d'arrêt consécutives à 5 maximum
4. **Exclusion détection** — retire les indices 8-15 du vecteur brut
5. **Features ingéniérées** — calcule les 9 features dérivées
6. **Fenêtre glissante** — construit les vecteurs de 750 dimensions
7. **Normalisation z-score** — centre et réduit sur le train set

### 6.2 Architecture du modèle

Le modèle `ZumiMLP` utilise des couches entièrement connectées avec **BatchNorm** :

```
Entrée (750) → [Linear → BatchNorm → GELU → Dropout] × N → Linear → Tanh → Sortie (2)
```

- **Activation** : GELU (plus douce que ReLU, meilleure convergence)
- **BatchNorm** : normalisation par couche, fusionnée dans les poids lors de l'export TFLite
- **Dropout** : 0.3 par défaut (régularisation)
- **Sortie** : Tanh borne les prédictions dans [-1, 1]
- **Initialisation** : Xavier uniform

### 6.3 Hyperparamètres d'entraînement

| Hyperparamètre | Valeur | Description |
|----------------|--------|-------------|
| Optimiseur | AdamW | Adam avec weight decay découplé |
| Perte | RangeAwareLoss | MSE + pénalité de variance (lambda=0.2) |
| Scheduler | CosineAnnealingLR | Décroissance cosinus après warmup |
| Warmup | 5 époques | Montée progressive du LR |
| Early stopping | patience = 8 | Arrêt si val_loss ne s'améliore pas pendant 8 époques |
| Gradient clipping | max_norm = 1.0 | Prévient l'explosion des gradients |
| Échantillonnage | WeightedRandomSampler | Poids = 1/sqrt(count) par catégorie d'action |

**RangeAwareLoss** : combine la MSE classique avec une pénalité si le modèle compresse ses prédictions (variance trop faible par rapport aux cibles). Cela empêche le modèle de converger vers la moyenne.

### 6.4 Sortie de l'entraînement

```
Epoch   1 | Train: 0.0234 | Val: 0.0223 | LR: 1.00e-03 | Time: 12.3s *
Epoch   2 | Train: 0.0198 | Val: 0.0201 | LR: 1.00e-03 | Time: 12.1s *
...
Epoch  35 | Train: 0.0138 | Val: 0.0122 | LR: 5.00e-04 | Time: 12.0s *

Entraînement terminé
Meilleur val_loss: 0.0122
Modèle sauvegardé: checkpoints/best_model.pt
```

**Fichiers générés dans `checkpoints/`** :

| Fichier | Contenu |
|---------|---------|
| `best_model.pt` | Modèle PyTorch (poids + stats normalisation + masque) |
| `training_report.json` | Rapport JSON (architecture, métriques, hyperparamètres, historique) |
| `training_loss.png` | Courbes train loss vs validation loss |
| `learning_rate.png` | Évolution du learning rate |
| `predictions.png` | Scatter plot prédictions vs cibles |
| `residuals.png` | Distribution des erreurs |

### 6.5 Interpréter les métriques

| Métrique | Description | Bon signe |
|----------|-------------|-----------|
| **MSE** | Erreur quadratique moyenne | < 0.02 |
| **MAE** | Erreur absolue moyenne | < 0.10 |
| **RMSE** | Racine de MSE | < 0.15 |
| **R²** | Variance expliquée | > 0.80 |

**Interpréter les courbes** :
- Train loss et val loss diminuent en parallèle → bon
- Val loss remonte alors que train loss baisse → overfitting
- Les deux stagnent → modèle trop petit ou données insuffisantes

---

## 7. Augmentation de données

```bash
python augment.py
```

Quatre techniques ciblent exclusivement les capteurs IR (indices 0-5). Les features dérivées (`IR_diff`, `IR_sum`) sont recalculées après perturbation. **Les labels ne sont jamais modifiés.**

| Technique | Description | Multiplicateur |
|-----------|-------------|----------------|
| Bruit IR | Bruit gaussien (sigma variable) | ×3 |
| Scaling IR | Facteur multiplicatif (0.85-1.15) | ×4 |
| Dropout IR | Mise à zéro aléatoire d'un capteur | ×1 |
| Combiné | Bruit + scaling simultanés | ×4 à ×6 |

L'augmentation est recommandée lorsque le ratio échantillons/paramètres est inférieur à 5.

---

## 8. Évaluation

### 8.1 Évaluation quantitative

```bash
python evaluate.py
```

Produit :
- Métriques globales (MSE, MAE, RMSE, R²)
- Métriques par catégorie d'action (arrêt, avance, virage G/D, recul)
- Analyse d'importance par permutation — identifie les features les plus discriminantes

La classification des actions est basée sur l'IMU (delta gyro_z) :
- |delta| > 3°/tick → virage
- vitesse moyenne > 0.02 et pas de rotation → avance
- vitesse moyenne ~ 0 → arrêt
- vitesse moyenne < -0.02 → recul

### 8.2 Simulateur 2D

```bash
python simulator_2d.py
```

Simulateur temps réel (pygame) qui génère un circuit procédural par courbes de Catmull-Rom et fait naviguer le modèle dessus. Simule les capteurs IR, l'IMU et l'asymétrie moteur. Permet d'observer visuellement le comportement du modèle **avant** le déploiement sur le robot physique.

---

## 9. Conversion et déploiement

### 9.1 Convertir en TFLite

```bash
python convert_to_tflite.py
```

Le pipeline de conversion :
1. Charge le modèle PyTorch (`checkpoints/best_model.pt`)
2. Fusionne les couches BatchNorm dans les poids linéaires (requis pour TFLite)
3. Reconstruit un modèle Keras équivalent (Dense + activations)
4. Convertit en TFLite (quantification INT8 optionnelle avec `--quantize`)
5. Exporte `normalization_stats.json` avec toutes les constantes nécessaires à l'inférence

**Fichiers générés dans `export/`** :
```
export/
├── zumi_mlp.tflite              ← Modèle pour le robot
└── normalization_stats.json     ← Config complète pour l'inférence
```

Le fichier `normalization_stats.json` contient :
```json
{
  "feature_mean": [...],
  "feature_std": [...],
  "input_dim": 750,
  "window_size": 25,
  "window_feature_dim": 30,
  "temporal_decay": 0.85,
  "ir_offset_bottom": 8.8,
  "gap_threshold": 210.8,
  "exclude_detection": true,
  "detection_indices": [8,9,10,11,12,13,14,15]
}
```

### 9.2 Déployer sur le robot

Le script de conversion copie automatiquement les fichiers vers `core/control/controlers/models/`. Le `MLController` charge le modèle au démarrage et reproduit le pipeline de prétraitement à l'identique :

```
VisionAdapter (29-dim brut)
  ↓ Exclusion détection (indices 8-15) → 21-dim
  ↓ Features ingéniérées (+9) → 30-dim
  ↓ Fenêtre glissante (25 pas × decay 0.85) → 750-dim
  ↓ Z-score normalization → 750-dim normalisé
  ↓ Inférence TFLite → [left, right] dans [-1, 1]
  ↓ Dénormalisation × MOTOR_SPEED_MAX (50) → commandes moteur
```

**Sur le Pi** : le runtime `tflite-runtime` (plus léger que TensorFlow complet) est utilisé avec le délégué XNNPACK pour accélérer les opérations sur ARM.

### 9.3 Déploiement manuel (si la copie automatique n'est pas disponible)

```bash
# Copier le modèle et les stats sur le robot
scp export/zumi_mlp.tflite export/normalization_stats.json \
    pi@192.168.0.1:~/PFE/core/control/controlers/models/
```

Les deux fichiers (`zumi_mlp.tflite` + `normalization_stats.json`) doivent être dans le même répertoire.

---

## 10. Flux complet — Résumé

```bash
# 1. Environnement
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Menu principal (agréger, analyser, entraîner)
python train.py

# 3. (Optionnel) Augmenter les données si le ratio est insuffisant
python augment.py

# 4. (Optionnel) Évaluer en détail
python evaluate.py

# 5. (Optionnel) Tester dans le simulateur 2D
python simulator_2d.py

# 6. Convertir et déployer
python convert_to_tflite.py
```

---

## 11. Troubleshooting

### "FileNotFoundError: captures.jsonl non trouvé"

Les fichiers de données n'existent pas dans `data/`. Lancer d'abord l'agrégation (option 1 du menu) pour consolider les séquences.

### "CUDA out of memory"

Réduire le batch size dans le profil custom, ou laisser le profil adaptatif choisir.

### "Dimension mismatch" à l'inférence

Le modèle a été entraîné avec une dimension d'entrée différente de celle produite par le `MLController`. Vérifier que `normalization_stats.json` sur le robot correspond au modèle `.tflite` déployé. Les deux fichiers doivent provenir de la même exécution de `convert_to_tflite.py`.

### "Python 3.13 is not supported"

Utiliser Python 3.11 ou 3.12. Créer un environnement virtuel avec la bonne version :
```bash
python3.11 -m venv venv
```

### Les graphiques ne s'affichent pas (serveur sans GUI)

Les fichiers PNG sont quand même générés dans `checkpoints/`. Les télécharger sur votre machine pour les visualiser.

### Entraînement très long sur laptop

Pour les datasets de plus de 500k échantillons, un serveur dédié est recommandé. Le projet a utilisé un VPS de 44 cœurs / 125 Go de RAM pour les entraînements à grande échelle.

---

## 12. Référence rapide des constantes

| Constante | Valeur | Fichier | Description |
|-----------|--------|---------|-------------|
| `WINDOW_SIZE` | 25 | dataset.py | Pas de temps dans la fenêtre |
| `WINDOW_FEATURE_DIM` | 30 | dataset.py | Features par pas (détection exclue) |
| `TEMPORAL_DECAY` | 0.85 | dataset.py | Facteur de pondération exponentielle |
| `IR_OFFSET_DEFAULT` | 8.8 | dataset.py | Offset IR calibré (zumi_1) |
| `GAP_THRESHOLD` | 210.8 | dataset.py | Seuil IR_sum pour visibilité de la ligne |
| `INTEGRAL_WINDOW` | 5 | dataset.py | Fenêtre pour ir_error_integral |
| `MOTOR_SPEED_MAX` | 50.0 | ml_controller.py | Plage de vitesse moteur |
| `EARLY_STOPPING_PATIENCE` | 8 | train.py | Époques sans amélioration avant arrêt |

---

**Mis à jour le 13 avril 2026**
**Projet PFE GPA 793 — Contrôle d'un robot Zumi par MLP**
