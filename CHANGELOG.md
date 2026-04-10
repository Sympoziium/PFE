# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).


## [Non publie] — Anti-compression, features engineered v2 et split detecteurs (2026-04-09)

### Contexte
Le MLP (R²=0.51, val_loss=0.0092) souffrait de compression des predictions vers la moyenne:
les scatter plots montraient des predictions regroupees en bande horizontale au lieu de suivre
la diagonale. Le modele predisait des valeurs conservatrices, incapable de produire des commandes
franches (virages marques, arrets nets, marche arriere). Diagnostic: (1) le MSE pur incite le
modele a predire la moyenne conditionnelle, (2) les features ne capturaient pas assez de signal
predictif (derivees, integrales, anticipation camera-IR), (3) le dropout 0.3 etait trop
conservateur pour 2.6M+ echantillons.

### Added
- **RangeAwareLoss** (`train.py`): nouvelle loss MSE + penalite de variance. Penalise le modele
  quand la variance de ses predictions est inferieure a celle des cibles (`torch.relu(target_var -
  pred_var)`). Parametre `lambda_var=0.1` (ajustable: 0.05-0.2). Adresse directement la compression
  des predictions sans revenir a Huber (qui discretisait les sorties avec delta=0.1).

- **4 nouvelles features engineered** (`dataset.py`, `simulator_2d.py`, `ml_controller.py`):
  le vecteur passe de 26-dim/pas (21 raw + 5 eng.) a **30-dim/pas** (21 raw + 9 eng.),
  fenetre glissante 25x30 = **750-dim d'entree** (etait 650-dim).
  - `ir_error_derivative`: `calibrated_error[t] - calibrated_error[t-1]` — vitesse de derive
    laterale. Permet au modele de savoir si la ligne s'eloigne rapidement ou lentement.
  - `ir_error_integral`: moyenne glissante de `calibrated_error` sur 5 pas — biais persistant
    accumule. Indique un decentrage soutenu (terme I du PID).
  - `gyro_z_accel`: `gyro_z_rate[t] - gyro_z_rate[t-1]` — acceleration angulaire. Indique si
    un virage s'intensifie ou se relache (courbure du trajet).
  - `lookahead_delta`: `(line_camera_offset - cal_error_norm) * line_visible` — discordance
    entre la position de la ligne vue par la camera (devant le robot) et celle vue par les IR
    (sous le robot). Signal d'anticipation: quand la camera voit la ligne a droite mais les IR
    la voient au centre, un virage a droite approche.

- **Split detecteurs passifs** (`vision_pipeline.py`, `server_controller.py`):
  nouvelle methode `set_passive_detectors()` pour changer dynamiquement les detecteurs passifs.
  - Onglet Controle: detection passive = **Line detector seulement** (economie CPU, Haar inutile)
  - Onglet Vision: detection passive = **Haar classifiers seulement** (monitoring objets)
  - Garde-fou dans `start_passive_detection()`: si aucun controleur actif, force Haar.

### Changed
- **Dropout** (`train.py`): reduit de 0.3 a 0.15. Avec 2.6M+ echantillons, le dropout elevé
  empechait le modele de faire des predictions confiantes vers les extremes.
- **Loss function** (`train.py`): `nn.MSELoss()` -> `RangeAwareLoss(lambda_var=0.1)`
- **Dimension d'entree MLP**: 650-dim -> 750-dim (necessite re-agregation du dataset)
- **WINDOW_FEATURE_DIM** (`dataset.py`, `ml_controller.py`): 26 -> 30
- **Groupes permutation importance** (`evaluate.py`): Engineered 21-25 -> 21-29

### Notes techniques
- Toutes les nouvelles features respectent les frontieres de sequence (zero aux transitions).
- `ir_error_integral` utilise une somme cumulee vectorisee par segment (O(n), pas de boucle Python
  sur les echantillons individuels).
- `lookahead_delta` est conditionne par `line_visible` pour eviter du bruit quand la camera ne
  detecte pas de ligne.
- Le `compute_engineered()` du simulateur et du ml_controller recoit maintenant le `window_buffer`
  pour calculer l'integrale sur les pas precedents.
- **Compatibilite**: l'ancien modele (650-dim) n'est PAS compatible. Il faut re-agreger (option 1)
  puis re-entrainer (option 4).

---

## [Non publie] — Debug boucle fermee, cleanup legacy et rapport (2026-04-10)

### Contexte
Le deploiement du modele 750-dim a revele un probleme de dimension (le modele deploye etait encore
en 650-dim). Une fois corrige, le modele s'est avere fonctionnel en boucle fermee — premier modele
a reagir correctement aux lignes sur le robot physique. Le split des detecteurs passifs a eu une
consequence inattendue : la detection de ligne se fait maintenant a chaque frame (plus d'interdecoupage
avec Haar), rendant le `line_offset` beaucoup plus stable et continu.

### Added
- **Debug logging MLController** (`ml_controller.py`, `control_manager.py`, `server_controller.py`,
  `flask_router.py`, `onglet_control.py`): instrumentation complete du controleur ML.
  - Timing d'inference (ms par tick)
  - Features intermediaires (calibrated_error, gyro_z_rate, lookahead_delta, etc.)
  - Sortie modele + delta entre ticks consecutifs
  - Suivi des overrides WASD dans le log (distingues des ticks ML)
  - Bouton toggle dans l'UI de controle (route `/controller/debug/toggle`)
  - Resume console a l'arret + sauvegarde `debug_log.json`
  - Alerte automatique si `output_delta` proche de zero (modele qui ne reagit pas)

### Changed
- **Validation IMU** (`vision_adapter.py`): les angles cumulatifs (gyro_x/y/z, rot_x/y/z) ne sont
  plus valides contre la plage [-360, 360] — ils s'accumulent naturellement au-dela apres quelques
  tours de circuit. Seuls les angles non-cumulatifs (acc_x/y, comp_x/y) sont valides.
- **Temporal decay** (`dataset.py`): 0.95 -> 0.85 pour prioriser davantage le present par rapport
  a l'historique dans la fenetre glissante.

### Removed (cleanup legacy)
- **Concept `feature_version`** (`ml_controller.py`): le systeme de versionnement des features
  (v1=2 features, v2=5 features) est retire. Les constantes IR_OFFSET_BOTTOM et GAP_THRESHOLD
  sont maintenant chargees inconditionnellement depuis `normalization_stats.json`.
- **Delegate fallback mort** (`ml_controller.py`): `_interpreter._load_delegate(None)` dans un
  try/except qui ne faisait rien — retire.
- **`_feature_mask` orphelin** (`ml_controller.py`): variable referencee dans le gestionnaire
  d'erreur mais jamais definie — retiree.
- **Defaults stale** (`ml_controller.py`): `IR_OFFSET_BOTTOM=-17.0` et `GAP_THRESHOLD=195.0`
  remplaces par les valeurs mesurees (8.8 et 210.8). Les fallbacks dans `_load_normalization_stats()`
  utilisent maintenant les valeurs de classe au lieu de valeurs hardcodees differentes.
- **Commentaires stale**: mise a jour des docstrings dans tous les fichiers du module
  (dimensions 26->30, 650->750, 5->9 features, ReLU->GELU, Huber->RangeAwareLoss).

---

