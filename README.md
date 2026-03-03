# PFE — Véhicule Autonome Miniature Zumi

> **Projet de fin d'études** — École de technologie supérieure (ÉTS), Département de génie de la production automatisée  
> **Session** : Hiver 2026 — GPA 793  
> **Équipe** : 4 étudiants

---

## 1. Description du projet

Ce projet s'inscrit dans la continuité d'un PFE multi-session dont l'objectif est de concevoir un véhicule autonome miniature à partir du robot éducatif **Zumi** (Robolink). Le robot doit être capable de naviguer de façon autonome dans un environnement contrôlé en exploitant des algorithmes de vision artificielle embarqués.

### Objectifs de la session courante

| # | Objectif | État |
|---|----------|------|
| 1 | **Modularisation** — Refactoriser le code monolithique de l'équipe précédente en une architecture modulaire, testable et extensible. | Complété |
| 2 | **Vision artificielle** — Implémenter et comparer plusieurs détecteurs d'objets (HSV, Haar/LBP cascades) pour la signalisation routière. | En cours |
| 3 | **Interface opérateur** — Fournir un serveur web Flask embarqué pour le contrôle du robot, le live feed caméra et le diagnostic de détection. | Complété |
| 4 | **Entraînement de modèles** — Développer un pipeline automatisé d'entraînement de cascades Haar/LBP (PC-side) avec évaluation et hard negative mining. | Complété |
| 5 | **Continuité** — Poursuivre l'amélioration du projet en s'appuyant sur les travaux des équipes précédentes. | En cours |

### Contraintes principales

