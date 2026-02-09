# PFE - Projet Robot Zumi 🤖

Projet de fin d'étude centré sur le robot Zumi et la conception de features d'intelligence artificielle.

## 📚 Documentation Git

Pour les membres de l'équipe qui débutent avec Git, nous avons préparé deux documents :

### [📖 Guide Git Complet](GUIDE_GIT.md)
Guide détaillé avec toutes les procédures Git Bash pour débutants :
- Introduction et concepts fondamentaux
- Commandes de base avec exemples
- Procédures pour créer et gérer les branches
- Workflows collaboratifs
- Résolution des problèmes courants
- Bonnes pratiques

### [📋 Aide-Mémoire Git](AIDE_MEMOIRE_GIT.md)
Référence rapide des commandes Git essentielles pour le quotidien.

## 🚀 Démarrage Rapide

```bash
# Cloner le projet
git clone https://github.com/Sympoziium/PFE.git
cd PFE

# Créer une branche pour votre travail
git checkout -b feature/votre-fonctionnalite

# ... travaillez sur votre code ...

# Enregistrer et envoyer vos modifications
git add .
git commit -m "Description de vos modifications"
git push -u origin feature/votre-fonctionnalite
```

Pour plus de détails, consultez le [Guide Git Complet](GUIDE_GIT.md).

## 👥 Équipe

Projet réalisé dans le cadre du programme de fin d'études.

## Procédure de connexion au zumi via SSH
On souhaite se connecter au Raspberry Pi du robot afin d'avoir un plein contrôle de celui-ci

1. se connecter au Wifi du zumi. 
    En allumant le robot, il va afficher le SSID de son réseau, on doit alors s'y connecter en entrant le mot de passe qui est le même que le SSID. 
    SSID connu: `zumi3257`, `zumi4585`

2. se connecter sur dans un browser chrome a `http://zumidashboard.ai/`
    on veut aller chercher l'adresse ip du robot qui se trouve dans les settings lorsque connecté.
    **Cette Étape est facultative** on peut se connecter avec le default gateway `192.168.10.1`

3. Ouvrir un terminal et tenter une connexion ssh au robot.

    entrez la commande suivante `ssh pi@adresse_ip_du_robot`comme ceci:
    ```
    ssh pi@10.192.181.46
    ```

4. à la première connexion il vont demander si tu veux fingerprint l'encription il faut entrer `yes`
    ```
    The authenticity of host '10.192.181.46 (10.192.181.46)' can't be established.
    ED25519 key fingerprint is SHA256:DjT/j9wBuWBwYsjfBbCoAbD+RFQeL6+tj6RO3I/2/s8.
    This key is not known by any other names.
    Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
    Warning: Permanently added '10.192.181.46' (ED25519) to the list of known hosts.
    ```

5. finalement, on va demander le mot de passe pour se connecter au robot, le mot de passe est `pi` puis appuyer sur enter vous verrez allors le terminal bash du robot.
    ```
    pi@zumi3257:~ $
    ```


pour consulter la doc des fonctions de la library zumi aller a `https://docs.robolink.com/docs/Zumi/Python/Function-Documentation`


## CHANGELOG

### Modification architecture
- Refonte complète de l’architecture logicielle afin de modulariser au maximum le code.
Le code de l’équipe précédente était principalement centralisé dans un seul fichier, ce qui rendait la maintenance, l’évolution et les tests difficiles.

- La nouvelle architecture vise à isoler chaque fonctionnalité du système dans des modules indépendants :

- acquisition caméra,
- pipeline de vision,
- détecteurs,
- logique robot,
- interface opérateur.
Cette approche améliore :
- la lisibilité du code,
- la maintenabilité,
- la testabilité,
- la réutilisabilité des modules.

-Elle permet également de remplacer facilement un composant matériel (ex. caméra) sans impacter la logique globale du système.
Il suffit d’implémenter un nouveau driver respectant les abstractions définies (interfaces de base).

