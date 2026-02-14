# Haar Cascade Trainer

**Module d'entraînement automatisé de détecteurs d'objets** — Crée des fichiers `.xml` 
prêts à déployer sur le robot Zumi (Raspberry Pi Zero V1).

Le script gère le pipeline complet : préparation des données, augmentation, entraînement 
de la cascade Haar, et évaluation. **Aucune connaissance préalable en machine learning 
requise** — il suffit de collecter des images et lancer le script.

> **Environnement** : Le script tourne sur votre **PC** (Python 3.8+). 
> Seul le résultat final (`.xml`) est déployé sur le Raspberry Pi.

---

## 📁 Structure du module

```
Haar_Classifier_model_trainer/
├── train_cascade.py              # Script principal — lancer celui-ci
├── positive_image_downloader.py  # Utilitaire pour télécharger des images
├── requirements.txt              # Dépendances Python
├── README.md                     # Ce fichier
│
└── data/                         # Dossier des données
    ├── positive/                 # Vos images positives (à remplir)
    ├── negative/                 # Images de fond / négatives (~500 incluses)
    ├── train/                    # Données d'entraînement (généré automatiquement)
    ├── test/                     # Données de test (généré automatiquement)
    ├── augmented/                # Images augmentées (généré automatiquement)
    ├── annotations.txt           # Fichier d'annotations (généré automatiquement)
    ├── bg.txt                    # Liste des images négatives (généré automatiquement)
    ├── samples.vec               # Données binaires pour l'entraînement (généré)
    └── cascade/                  # Modèle final (cascade.xml généré ici)
```

---

## ⚙️ Prérequis

### 1. Python et dépendances

**Étape 1.1 : Créer un environnement virtuel dans VS Code**

Un environnement virtuel isole les dépendances du projet — c'est une bonne pratique pour éviter les conflits.

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

Cela installe :
- `opencv-python` (bibliothèque de vision par ordinateur)
- `numpy` (calculs numériques)
- `tqdm` (barres de progression)

**Vérifier l'installation** :
```powershell
python -c "import cv2; print('OpenCV', cv2.__version__)"
```

---

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

