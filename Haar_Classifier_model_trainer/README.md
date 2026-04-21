# Haar Cascade Trainer

**Module d'entraînement automatisé de détecteurs d'objets** — Crée des fichiers `.xml` 
prêts à déployer sur le robot Zumi (Raspberry Pi Zero V1).

Le module gère le pipeline complet : préparation des données, augmentation, entraînement 
de la cascade Haar/LBP, évaluation, hard negative mining et analyse avancée.  
**Aucune connaissance préalable en machine learning requise** — il suffit de collecter des images et lancer le script.

> **Environnement** : Le module tourne sur votre **PC** (Python 3.8+). 
> Seul le résultat final (`.xml`) est déployé sur le Raspberry Pi.

---

## 📁 Structure du module

```
Haar_Classifier_model_trainer/
├── train_cascade.py              # Point d'entrée — menu interactif
├── positive_image_downloader.py  # Utilitaire pour télécharger des images
├── requirements.txt              # Dépendances Python
├── README.md                     # Ce fichier
│
├── cascade/                      # Package principal (logique métier)
│   ├── __init__.py               # API publique + exports
│   ├── config.py                 # Constantes et préconfigurations
│   ├── environment.py            # Validation de l'environnement
│   ├── data_prep.py              # Préparation des données (split, augmentation, annotations)
│   ├── training.py               # Entraînement (samples .vec, cascade, génération XML)
│   ├── evaluation.py             # Évaluation (test, métriques, plaque modèle)
│   ├── mining.py                 # Hard Negative Mining (simple + itératif)
│   └── analysis/                 # Analyse avancée du modèle
│       ├── __init__.py           # Orchestrateur (7 phases d'analyse)
│       ├── utils.py              # Utilitaires internes
│       ├── stages.py             # Évaluation par stage, mosaïque FN/TP
│       ├── charts.py             # Courbes PR/ROC, graphiques par stage
│       ├── sweep.py              # Sweep complet scaleFactor × minNeighbors
│       └── data_quality.py       # Qualité des données, fenêtre optimale
│
├── data/                         # Dossier des données
│   ├── positive/                 # Images positives (à remplir par l'utilisateur)
│   ├── negative/                 # Images négatives (~500 incluses)
│   ├── train/                    # Données d'entraînement (généré automatiquement)
│   ├── test/                     # Données de test (généré automatiquement)
│   ├── augmented/                # Images augmentées (généré automatiquement)
│   ├── hard_negatives/           # Hard negatives extraits (généré par option [5])
│   ├── filtered_too_small/       # Images positives filtrées (trop petites)
│   ├── cascade/                  # Modèle final (cascade.xml + stages)
│   ├── analysis/                 # Graphiques d'analyse (généré par option [6])
│   ├── annotations.txt           # Annotations positives (généré)
│   ├── bg.txt                    # Liste des négatifs (généré)
│   └── samples.vec               # Données binaires pour l'entraînement (généré)
│
└── Incubator/                    # Archive des modèles entraînés (plaques .md + .xml)
```

---

## ⚙️ Prérequis

### 1. Python et dépendances

**Étape 1.1 : Créer un environnement virtuel**

1. Ouvrir le terminal dans VS Code : `Ctrl + '` (backtick)
2. Lancer la commande pour créer l'environnement :
   ```powershell
   python -m venv .venv
   ```
3. Activer l'environnement (le terminal change d'apparence) :
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   > Si vous avez une erreur de permission, lancer PowerShell en administrateur puis relancer.

**Étape 1.2 : Installer les dépendances**

Avec l'environnement activé (vous devriez voir `(.venv)` au début du terminal), lancer :
```powershell
pip install -r requirements.txt
```

Packages installés : `opencv-python`, `numpy`, `tqdm`, `matplotlib`, `scikit-learn` (optionnel)

**Vérifier l'installation** :
```powershell
python -c "import cv2; print('OpenCV', cv2.__version__)"
```

### 2. Outils CLI OpenCV (obligatoire)

Les outils `opencv_createsamples` et `opencv_traincascade` sont des **exécutables** 
séparés — ils ne sont pas inclus dans le package `opencv-python`.

**Windows** :