## [Non publie] — Migration simulateur + refonte evaluations (2026-04-04)

### Contexte
Le simulateur 2D et le module d'evaluation referençaient encore l'ancien systeme de deltas
temporels supprime le 2026-04-02. Le vecteur de base 29-dim (ajout line_offset/line_detected)
n'etait pas reflete dans le simulateur. Les tests d'evaluation etaient obsoletes.

### Changed
- **simulator_2d.py**: migration deltas -> fenetre glissante (20x34=680-dim), vecteur 27->29-dim
  avec zero-padding identique au training pipeline
- **simulate.py [1]**: tests scenariques synthetiques -> evaluation sur sequences reelles du dataset
  avec visualisation predictions vs labels (graphique temporel par segment)
- **simulate.py [2]**: pipeline corrige (compute_engineered_features + compute_sliding_windows),
  categorisation par gyroscope (classify_actions) au lieu des commandes moteur
- **simulate.py [3]**: ablation regression lineaire -> permutation importance sur le vrai MLP,
  par groupe de features (IR, IMU, engineered, etc.) avec bar chart et repetitions pour robustesse
- **Menu option 5**: "Simulation & evaluation avancee" -> "Evaluation avancee"

### Added
- **Menu option [7] Importer et convertir un modele (TFLite)**: telecharge un modele depuis
  le VPS (root@38.69.13.3) via SCP ou copie depuis un chemin local, puis convertit en TFLite.
  Utile pour recuperer un modele entraine sur le serveur.

### Removed
- simulate.py [4] "Simulation boucle ouverte" — redondant avec le simulateur 2D (option 6)
- References aux constantes DELTA_* dans simulator_2d.py et simulate.py
- Regression lineaire sklearn dans l'ablation (remplacee par permutation importance)

---

## [Non publié] — Fenetre glissante, Huber Loss et augmentation de donnees (2026-04-02)

### Contexte
Le MLP avec deltas temporels (82-dim, R²=0.48) sous-apprenait : l'ecart train/val etait quasi nul,
indiquant un probleme de representation. La ligne blanche pointillee disparait aux capteurs IR quand
le robot est centre, creant des etats ambigus que 5 pas de deltas ne suffisent pas a resoudre.

### Added
- **Fenetre glissante** (`dataset.py`): remplace les deltas temporels par une fenetre de 20 pas
  consecutifs (1 seconde a 20Hz) de vecteurs 34-dim (29 raw + 5 engineered) = **680-dim d'entree**.
  Le modele recoit 1 seconde complete de contexte temporel brut au lieu de differences ponderees.
  - `compute_sliding_windows()`: construction vectorisee avec detection de frontieres de sequence
    et zero-padding aux limites
  - Buffer circulaire 20 pas dans `ml_controller.py` pour l'inference temps reel
- **ZumiMLPWindow** (`model.py`): variante [256, 128, 64] avec dropout 0.15, ~210K params,
  dimensionnee pour les 680-dim d'entree. Accessible via `create_model(size="window")`.
- **Module d'augmentation de donnees** (`augment.py`, nouveau):
  - `augment_ir_noise()`: bruit gaussien N(0, sigma) sur les 6 capteurs IR, sigma=[1.5, 3.0, 4.5]
  - `augment_ir_scaling()`: facteurs multiplicatifs [0.85, 0.92, 1.08, 1.15] simulant des variations d'eclairage
  - `augment_ir_dropout()`: zero-out aleatoire des capteurs IR bottom sur des patches de 3 frames
  - `augment_combined()`: bruit + scaling combine, multiplicateur ~4x
  - Menu interactif avec resume, validation, et log de tracabilite (`augmentation_log.json`)
  - **Contrainte respectee**: les labels moteur ne sont jamais modifies (preservation du PID asymetrique)
- **Menu [3] Augmenter les donnees** dans `train.py`: sous-menu pour choisir et appliquer les techniques
  d'augmentation avant l'entrainement

### Changed
- **Huber Loss** (`train.py`): `nn.SmoothL1Loss(beta=0.1)` remplace `nn.MSELoss()`. Le MSE causait
  une regression vers la moyenne sur les etats ambigus (ligne invisible entre les tirets). Huber
  penalise lineairement les grands ecarts, produisant des predictions plus tranchees.
- **`suggest_training_profile()`** refactore:
  - Calcule `effective_dim = step_dim * WINDOW_SIZE` (680-dim) pour le budget de parametres
  - Ratio cible ajuste a 2.5:1 (vs 3:1) pour les entrees fortement correlees
  - Affiche un tableau des architectures possibles avec le nombre d'echantillons requis pour chacune
  - Warning explicite quand les donnees sont insuffisantes + recommande l'augmentation
- **`choose_training_profile()`** simplifie: [1] Adaptatif + [2] Custom. Le profil fenetre en dur est retire.
- **`export_normalization_stats()`** inclut les metadonnees de fenetre (`mode`, `window_size`, `window_feature_dim`)
- **Menu principal** renumerote: [3]=Augmentation, [4]=Entrainement, [5]=Simulation, [6]=Simulateur 2D

### Removed
- `compute_deltas()` et constantes `DELTA_FEATURE_INDICES`, `DELTA_STEPS`, `DELTA_WEIGHTS` de `dataset.py`
- Profil statique `'fenetre'` de `TRAINING_PROFILES`
- Ancien buffer de deltas dans `ml_controller.py` (remplace par `_window_buffer`)

### Resultats premier entrainement (fenetre, avant augmentation)
- **R² = 0.35** (vs 0.48 avec deltas) — regression due a l'overfitting (215K params / 72K samples = ratio 0.3:1)
- Train/Val gap: 0.032 vs 0.060 — **overfitting confirme** (le modele memorise)
- Conclusion: le modele fenetre a besoin de significativement plus de donnees.
  L'augmentation (x4-6) devrait amener le ratio a un niveau sain.

---

## [Non publié] — Feature engineering PID-inspired et vecteur 95-dim (2026-03-26)

### Added
- Systeme de calibration IR: mesure les baselines et offsets des 6 capteurs IR (mode light N=50 auto, heavy N=200 manuel)
- 8 features PID-inspired remplacent les 2 anciennes (line_position, line_confidence):
  - calibrated_error, line_visible, cal_error_norm, approaching_line, on_road, grass_detect, gyro_z_rate, heading_drift
- Deltas temporels etendus: 12 features x 5 pas (60 colonnes, vs 7x3=21 avant)
- Vecteur d'entree total: 95-dim (27 raw + 8 engineered + 60 deltas)
- Modele cible plus gros: [128, 64, 32] ~14K params, ~50-60KB TFLite
- Section [PID-FEATURES] dans analyze_dataset.py pour evaluer les nouvelles features
- Auto-deploy des fichiers TFLite vers core/control/controlers/models/

### Changed
- Categorisation des actions basee sur l'IMU (delta gyro_z) au lieu des commandes moteur
- Deduplication intelligente: seuls les groupes >= 5 echantillons consecutifs identiques sont retires
- Simulation moteur: asymetrie du moteur gauche (efficiency=0.928) au lieu du biais droit
- Calibration IR automatique (light) avant chaque activation de controleur
- Constantes de feature engineering synchronisees via normalization_stats.json

