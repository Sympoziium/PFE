# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).



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
