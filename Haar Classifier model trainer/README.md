# Haar Cascade Trainer

Module d'entraînement automatisé de classifieurs Haar cascade via OpenCV 3.4.
Produit un fichier `.xml` directement déployable sur le robot Zumi (Raspberry Pi Zero V1, OpenCV 3.x).

> **Note** : Ce script tourne sur le **PC de développement** (Python 3.8+).
> Seul le `.xml` final est déployé sur le Raspberry Pi.

## Prérequis

| Composant | Version | Installation |
|---|---|---|
| Python | 3.8+ | Standard |
| OpenCV (Python) | 3.4.x ou 4.x | `pip install opencv-python` |
| OpenCV CLI tools | **3.4.x** | Voir [Installation des outils CLI](#installation-des-outils-cli) |
| NumPy | ≥ 1.19 | `pip install numpy` |
| tqdm | ≥ 4.0 | `pip install tqdm` |

### Installation des outils CLI

Les outils `opencv_createsamples` et `opencv_traincascade` sont des **exécutables C++**
séparés de la librairie Python. Ils ont été retirés d'OpenCV 4.0 — il faut les
obtenir depuis la branche 3.4 :

**Windows** : Télécharger [OpenCV 3.4 releases](https://github.com/opencv/opencv/releases/tag/3.4.18).
Les `.exe` sont dans `build/x64/vc15/bin/`. Ajouter ce dossier au PATH.

**Linux/Mac** : Build from source :
```bash
git clone -b 3.4 https://github.com/opencv/opencv.git
cd opencv && mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_opencv_apps=ON ..
make -j$(nproc)
```

Vérifier l'installation :
```bash
opencv_createsamples --help
opencv_traincascade --help
```

## Concept clé

L'entraînement Haar cascade se fait via des outils **CLI** d'OpenCV, pas via l'API Python.
Ce script Python est un **orchestrateur** qui :
1. Prépare les données (annotation, augmentation, split)
2. Appelle `opencv_createsamples` pour créer le fichier `.vec`
3. Appelle `opencv_traincascade` pour entraîner la cascade
4. Évalue le modèle résultant via `cv2.CascadeClassifier` en Python
5. Exporte le `.xml` prêt au déploiement

## Utilisation rapide

```bash
# 1. Placer les images croppées de l'objet dans data/positive/
# 2. Lancer le script
python train_cascade.py --output stop_sign_v2.xml

# Options utiles
python train_cascade.py \
    --output stop_sign_v2.xml \
    --profile balanced \           # rapid | balanced | precise
    --augment \                    # Activer l'augmentation de données
    --deploy-to ../core/vision/detectors/models/
```

## Méthodologie

### 1. Collecte des données (préalable utilisateur)

Accumuler **200 à 2000 images croppées** de l'objet à détecter (ex: panneaux stop).

- Les images doivent contenir **uniquement l'objet** (pas de scène complète)
- Varier les conditions : angles, éclairages, distances, arrière-plans
- Plus d'échantillons = meilleur modèle, mais la qualité prime : **Garbage in, garbage out**

### 2. Préparation des données (automatisée par le script)

- **Annotation automatique** : chaque image croppée = 1 objet plein cadre → fichier `annotations.txt`
- **Augmentation** (optionnel) : flip, rotation, luminosité, flou → multiplie la banque ×5
- **Split** : 85% entraînement / 15% test
- **Pas de normalisation manuelle** : `opencv_createsamples` gère le redimensionnement,
  `detectMultiScale` applique sa propre égalisation d'histogramme
- **Négatifs** : banque pré-chargée de ~500-1000 images de fond (fournie avec le module)

> **Pourquoi pas de validation set ?** L'entraînement Haar cascade n'utilise pas de
> validation set externe. Chaque stage utilise internement `minHitRate` et
> `maxFalseAlarmRate` comme critères de convergence. Le grid search classique est
> irréaliste (chaque run = heures). On propose plutôt 3 profils prédéfinis.

### 3. Création du .vec

`opencv_createsamples` convertit les images annotées en fichier binaire `.vec`
redimensionné à la taille de la fenêtre d'entraînement (défaut : 24×24 pixels).

### 4. Entraînement

`opencv_traincascade` entraîne la cascade en stages successifs. Chaque stage ajoute
des classifieurs faibles (arbres de décision) pour atteindre les cibles de
`minHitRate` et `maxFalseAlarmRate`.

**Profils d'entraînement** :

| Profil | Stages | Features | Durée estimée | Usage |
|---|---|---|---|---|
| `rapid` | 12 | LBP | ~15 min | Prototypage, validation rapide |
| `balanced` | 16 | HAAR | ~4 heures | **Recommandé** — bon compromis |
| `precise` | 20 | HAAR | ~12 heures+ | Meilleure qualité possible |

Le script affiche la progression en temps réel (stage courant, hit rate, false alarm rate)
et maintient un log détaillé.

### 5. Évaluation

Le modèle `.xml` est évalué sur le test set (15% réservé) via `cv2.CascadeClassifier` :

| Métrique | Description |
|---|---|
| Taux de détection (Recall) | % d'objets correctement détectés |
| Faux positifs / image | Nombre moyen de fausses alertes par image négative |
| Précision | TP / (TP + FP) |
| IoU moyen | Qualité de la localisation (overlap bbox) |

### 6. Export

Le modèle final est renommé et optionnellement copié dans
`core/vision/detectors/models/` pour déploiement immédiat sur le robot.

## Exigences non-fonctionnelles

- Le script affiche sa progression dans la console avec barres de chargement dynamiques
- Des logs détaillés sont sauvegardés dans `logs/`
- Le modèle `.xml` compilé est prêt à déployer par simple copie dans le dossier `models/`
- L'utilisateur ne fournit que les images positives ; les négatifs sont pré-chargés
- L'entraînement peut être repris après interruption (mécanisme natif d'`opencv_traincascade`)

## Références

- [Documentation officielle OpenCV 3.4 — Cascade Classifier Training](https://docs.opencv.org/3.4/dc/d88/tutorial_traincascade.html)
- [Viola-Jones (2001) — Rapid Object Detection using a Boosted Cascade of Simple Features](https://www.cs.cmu.edu/~efros/courses/LBMV07/Papers/viola-cvpr-01.pdf)
- Voir [PLAN_DEVELOPPEMENT.md](PLAN_DEVELOPPEMENT.md) pour le plan technique détaillé