### Fixed
- WeightedRandomSampler desactive (causait une regression du suivi de ligne)
- Nom du fichier TFLite toujours zumi_mlp.tflite (plus de _quant)

---

## [Non publié] — Optimisation pipeline MLP : normalisation z-score, profil adaptatif et feature engineering (2026-03-21)

### Objectif
Optimiser le pipeline d'entraînement MLP pour améliorer la qualité d'apprentissage et préparer le passage à l'échelle (de ~3 400 à ~10 000+ échantillons). Les changements touchent la normalisation des features, la sélection automatique d'architecture, et l'ajout de features engineered pour le suivi de ligne.

### Phase 1 — Fondations de l'entraînement

#### Normalisation z-score (pipeline complet)
- **`MLP_model_trainer/dataset.py`**
  - Ajout de `normalize(mean, std)` : applique la normalisation z-score aux captures
  - Ajout de `apply_feature_mask(mask)` : retire les features mortes (std < 1e-6)
  - `create_data_loaders()` : calcule mean/std sur le train set uniquement (après masque), normalise tout le dataset, stocke les stats pour export
  - Ajout du paramètre `feature_mask` optionnel
- **`MLP_model_trainer/train.py`**
  - Sauvegarde `feature_mean`, `feature_std` et `feature_mask` dans le checkpoint PyTorch
  - Le profil adaptatif passe le masque à `create_data_loaders()`
- **`MLP_model_trainer/convert_to_tflite.py`**
  - Ajout de `export_normalization_stats()` : exporte `normalization_stats.json` à côté du `.tflite` depuis le checkpoint (contient mean, std, mask, input_dim)
  - Intégré comme étape 4 dans la pipeline de conversion
- **`core/control/controlers/ml_controller.py`**
  - Ajout de `_load_normalization_stats()` : charge `normalization_stats.json` depuis le même répertoire que le modèle .tflite
  - Ajout de `_apply_zscore()` : applique la normalisation z-score au vecteur d'état
  - `_build_state_vector()` : pipeline complet VisionAdapter → masque → z-score
  - `get_debug_info()` : expose `zscore_loaded` pour le diagnostic

#### Pipeline de normalisation — z-score unique
La range normalization (IR/255, IMU/180) qui était dans le VisionAdapter a été retirée
car elle est redondante avec le z-score : mathématiquement, le z-score absorbe toute
transformation linéaire préalable. Le VisionAdapter ne fait désormais que la vectorisation
structurelle (assemblage, one-hot, bbox relative). Les valeurs IR (0-255) et IMU (degrés)
sont stockées brutes dans captures.jsonl, ce qui rend les données plus lisibles et élimine
le travail en double.

```
                        Entraînement                         Inférence
                        ─────────────                        ─────────
VisionAdapter           vectorisation structurelle            (identique)
    ↓ raw               → IR brut 0-255, IMU degrés          → IR brut 0-255, IMU degrés
    ↓                   → bbox relative [0,1] (structurel)   → bbox relative [0,1]
    ↓ captures.jsonl    → sauvegardé                         (pas de fichier)
    ↓ feature_mask      → retrait features mortes            → retrait features mortes
    ↓ z-score           → (x - mean) / std                   → (x - mean) / std
    ↓ modèle            → entraînement                       → inférence TFLite
```

#### Profil d'entraînement adaptatif
- **`MLP_model_trainer/train.py`** — `suggest_training_profile()`
  - Remplace les 3 profils hardcodés (Rapide/Équilibré/Précision) par une analyse automatique
  - Calcule le nombre de features actives (std > 1e-6) et propose un masque
  - Calcule le budget de paramètres (ratio cible params:samples = 1:7)
  - Recherche les architectures candidates maintenant un ratio sain
  - Warning "dataset insuffisant" quand la meilleure architecture a <2 couches cachées : affiche l'architecture minimale viable ([32,16]) et le nombre d'échantillons nécessaires
  - Affiche les justifications (ex: "3425 samples, 19 features actives → [32,16] recommandé")
  - Option Custom préservée pour ajustement manuel

#### Shuffle activé par défaut
- **`MLP_model_trainer/dataset.py`** : `shuffle=True` par défaut dans `create_data_loaders()`

### Phase 2 — Feature Engineering

#### Features IR engineered (`IR_diff`, `IR_sum`)
- **`core/vision/vision_adapter.py`**
  - Vecteur d'état passe de 22+N à **24+N** dimensions (27-dim avec N=3 classes)
  - `IR_diff = bottom_left - bottom_right` (indice 6) : position latérale de la ligne
  - `IR_sum = (bottom_left + bottom_right) / 2` (indice 7) : confiance
  - Tous les indices suivants décalés de +2 (détection à 8, classes à 9, bbox à 9+N, IMU à 13+N)
  - Mise à jour de `debug_print_state()`, `validate_imu()`, `validate_detection()`, `validate_IR()`

#### Retrait de la range normalization (valeurs brutes)
- **`core/vision/vision_adapter.py`**
  - Retrait de `/IR_MAX_VALUE` (255), `/ANGLE_MAX_DEG` (180), `/TILT_STATE_MAX` (7)
  - Retrait du `np.clip(-1, 1)` final (cachait les outliers au z-score)
  - Les IR sont stockés bruts (0-255), les IMU bruts (degrés), les features engineered brutes
  - Seule la bbox reste normalisée par les dimensions image (transform structurel, résolution-indépendant)
  - Raison : la range normalization est mathématiquement redondante avec le z-score.
    `zscore(x/255) = (x/255 - μ) / σ` est équivalent à un z-score avec des stats différentes.
    Stocker les valeurs brutes rend les données plus lisibles et élimine le travail en double.

**Nouveau layout du vecteur d'état (27-dim avec 3 classes)** :

| Index | Donnée | Plage | Description |
|-------|--------|-------|-------------|
| 0-5 | IR sensors [6] | 0-255 | Capteurs infrarouges bruts (8 bits) |
| 6 | IR_diff | -255..255 | Position latérale ligne (bottom_L - bottom_R) |
| 7 | IR_sum | 0-255 | Confiance ligne (bottom_L + bottom_R)/2 |
| 8 | detect_flag | {0, 1} | Drapeau détection |
| 9-11 | class [N] | {0, 1} | Classes détectées (one-hot) |
| 12-15 | bbox [4] | [0, 1] | Boîte englobante relative (cx, cy, w, h) |
| 16-26 | IMU [11] | degrés | Gyro(3) + Acc(2) + Comp(2) + Rot(3) + Tilt(1) |

#### Masque de features mortes
- **`MLP_model_trainer/dataset.py`** : `apply_feature_mask(mask)` applique le masque avant z-score
- **`MLP_model_trainer/train.py`** : détection automatique des features mortes, masque sauvé dans checkpoint
- **`MLP_model_trainer/convert_to_tflite.py`** : masque exporté dans `normalization_stats.json`
- **`core/control/controlers/ml_controller.py`** : masque chargé et appliqué à l'inférence

#### Analyse du dataset mise à jour
- **`MLP_model_trainer/analyze_dataset.py`** : `feature_names` mis à jour pour 27 features (ajout IR_diff, IR_sum)