Compiler à partir des sources (voir [PLAN_DEVELOPPEMENT.md](/PLAN_DEVELOPPEMENT.md#installation-des-outils-cli))

---

### ⚠️ Restriction importante : Pas d'espaces ni d'accents

OpenCV ne gère **pas** les chemins avec espaces ou accents. Vérifiez que :
- ✓ Le dossier du projet n'a **pas d'espaces** (ex: `C:\Users\YourName\my_project\`)
- ✓ Les noms d'images n'ont **pas d'accents** (ex: `stop_sign_1.jpg`, pas `panneau_arrêt_1.jpg`)
- ✓ Les chemins ne contiennent que des caractères ASCII standards (a-z, A-Z, 0-9, _, -)

---

## 🚀 Utilisation rapide

### Cas d'usage typique : Entraîner un détecteur de panneau stop

**Étape 0 : Collecter les images (voir section suivante)**

Placer ~300 images croppées de panneaux dans `data/positive/`

**Étape 1 : Lancer le script**

Ouvrir le terminal (`.venv` activé) et exécuter :
```powershell
python train_cascade.py
```

Le script va :
1. ✓ Valider votre environnement
2. ✓ Préparer les données (split 85% entraînement / 15% test)
3. ✓ Augmenter automatiquement les images positives (×5)
4. ✓ Entraîner le modèle (durée : ~15 min pour le profil rapide, ~4h pour équilibré)
5. ✓ Évaluer le modèle sur les images de test
6. ✓ Générer un rapport avec des recommandations

**Le résultat final** : `data/cascade/cascade.xml`

---

## 📸 Collecter les données (le plus important)

**La qualité des images = la qualité du modèle**. Garbage in, garbage out.

### Qu'est-ce qu'une bonne image positive ?

Une **image positive** est une photo contenant l'objet à détecter, **croppée serrée** :
- ✓ L'objet doit occuper **70-100 %** de l'image
- ✓ Fond **uni ou simple** (blanc, gris, texture uniforme)
- ✓ **Un seul objet par image**
- ✓ Variés : différents angles, éclairages, distances, arrière-plans
- ✗ Pas de cadre, pas d'arrière-plan complexe, pas d'autres objets

**Exemple** : Pour un panneau stop
- ✓ BON : Photo de juste le panneau rouge-blanc, fond blanc
- ✗ MAUVAIS : Panneau stop au loin sur une route (trop petit, arrière-plan complexe)

### Combien d'images ?

Minimum : **150-200 images**  
Recommandé : **500-2000 images**  
➜ Plus d'images = meilleur modèle, mais la qualité prime toujours.

### Télécharger automatiquement depuis Internet

Utiliser `positive_image_downloader.py` pour récupérer facilement des centaines d'images.

**Utilisation** :

1. Éditer le dossier `positive_image_downloader.py` et modifier la liste `queries` :
   ```python
   queries = [
       "stop sign isolated white background",
       "stop sign red white photo",
       "panneau stop fond blanc",
       # Ajouter plus de variantes...
   ]
   ```
   ➜ Utiliser des mots-clés en anglais ou français ou même d'autres langues, **plusieurs queries = plus de variétés**.

2. Lancer le script :
   ```powershell
   pip install icrawler  # Une seule fois
   python positive_image_downloader.py
   ```

3. Les images seront téléchargées dans un dossier `positives/` organisé par query.

4. **Trier manuellement** :
   - Garder les images de bonne qualité (crop serré, fond simple)
   - Supprimer les mauvaises (trop petites, arrière-plans complexes, plusieurs objets)
   - Copier les bonnes dans `data/positive/`
   - Vous pouvez même les modifier sur paint pour crop l'objet et uniformiser le background.

**Conseils pour les queries** :
- Varier les langues : "stop sign", "panneau arrêt", "señal de alto"
- Ajouter les contextes : "white background", "isolated", "close-up", "product photo"
- Utiliser des variantes : "stop sign", "octagon red", "traffic stop"

### Où trouver des images négatives

Les **images négatives** sont des photos sans l'objet d'intérêt (fond, paysages, routes, etc.).  

Ressource recommandée : [Describable Textures Dataset (DtD)](https://www.robots.ox.ac.uk/~vgg/data/dtd/)
- Télécharger, extraire, copier les images dans `data/negative/`

---

## 🔧 Méthodologie du script

Le script automatise un **pipeline complet** d'entraînement. Voici ce qui se passe :

### 1️⃣ Préparation des données

- **Annotation automatique** : Chaque image croppée devient un exemple d'entraînement
- **Séparation train/test** : 85% pour entraîner, 15% pour évaluer
- **Aucune normalisation manuelle** : Le script gère tout automatiquement

### 2️⃣ Augmentation (multiplication des images)

Chaque image positive est transformée aléatoirement (rotation, flou, luminosité, etc.)  
➜ 300 images originales → ~1500 images d'entraînement  
➜ **Augmente la robustesse du modèle.**

### 3️⃣ Création du fichier .vec

Conversion des images en format binaire optimisé pour l'entraînement.

### 4️⃣ Entraînement de la cascade

Le script entraîne un **classifieur en cascade** (Viola-Jones) avec OpenCV.

**Profils disponibles** :

| Profil | Durée | Précision | Usage |
|--------|-------|-----------|-------|
| 🚀 **Rapide** | ~15 min | Moyenne | Prototypage / tests |
| ⚖️ **Équilibré** | ~4 heures | Bonne | **Recommandé** |
| 🎯 **Précis** | ~12 heures+ | Excellente | Production |

Le script affiche la progression en temps réel.

### 5️⃣ Évaluation du modèle

Le modèle est testé sur le 15% d'images réservé.

**Métriques affichées** :

| Métrique | Signification | Bon score |
|----------|---------------|-----------|
| **Recall** (Taux de détection) | % d'objets correctement détectés | > 85 % |
| **Précision** | % des détections qui sont correctes | > 80 % |
| **F1-Score** | Moyenne harmoniqu recall + précision | > 0.7 |
| **Spécificité** | % des images sans objet correctement rejetées | > 90 % |
| **IoU** | Qualité de localisation (où est l'objet) | > 0.6 |
| **Multi-détections** | % des objets avec >1 détection | < 30 % |

Le script recommande aussi les **paramètres optimaux pour le Raspberry Pi Zero** (vitesse vs précision).

### 6️⃣ Export du modèle

Le fichier `cascade.xml` est généré dans `data/cascade/`  
➜ Prêt à déployer !

---

## 📊 Interpréter les résultats

### L'script affiche un rapport avec 3 sections

**1. Tableau comparatif** de toutes les configurations testées :
```
     SF   MN    Recall    Préc.      F1    Spéc.   FP/img
  ► 1.20    7    73.4%    42.3%   0.537    90.8%    0.092
```
La ligne avec `►` est le meilleur compromis.

**2. Rapport détaillé** de la meilleure configuration :
- Tous les scores (Recall, Précision, F1, etc.)
- Compteurs bruts (TP, FN, FP, TN)
- IoU moyen et pourcentage de multi-détections

**3. Diagnostic + Recommandations** :
```
⚠ Recall faible (73.4%) — ~27% des objets manqués.
  → Augmenter le nombre d'images positives originales
  → Diversifier les augmentations (angles, éclairages)
  → Réduire scaleFactor pour scanner plus d'échelles
```

### Quand le modèle est-il bon ?

✅ **Excellent** : Recall > 90 %, Précision > 85 %, F1 > 0.8
✅ **Bon** : Recall > 80 %, Précision > 75 %, F1 > 0.7
⚠️ **Acceptable** : Recall > 70 %, Précision > 60 %, F1 > 0.5
❌ **À améliorer** : F1 < 0.5 → recommencer avec plus d'images ou profil Équilibré

### Recommandations Raspberry Pi Zero V1

Le script estime la **vitesse de détection** selon les paramètres :
- `scaleFactor=1.2` → ~2-4 FPS (bon compromis)
- `scaleFactor=1.3` → ~4-6 FPS (rapide mais moins précis)

➜ Préférer `scaleFactor ≥ 1.2` pour le temps réel sur le Pi Zero.

---

## 🔌 Déployer le modèle sur le robot

### Étape 1 : Renommer le modèle

Le modèle `.xml` généré est dans `data/cascade/cascade.xml`.  
Le renommer selon l'objet détecté (ex: `stop_sign_v1.xml`) pour mieux l'identifier.

### Étape 2 : Copier sur le robot

1. Naviguer jusqu'à : `PFE/core/vision/detectors/models/`
2. Coller le fichier `.xml` là-dedans

### Étape 3 : Charger dans le détecteur

Ouvrir `PFE/main.py` et ajouter le classifieur à la liste :

```python
# Dossier contenant les modèles .xml pour les classificateurs de Haar       
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'vision', 'detectors', 'models')

haar_classifier.add_classifier('stop_sign', os.path.join(MODELS_DIR, 'stop_sign_v1.xml'))
haar_classifier.add_classifier('Pieton', os.path.join(MODELS_DIR, 'pedestrian_classifier.xml'))
# Ajouter votre nouveau classifieur ici
haar_classifier.add_classifier('mon_objet', os.path.join(MODELS_DIR, 'mon_objet_v1.xml'))
```

### Étape 4 : Tester sur le robot

Démarrage du robot → accéder à l'interface web → voir les détections en direct.

---

## 📖 Pour aller plus loin

- **Évolution du modèle** : Si les résultats ne sont pas bons, retourner à l'étape de collecte de données (mais plus d'images ou meilleure variété)
- **Hard negative mining** : Récolter les fausses détections (FP), les ajouter comme négatifs, ré-entraîner
- **Paramètres avancés** : Voir [PLAN_DEVELOPPEMENT.md](PLAN_DEVELOPPEMENT.md) pour la configuration complète

---

## 📚 Ressources

- [Documentation officielle OpenCV 3.4 — Cascade Classifier](https://docs.opencv.org/3.4/dc/d88/tutorial_traincascade.html)
- [Algorithme Viola-Jones (2001)](https://www.cs.cmu.edu/~efros/courses/LBMV07/Papers/viola-cvpr-01.pdf)
- [PLAN_DEVELOPPEMENT.md](PLAN_DEVELOPPEMENT.md) — Documentation technique complète

---

## ❓ FAQ

**Q: Mon modèle n'a que 50 % de recall. Que faire ?**  
R: Augmenter le nombre d'images positives (minimum 500) et diversifier (angles, backgrounds).

**Q: Script interrompu. Comment reprendre ?**  
R: Relancer simplement `python train_cascade.py` — il détectera l'entraînement précédent et demandera si reprendre ou recommencer.

**Q: Combien de temps pour entraîner ?**  
R: Profil Rapide (LBP) = 15 min. Profil Équilibré (HAAR) = 4h. Profil Précis = 12h+.

**Q: Puis-je utiliser mon propre dataset d'images ?**  
R: Oui, ces pour ça que j'ai fait ce module. Place les images croppées dans `data/positive/`. Le script gère le reste.

---

## 📝 Notes

- ✅ L'augmentation crée automatiquement 5 variantes par image
- ✅ L'entraînement peut être interrompu et repris
- ✅ Aucune édition de code requis, sauf pour le script de download d'images — juste des images et un clic

---