```
PFE/
│
├── core/
│   ├── camera/
│   │   ├── __init__.py
│   │   ├── camera_base.py
│   │   ├── picam2.py
│   │   └── zumi_camera.py          # Wrapper pour caméra Zumi (RGB→BGR)
│   │
│   ├── robot/
│   │   ├── Archive/
│   │   │   ├── Programme_UI.py
│   │   │   └── Zumi_mock/
│   │   │       └── SimZumi.py
│   │   ├── __init__.py
│   │   ├── robot_base.py
│   │   └── robot_zumi.py
│   │
│   └── vision/
│       ├── detectors/
│       │   ├── detector_base.py    # Classe de base pour tous les détecteurs
│       │   ├── Line_detector.py
│       │   ├── Luminosity.py
│       │   ├── Stop_detector_zumi.py  # Détecteur Zumi (lib Vision)
│       │   ├── Stop_detector_cv.py    # Détecteur HSV conventionnel
│       │   ├── Stop_detector_matt.py  # Détecteur HSV avancé (pureté/bordures)
│       │   ├── Haar_classifier.py     # Classificateur Haar générique multi-modèles
│       │   └── models/                # Modèles .xml pour Haar cascades
│       │       └── stop_sign_classifier_2.xml
│       ├── Objectif.md
│       └── vision_pipeline.py
│
├── interface/
│   ├── flask_router.py
│   ├── onglet_acceuil.py
│   ├── onglet_template.py
│   ├── onglet_vision.py            # UI avec système de diagnostic
│   ├── server_controller.py        # Routes backend pour détection
│   └── static/
│       └── captured_images/
│           └── diagnostics/         # Overlays de diagnostic
│
├── Doc/
│   ├── AIDE_MEMOIRE_GIT.md
│   ├── GUIDE_GIT.md
│   ├── GUIDE_GIT.pdf
│   ├── Procédure serveur flask.md
│   ├── Procédure test zumi.md
│   └── Workflow_GIT.md
│
├── .gitignore
├── main.py
├── zumi_prepare.sh
└── README.md
```

### Modularisation du système de vision

- Le système de vision a été découpé en plusieurs niveaux d’abstraction :

1. Niveau matériel (hardware)
    - Les drivers caméra sont isolés dans le module camera/.
    - Le reste du système ne dépend que de l’interface camera_base.

2. Niveau logique (pipeline de vision)
    - Le fichier vision_pipeline.py orchestre :
        - la capture des images,
        - l’exécution des détecteurs,
        - la collecte des résultats.
    - Il agit comme un point central, indépendant du matériel et des algorithmes spécifiques.

3. Niveau algorithmes (détecteurs)
    - Chaque détecteur est implémenté comme un module indépendant.
    - Les détecteurs héritent d’une classe de base commune (detector_base).
    - Cela permet d’ajouter, retirer ou remplacer un détecteur sans modifier le pipeline.
- Cette architecture découple complètement la vision du reste du système, ce qui facilitera :
    - l’ajout de nouveaux détecteurs,
    - l’intégration future d’un modèle CNN,
    - les tests sur matériel réel ou simulé.


### Ajout d'un serveur FLASK
**TLDR** : J'ai commencer le développement d'un serveur flask custom pour la vision. Pour le moment j'ai seulement copier les parties du live feed caméra du code original.

**Added**
- ajouté un framework de base pour un serveur web dédié à la vision.
- ajouté un bouton pour la capture d'image via le serveur web.
- ajouté plusieurs fonctions getter pratique dans la classe `VisionPipeline`.
- ajouté la gestion de caméra sur thread depuis `flask_server.py`. voir si on serais mieux de le faire ailleur.
- ajouté le lancement du `flask_server.py` sur un thread.
- ajout de l'enregistrement des images sur le PC via le serveur flask.

