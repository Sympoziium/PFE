# PFE — Véhicule Autonome Miniature Zumi

> **Projet de fin d'études** — École de technologie supérieure (ÉTS), Département de génie de la production automatisée
> **Session** : Hiver 2026 — GPA 793
> **Équipe** : Cédric Senécal ; François Gagné ; Olivier Poitras ; Alycia-Rose Sévigny

---

## 1. Description du projet

Ce projet s'inscrit dans la continuité d'un PFE multi-session dont l'objectif est de concevoir un véhicule autonome miniature à partir du robot éducatif **Zumi** (Robolink). Nos pricipaux objectifs sont des contributions logicielles le but étant de s'affranchir de l'environnement de développement propriétaire de Robolink pour créer une plateforme logicielle flexible, modulaire et extensible, compatible avec les futures évolutions matérielles du robot. Nous souhaitons également explorer l'implantation de différents algorithmes d'apprentissage machine (ML) afin de comparer leur efficacité dans le contexte de la conduite autonome sur un robot à ressources limitées.

### Objectifs de la session courante

| # | Objectif | État |
|---|----------|------|
| 1 | **Migration matérielle** — Migrer du Pi Zero W (V1) au Pi Zero 2W (V2) : OS Bookworm 64-bit, Python 3.11, compatibilité SDK Zumi, drivers OLED et caméra. | Complété |
| 2 | **Modularisation** — Refactoriser le code monolithique en architecture modulaire (pattern Strategy) avec contrôleurs interchangeables et DTOs standardisés. | Complété |
| 3 | **Vision artificielle** — Implémenter et valider les détecteurs d'objets (HSV, Haar/LBP cascades) pour la signalisation routière, avec estimation de distance. | Complété |
| 4 | **Interface opérateur** — Serveur web Flask embarqué : contrôle du robot, live feed caméra, diagnostic de détection, réglage PID et collecte de données. | Complété |
| 5 | **Entraînement Haar/LBP** — Pipeline automatisé d'entraînement de cascades avec évaluation, hard negative mining et hard positive mining. | Complété |
| 6 | **Contrôle par apprentissage** — Contrôleur MLP avec pipeline PyTorch complet (entraînement, normalisation z-score, conversion TFLite, déploiement embarqué). | Complété |
| 7 | **Réseau AP+STA** — Point d'accès Wi-Fi permanent + connexion station simultanée via interface virtuelle sur puce unique. | Complété |
| 8 | **Continuité** — Documentation complète, transfert de connaissances et préparation pour les sessions futures. | Complété |

---

## 2. Architecture logicielle

![Architecture du module de contrôle v2](control_module_architecture_v2.svg)
*Aperçu du module de contrôle (v2) réécrit en utilisant le pattern Strategy pour garantir isolation et flexibilité.*

