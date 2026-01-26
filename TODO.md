# TODO List

poursuivre le développement de l'onglet acceuil. tu doit repomper les features général du programme original et les ajouter.
par exemple on veux pouvoir regarder le livefeed en ayant les boutons de contrôle du robot.

le robot ne supporte vraiment pas les accents, donc fait tout en UTF-8 


- ajouter un bouton exit pour bien fermer le thread du serveur sur la page d'acceuil

- Eventuellement il faudrais peutetre migrer le serveur flask sur pc et rendre le robot le client. sa devrais liberer des ressources du cpu du robot.

schema ideal
```
┌───────────────┐
│   Flask UI    │   ← télécommande
└───────┬───────┘
        │ HTTP
┌───────▼───────┐
│  Controlleur  │   ← logique
└───────┬───────┘
        │ API Python
┌───────▼────────┐
│ Vision Pipeline │
└───────┬────────┘
        │
┌───────▼───────┐
│    Camera     │
└───────────────┘
```


structure du projet modulaire
```
PFE/
│
├── core/
│   ├── camera/
│   │   ├── camera_base.py
│   │   └── picam2_camera.py
│   │   
│   │
│   ├── vision/
│   │   ├── detector/
|   │   │   ├── detector_base.py
|   │   │   ├── Line_detector.py
|   │   │   └── Luminosité.py
│   │   └── vision_pipeline.py
│   │
│   └── robot/ # Todo
│       ├── robot_base.py
│       ├── zumi_robot.py
│       └── sim_robot.py
│
├── interface/
│   └── flask_server.py
│
└── main.py

```