- Le robot embarque un **Raspberry Pi Zero W** (voir section [Matériel](#3-matériel)). Toute logique de traitement temps réel doit tenir dans ses limites de calcul.
- La caméra fournit un flux **480p maximum**. Les modèles de détection doivent être optimisés pour cette résolution.
- Le code embarqué doit être compatible **Python 3.5.3** (pas de f-strings, encodage UTF-8 forcé).
- L'entraînement des modèles Haar/LBP s'effectue sur un **PC hôte** (Python 3.8+, OpenCV 3.4+). Seul le fichier `.xml` résultant est déployé sur le robot.

---

## 2. Architecture logicielle

```
PFE/
├── main.py                          # Point d'entrée principal (robot)
├── zumi_prepare.sh                  # Script de préparation du Zumi (arrêt services de base)
├── README.md
├── CHANGELOG.md                     # Historique des modifications
├── TODO.md
│
├── core/                            # Couche métier embarquée
│   ├── camera/
│   │   ├── __init__.py
│   │   ├── camera_base.py           # Interface abstraite caméra
│   │   ├── picam2.py                # Driver PiCamera2 (Raspberry Pi)
│   │   └── zumi_camera.py           # Wrapper Zumi (RGB → BGR)
│   │
│   ├── robot/
│   │   ├── __init__.py
│   │   ├── robot_base.py            # Interface abstraite robot
│   │   ├── robot_zumi.py            # Implémentation Zumi (moteurs, capteurs)
│   │   └── Archive/                 # Code legacy conservé pour référence
│   │       ├── Programme_UI.py
│   │       └── Zumi_mock/
│   │           └── SimZumi.py
│   │
│   └── vision/
│       ├── vision_pipeline.py       # Orchestrateur : capture → détection → résultats
│       └── detectors/
│           ├── detector_base.py     # Classe de base pour tous les détecteurs
│           ├── Line_detector.py     # Détecteur de lignes
│           ├── Luminosity.py        # Détecteur de luminosité
│           ├── Stop_detector_zumi.py    # Détecteur Zumi natif (ground truth)
│           ├── Stop_detector_cv.py      # Détecteur HSV conventionnel
│           ├── Stop_detector_matt.py    # Détecteur HSV avancé (score composite)
│           ├── Haar_classifier.py       # Classificateur Haar/LBP multi-modèles
│           └── models/              # Fichiers .xml des cascades entraînées
│               ├── stop_sign_classifier_2.xml
│               ├── LBP_Alpha_Prime.xml
│               ├── LBP_Alpha.xml
│               ├── HAAR_2026-02-19.xml
│               ├── haar1pieton.xml
│               └── pedestrian_classifier.xml
│
├── interface/                       # Serveur Flask (UI opérateur)
│   ├── _init_.py
│   ├── flask_router.py              # Déclaration des routes
│   ├── server_controller.py         # Logique backend (endpoints REST)
│   ├── run_server.py                # Lanceur du serveur
│   ├── mock_zumi.py                 # Mock pour développement hors-robot
│   ├── onglet_acceuil.py            # Onglet Accueil (contrôle moteur, exit)
│   ├── onglet_vision.py             # Onglet Vision (live feed, détection, diagnostic)
│   └── onglet_template.py           # Template de base pour les onglets
│
├── Haar_Classifier_model_trainer/   # Pipeline d'entraînement (PC-side)
│   ├── train_cascade.py             # Point d'entrée — menu interactif (9 options)
│   ├── positive_image_downloader.py # Utilitaire de téléchargement d'images
│   ├── requirements.txt             # Dépendances Python
│   ├── README.md                    # Documentation complète du module
│   ├── cascade/                     # Package principal (logique métier)
│   │   ├── __init__.py              # API publique + exports
│   │   ├── config.py                # Constantes et préconfigurations
│   │   ├── environment.py           # Validation de l'environnement
│   │   ├── data_prep.py             # Préparation données (split, augmentation, filtrage)
│   │   ├── training.py              # Entraînement (samples .vec, cascade, XML)
│   │   ├── evaluation.py            # Évaluation (métriques, plaque modèle)
│   │   ├── mining.py                # Hard Negative Mining (simple + itératif)
│   │   └── analysis/                # Analyse avancée du modèle
│   │       ├── __init__.py          # Orchestrateur (7 phases)
│   │       ├── utils.py
│   │       ├── stages.py            # Évaluation par stage, mosaïque FN/TP
│   │       ├── charts.py            # Courbes PR/ROC, graphiques
│   │       ├── sweep.py             # Sweep scaleFactor × minNeighbors
│   │       └── data_quality.py      # Qualité des données, fenêtre optimale
│   ├── data/                        # Données d'entraînement
│   │   ├── positive/                # Images positives (fournies par l'utilisateur)
│   │   ├── negative/                # Images négatives
│   │   ├── train/                   # Split entraînement (généré)
│   │   ├── test/                    # Split test (généré)
│   │   ├── augmented/               # Images augmentées (généré)
│   │   ├── hard_negatives/          # Hard negatives extraits
│   │   ├── filtered_too_small/      # Images positives filtrées (trop petites)
│   │   └── cascade/                 # Modèle final (.xml + stages)
│   ├── Incubator/                   # Archive des modèles entraînés (.xml + plaques .md)
│   └── new positive/ | new negative/  # Images sources brutes
│
└── Doc/                             # Documentation interne
    ├── AIDE_MEMOIRE_GIT.md
    ├── GUIDE_GIT.md
    ├── GUIDE_GIT.pdf
    ├── Workflow_GIT.md
    ├── Procédure serveur flask.md
    └── Procédure test zumi.md
```

### Principes d'architecture

| Principe | Application |
|----------|-------------|
| **Abstraction matérielle** | Les interfaces `camera_base` et `robot_base` découplent le matériel du reste du système. Un changement de caméra ou de plateforme robot n'impacte pas la logique applicative. |
| **Pipeline de vision modulaire** | `vision_pipeline.py` orchestre la capture et la détection sans connaître les détecteurs spécifiques. Chaque détecteur hérite de `detector_base` et peut être ajouté ou retiré sans modifier le pipeline. |
| **Séparation entraînement / déploiement** | L'entraînement des cascades s'exécute sur PC (`Haar_Classifier_model_trainer/`). Seul l'artefact `.xml` est déployé sur le robot. |
| **Interface opérateur découplée** | Le serveur Flask communique avec le pipeline de vision via une API Python interne, sans dépendance directe au matériel. |

---

## 3. Matériel

### Raspberry Pi Zero W (V1)

Le robot Zumi embarque un **Raspberry Pi Zero W** (première génération). Les spécifications sont les suivantes :

| Caractéristique | Valeur |
|-----------------|--------|
| **SoC** | Broadcom BCM2835 |
| **CPU** | ARM1176JZF-S (ARM11) — 1 cœur, 32-bit, 1 GHz |
| **GPU** | VideoCore IV — 250 MHz |
| **RAM** | 512 Mo (partagée CPU/GPU) |
| **Stockage** | Carte microSD |
| **Connectivité** | Wi-Fi 802.11 b/g/n 2.4 GHz, Bluetooth 4.1/BLE |
| **Ports** | Mini HDMI, Micro USB OTG, Micro USB (alimentation) |
| **GPIO** | 40 broches (non soudées) |
| **Caméra** | Connecteur CSI (v1.3+) |
| **OS** | Raspbian (Debian) — Python 3.5.3 |
| **Dimensions** | 65 mm × 30 mm × 5 mm |
| **Alimentation** | 5 V / 1.2 A via Micro USB |

> **Implications sur le développement :**
> - **CPU monocœur 32-bit** — Les algorithmes de vision doivent être légers. Les cascades Haar/LBP sont privilégiées car elles s'exécutent sur CPU sans nécessiter de GPU dédié ou d'accélérateur IA.
> - **512 Mo de RAM partagée** — Le budget mémoire est serré. Les images sont traitées une par une (pas de batch). Le serveur Flask doit rester minimal.
> - **Python 3.5.3** — Pas de f-strings, pas de `dataclasses`, pas de `typing` avancé. Encodage UTF-8 forcé via `# -*- coding: utf-8 -*-`.
> - **Pas de support Vulkan/OpenCL** — Pas d'accélération GPU pour le traitement d'images. OpenCV software-only.

### Robot Zumi (Robolink)

| Caractéristique | Valeur |
|-----------------|--------|
| **Constructeur** | Robolink Inc. |
| **Plateforme** | Raspberry Pi Zero W |
| **Caméra** | Pixy-like camera, flux 480p max |
| **Moteurs** | 2× moteurs DC (différentiel) |
| **Capteurs** | IR frontaux et arrière, accéléromètre, gyroscope |
| **Alimentation** | Batterie LiPo rechargeable |
| **Réseau** | Wi-Fi access point (SSID = nom du robot, mot de passe = SSID) |
| **Dashboard** | `http://zumidashboard.ai/` (interface web d'origine) |
| **API Python** | [Documentation Robolink](https://docs.robolink.com/docs/Zumi/Python/Function-Documentation) |

---

## 4. Démarrage rapide

### Prérequis

- Accès Wi-Fi au réseau du Zumi (SSID connu : `zumi3257`, `zumi4585`)
- Client SSH (PuTTY, OpenSSH, etc.)
- Python 3.8+ sur le PC de développement (pour l'entraînement des modèles)

### Connexion SSH au robot

```bash
# 1. Se connecter au Wi-Fi du Zumi (mot de passe = SSID)

# 2. Ouvrir un terminal et se connecter en SSH
ssh pi@192.168.10.1
# Mot de passe : pi

# 3. Préparer le robot (arrêter les services de base)
bash zumi_prepare.sh

# 4. Lancer le programme principal
python main.py
```

Le serveur Flask sera accessible à l'adresse affichée dans le terminal (ex. `http://192.168.10.1:5000/`).

### Entraînement d'un modèle (PC-side)

```bash
cd Haar_Classifier_model_trainer

# Installer les dépendances
pip install -r requirements.txt

# Lancer le menu interactif
python train_cascade.py
```

Voir [Haar_Classifier_model_trainer/README.md](Haar_Classifier_model_trainer/README.md) pour la documentation complète du module d'entraînement.

---

## 5. Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Historique détaillé des modifications par branche |
| [Haar_Classifier_model_trainer/README.md](Haar_Classifier_model_trainer/README.md) | Guide complet du pipeline d'entraînement Haar/LBP |
| [Doc/GUIDE_GIT.md](Doc/GUIDE_GIT.md) | Guide Git pour les membres de l'équipe |
| [Doc/AIDE_MEMOIRE_GIT.md](Doc/AIDE_MEMOIRE_GIT.md) | Aide-mémoire Git (référence rapide) |
| [Doc/Workflow_GIT.md](Doc/Workflow_GIT.md) | Workflow de branches Git pour le projet |
| [Doc/Procédure serveur flask.md](Doc/Proc%C3%A9dure%20serveur%20flask.md) | Procédure de déploiement du serveur Flask |
| [Doc/Procédure test zumi.md](Doc/Proc%C3%A9dure%20test%20zumi.md) | Procédure de test sur le robot Zumi |

---

## 6. Dépôt Git

```bash
# Cloner le projet
git clone https://github.com/Sympoziium/PFE.git
cd PFE

# Créer une branche de travail
git checkout -b feature/ma-fonctionnalite

# Pousser les modifications
git add .
git commit -m "Description des modifications"
git push -u origin feature/ma-fonctionnalite
```

Consulter [Doc/GUIDE_GIT.md](Doc/GUIDE_GIT.md) et [Doc/Workflow_GIT.md](Doc/Workflow_GIT.md) pour les conventions de branchement et le workflow collaboratif.

---

## 7. Licence

Projet académique — ÉTS, Département de génie de la production automatisée.