```
PFE/
├── main.py                          # Point d'entrée principal (robot)
├── README.md
├── CHANGELOG.md                     # Historique des modifications
├── ARCHITECTURE_CONTROLE.md         # Documentation architecture du module de contrôle
├── MIGRATION_NOTES.md               # Journal de migration Pi Zero W → Pi Zero 2W
├── requirements-robot.txt           # Dépendances Python (robot)
│
├── script/                          # Scripts système embarqués
│   ├── zumi_ap_setup.sh             # Configuration initiale du profil AP (une seule fois)
│   ├── zumi_ap_sta_start.sh         # Démarrage AP+STA au boot (appelé par systemd)
│   ├── zumi_wifi_config.sh          # Configuration interactive de la connexion STA
│   ├── setup_dns_rpi.sh             # Configuration DNS du Raspberry Pi
│   ├── zumi-ap.service              # Service systemd pour le point d'accès
│   └── zumi_prepare.sh              # [DEPRECATED — V1 uniquement]
│
├── core/                            # Couche métier embarquée
│   ├── camera/
│   │   ├── camera_base.py           # Interface abstraite caméra
│   │   ├── picam2.py                # Driver PiCamera2 (Raspberry Pi)
│   │   └── zumi_camera.py           # Wrapper Zumi (RGB → BGR)
│   │
│   ├── control/
│   │   ├── control_manager.py       # Orchestrateur pluggable des contrôleurs
│   │   ├── controlers/              # Implémentations concrètes (pattern Strategy)
│   │   │   ├── controller_base.py   # Interface abstraite contrôleur (ABC)
│   │   │   ├── manual_controller.py # Contrôle manuel (joystick)
│   │   │   ├── ml_controller.py     # Contrôleur prédictif MLP (TFLite)
│   │   │   ├── pid_ir_controller.py # Contrôleur PID par capteurs infrarouges
│   │   │   └── models/              # Modèles TFLite + stats de normalisation
│   │   ├── IO_drivers/              # Couche traductrice robotique/framework (DTOs)
│   │   │   ├── motor_command.py
│   │   │   ├── motor_driver.py
│   │   │   ├── sensor_driver.py
│   │   │   └── sensor_state.py
│   │   └── legacy/                  # Anciennes implémentations retirées
│   │
│   ├── hardware/
│   │   ├── boot.py                  # Handshake Pi ↔ ATmega (patch compatibilité V2)
│   │   ├── personality.py           # Expressions et personnalité du robot
│   │   ├── screen.py                # Driver OLED (luma.oled — remplace Adafruit_SSD1306)
│   │   └── postbootup.service       # Service systemd handshake (V2)
│   │
│   ├── robot/
│   │   ├── robot_base.py            # Interface abstraite robot
│   │   ├── robot_zumi.py            # Implémentation Zumi (moteurs, capteurs)
│   │   └── Archive/                 # Code legacy conservé pour référence
│   │
│   └── vision/
│       ├── vision_adapter.py        # Vectorisateur numérique (inférences ML)
│       ├── vision_pipeline.py       # Orchestrateur : capture → détection → résultats
│       └── detectors/
│           ├── detector_base.py     # Classe de base pour tous les détecteurs
│           ├── Line_detector.py     # Détecteur de lignes
│           ├── Luminosity.py        # Détecteur de luminosité
│           ├── Stop_detector_zumi.py
│           ├── Stop_detector_cv.py
│           ├── Stop_detector_matt.py
│           ├── Haar_classifier.py
│           └── models/              # Fichiers .xml des cascades entraînées
│
├── interface/                       # Serveur Flask (UI opérateur)
│   ├── flask_router.py
│   ├── server_controller.py
│   ├── run_server.py
│   ├── mock_zumi.py
│   ├── onglet_acceuil.py
│   ├── onglet_control.py
│   ├── onglet_pid.py
│   ├── onglet_vision.py
│   └── onglet_template.py
│
├── Haar_Classifier_model_trainer/   # Pipeline d'entraînement Haar/LBP (PC-side)
│   └── ...                          # Voir Haar_Classifier_model_trainer/README.md
│
├── MLP_model_trainer/               # Pipeline d'entraînement MLP PyTorch (PC-side)
│   ├── sequences/                   # Séquences de conduite (captures.jsonl + labels.jsonl)
│   ├── checkpoints/                 # Modèles sauvegardés (.pt)
│   ├── export/                      # Modèles convertis (.onnx, .tflite)
│   ├── dataset.py                   # Chargement JSONL → PyTorch DataLoader
│   ├── model.py                     # Architecture MLP (Small/Medium/Large)
│   ├── train.py                     # Script d'entraînement interactif avec validation
│   ├── convert_to_tflite.py         # Conversion PyTorch → ONNX → TFLite
│   ├── validate_env.py              # Validation de l'environnement d'entraînement
│   ├── aggregate_sequences.py       # Agrégation des séquences de conduite
│   ├── analyze_dataset.py           # Analyse statistique du dataset
│   ├── requirements.txt             # Dépendances Python
│   ├── GUIDE_UTILISATION.md         # Guide d'utilisation complet
│   └── TUTORIAL_MLP_PYTORCH.md      # Tutoriel complet PyTorch/MLP
│
├── Pont/                            # Code Arduino pour le pont (ATmega)
│   └── Pont.ino
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
| **Couche de contrôle pluggable** | Le dossier `core/control/` utilise le pattern Strategy : chaque contrôleur hérite de `ControllerBase` et implémente `step(SensorState) → MotorCommand`. Le `ControlManager` orchestre le cycle lecture → inférence → exécution sans connaître les détails des contrôleurs. |
| **Pipeline de vision modulaire** | `vision_pipeline.py` orchestre la capture et la détection sans connaître les détecteurs spécifiques. Chaque détecteur hérite de `detector_base` et peut être ajouté ou retiré sans modifier le pipeline. |
| **Séparation entraînement / déploiement** | L'entraînement des modèles s'exécute sur PC (`Haar_Classifier_model_trainer/` pour les cascades, `MLP_model_trainer/` pour les réseaux de neurones). Seuls les artefacts (`.xml`, `.tflite`) sont déployés sur le robot. |
| **Interface opérateur découplée** | Le serveur Flask communique avec le pipeline de vision via une API Python interne, sans dépendance directe au matériel. |

---

## 3. Matériel

> **Note — Session Hiver 2026**
> La migration du Pi Zero W (V1) vers le Pi Zero 2W (V2) est **complétée**. Le V2 est désormais la plateforme active.
> La section V1 ci-dessous est conservée pour référence. Voir `MIGRATION_NOTES.md` pour le journal complet de la migration.

### Pi Zero W — V1 (configuration originale Robolink)

| Caractéristique | Valeur |
|-----------------|--------|
| **SoC** | Broadcom BCM2835 |
| **CPU** | ARM1176JZF-S (ARM11) — 1 cœur, 32-bit, 1 GHz |
| **RAM** | 512 Mo (partagée CPU/GPU) |
| **OS** | Raspbian (Debian) — Python 3.5.3 |
| **Réseau** | AP natif Zumi — `ssh pi@192.168.10.1` |
| **Alimentation** | 5 V / 1.2 A via Micro USB |

> **Contraintes V1 :** CPU monocœur 32-bit — algorithmes de vision légers obligatoires. Python 3.5.3 — pas de f-strings, encodage UTF-8 forcé (`# -*- coding: utf-8 -*-`).

