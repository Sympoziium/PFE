# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

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