### Résultats de validation Phase 1
- Courbe d'entraînement beaucoup plus saine (lisse, pas de gap overfitting)
- Val_loss : 0.010701 (vs baseline 0.009296)
- R² = -0.047 → diagnostic : dataset trop petit (3 425 échantillons < minimum viable)
- Le profil adaptatif recommande correctement [16] (1 couche) pour ce dataset, avec warning que c'est insuffisant pour apprendre la relation non-linéaire
- Estimation minimum : ~7 742 échantillons pour architecture [32,16] (ratio 7:1)

### Fichiers modifiés

| Fichier | Modifications |
|---------|--------------|
| `MLP_model_trainer/dataset.py` | z-score, masque, shuffle par défaut |
| `MLP_model_trainer/train.py` | profil adaptatif, sauvegarde norm stats + masque, warning dataset insuffisant |
| `MLP_model_trainer/convert_to_tflite.py` | export normalization_stats.json |
| `MLP_model_trainer/analyze_dataset.py` | feature_names 27-dim |
| `core/vision/vision_adapter.py` | IR_diff, IR_sum, layout 24+N |
| `core/control/controlers/ml_controller.py` | chargement z-score + masque, pipeline inférence |

### Prochaines étapes
- Rééchantillonner ~10 000+ échantillons avec le nouveau vecteur 27-dim
- Revalider le pipeline complet avec un dataset suffisant
- Phase 3 (optionnel) : HuberLoss, déduplication, split stratifié

---

## [Non publié] — Pipeline d'entraînement MLP complet (2026-03-18)

### Objectif
Implémenter un pipeline complet d'entraînement et de déploiement de modèles MLP (Multilayer Perceptron) pour le contrôle du robot par apprentissage par imitation. Le modèle est entraîné côté PC avec PyTorch, converti en TensorFlow Lite, puis déployé sur le Raspberry Pi Zero 2.

### Architecture du pipeline
```
[Collecte données] → [JSONL] → [PyTorch Dataset] → [Entraînement MLP]
                                                          ↓
[Robot Pi Zero] ← [TFLite] ← [TensorFlow] ← [ONNX] ← [PyTorch Model]
```

### Ajouté

#### Module d'entraînement (`MLP_model_trainer/`)
- **`dataset.py`** — Chargement des données JSONL et création des DataLoaders PyTorch
  - Classe `ZumiControlDataset` héritant de `torch.utils.data.Dataset`
  - Fonction `create_data_loaders()` avec split train/validation (80/20)
  - Statistiques du dataset (moyennes, écarts-types, distributions)

- **`model.py`** — Architecture MLP avec plusieurs variantes
  - `ZumiMLP` : Architecture modulaire avec couches configurables
  - `ZumiMLPSmall` : Version compacte [32, 16] pour Pi Zero (1410 paramètres)
  - `ZumiMLPLarge` : Version étendue [128, 64, 32] pour tâches complexes
  - Initialisation Xavier, dropout configurable, sortie Tanh bornée [-1, 1]

- **`train.py`** — Script d'entraînement complet
  - Classe `Trainer` avec boucle d'entraînement PyTorch standard
  - Optimiseur AdamW avec weight decay (régularisation L2)
  - Learning rate scheduler `ReduceLROnPlateau`
  - Early stopping configurable (patience=20 par défaut)
  - Gradient clipping pour stabilité
  - Sauvegarde automatique du meilleur modèle + rapport JSON

- **`convert_to_tflite.py`** — Conversion vers TensorFlow Lite
  - Export PyTorch → ONNX avec `torch.onnx.export()`
  - Conversion ONNX → TensorFlow SavedModel via `onnx-tf`
  - Conversion TensorFlow → TFLite avec quantization optionnelle
  - Vérification automatique du modèle converti

- **`requirements.txt`** — Dépendances Python pour l'entraînement PC

- **`TUTORIAL_MLP_PYTORCH.md`** — Tutoriel complet de 12 sections
  - Fondamentaux PyTorch et MLPs
  - Architecture du pipeline de bout en bout
  - Explication détaillée de chaque composant
  - Techniques d'optimisation avancées
  - Guide de déploiement sur système embarqué
  - Dépannage et bonnes pratiques

#### MLController finalisé (`core/control/controlers/ml_controller.py`)
- Chargement du modèle TFLite (compatible `tflite_runtime` et `tensorflow`)
- Méthode `_build_state_vector()` pour construire le vecteur d'état depuis SensorState
- Méthode `_inference()` pour l'inférence TFLite optimisée
- Dénormalisation automatique des sorties [-1, 1] → commandes moteur
- Méthodes de debug : `get_debug_info()`, `get_params()`
- Fallback gracieux si modèle non chargé (commandes = 0)

### Données d'entraînement
- 1405 échantillons collectés via le système de sampling existant
- Format JSONL : `captures.jsonl` (états) + `labels.jsonl` (commandes)
- Vecteur d'état : 21 dimensions (6 IR + 1 flag + 4 classes + 4 bbox + 6 IMU)
- Vecteur de sortie : 2 dimensions (vitesses gauche/droite normalisées)

### Choix techniques

| Aspect | Choix | Justification |
|--------|-------|---------------|
| Framework entraînement | PyTorch | API intuitive, debugging facile, écosystème riche |
| Framework déploiement | TFLite | Optimisé ARM, faible empreinte mémoire (~5MB runtime) |
| Format intermédiaire | ONNX | Standard portable, conversion bidirectionnelle |
| Fonction d'activation sortie | Tanh | Garantit sorties dans [-1, 1] |
| Optimiseur | AdamW | Convergence rapide + weight decay correct |
| Régularisation | Dropout + L2 | Prévention du sur-apprentissage |

### Fichiers créés
- `MLP_model_trainer/dataset.py`
- `MLP_model_trainer/model.py`
- `MLP_model_trainer/train.py`
- `MLP_model_trainer/convert_to_tflite.py`
- `MLP_model_trainer/requirements.txt`
- `MLP_model_trainer/TUTORIAL_MLP_PYTORCH.md`
- `MLP_model_trainer/data/` (données extraites du sampling)

### Fichiers modifiés
- `core/control/controlers/ml_controller.py` — Implémentation complète
- `MLP_model_trainer/DEV_PLAN.md` — Mise à jour avec documentation du pipeline

### Usage
```bash
# 1. Installer les dépendances (PC)
cd MLP_model_trainer
pip install -r requirements.txt

# 2. Entraîner le modèle
python train.py --epochs 100 --model-size medium

# 3. Convertir vers TFLite
python convert_to_tflite.py --quantize

# 4. Déployer sur le robot
scp export/zumi_mlp_quant.tflite pi@<ip>:~/robot/models/
```

### Optimisation du ControlManager et de la gestion des contrôleurs
le but est d'améliorer la fluidité des commandes manuelles afin d'avoir une meilleure réactivité du robot lors du contrôle manuel, et aussi de réduire la latence globale du système pour les futurs contrôleurs ML qui seront plus gourmands en ressources. 

┌─────────────────────────────────────────────────────────────┐
│  AVANT                        APRÈS                        │
├─────────────────────────────────────────────────────────────┤
│  Polling: 250ms (4 Hz)   →   80ms (12.5 Hz)                │
│  Watchdog: 0.6s          →   0.3s                          │
│  Loop delay: fixe 50ms   →   adaptatif (33/50ms)           │
│  Line detection: toujours →   skip en manuel/ML            │
│  Debug prints: activé    →   désactivé                     │
│  Constantes: éparpillées →   centralisées                  │
└─────────────────────────────────────────────────────────────┘