### Pi Zero 2W — V2 (nouvelle configuration)

| Caractéristique | Valeur |
|-----------------|--------|
| **SoC** | Broadcom BCM2710A1 |
| **CPU** | Cortex-A53 — 4 cœurs, 64-bit, 1 GHz |
| **RAM** | 512 Mo |
| **OS** | Raspberry Pi OS Lite 64-bit (Bookworm) — Python 3.11.2 |
| **Réseau** | AP+STA simultané — `ssh pi@192.168.0.1` (voir section 4.2) |
| **Alimentation** | 5 V / 2.5 A via Micro USB (alimentation externe recommandée) |

> **Avantages V2 :** quad-core 64-bit — résolution caméra augmentée (HD), framerate jusqu'à 60 fps. Environnement Python moderne (3.11) dans venv isolé.

### Robot Zumi (Robolink) — commun aux deux configurations

| Caractéristique | Valeur |
|-----------------|--------|
| **Constructeur** | Robolink Inc. |
| **Caméra** | Pixy-like camera, flux 480p (V1) / HD (V2) |
| **Moteurs** | 2× moteurs DC (différentiel) |
| **Capteurs** | IR frontaux et arrière, accéléromètre, gyroscope |
| **Alimentation** | Batterie LiPo rechargeable (V2 : alimentation USB externe requise) |
| **API Python** | [Documentation Robolink](https://docs.robolink.com/docs/Zumi/Python/Function-Documentation) |

---

## 4. Démarrage rapide

### 4.1 — Pi Zero W V1 (configuration Robolink originale)

> ⚠️ `zumi_prepare.sh` est **deprecated** et réservé au V1. Ne pas utiliser sur le V2.

```bash
# 1. Se connecter au Wi-Fi natif du Zumi (mot de passe = SSID)
#    SSID connus : zumi3257, zumi4585

# 2. Connexion SSH
ssh pi@192.168.10.1
# Mot de passe : pi

# 3. Arrêter les services Robolink et connecter au Wi-Fi de développement
sudo ~/PFE/zumi_prepare.sh full

# 4. Se reconnecter via l'IP Wi-Fi affichée par le script, puis lancer le programme
cd ~/PFE
python3 main.py
```

### 4.2 — Pi Zero 2W V2 (nouvelle configuration)

Le V2 démarre automatiquement en mode **AP+STA simultané** via le service `zumi-ap.service`.

**Connexion permanente via l'AP du robot (recommandé) :**

```bash
# 1. Se connecter au Wi-Fi du robot
#    SSID     : zumi-robot
#    Password : zumirobot

# 2. Connexion SSH via l'AP (toujours disponible, même sans réseau externe)
ssh pi@192.168.0.1
# Mot de passe : pi

# 3. Activer l'environnement virtuel (automatique si .bashrc configuré)
source ~/venv/bin/activate

# 4. Lancer le programme principal
cd ~/PFE
python3 main.py
```

**Connexion au réseau externe (STA) — pour git pull et accès Internet :**

```bash
# Configurer la connexion STA (à faire une seule fois, ou après changement de réseau)
sudo ~/PFE/script/zumi_wifi_config.sh
# Le script demande le SSID et le mot de passe du réseau cible.
# La connexion est persistée dans NetworkManager et s'active automatiquement au boot.
```

**Vérification de l'état réseau :**

```bash
ip addr show wlan0   # Interface STA — IP dynamique si connecté au réseau externe
ip addr show wlan1   # Interface AP  — 192.168.0.1 (toujours présente)
```

### 4.3 — Entraînement d'un modèle (PC-side, commun V1/V2)

```bash
cd Haar_Classifier_model_trainer

# Installer les dépendances
pip install -r requirements.txt

# Lancer le menu interactif
python train_cascade.py
```

Voir [Haar_Classifier_model_trainer/README.md](Haar_Classifier_model_trainer/README.md) pour la documentation complète.

### 4.4 — Entraînement d'un modèle MLP (PC-side)

```bash
cd MLP_model_trainer

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'entraînement (100 epochs, modèle medium)
python train.py --epochs 100 --model-size medium

# Convertir vers TFLite pour déploiement sur Pi
python convert_to_tflite.py --quantize

# Déployer sur le robot
scp export/zumi_mlp_quant.tflite pi@192.168.0.1:~/PFE/core/control/controlers/models/
```

Voir [MLP_model_trainer/TUTORIAL_MLP_PYTORCH.md](MLP_model_trainer/TUTORIAL_MLP_PYTORCH.md) pour le tutoriel complet.

---

## 5. Gestion des branches

La migration V1 → V2 est complétée. La branche `main` est désormais la référence pour le Pi Zero 2W.

| Branche | Description |
|---------|-------------|
| `main` | Branche stable — plateforme V2 (Pi Zero 2W, Bookworm 64-bit) |
| `feature/*` | Développement de nouvelles fonctionnalités — partir de `main` |

```bash
# Démarrage d'une nouvelle feature
git checkout main
git checkout -b feature/ma-fonctionnalite
git push -u origin feature/ma-fonctionnalite
```

Consulter [Doc/GUIDE_GIT.md](Doc/GUIDE_GIT.md) et [Doc/Workflow_GIT.md](Doc/Workflow_GIT.md) pour les conventions complètes.

---

## 6. Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Historique détaillé des modifications par branche |
| [ARCHITECTURE_CONTROLE.md](ARCHITECTURE_CONTROLE.md) | Architecture détaillée du module de contrôle (pattern Strategy) |
| [MIGRATION_NOTES.md](MIGRATION_NOTES.md) | Journal complet de la migration Pi Zero W → Pi Zero 2W |
| [Haar_Classifier_model_trainer/README.md](Haar_Classifier_model_trainer/README.md) | Guide complet du pipeline d'entraînement Haar/LBP |
| [MLP_model_trainer/GUIDE_UTILISATION.md](MLP_model_trainer/GUIDE_UTILISATION.md) | Guide d'utilisation du pipeline MLP |
| [MLP_model_trainer/TUTORIAL_MLP_PYTORCH.md](MLP_model_trainer/TUTORIAL_MLP_PYTORCH.md) | Tutoriel complet : MLP avec PyTorch et déploiement TFLite |
| [core/control/controlers/PID_IR_TUNING.md](core/control/controlers/PID_IR_TUNING.md) | Guide de réglage du contrôleur PID infrarouge |
| [Doc/GUIDE_GIT.md](Doc/GUIDE_GIT.md) | Guide Git pour les membres de l'équipe |
| [Doc/AIDE_MEMOIRE_GIT.md](Doc/AIDE_MEMOIRE_GIT.md) | Aide-mémoire Git (référence rapide) |
| [Doc/Workflow_GIT.md](Doc/Workflow_GIT.md) | Workflow de branches Git pour le projet |
| [Doc/Procédure serveur flask.md](Doc/Proc%C3%A9dure%20serveur%20flask.md) | Procédure de déploiement du serveur Flask |
| [Doc/Procédure test zumi.md](Doc/Proc%C3%A9dure%20test%20zumi.md) | Procédure de test sur le robot Zumi |

---

## 7. Licence

Projet académique — ÉTS, Département de génie de la production automatisée.
