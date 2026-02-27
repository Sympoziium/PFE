# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

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