### Modification pour le Zumi
- le zumi fonctionne avex `python 3.5.3`, j'ai donc du modifier les fichiers sources du projet pour ne plus utiliser les print format `f` et forcer l'encodage de tout les fichiers en UTF-8 avec l'entête:
```
#!/usr/bin/env python
# -*- coding: utf-8 -*-
```
- j'ai conçu avec chatGPT un script de préparation du Zumi qui est a run avant de faire les tests. en gros il permet d'arrêter les process du programme de base du zumi et libère les ressources du robot pour notre code a nous. voir `Procédure test zumi.md` pour les détails.
- le robot est capable d'exécuter notre programme et son serveur flask est fonctionnel, deplus les api zumi sont toujours fonctionnel.
- ajout d'un bouton exit sur la paje d'acceuil pour permettre de quitter le programme normalement.
- ajout des fonctions de contrôle moteur au serveur flask.

**Modification du serveur flask**
- Le serveur est rendu modulaire, il est constitué des fichiers d'onglets permettant de segmenté chaque fonctionnalitée.
- l'onglet vision offre toute les fonctionnalitées pour l'intéraction avec vision artificielle.
    - on peut voir le livefeed;
    - on peut capturer des images;
    - on pourra choisir le détecteur
    - on pourra faire uen prédiction avec ce détecteur.

### Ajout d'un détecteur de stop de base
parmis les fonctions fournies par le package zumi on à une api appelé `find_stop_sign()`. pour cette première implémentation, nous allons l'ajouter au détecteurs de notre projet comme ground truth, elle
servira de base pour comparer avec nos propres détecteurs.

### Intégration sélection de détecteur et exécution (Vision)

- Interface Vision:
  - Remplacement du bouton temporaire par une liste déroulante listant les détecteurs disponibles.
  - Chargement dynamique via `GET /detectors` et présélection de l’index courant.
  - Envoi de la sélection au backend via `POST /detector`.
  - Le bouton “Lancer Détection” appelle `POST /run_detection` et affiche le JSON de résultat.

- Backend Flask:
  - Ajout de l’attribut `selected_detector_index` dans le contrôleur pour mémoriser le détecteur choisi.
  - Nouvelles routes: `GET /detectors`, `POST /detector`, `POST /run_detection`.
  - Récupération du frame courant via `vision_pipeline.get_last_frame()` (repli sur `capture_frame()` si nécessaire).
  - Exécution de la détection avec `VisionPipeline.process_frame(frame, detetor_index=selected_detector_index)`.

- Routes et fichiers modifiés:
  - `interface/flask_router.py`: ajout des règles pour `detectors`, `detector`, `run_detection`.
  - `interface/server_controller.py`: ajout de l’état sélection + endpoints de liste/sélection/exécution + gestion d’erreurs.
  - `interface/onglet_vision.py`: ajout de la liste déroulante, du JS de chargement/sélection et de l’affichage des résultats.

- Note technique:
  - Les frames caméra sont des `ndarray` au format BGR (OpenCV). Conversion en RGB uniquement si exigée par un détecteur (`cv2.cvtColor(..., cv2.COLOR_BGR2RGB)`).


  ### Cleanup pré merge

  - ajout d'un toggle button sur le UI de vision pour activer ou désactiver le download automatique des images capturé.
  - bug fix, on ferme le livefeed vidéo quand on change d'onglet
  - added un seul bouton pour lancer le diagnostique du detecteur actif.
  - removed le boutton toggle d'affichage des resultats sous la boite de capture.

---

## 🔄 CHANGELOG - Branche Detecteur_Stop_Zumi (2026-02-06)

### 🎯 Nouveaux Détecteurs de Panneau Stop

#### **StopDetectorCV** - Détecteur HSV Conventionnel
**Fichier**: `core/vision/detectors/Stop_detector_cv.py`

Implémentation classique basée sur:
- **Segmentation HSV**: Double plage pour capturer le rouge (H=[0-10] + [160-180])
- **Prétraitement morphologique**:
  - `MORPH_OPEN` (kernel 3×3, 3 iterations) pour nettoyer le bruit
  - `MORPH_CLOSE` (kernel 7×7, 4 iterations) pour reconstruire la forme