---

## [Non publié] — Refactor complet du control manager (2026-03-16)

### Objectif
Refonte architecturale intégrale du module de contrôle (`core/control/`) pour adopter le patron de conception **Strategy**. Le but est de rendre l'orchestrateur (`ControlManager`) complètement agnostique (aveugle) aux détails d'implémentation des algorithmes de contrôle (PID, State Machine, ML), permettant un système 100% "Plug & Play". 

![Architecture de Contrôle V2](control_module_architecture_v2.svg)

### Modifications apportées
- **Standardisation des Entrées/Sorties (DTO)** :
  - Création de `SensorState` : DTO encapsulant de manière uniforme toutes les lectures des capteurs du robot à l' instant T (IR, IMU, offset ligne, batterie, détections).
  - Création de `MotorCommand` : DTO décrivant les intentions de mouvement (`CommandType` : SPEED, TURN, STOP, FORWARD_STEP) pour abstraire l'interface matérielle.
- **Couche Drivers IO (`core/control/IO_drivers/`)** :
  - `SensorDriver` : Lit l'état du SDK robotique et de la vision pour construire et retourner un objet `SensorState` propre.
  - `MotorDriver` : Interprète les objets `MotorCommand` et les traduit en commandes hardware spécifiques de notre Zumi.
- **Contrat d'interface (Pattern Strategy)** :
  - Création de `ControllerBase` : Classe de base abstraite (ABC) dictant le format d'un contrôleur. Tout nouveau contrôleur implémente obligatoirement `step(sensor_state) -> MotorCommand`.
- **Refonte de l'orchestrateur (`ControlManager`)** :
  - Disparition complète des constantes de mode hardcodés (`MODE_PID`, etc.) et des fonctions `_tick_pid`.
  - Intégration d'un registre dynamique sous forme de dictionnaire (`_controllers`) alimenté via `register_controller(name, controller)`. 
  - La boucle principale de contrôle est désormais universelle : `1. Lecture capteurs -> 2. Inférence du contrôleur actif -> 3. Exécution de la commande moteur`.
- **Nouveaux Contrôleurs (`core/control/controlers/`)** :
  - Adaptation de la logique existante en un `LineFollowerController` unifié et compatible avec la nouvelle baseline.
  - Création à blanc d'un `MLController`, conçu comme prochain jalon utilisant un Multi-Layer Perceptron (MLP) en inférence via TFLite.
  - Création d'un `ManualController` pour le contrôle manuel via l'interface, avec PWM logiciel pour les virages (configurable).
- **Adaptateur Vision** :
  - Création de `VisionAdapter` (`core/vision/vision_adapter.py`) responsable de prendre un `SensorState` en entrée et de la vectoriser mathématiquement (Bounding Boxes, encodage one-hot des classes, normalisation MPU/IR). Ce qui retire cette lourde logique anciennement codée en dur dans les objets DTO.
- **Assainissement du module de contrôle** :
  - Déplacement des anciens outils ou algorithmes obsolètes/déclinés dans un sous-dossier de maintien `legacy/`.
- **Sampling MLP (dataset)** :
  - Export ZIP en `captures.jsonl` + `labels.jsonl` (entrees vectorisees + labels moteurs par ligne).
  - Vectorisation alignee sur `VisionAdapter` avec classes inferees depuis les detecteurs.
  - Labels derives de la derniere commande moteur (SPEED/FORWARD_STEP, STOP/TURN -> zeros).
- **Controle modulaire via ControlManager** :
  - Routes controleur mises a jour (start/stop/status) avec selection par nom de controleur.
  - Override manuel: la croix directionnelle force le basculement sur `manual_controller`.
- **UI onglet controle** :
  - Ajout d'un selecteur de controleur + bouton toggle.
  - Ajout d'un bouton de telechargement des echantillons.


## [Non publié] — Rework complet du LineDetector et intégration VisionPipeline (2026-03-05)

### Objectif
1. Uniformiser le **LineDetector** avec le format standardisé BaseDetector (`{'Object_detected', 'detections', 'logs'}`)
2. Éliminer le **circuit parallèle** où les state machines déshérissaient le détecteur directement
3. Forcer l'architecture **VisionPipeline** comme point d'accès unique pour la détection
4. Supprimer la **duplication de code** (`set_photo_directory`, accès caméra, etc.)

### Modifié

#### LineDetector (`core/vision/detectors/Line_detector.py`) — Format standardisé
- **Ancien format** : `{'detector': 'line', 'value': offset, 'Object_detected': bool, 'detections': [dicts complexes], '_annotation_data': {...}, 'detection_stats': {...}}`
- **Nouveau format** : `{'Object_detected': bool, 'detections': [], 'line_offset': offset|None, 'logs': []}`
  - Clés éliminées : `detector`, `value`, `_annotation_data`, `detection_stats`, `detection_data`
  - `line_offset` est la **clé d'extension spécialisée** pour les state machines
  - Données d'annotation internes : stockées sur `self._last_annotation_data` au lieu de retournées
  
- **Méthode `annotate_detection(frame)`** : signature modifiée
  - Ancien : `annotate_detection(frame, detection_result)` — passait le résultat entier
  - Nouveau : `annotate_detection(frame)` — lit depuis `self._last_annotation_data` intrinsèque
  - Permet une séparation nette entre **détection logique** et **annotation visuelle**
  