1. Télécharger la version pré-compilée :  
   [OpenCV 3.4.18 pour Windows](https://github.com/opencv/opencv/releases/tag/3.4.18)  
   (chercher le fichier `opencv-3.4.x-vc14_vc15.exe` ~182 MB)

2. Exécuter le fichier + accepter l'installation. Les binaires seront extraits 
   (ex: `C:\opencv-3.4.18\`)

3. Localiser les exécutables :
   ```
   C:\opencv-3.4.18\opencv\build\x64\vc15\bin\
     ├── opencv_createsamples.exe
     └── opencv_traincascade.exe
   ```

4. **Ajouter au PATH (permanent)** :
   - Ouvrir `Paramètres système avancés` → `Variables d'environnement` → `PATH`
   - Ajouter une nouvelle entrée pointant vers le dossier ci-dessus
   - Redémarrer VS Code

5. **Vérifier l'installation** dans le terminal (tout environnement) :
   ```powershell
   opencv_createsamples --help
   opencv_traincascade --help
   ```
   Si vous voyez des messages d'aide, c'est bon ✓

**Linux / Mac** :

Compiler OpenCV 3.4 depuis les sources avec les modules CLI `opencv_traincascade` et `opencv_createsamples` (voir la [documentation officielle OpenCV 3.4](https://docs.opencv.org/3.4/d7/d9f/tutorial_linux_install.html)). Les outils ne sont plus distribués dans OpenCV 4.x.

---

### ⚠️ Restriction importante : Pas d'espaces ni d'accents

OpenCV ne gère **pas** les chemins avec espaces ou accents. Vérifiez que :
- ✓ Le dossier du projet n'a **pas d'espaces** (ex: `C:\Users\YourName\my_project\`)
- ✓ Les noms d'images n'ont **pas d'accents** (ex: `stop_sign_1.jpg`, pas `panneau_arrêt_1.jpg`)
- ✓ Les chemins ne contiennent que des caractères ASCII standards (a-z, A-Z, 0-9, _, -)

---

## 🚀 Utilisation

### Lancer le module

```powershell
python train_cascade.py
```

### Menu principal

Le menu s'affiche avec l'**état actuel des données** (✓/✗) et les options disponibles :

| Option | Description | Quand l'utiliser |
|--------|-------------|------------------|
| **[1]** | Pipeline complet | Première utilisation — fait tout automatiquement |
| **[2]** | Préparer les données | Split + augmentation + .vec seulement |
| **[3]** | Entraîner / reprendre | Données déjà préparées, lancer l'entraînement |
| **[4]** | Finaliser cascade.xml | Générer le .xml à partir des stages existants |
| **[5]** | Hard Negative Mining | Extraire les FP pour améliorer le modèle |
| **[6]** | Analyse avancée | Graphiques, métriques par stage, sweep SF×MN |
| **[7]** | Stage intermédiaire | Générer un modèle à partir d'un stage choisi |
| **[8]** | HNM Itératif | Automatise mine → retrain × N rounds |
| **[Q]** | Quitter | — |

> Les options sont affichées dynamiquement selon l'état des données.  
> Par exemple, [5] n'apparaît que si un `cascade.xml` existe.

---

## 📋 Workflow recommandé

### Premier entraînement

1. Placer les images positives croppées dans `data/positive/`
2. Lancer `python train_cascade.py` → **Option [1]** (Pipeline complet)
3. Choisir le profil d'entraînement (Rapide pour tester, Équilibré pour production)
4. Le script fait tout : filtrage → split → augmentation → .vec → entraînement → évaluation

### Améliorer un modèle existant

1. **Option [6]** — Analyse avancée : identifier les faiblesses (FN visuels, sweep SF×MN)
2. **Option [5]** ou **[8]** — Hard Negative Mining : corriger les faux positifs
3. **Option [1]** — Ré-entraîner avec les hard negatives intégrés automatiquement
4. Répéter jusqu'à satisfaction

### Cycle HNM itératif (automatisé)

Pour automatiser le cycle mine → retrain :

1. Avoir un `cascade.xml` existant
2. **Option [8]** → Choisir le nombre de rounds (recommandé : 2-3)
3. Le module va automatiquement : miner les FP → ré-entraîner → évaluer → répéter

---

## 📸 Collecter les données

**La qualité des images = la qualité du modèle.**

### Images positives

- **Croppées serrées** : l'objet occupe 70-100% de l'image
- **Un seul objet par image**
- **Variées** : différents angles, éclairages, distances
- **Minimum 150-200**, recommandé **500+**

> ⚠️ Les images trop petites (< 2× la fenêtre de détection) sont automatiquement  
> filtrées et indexées dans `data/filtered_small_images.log`.

### Images négatives

Photos **sans** l'objet d'intérêt (fonds, textures, paysages).

Ressource recommandée : [Describable Textures Dataset (DtD)](https://www.robots.ox.ac.uk/~vgg/data/dtd/)

### Télécharger automatiquement

```powershell
pip install icrawler
python positive_image_downloader.py
```

Éditer les `queries` dans le script pour cibler votre objet.

---

## 🔧 Pipeline détaillé

### 1. Préparation des données

- **Filtrage** : les images < 2× la fenêtre de détection sont écartées et indexées dans `data/filtered_small_images.log`
- **Split** : 85% train / 15% test (avant augmentation pour éviter le data leakage)
- **Hard negatives** : si `data/hard_negatives/` contient des images, elles sont intégrées au train set
- **Augmentation** : ×5 variantes par image (9 transforms sans modification des contours)

### 2. Augmentation des images

Les images positives étant croppées plein cadre, **aucune transformation géométrique** 
n'est utilisée (pas de rotation, translation, perspective — elles ajouteraient des bordures parasites).

Transforms appliquées :

| Transform | Probabilité | Effet |
|-----------|------------|-------|
| Flip horizontal | 50% | Double la variabilité |
| Brightness + contraste | 100% | Simule éclairages variables |
| Correction gamma | 40% | Simule réponse caméra |
| **Flou gaussien** | 35% | Simule défocus / flou caméra Zumi |
| **Bruit gaussien** | 30% | Simule bruit capteur Pi camera |
| **CLAHE** | 20% | Égalisation adaptative (conditions extrêmes) |
| **Sharpening** | 20% | Renforce les contours |
| **Scale jitter** | 25% | Downscale+upscale → simule basse résolution |
| **Compression JPEG** | 20% | Simule artefacts de compression |

### 3. Entraînement de la cascade

**Profils disponibles** :

| Profil | Feature | Stages | Durée estimée | Usage |
|--------|---------|--------|---------------|-------|
| 🚀 **Rapide** | LBP | 14 | ~1-2h | Prototypage |
| ⚖️ **Équilibre** | HAAR | 14 | ~6-12h | **Recommandé** |
| 🎯 **Précision** | HAAR | 18 | ~12-24h+ | Production |
| 🔧 **Test** | Au choix | Custom | Variable | Expérimentation |

Le profil **Test** permet de configurer : feature type, nombre de stages, `minHitRate`, 
`maxFalseAlarmRate`, et taille de la fenêtre.

**Paramètres clés** :
- `maxFalseAlarmRate` : taux max de FP par stage (défaut 0.5, configurable via profil Test ou `cascade/config.py`)
- `minHitRate` : taux min de détection par stage (défaut 0.995)
- L'entraînement peut être **interrompu et repris** automatiquement

### 4. Évaluation

Le modèle est testé avec 3 presets de détection :

| Preset | scaleFactor | minNeighbors | Caractéristique |
|--------|------------|-------------|-----------------|
| Sensible | 1.05 | 3 | Max recall, plus de FP |
| Équilibré | 1.10 | 5 | Compromis |
| Strict | 1.20 | 7 | Max précision |

**Métriques** : Recall, Précision, F1-Score, Spécificité, FP/image, IoU moyen, taux de multi-détections.

### 5. Analyse avancée (Option [6])

7 phases d'analyse automatique :

1. **Sweep SF×MN** — Heatmap 70 combinaisons (7 SF × 10 MN)
2. **Mosaïque FN/TP** — Visualisation des images manquées vs détectées
3. **Évaluation par stage** — Évolution des métriques stage par stage
4. **Courbes PR/ROC** — Precision-Recall et ROC avec points annotés
5. **Qualité des données** — Analyse de diversité, complexité, clustering des négatifs
6. **Graphiques par stage** — F1, Recall, Précision, Spécificité par nombre de stages
7. **Fenêtre optimale** — Analyse dimensionnelle + recommandation de taille

Tous les graphiques sont sauvegardés dans `data/analysis/`.

### 6. Hard Negative Mining

**Simple (Option [5])** : 
- Analyse les images négatives avec le modèle courant
- Croppe chaque fausse détection → sauvegarde dans `data/hard_negatives/`
- Au prochain entraînement, ces images sont intégrées automatiquement

**Itératif (Option [8])** :
- Automatise le cycle : mine → retrain → évalue → mine → retrain...
- 1 à 5 rounds configurables
- Arrêt anticipé si aucun FP n'est trouvé (convergence)

---

## 📊 Interpréter les résultats

### Métriques principales

| Métrique | Signification | Bon score |
|----------|---------------|-----------|
| **Recall** | % d'objets correctement détectés | > 85% |
| **Précision** | % des détections qui sont correctes | > 80% |
| **F1-Score** | Moyenne harmonique recall + précision | > 0.7 |
| **Spécificité** | % des négatifs correctement rejetés | > 90% |

### Qualité du modèle

| Niveau | F1 | Recall | Précision |
|--------|----|--------|-----------|
| ✅ Excellent | > 0.8 | > 90% | > 85% |
| ✅ Bon | > 0.7 | > 80% | > 75% |
| ⚠️ Acceptable | > 0.5 | > 70% | > 60% |
| ❌ À améliorer | < 0.5 | — | — |

### Recommandations Raspberry Pi Zero V1

- `scaleFactor=1.2` → ~2-4 FPS (bon compromis)
- `scaleFactor=1.3` → ~4-6 FPS (rapide mais moins précis)
- Préférer `scaleFactor ≥ 1.2` pour le temps réel sur le Pi Zero

---

## 🔌 Déployer le modèle sur le robot

1. **Renommer** `data/cascade/cascade.xml` → `mon_objet_v1.xml`
2. **Copier** dans `PFE/core/vision/detectors/models/`
3. **Charger** dans `PFE/main.py` :

```python
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'vision', 'detectors', 'models')
haar_classifier.add_classifier('mon_objet', os.path.join(MODELS_DIR, 'mon_objet_v1.xml'))
```

4. **Tester** : démarrer le robot → interface web → détections en direct.

---

## 🏗️ Architecture du code

Le module est organisé en **package `cascade/`** avec séparation claire des responsabilités :

```
train_cascade.py          ← Point d'entrée (menu + dispatch, ~550 lignes)
  └── cascade/
        ├── config.py     ← Constantes partagées (DETECTION_PRESETS, WINDOW_SIZE, etc.)
        ├── environment.py← Validation (CLI tools, Python, OpenCV, dossiers)
        ├── data_prep.py  ← Pipeline données (filter → split → augment → annotate)
        ├── training.py   ← Entraînement (create_samples → train_cascade → generate_xml)
        ├── evaluation.py ← Évaluation (detect → metrics → plaque markdown)
        ├── mining.py     ← HNM simple + itératif
        └── analysis/     ← Analyse avancée (sweep, PR/ROC, stages, data quality)
```

Pour modifier une étape spécifique, éditez le fichier correspondant. Les constantes 
partagées sont centralisées dans `config.py`.

---

## ❓ FAQ

**Q: Mon modèle n'a que 50% de recall. Que faire ?**  
R: 1) Ajouter plus d'images positives (minimum 500). 2) Lancer l'option [6] pour 
identifier les faiblesses. 3) Utiliser le HNM itératif [8] si le problème est la précision.

**Q: Le script a filtré des images "trop petites". Pourquoi ?**  
R: Les images plus petites que 2× la fenêtre de détection (32×60 px par défaut) ne 
contiennent pas assez de pixels pour que le cascade apprenne. Consultez 
`data/filtered_small_images.log` pour la liste complète. Si beaucoup d'images sont 
filtrées, recollectez des images plus grandes ou ajustez la taille de fenêtre.

**Q: Comment reprendre un entraînement interrompu ?**  
R: Relancer `python train_cascade.py` → Option [3]. Le script détecte les stages 
existants et propose de reprendre.

**Q: Quelle est la différence entre HNM simple [5] et itératif [8] ?**  
R: L'option [5] fait un seul cycle de mining (extraction des FP). L'option [8] automatise le 
cycle complet : mine → retrain → évalue → mine → retrain... pour N rounds, avec arrêt 
anticipé si le modèle ne produit plus de FP.

**Q: Comment changer la taille de la fenêtre de détection ?**  
R: Modifier `WINDOW_SIZE['recommended']` dans `cascade/config.py`. La taille doit 
correspondre au ratio d'aspect de votre objet. Utilisez l'option [6] → analyse de 
fenêtre optimale pour une recommandation basée sur vos données.

**Q: Puis-je ajuster le `maxFalseAlarmRate` ?**  
R: Oui, de deux façons : 1) Via le profil **Test** [4] dans le menu d'entraînement — 
vous pouvez saisir une valeur custom. 2) Modifier la constante globale `MAX_FALSE_ALARM_RATE` 
dans `cascade/config.py`. La valeur par défaut est 0.5 (chaque stage divise les FP par 2). 
Une valeur plus basse (ex: 0.4) rend chaque stage plus sélectif.

**Q: Puis-je utiliser mon propre dataset d'images ?**  
R: Oui, c'est le but du module. Placez vos images croppées dans `data/positive/` et le script gère tout le reste.

---

## 📚 Ressources

- [Documentation OpenCV 3.4 — Cascade Classifier](https://docs.opencv.org/3.4/dc/d88/tutorial_traincascade.html)
- [Algorithme Viola-Jones (2001)](https://www.cs.cmu.edu/~efros/courses/LBMV07/Papers/viola-cvpr-01.pdf)

---