- **Détection de contours**: `findContours` avec approximation polygonale
- **Filtrage multi-critères**:
  - Aire minimale configurable (défaut: 500 pixels)
  - Ratio largeur/hauteur proche de 1.0 (tolérance: 0.35)
  - Nombre de sommets polygonaux: 5-10 (octogone)
  - Solidité convexe: > 0.85
  - Ratio de remplissage boîte englobante: > 0.5

**Caractéristiques**:
- ✅ Support Python 3.5.3 (format strings `.format()`)
- ✅ Compatible OpenCV 3.x et 4.x (`findContours` auto-détection)
- ✅ Logs détaillés avec raisons de rejet explicites
- ✅ Méthode `diagnostique_detecteur()` générique

#### **StopDetectorMatt** - Détecteur HSV Avancé
**Fichier**: `core/vision/detectors/Stop_detector_matt.py`

Approche avancée avec analyse multi-scores:
- **Paramètres HSV configurables**: Plages H/S/V personnalisables à l'initialisation
- **Score composite** pondéré:
  - **Ratio rouge/blanc** (15%): Analyse du rapport rouge/blanc dans le patch détecté
  - **Centrage texte** (15%): Détection de zone blanche centrale (texte "STOP")
  - **Détection bordures** (25%): Vérification bordure blanche sur les 4 côtés
  - **Ratio aspect** (15%): Proximité forme carrée
  - **Score pureté** (20%): Soft gate seulement (évite faux négatifs)
  - **Bonus taille** (10%): Favorise détections larges
- **Seuil adaptatif**: `min_score` configurable (défaut: 0.35, plus permissif que hard gates)

**Améliorations vs version originale**:
- ❌ **Suppression hard gate pureté**: Était trop strict (rejetait à < 0.65)
- ✅ **Soft gate pureté**: Contribue au score mais ne rejette pas directement
- ✅ **Détection 4 bordures**: Au lieu de 2 seulement
- ✅ **Logs enrichis**: Affiche tous les scores intermédiaires

**Caractéristiques communes**:
- Format de résultat standardisé: `{'Object_detected': bool, 'detection_box': (x,y,w,h), 'confidence': float, 'area': int, 'logs': [...], 'steps': [...], 'source_file_url': str, 'annotated_url': str}`
- Support format BGR (OpenCV natif) tout au long du pipeline
- Sauvegarde overlays en RGB pour affichage web

---

### 🔧 Système de Diagnostic

#### **Architecture Diagnostic Générique**
**Fichier**: `core/vision/vision_pipeline.py`

Nouvelle méthode `get_current_detector_diagnostic()`:
- Délègue au détecteur actif via sa méthode `diagnostique_detecteur()`
- Permet à chaque détecteur d'implémenter son propre diagnostic spécialisé
- Retourne JSON avec:
  - `steps`: Liste d'étapes intermédiaires avec URLs d'images
  - `logs`: Array de messages de debug
  - `best`: Meilleure détection avec bbox et aire
  - `source_file_url`: URL image source

#### **Overlays de Diagnostic**
Les détecteurs génèrent des overlays automatiquement:
- **Contours détectés**: Tracés en bleu
- **Candidats rejetés**: Visibles avec logs explicites
- **Meilleure détection**: Rectangle vert + label "STOP"
- **Sauvegarde**: Dossier `static/captured_images/diagnostics/`

#### **Routes Backend**
**Fichier**: `interface/server_controller.py`

Nouvelles routes:
- `POST /diagnose_detector`: Appelle diagnostic générique du détecteur actif
- `POST /run_detection`: Exécution simple avec overlay si détection
- Helper `format_detection_result()`: Formatage console unifié

---

#### **Panel Diagnostic Interactif**
**Fichier**: `interface/onglet_vision.py` (lignes 283-289)

Structure:
```html
<div class='stop-detect-panel' id='stopDetectPanel'>
    <div class='tab-subtitle'>Diagnostic Stop</div>
    <div class='indicator-and-terminal'>
        <div id='stopDetectIndicator' class='detect-indicator'>Aucune détection</div>
        <div id='stopDetectTerminal' class='log-terminal'>Terminal vide</div>
    </div>
</div>
```

