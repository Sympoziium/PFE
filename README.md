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
│   │   └── picam2.py
│   │
│   ├── robot/
│   │   ├── Archive/
│   │   ├── __init__.py
│   │   ├── robot_base.py
│   │   └── robot_zumi.py
│   │
│   └── vision/
│       ├── detectors/
│       │   ├── detector_base.py
│       │   ├── Line_detector.py
│       │   ├── Luminosity.py
│       │   └── Stop_detector_zumi.py
│       ├── Objectif.md
│       └── vision_pipeline.py
│
├── interface/
│   ├── flask_router.py
│   ├── onglet_acceuil.py
│   ├── onglet_template.py
│   ├── onglet_vision.py
│   └── server_controller.py
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