- **Méthode `_detect_lines()`** : nettoyage
  - Correction : `show_ROI=False` (pas d'annotation lors de la détection)
  - Suppression : code mort testant `'ctn' in dash` (clé n'existe pas, était `'contour'`)
  - Simplifie et clarifie le retour `{'offset', 'avg_cx', 'avg_cy', 'best_group', 'valid_dashes', 'image_stats'}`
  
- **Méthode `process_passive()`** : refactorisation
  - Ancien : implémentation dupliquée avec `_detect_lines()` + appels récursifs
  - Nouveau : appelle simplement `process()` + ajoute `timestamp` pour le live feed

#### State Machines (`core/control/line_following_state_machine.py`) — VisionPipeline au lieu de circuit isolé
- **Constructeur `LineFollowingStateMachine`**
  - Ancien : `__init__(robot, camera, pid_controller, line_detector, stop_condition_detector=None)`
  - Nouveau : `__init__(robot, vision_pipeline, pid_controller, stop_condition_detector=None)`
  - Caméra et détecteur de ligne **trouvés via pipeline** à la demande
  
- **Constructeur `StepByStepStateMachine`**
  - Ancien : `__init__(robot, camera, pid_controller, line_detector)`
  - Nouveau : `__init__(robot, vision_pipeline, pid_controller)`
  - Même principe : accès unifié via `vision_pipeline`
  
- **Nouveaux helpers** (tous deux machines)
  - `_find_line_detector_index()` : cherche le détecteur par `name == 'line'` dans `vision_pipeline.detectors`
  - `_run_line_detection(frame)` : exécute `vision_pipeline.process_frame(frame, index)` et extrait `line_offset`
  
- **Suppression de la duplication**
  - `set_photo_directory(dir)` éliminé → utilise `vision_pipeline.CAPTURE_DIR` directement
  - `self.camera.capture()` → `self.vision_pipeline.camera.capture()`
  - Tous les `self.line_detector.process()` → remplacés par `self._run_line_detection(frame)`
  
- **Remplacement systématique des appels**
  - Ancien : `line_result = self.line_detector.process(frame.copy())` + `line_offset = line_result.get('value')`
  - Nouveau : `line_offset = self._run_line_detection(frame)`
  - Appliqué à **10+ locations** : `_handle_waiting_approval`, `_handle_moving`, `_handle_approach_line`, `_handle_recenter`, `_handle_line_lost`, etc.

#### ControlManager (`core/control/control_manager.py`) — Extraction correcte de l'offset
- **Boucle `_control_loop()`**
  - Ancien : filtre par `res.get("detector") == "line"` + extrait `res.get("value")`
  - Nouveau : filtre par `'line_offset' in res` + extrait `res.get('line_offset')`
  - Plus robuste : fonctionne même si plusieurs détecteurs retournent `line_offset`
  
- **Méthode `_create_step_machine()`**
  - Ancien : cherchait manuellement le line_detector dans pipeline, passait camera + line_detector séparément
  - Nouveau : passe `vision_pipeline` directement, laisse le machine trouver le détecteur
  - Élimine `register_line_detector()` : plus de nécessité d'une référence globale

#### main.py — Wiring simplifié
- **Création `LineFollowingStateMachine`**
  - Ancien : `LineFollowingStateMachine(robot=zumi, camera=zumi.camera, ..., line_detector=line_detector, ...)`
    + `state_machine.set_photo_directory(PHOTOS_DIR)`
    + `control_manager.register_line_detector(line_detector)`
  - Nouveau : `LineFollowingStateMachine(robot=zumi, vision_pipeline=vision_pipeline, ...)`
    + Plus de `set_photo_directory()` ni `register_line_detector()`
    + Photos sauvegardées via `vision_pipeline.CAPTURE_DIR` configuré au bootstrap

#### VisionPipeline (`core/vision/vision_pipeline.py`) — Annotation générique
- **Méthode `annotate_detection_result(frame, detector, result)`**
  - Ancien : détectait via `result.get('detector') == 'line'` + appelait `detector.annotate_detection(frame, result)`
  - Nouveau : détecte via `'line_offset' in result` + appelle `detector.annotate_detection(frame)` (sans result)
  - Signature new-school plus simple et modulaire

#### server_controller.py (`interface/server_controller.py`) — Fallback legacy mis à jour
- **Route `pid_step_start()` — Fallback pour créer StepByStepStateMachine sans ControlManager**
  - Ancien : `StepByStepStateMachine(robot=self.robot, camera=vp.camera, pid_controller=..., line_detector=detector)`
  - Nouveau : `StepByStepStateMachine(robot=self.robot, vision_pipeline=vp, pid_controller=...)`
  - Élimine la recherche manuelle du line_detector

#### test_line_detector_refactoring.py — Mise à jour tests
- **Tous les 6 tests révisés** pour vérifier le **nouveau format standardisé**
- Tests clés :
  - ✓ Format correct : `['Object_detected', 'detections', 'line_offset', 'logs']`
  - ✓ Pas de clés anciennes : `detector`, `value`, `_annotation_data`, `detection_stats`
  - ✓ `annotate_detection(frame)` sans paramètre result
  - ✓ `process_passive()` + `timestamp`
  - ✓ Image noire → `Object_detected=False, line_offset=None`
  - ✓ Intégration VisionPipeline.annotate_detection_result()

### Impact architectural

| Aspect | Avant | Après |
|--------|-------|-------|
| **Point d'accès caméra** | Duplicé : `robot.camera`, `vision_pipeline.camera`, state machines | Unique : `vision_pipeline.camera` |
| **Détection de ligne** | Direct : `state_machine.line_detector.process()` | VisionPipeline : `_run_line_detection()` |
| **Format des résultats** | Fragmenté (3+ formats différents par détecteur) | Unifié : format BaseDetector |
| **Stockage photos** | Via attribut `self.photo_save_dir` | Via `vision_pipeline.CAPTURE_DIR` |
| **Annotation visuelle** | Embarquée dans process() | Séparée : annotate_detection(frame) |
| **Clés d'extension** | `value`, `detector`, `detection_stats` | `line_offset` simple et claire |

### Fichiers modifiés
- `core/vision/detectors/Line_detector.py` — Refactorisation majeure (format + annotation)
- `core/control/line_following_state_machine.py` — Rework complet (2 machines, helpers, wiring)
- `core/control/control_manager.py` — Extraction offset corrigée, création step_machine simplifiée
- `core/vision/vision_pipeline.py` — Annotation alignée sur nouveau format
- `main.py` — Wiring simplifié, suppression set_photo_directory + register_line_detector
- `interface/server_controller.py` — Fallback legacy mis à jour
- `test_line_detector_refactoring.py` — Tests refactorisés pour nouveau format

---

## [Non publié] — Amélioration du sctipt de préparation du zumi (2026-03-05)

### Objectif :
1. Refactor complet du script `zumi_prepare.sh` pour le rendre plus robuste, fiable et adapté aux tests terrain.
2. Ajouter une fonctionnalité de diagnostic pour vérifier que le port 5000 est bien libé avant de lancer le programme, avec un système de retry automatique.
3. Ajouter une méthode pour bootstrap le programme principale et offirir une barre de chargement pour indiquer la progression de la préparation.

### Modifications apportées
- Refactor complet de `zumi_prepare.sh` en mode plus robuste avec fonctions utilitaires (`port_is_free`, `get_pids_on_port`, `free_port`, `kill_by_pattern`).
- Réécriture de la boucle FAST pour libérer le port 5000 avec vérification réelle et retry (jusqu'à 10 tentatives) avant d'annoncer un succès.
- Correction de l'extraction des PID sur un port (méthode robuste via `ss` + fallback `fuser`) pour éviter les faux positifs de libération.
- Passage des kills critiques en `-9` pour les processus récalcitrants (`main.py`, `flask`, `werkzeug`).
- Ajout d'une vérification post-kill des processus Python restants en mode FULL.
- Suppression des credentials Wi-Fi hardcodés : le mode FULL demande maintenant SSID et mot de passe de façon interactive.
- Sécurisation du fichier temporaire Wi-Fi (`chmod 600`) et meilleure gestion de `wpa_supplicant` (arrêt propre + fallback).
- Ajout d'un retry de connectivité réseau avec plusieurs tentatives de ping avant échec.
- Nettoyage de la sortie `dhclient` pour éviter les messages parasites dans les logs.
- Le mode FULL réutilise explicitement la logique FAST en fin de parcours pour garantir que le port 5000 est libre avant lancement du programme.
- Ajout d'un handler `SIGINT`/`SIGTERM` dans `main.py` pour forcer un arrêt propre et éviter d'avoir à relancer `zumi_prepare.sh fast` entre deux tests.
- Ajout d'une barre de progression visuelle dans le terminal pour indiquer les étapes de chargement au lancement de notre programme.

### Résultat
- Le mode FAST est plus fiable et déterministe : il valide que le port 5000 est effectivement libre.
- Le mode FULL est plus versatile pour les tests terrain (choix réseau au moment du lancement).
- Réduction des cas `OSError: [Errno 98] Address already in use` lors des redémarrages rapides.


## [Non publié] — Amélioration algorithme de calcul de distance (2026-03-04)

### Objectif : 
1. Améliorer la précision du calcul de distance approximative à partir de la taille de la bounding box.

### Solution proposée :
- La première estimation de la distance focale c'est basé sur 2 point (15 et 30 cm). pour améliorer la précision on va ajouter 2 points supplémentaires (20 et 45 cm) pour faire une régression linéaire plus précise.

### Modification apporté
- réduction de la férquence de polling de l'utilisation des ressources à 20 sec au lieu de 5.
- Comme il semble y avoir une légère distortion entre les objets, on change l'apporche de la focale globale pour une focale spécifique par objet.
- On a précédement déterminer les distance focale en utilisant des moyennes, mais pour améliorer la précision on va faire une régression linéaire pour chaque objet en utilisant les 4 points de données (15, 20, 30, 45 cm) au lieu de 2 points (15 et 30 cm). pour faire la régression j'ai fait un script `Régression_lin_distance_focale.py` qui utilise la méthode des moindres carrés pour trouver les coefficients de la régression linéaire (focale = a * taille_image + b).
- j'ai entrainer un nouveau modèle pour les panneau stop et il torche le cul du modèle de git big time. genre il peut voir dans le noir et les résultats de son approximation sont beaucoup plus précis que le modèle de git. dire que je viens d'entrainer mon meilleur modèle avec moins de 200 images positives. je pense que le maxFalseAlarmRate de 0.4 a vraiment aidé à améliorer la précision du modèle, ça a permis d'avoir des bounding box plus précises ce qui a un impact direct sur la précision du calcul de distance. je vais tenter de log les résultats pour ajouter au rapport plus tard.
- ajout d'une limite de fréquence d'annotation sur le live feed pour réduire la charge CPU (annotation toutes les 10 frames (0.5s à 20fps))
- j'ai aussi changer la fréquence de détection passive de 4sec a 0.5sec pour le moment tout semble bien aller et sa semble être bénéfique en basse résolution. avec l'arrivé des nouveau Pi V2 on va pouvoir se gater un peu plus niveau ressources.
### Commentaires :
- la première implémentation a été fait avec 2 points (15 et 30 cm), les résultats était relativement bien avec une erreur d'environ 3-4 cm à 30 cm et plus, ces pour quoi on a décider d'ajouter 2 point supplémentaire pour améliorer la précision. cela dit ce n'est pas la seul chose qui sera tester, on va également essayer une focale spécifique par objet et on va tenter 2 méthodes pour les calculer (moyenne et régression linéaire) pour voir laquelle donne les meilleurs résultats. je vais tenter de log les résultats pour ajouter au rapport plus tard.
- après expérimentation, il n'y a pas de différence significative entre les deux méthodes. ce qui a un plus gros impact cependant ces la qualité des bounding box du modèle. si elle sont trop large ou trop mince cela va fausser le calcul de la distance. c'est pour ça que je pense que l'amélioration de la précision du modèle de détection aura un impact plus significatif sur la précision du calcul de distance que l'amélioration de la méthode de calcul elle même.

#### Résumé pour le rapport
La conclusion que tu devrais tirer de cette analyse est la suivante : le modèle pinhole avec focale fixe est adéquat pour des distances courtes (15–30 cm), mais sa précision est fondamentalement limitée par la qualité des bounding boxes produites par le détecteur HAAR, et non par la méthode d'estimation de la constante focale. L'amélioration prioritaire serait donc d'améliorer la précision des bounding boxes via un meilleur entraînement du modèle, ou d'introduire un facteur correctif empirique par classe d'objet.

---

## [Non publié] — Resources Monitoring (2026-02-27)

### Objectif : 
1. Implémenter un système de monitoring des ressources (CPU, RAM) pour la détection passive en temps réel, avec affichage dans le terminal.
2. voir si ya moyen de faire du calcul de distance approximative à partir de la taille de la bounding box (pour future estimation de distance à l'objet)
### Contraintes :
- Doit être très léger, on refresh les stats toutes les 5 secondes seulement
- Affichage clair et lisible dans le terminal (pas de logs redondants)
- Utilisation de `psutil` pour les stats système (CPU, RAM)
- Calcul de distance approximative basé sur la taille de la bounding box (en pixels) et une estimation de la taille réelle de l'objet. On va se baser sur la formule de la distance focale : `distance = (taille_reelle * focale) / taille_image`
- La focale peut être estimée à partir de tests préliminaires (ex: mesurer la taille de la bounding box pour un objet à une distance connue)


## [Non publié] — Révision majeure de la détection passive et hard positive mining (2026-02-26)

### Ajouté

#### Détection en temps réel — Compteur visuel live
- **Compteur de détections** sur le live feed : badge vert en haut à gauche montrant le nombre de détections courantes
  - Implémenté dans `_draw_passive_overlay()` via `cv2.putText()` — zero overhead (~0.01ms/frame)
  - Fournit un feedback visuel instantané sans requête HTTP supplémentaire

#### Système de résolution caméra dynamique
- **Dropdown de résolution** remplaçant l'ancien toggle "High Res" (`interface/onglet_vision.py`)
  - 4 options natives : QQVGA 160×128 (défaut), QCIF 176×144, QVGA 320×240, VGA 640×480
  - Changement appliqué immédiatement : ferme caméra → change résolution → relance flux et détection passive
  - La résolution sélectionnée affecte **tous les aspects** : live feed, captures, détection passive (une seule instance caméra)
- **Endpoint backend** : `POST /set_resolution` avec JSON `{width, height}`
- **Méthode pipeline** : `VisionPipeline.change_camera_resolution(w, h)` instancie une caméra à la nouvelle résolution
- Passe de `capture_hires()` temporaire à une approche unifiée (plus simple, plus robuste)

#### Hard Positive Mining — Système complet de collecte d'entraînement
- **Architecture** : Quand le mining est activé, chaque détection passive réussie génère un crop de la bounding box
  - Stockage temporaire dans `captured_images/mining_crops/` pendant la session
  - Nommage descriptif : `<objet>_<timestamp>_<largeur>x<hauteur>_<uuid>.jpg`
    - Exemple : `Stop_Sign_20260226_143022_45x52_a3f2b1.jpg`
    - Facilite le tri rapide des images et l'identification manuelle lors du téléchargement
  
- **Méthodes VisionPipeline** (`core/vision/vision_pipeline.py`)
  - `_harvest_crops(frame, detections)` — Extraction et sauvegarde des crops (appelée depuis thread passive)
  - `enable_mining()` / `disable_mining()` — Contrôle du mode mining
  - `get_mining_stats()` — Statistiques courantes (total, par objet)
  - `collect_mining_crops()` — Liste tous les fichiers crop
  - `clear_mining_crops()` — Supprime tous les crops + remet compteurs à zéro

- **Endpoints serveur** (`interface/server_controller.py`, `interface/flask_router.py`)
  - `POST /toggle_mining` — Active/désactive le mining + retourne stats
  - `GET /mining_stats` — Poll des statistiques (refresh JS toutes les 3s)
  - `GET /download_mining_crops` — ZIP en mémoire + envoi client + suppression robot (évite memory leak)

- **UI interactif** (`interface/onglet_vision.py`)
  - Bouton toggle `⛏️ Mining Off/On` (classe `remoteDL-toggle-btn`)
  - Badge violet affichant total + détails par objet (ex: "12 crops (Stop_Sign: 8, Pieton: 4)")
  - Bouton download `📖 Download Crops` (activé uniquement quand ≥1 crop disponible)
  - Polling automatique des stats toutes les 3 secondes pendant le mining
  - Feedback toast lors de l'activation/désactivation et téléchargement

- **Performance** : Extraction + I/O (cv2.imwrite) se fait pendant le `sleep(1.0s)` du thread passive (~0.5ms/crop), n'impacte pas le live feed

### Modifié

#### Déploiement et correction des bugs post-test
- **StopDetectorMatt** — Standardization complète du format de sortie
  - `process_passive()` implémentation légère (évite disk I/O, `url_for`, création dossier diagnostic)
  - `process()` retourne maintenant `{Object_detected, detections: [...], logs}` (format standardisé)
  - Ajout imports : `import time` et try/except pour `url_for` (compatibility Flask optionnel)

- **Détecteur d'indicateur** — Fix CSS color bug
  - `runDetection()` et `runDiagnostics()` maintenant `classList.remove('on', 'off')` avant d'ajouter la nouvelle classe
  - Prévient accumulation de classes et CSS specificity issues (rouge restait coincé)

- **Passive Detection button** — Implémentation fonctionnelle
  - `togglePassiveDetection()` appelle maintenant `POST /start_passive_detection` ou `/stop_passive_detection`
  - Pas juste un toggle visuel — action backend réelle

- **Typo parameter** — `vision_pipeline.start_passive_detection(detctor_index=...)` → `detector_index=...`

- **Layout caméra** — Flex grid plus clean
  - Boutons groupés dans containers flex avec `gap: 8px` et `flex-wrap: wrap`
  - Removed hardcoded `margin-top: 15px` des toggle buttons CSS (maintenant géré par gap)

### Technique - Performance & Architecture

- **Zero-overhead live stats** : Compteur dessiné directement sur frame (cv2.putText) au lieu de polling JS
- **Thread-safe mining** : Mutex `_mining_lock` pour les compteurs partagés entre threads passive + HTTP
- **Memory-safe cleanup** : ZIP temporaire en mémoire, suppression crops après envoi client
- **Modularité caméra** : `change_camera_resolution()` réutilise le même type de caméra (ZumiCamera, ou autre)
- **Pas de breaking change** : Former API reste fonctionnelle (backward compatible)

---

## [Non publié] — Branche Haar_Classifier (2026-02-09)

### Ajouté
- **HaarClassifier** — Détecteur générique Haar Cascade multi-modèles (`core/vision/detectors/Haar_classifier.py`)
  - Chargement dynamique : `add_classifier(name, xml_path)` / `remove_classifier(name)`
  - Détection multi-classifieurs avec fusion des résultats
  - Paramètres configurables par classifieur : `scaleFactor`, `minNeighbors`, `minSize`
  - Méthode `diagnostique_detecteur()` avec balayage automatique de paramètres
- Dossier centralisé pour les modèles `.xml` : `core/vision/detectors/models/`
- Chargement des modèles via chemin absolu résolu depuis `main.py`

### Modifié
- **StopDetectorZumi** (`core/vision/detectors/Stop_detector_zumi.py`)
  - Classe renommée `StopDetector` → `StopDetectorZumi`
  - Format de sortie unifié : `{Object_detected, detection_box, confidence, area, logs, source_file_url, annotated_url}`
  - Ajout de `diagnostique_detecteur(filename)` avec balayage de paramètres
- **Consolidation JS** (`interface/onglet_vision.py`)
  - Trois fonctions de diagnostic fusionnées en `runDiagnostics()` générique
  - `updateStopUIPanelVisibility()` → `updateDiagnosticPanelVisibility()` (tous détecteurs)
- **Corrections UI Accueil** (`interface/onglet_acceuil.py`)
  - 12 erreurs CSS `}}` corrigées
  - Bug `getElementById('camBtn')` → `getElementById('cameraToggleBtn')`
  - Remplacement `ontouchstart` inline par `addEventListener(..., {passive: true})`

### Supprimé
- Route legacy `/diagnose_stop` (`flask_router.py`, `server_controller.py`)
- Import `itertools` (plus utilisé)

---

## [Non publié] — Branche Detecteur_Stop_Zumi (2026-02-06)

### Ajouté
- **StopDetectorCV** — Détecteur HSV conventionnel (`core/vision/detectors/Stop_detector_cv.py`)
  - Segmentation HSV double plage (rouge H=[0-10] + [160-180])
  - Prétraitement morphologique (MORPH_OPEN + MORPH_CLOSE)
  - Filtrage multi-critères : aire, ratio, polygone, solidité convexe, remplissage
- **StopDetectorMatt** — Détecteur HSV avancé (`core/vision/detectors/Stop_detector_matt.py`)
  - Score composite pondéré (ratio rouge/blanc, centrage texte, bordures, aspect, pureté, taille)
  - Seuil adaptatif `min_score` configurable (défaut 0.35)
  - Soft gate pureté (remplace le hard gate qui causait des faux négatifs)
- **Système de diagnostic générique** (`core/vision/vision_pipeline.py`)
  - Méthode `get_current_detector_diagnostic()` déléguant au détecteur actif
  - Overlays automatiques (contours, candidats rejetés, meilleure détection)
  - Sauvegarde dans `static/captured_images/diagnostics/`
- **Routes backend** : `POST /diagnose_detector`, `POST /run_detection`
- **Panel diagnostic interactif** dans l'onglet Vision (indicateur dynamique, terminal de logs)
- **Galerie d'images diagnostic** (ouverture dans un nouvel onglet)
- **Format de logs unifié** via `format_detection_result()`

### Modifié
- Format de résultat standardisé sur tous les détecteurs
- Support format BGR maintenu partout (convention OpenCV)

---

## [Non publié] — Architecture initiale (2026-01)

### Ajouté
- **Refonte complète de l'architecture** — Modularisation du code monolithique de l'équipe précédente
  - Module `core/camera/` : drivers caméra isolés avec interface abstraite `camera_base`
  - Module `core/vision/` : pipeline de vision + détecteurs indépendants
  - Module `core/robot/` : logique robot avec abstraction `robot_base`
  - Module `interface/` : serveur Flask modulaire avec onglets
- **Serveur Flask** (`interface/`)
  - Framework web dédié à la vision avec live feed caméra
  - Capture d'image, sélection de détecteur, exécution de détection
  - Onglets modulaires (accueil, vision, template)
  - Routes : `GET /detectors`, `POST /detector`, `POST /run_detection`
- **StopDetectorZumi** — Ground truth basé sur l'API `find_stop_sign()` de la librairie Zumi
- **Compatibilité Zumi** — Adaptation Python 3.5.3 (pas de f-strings, encodage UTF-8)
- **Script `zumi_prepare.sh`** — Préparation du robot (arrêt des processus de base, libération des ressources)
- **Contrôle moteur** via le serveur Flask
- **Toggle download automatique** des images capturées
- **Bouton exit** sur la page d'accueil

### Modifié
- Migration de `Camera` vers `ZumiCamera` dans `robot_zumi.py`