**Indicateur dynamique**:
- Classe `.on` (vert): Stop détecté
- Classe `.off` (rouge): Aucune détection
- Classe par défaut (gris): État neutre

**Reset automatique** lors changement détecteur:
```javascript
function onDetectorChange() {
    // ... code ...
    indicator.classList.remove('on', 'off');
    indicator.textContent = 'Aucune détection';
    terminal.textContent = 'Terminal vide';
}
```

#### **Galerie d'Images Diagnostic**
**Fichier**: `interface/onglet_vision.py` (fonction `runGenericDiagnostics`, lignes 691-704)

Ouvre nouvel onglet avec galerie HTML:
- Affiche toutes les étapes de traitement (`payload.steps`)
- Format: Nom étape + image overlay
- Utile pour debug visuel du pipeline de détection

---

### 📝 Autres Améliorations

#### **Format de Logs Unifié**
**Fichier**: `interface/server_controller.py` (fonction `format_detection_result()`)

Formatage console structuré:
```
============================================================
RÉSULTATS DE DÉTECTION - StopDetectorCV
============================================================
Objet détecté: OUI
Position: x=120, y=85
Taille: largeur=80, hauteur=78
Confiance: 85.0%
Aire du contour: 6240 pixels
Temps de traitement: 0.045s
--- Détails du traitement ---
[logs du détecteur...]
============================================================
```

#### **Gestion d'Erreurs Robuste**
- Try-catch sur toutes les opérations I/O
- Messages d'erreur explicites dans JSON responses
- Logs d'erreur avec stack trace pour debug

---

## 🔄 CHANGELOG - Branche Haar_Classifier (2026-02-09)

### 🎯 Nouveau Détecteur : HaarClassifier (générique)

#### **HaarClassifier** - Classificateur Haar Cascade Multi-Modèles
**Fichier**: `core/vision/detectors/Haar_classifier.py`

Détecteur générique basé sur les cascades Haar d'OpenCV, capable de charger **plusieurs modèles .xml** simultanément:
- **Chargement dynamique**: `add_classifier(name, xml_path)` / `remove_classifier(name)`
- **Détection multi-classifieurs**: Itère sur tous les classifieurs chargés, fusionne les résultats
- **Paramètres configurables** par classifieur: `scaleFactor`, `minNeighbors`, `minSize`
- **Logs détaillés**: Nombre de détections par classifieur, raisons de rejet, timing
- **Méthode `diagnostique_detecteur()`**: Balayage de paramètres automatique avec sauvegarde d'overlays

**Organisation des modèles**:
- Nouveau dossier `core/vision/detectors/models/` pour centraliser les fichiers `.xml`
- Chargement via chemin absolu résolu depuis `main.py` avec `os.path.dirname(__file__)`

**Utilisation dans `main.py`**:
```python
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'vision', 'detectors', 'models')
haar_classifier = HaarClassifier()
haar_classifier.add_classifier('stop_sign', os.path.join(MODELS_DIR, 'stop_sign_classifier_2.xml'))
```

---

### 🔧 Modernisation de StopDetectorZumi
**Fichier**: `core/vision/detectors/Stop_detector_zumi.py`

- **Classe renommée**: `StopDetector` → `StopDetectorZumi` (clarté)
- **Format de sortie standardisé**: Adoption du payload unifié `{Object_detected, detection_box, confidence, area, logs, source_file_url, annotated_url}`
  - Remplace l'ancien format `{Object detected, Object coordinates, Object size}`
- **Paramètre `filename`** ajouté à `process()`: Compatible avec l'introspection du pipeline (`inspect.signature`)
- **Ajout de `diagnostique_detecteur(filename)`**: Balayage de paramètres (`scaleFactor` × `minNeighbors` × `minSize`) en BGR et RGB
- **Sauvegarde d'images annotées**: Bounding box + label sur détection
- **Logs enrichis**: Résultats visibles dans le terminal web de l'UI

---

### 🧹 Nettoyage Backend & UI

