# TODO List

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
│   │   ├── picam2_camera.py
│   │   └── mock_camera.py
│   │
│   ├── vision/
│   │   └── vision_pipeline.py
│   │
│   └── robot/
│       ├── robot_base.py
│       ├── zumi_robot.py
│       └── sim_robot.py
│
├── interface/
│   └── flask_server.py
│
└── main.py

```