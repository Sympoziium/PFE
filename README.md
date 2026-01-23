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
    SSID connu: `zumi3257`

2. se connecter sur dans un browser chrome a `http://zumidashboard.ai/`
    on veut aller chercher l'adresse ip du robot qui se trouve dans les settings lorsque connecté.
    adresse ip connue : `10.192.181.46`

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
│   │   ├── camera_base.py        # Abstraction caméra
│   │   └── picam2_camera.py      # Implémentation PiCamera (Picam2)
│   │   
│   ├── vision/
│   │   ├── detector/
│   │   │   ├── detector_base.py  # Interface des détecteurs
│   │   │   ├── line_detector.py
│   │   │   └── luminosite.py
│   │   └── vision_pipeline.py    # Orchestration du pipeline de vision
│   │
│   └── robot/                    # À implémenter
│       ├── robot_base.py
│       ├── zumi_robot.py
│       └── sim_robot.py
│
├── interface/
│   └── flask_server.py            # Interface opérateur (serveur Flask)
│
└── main.py                        # Point d’entrée du programme

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