#### Suppression de la route legacy `/diagnose_stop`
- `flask_router.py`: Route `/diagnose_stop` supprimée, seule `/diagnose_detector` est conservée
- `server_controller.py`: Méthode `diagnose_stop()` supprimée (~120 lignes de code de balayage paramétrique)
- Import `itertools` retiré (plus utilisé)

#### Consolidation des fonctions JS de diagnostic
**Fichier**: `interface/onglet_vision.py`
- Trois fonctions JS (`runStopDiagnostics()`, `runGenericDiagnostics()`, `runDiagnostics()`) fusionnées en une seule `runDiagnostics()` générique
- `updateStopUIPanelVisibility()` renommée en `updateDiagnosticPanelVisibility()`: Le panel diagnostic s'affiche maintenant pour **tous** les détecteurs (plus seulement StopDetector)

#### Corrections UI onglet Accueil
**Fichier**: `interface/onglet_acceuil.py`
- 12 erreurs CSS `}}` corrigées
- Bug `getElementById('camBtn')` → `getElementById('cameraToggleBtn')`
- Remplacement des `ontouchstart` inline par `addEventListener(..., {passive: true})`
- Ajout de hooks d'erreur globaux, état `CAMERA_ACTIVE`, binding `DOMContentLoaded`
- Compatibilité ES5

---

### 📦 Fichiers Modifiés

**Nouveaux fichiers / dossiers**:
- `core/vision/detectors/models/` — Dossier centralisé pour les modèles .xml Haar

**Fichiers modifiés**:
- `core/vision/detectors/Haar_classifier.py`: Réécriture complète (HaarStopDetector → HaarClassifier générique)
- `core/vision/detectors/Stop_detector_zumi.py`: Modernisation format + `diagnostique_detecteur()`
- `interface/onglet_vision.py`: Consolidation JS diagnostic
- `interface/flask_router.py`: Suppression route `/diagnose_stop`
- `interface/server_controller.py`: Suppression méthode `diagnose_stop()` + import `itertools`
- `interface/onglet_acceuil.py`: Corrections CSS/JS multiples
- `main.py`: Import `StopDetectorZumi`, `MODELS_DIR`, chemin absolu pour modèles

**Compatibilité**:
- ✅ Python 3.5.3 (`.format()` partout, pas de f-strings)
- ✅ Format de sortie unifié sur tous les détecteurs
- ✅ Route `/diagnose_detector` gère tous les détecteurs de manière générique

---

### 📦 Fichiers Modifiés (Branche précédente)

**Nouveaux fichiers**:
- `core/camera/zumi_camera.py`
- `core/vision/detectors/Stop_detector_cv.py`
- `core/vision/detectors/Stop_detector_matt.py`
- `core/vision/detectors/hsv_matt.py` (prototype)
- `core/vision/detectors/hsv_mattv2.py` (prototype)

**Fichiers modifiés**:
- `interface/server_controller.py`: Routes diagnostic + format helper
- `interface/onglet_vision.py`: Restructuration UI complète
- `interface/flask_router.py`: Nouvelles routes `/diagnose_detector`
- `core/vision/vision_pipeline.py`: Méthode `get_current_detector_diagnostic()`
- `core/robot/robot_zumi.py`: Import `ZumiCamera` au lieu de `Camera` direct

**Compatibilité**:
- ✅ Aucune breaking change sur API existante
- ✅ Backward compatible avec détecteurs existants (Line, Luminosity, etc.)
- ✅ Format BGR maintenu partout (convention OpenCV)

---

### 🚀 Prochaines Étapes

**Court terme**:
- Tests additionnels en conditions réelles variées
- Tuning paramètres HSV selon environnement déploiement
- Documentation utilisateur pour UI diagnostic

**Moyen terme**:
- Dataset d'images annotées pour validation quantitative
- Métriques précision/rappel comparatif entre détecteurs
- Optimisation performances (profilage CPU)

**Long terme**:
- Support détection multi-objets simultanés
- Recording vidéo avec timestamps détection
- Intégration modèle CNN


