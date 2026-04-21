# Architecture — Refonte du module de contrôle moteur

**Branche** : `MLP-ctrl-module`  
**Date** : 2026-03-08  
**Objectif** : Standardiser les entrées, les sorties et l'interface des contrôleurs pour permettre l'ajout de contrôleurs multiples (PID, StateMachine, MLP, RL, …) via un manager pluggable.

---

## 1. Diagnostic de l'architecture actuelle

### 1.1 Problèmes identifiés

| # | Problème | Impact |
|---|----------|--------|
| 1 | `ControllerBase` est vide et inutilisé — aucun contrôleur n'en hérite | Pas d'interface commune, impossible de traiter les contrôleurs de façon polymorphe |
| 2 | `PIDController` n'est pas un contrôleur mais un **algorithme PID** — il calcule des corrections à partir d'une erreur scalaire, il ne sait rien du robot ni de la caméra | Confusion de responsabilité, difficile à remplacer par un MLP sans tout réécrire |
| 3 | `ControlManager` est **hard-codé** — chaque nouveau mode exige un nouveau `MODE_*`, une nouvelle méthode `register_*`, un nouveau `_tick_*` | Violation du principe ouvert/fermé, frein à l'extensibilité |
| 4 | Pas de standardisation des entrées — chaque contrôleur accède directement au `VisionPipeline` et/ou au robot pour lire ses capteurs | Duplication de code, couplage fort |
| 5 | Pas de standardisation des sorties — le PID retourne `(left, right)`, les state machines appellent `robot.control_motors()` et `robot.turn()` directement | Impossible de logger, filtrer ou simuler les commandes uniformément |
| 6 | Couplage fort entre `server_controller.py` et les classes de contrôle — le Flask connait les détails internes du PID et des state machines | Fragile, chaque changement de contrôle casse les routes |

### 1.2 Flux actuel (simplifié)

```
server_controller ──► ControlManager ──► PIDController.compute(error)
                                    ──► LineFollowingStateMachine.step(frame)
                                    ──► StepByStepStateMachine.step(frame)
                                             │
                                             ▼
                                     robot.control_motors() / robot.turn()
                                     (appels directs éparpillés)
```

Chaque contrôleur fait sa propre cuisine pour lire les capteurs et commander les moteurs.

---

## 2. Architecture proposée

### 2.1 Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                     server_controller                         │
│               (Flask — interface opérateur)                    │
│   set_active("pid") / set_active("ml") / get_status()        │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                     ControlManager                            │
│                 (registre pluggable)                           │
│                                                               │
│  register(controller)     Ajoute un contrôleur au registre    │
│  set_active(name)         Active un contrôleur par son nom    │
│  deactivate()             Désactive le contrôleur courant     │
│  list_controllers()       Liste les noms enregistrés          │
│  tick()                   Un cycle : read → step → execute    │
│  get_status()             État courant pour le monitoring      │
│                                                               │
│  Boucle :  state = sensor_driver.read()                       │
│            cmd   = active_controller.step(state)              │
│            motor_driver.execute(cmd)                          │
└──────┬────────────────┬──────────────────────┬───────────────┘
       │                │                      │
       ▼                ▼                      ▼
 ┌───────────┐   ┌───────────────┐   ┌──────────────────┐
 │SensorDriver│   │ControllerBase │   │   MotorDriver     │
 │  (lecture) │   │    (ABC)      │   │  (exécution)      │
 └─────┬─────┘   └───────┬───────┘   └────────┬──────────┘
       │                 │                     │
       │          ┌──────┴──────┐              │
       │          │             │              │
       │    ┌─────┴────┐ ┌─────┴─────┐        │
       │    │PIDLine   │ │MLController│        │
       │    │Follower  │ │(TFLite)    │        │
       │    └──────────┘ └───────────┘        │
       │                                       │
       ▼                                       ▼
 ┌───────────┐                          ┌───────────┐
 │SensorState│                          │MotorCommand│
 │  (DTO)    │                          │   (DTO)    │
 └─────┬─────┘                          └─────┬─────┘
       │                                       │
       ▼                                       ▼
  ┌──────────┐                          ┌──────────┐
  │VisionPipe│                          │ RobotBase │
  │ + Robot  │                          │ (Zumi SDK)│
  │ sensors  │                          └──────────┘
  └──────────┘
```

### 2.2 Principes directeurs

1. **Un contrôleur = une classe héritant de `ControllerBase`** — interface uniforme `step(state) → MotorCommand`
2. **Entrées standardisées** via `SensorState` — un DTO contenant toutes les données capteur normalisées
3. **Sorties standardisées** via `MotorCommand` — un DTO décrivant la commande moteur à exécuter
4. **Découplage total** — le contrôleur ne connaît ni le robot ni la caméra, seulement `SensorState ↔ MotorCommand`
5. **Manager pluggable** — ajouter un contrôleur = `register(mon_controller)` + `set_active("mon_nom")`

---

## 3. Interfaces et DTOs

### 3.1 `SensorState` — Entrée standardisée

Encapsule tout ce qu'un contrôleur peut savoir du monde à un instant `t`.

```python
@dataclass
class SensorState:
    timestamp: float

    # ── Vision ──────────────────────────────
    frame: Optional[np.ndarray]           # Frame brute (pour contrôleurs visuels)
    line_offset: Optional[float]          # Offset de la ligne en pixels (None = pas de ligne)
    line_detected: bool                   # True si la ligne est visible
    detections: Optional[List[dict]]      # Détections passives [{class, distance, bbox, ...}]

    # ── IMU / Gyroscope ─────────────────────
    gyro_angles: Optional[List[float]]    # [x, y, z] degrés (via update_angles)
    orientation: int                      # État d'orientation Zumi (-1 à 7)

    # ── Capteurs IR ─────────────────────────
    ir_sensors: Optional[List[int]]       # 6 valeurs [0-255] (front_r, bottom_r, back_r,
                                          #                     bottom_l, back_l, front_l)

    # ── Batterie ────────────────────────────
    battery_voltage: float

    def to_vector(self) -> np.ndarray:
        """Convertit en vecteur numérique normalisé pour un modèle ML."""
        ...
```

### 3.2 `MotorCommand` — Sortie standardisée

Décrit ce que le robot doit faire, sans dépendance au SDK.

```python
class CommandType(Enum):
    STOP = 'stop'
    SPEED = 'speed'              # Contrôle direct vitesses G/D
    TURN = 'turn'                # Rotation d'un angle
    FORWARD_STEP = 'forward_step' # Un pas en avant avec correction heading

@dataclass
class MotorCommand:
    command_type: CommandType
    left_speed: int = 0          # [-127, 127] pour SPEED
    right_speed: int = 0
    angle: float = 0.0           # Degrés pour TURN
    speed: int = 0               # Pour FORWARD_STEP
    desired_angle: Optional[float] = None
    duration: float = 0.0

    # Factory methods
    @staticmethod
    def stop() -> 'MotorCommand': ...
    @staticmethod
    def speed(left, right) -> 'MotorCommand': ...
    @staticmethod
    def turn(angle) -> 'MotorCommand': ...
```

### 3.3 `ControllerBase` — Interface de contrôleur
classe de base abstraite des types contrôleurs, définissant l'interface commune et les méthodes par défaut.
```python
class ControllerBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Nom unique identifiant ce contrôleur (ex: 'pid_line', 'ml_imitation')."""

    @abstractmethod
    def step(self, state: SensorState) -> MotorCommand:
        """Calcule la prochaine commande moteur à partir de l'état capteur."""

    def start(self):
        """Appelé quand ce contrôleur devient actif. Override pour reset d'état."""
        pass

    def stop(self):
        """Appelé quand ce contrôleur est désactivé."""
        pass

    def get_debug_info(self) -> dict:
        """Données de monitoring pour l'interface opérateur."""
        return {}

    def get_params(self) -> dict:
        """Paramètres réglables de ce contrôleur."""
        return {}

    def update_params(self, **kwargs):
        """Mise à jour des paramètres en runtime (depuis l'UI)."""
        pass
```

---

## 4. Couches d'abstraction (Drivers)

### 4.1 `SensorDriver` — Lecture et normalisation des entrées

**Responsabilité** : Lire le `VisionPipeline`, le MPU (gyro/accéléromètre), les IR et la batterie du Zumi, et empaqueter le tout dans un `SensorState`.

**Fonctions Zumi SDK utilisées** :
| Donnée | Méthode SDK | Notes |
|--------|-------------|-------|
| Angles gyro/accéléromètre | `zumi.update_angles()` → liste de 11 valeurs | `[Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]` |
| Orientation | `zumi.get_orientation()` → int (-1 à 7) | 5 = roues au sol |
| IR (6 capteurs) | `zumi.get_all_IR_data()` → liste de 6 int | `[front_r, bottom_r, back_r, bottom_l, back_l, front_l]` |
| Batterie | `zumi.get_battery_voltage()` → float | Max 4.2V, min 3.0V |
| Frame caméra | `VisionPipeline.get_last_frame()` | Buffer partagé thread-safe |
| Offset ligne | `VisionPipeline.process_frame(frame, detector_index)` → `{line_offset: float}` | Via détecteur `LineDetector` |
| Détections passives | `VisionPipeline.get_passive_results()` | Haar cascades, etc. |

### 4.2 `MotorDriver` — Exécution des commandes moteur

**Responsabilité** : Traduire un `MotorCommand` en appels au SDK Zumi.

**Fonctions Zumi SDK utilisées** :
| CommandType | Méthode SDK | Notes |
|-------------|-------------|-------|
| `STOP` | `zumi.stop()` | Arrêt immédiat |
| `SPEED` | `zumi.control_motors(right, left)` | ⚠️ L'ordre SDK est (right, left) |
| `TURN` | `zumi.turn_left(angle)` / `zumi.turn_right(angle)` | Angle toujours positif dans le SDK |
| `FORWARD_STEP` | `zumi.forward_step(speed, desired_angle)` | Un pas avec correction PID interne Zumi |

**Note** : Le `MotorDriver` gère aussi les LEDs (clignotants, freins, phares) en fonction de la commande, centralisant la logique actuellement éparpillée dans `RobotZumi.control_motors()`.

---

## 5. Contrôleurs concrets

### 5.1 `PIDLineFollowerController`

Remplace l'usage direct de `PIDController` + _tick_pid dans le `ControlManager` actuel.

```python
class PIDLineFollowerController(ControllerBase):
    name = "pid_line"

    def __init__(self, pid: PIDController):
        self.pid = pid

    def step(self, state: SensorState) -> MotorCommand:
        if not state.line_detected:
            return MotorCommand.stop()

        if self.pid.rotation_mode:
            angle = self.pid.compute_rotation_angle(state.line_offset)
            return MotorCommand.turn(angle) if angle else MotorCommand.stop()
        else:
            left, right = self.pid.compute(state.line_offset)
            return MotorCommand.speed(left, right)

    def start(self):
        self.pid.reset()
```

> Le `PIDController` existant reste inchangé — c'est un **algorithme PID pur**, pas un contrôleur. Il est utilisé comme service par `PIDLineFollowerController`.

### 5.2 `MLController` (futur)

```python
class MLController(ControllerBase):
    name = "ml_imitation"

    def __init__(self, model_path: str):
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

    def step(self, state: SensorState) -> MotorCommand:
        input_vector = state.to_vector()
        # ... inférence TFLite ...
        left_speed, right_speed = output[0], output[1]
        return MotorCommand.speed(int(left_speed), int(right_speed))
```

### 5.3 `LineFollowingStateMachineController` (migration)

Wrap de la `LineFollowingStateMachine` existante pour respecter l'interface :

```python
class LineFollowingStateMachineController(ControllerBase):
    name = "state_machine"

    def __init__(self, robot, vision_pipeline, pid, stop_detector=None):
        self._sm = LineFollowingStateMachine(robot, vision_pipeline, pid, stop_detector)

    def step(self, state: SensorState) -> MotorCommand:
        # La SM gère ses propres appels moteur pour l'instant
        # Migration progressive : extraire les commandes moteur
        result = self._sm.step(state.frame)
        return MotorCommand.stop()  # La SM a déjà commandé le robot
```

> **Note** : La migration des state machines est plus complexe car elles pilotent directement le robot. L'approche recommandée est de les migrer progressivement en remplaçant les appels `robot.control_motors()` internes par des retours de `MotorCommand`.

---

## 6. `ControlManager` refactorisé

### 6.1 Nouvelle API

```python
class ControlManager:
    def register(self, controller: ControllerBase)
    def set_active(self, name: str)
    def deactivate(self)
    def list_controllers(self) -> List[str]
    def get_active_name(self) -> Optional[str]
    def tick(self)                          # Un cycle : read → step → execute
    def get_status(self) -> dict            # Monitoring
    def start_loop(self)                    # Démarre le thread de contrôle
    def stop(self)                          # Arrête tout
```

### 6.2 Ajout d'un contrôleur = 0 modification au Manager

```python
# Avant (hard-codé) :
control_manager.register_pid(pid_controller)          # Méthode spécifique
control_manager.register_state_machine(state_machine)  # Méthode spécifique
control_manager.activate(MODE_PID)                     # Constante spécifique

# Après (pluggable) :
control_manager.register(PIDLineFollowerController(pid))
control_manager.register(MLController("model.tflite"))
control_manager.register(MonNouveauController(...))
control_manager.set_active("pid_line")
control_manager.set_active("ml_imitation")
```

---

## 7. Modifications au `RobotBase` / `RobotZumi`

Le `RobotBase` actuel n'expose que `control_motors()` et `stop()`. Il faut ajouter :

| Méthode | SDK Zumi | Notes |
|---------|----------|-------|
| `turn(angle)` | `turn_left(abs(a))` / `turn_right(abs(a))` | Déjà dans `RobotZumi`, manque dans `RobotBase` |
| `forward_step(speed, angle)` | `forward_step(speed, angle)` | Avance d'un pas avec correction heading |
| `get_angles()` | `update_angles()` | Retourne liste de 11 floats |
| `get_ir_data()` | `get_all_IR_data()` | Retourne 6 ints |
| `get_orientation()` | `get_orientation()` | Retourne int |
| `get_battery_voltage()` | `get_battery_voltage()` | Retourne float |

Toutes ces méthodes ont une implémentation par défaut dans `RobotBase` retournant `None` / `0` / `-1`, permettant aux mocks de fonctionner sans modification.

---

## 8. Structure de fichiers

```
core/control/
├── __init__.py
├── controller_base.py          # ABC — interface ControllerBase
├── sensor_state.py             # DTO — SensorState (entrées)
├── motor_command.py            # DTO — MotorCommand (sorties)
├── sensor_driver.py            # Lecture capteurs → SensorState
├── motor_driver.py             # MotorCommand → appels robot
├── pid_controller.py           # Algorithme PID pur (inchangé)
├── pid_line_follower.py        # Contrôleur : PID + suivi de ligne
├── control_manager.py          # Manager pluggable (refactorisé)
├── line_following_state_machine.py  # Legacy — migration progressive
```

---

## 9. Plan de migration

### Phase A — Fondation (non-breaking)

- [x] Créer `sensor_state.py`, `motor_command.py`
- [x] Réécrire `controller_base.py` avec l'interface complète
- [x] Créer `sensor_driver.py`, `motor_driver.py`
- [x] Créer `pid_line_follower.py` (exemple concret)
- [x] Ajouter méthodes capteur à `RobotBase` / `RobotZumi`

> Rien ne casse — les nouveaux fichiers coexistent avec l'ancien code.

### Phase B — Migration du Manager

- [ ] Refactoriser `control_manager.py` pour utiliser le registre pluggable
- [ ] Adapter `server_controller.py` pour utiliser la nouvelle API
- [ ] Mettre à jour `main.py` (bootstrap)
- [ ] Valider que les modes PID et StateMachine fonctionnent identiquement

### Phase C — Contrôleur ML

- [ ] Créer `ml_controller.py` héritant de `ControllerBase`
- [ ] Implémenter `SensorState.to_vector()` avec normalisation
- [ ] Intégrer le module de collecte de données (enregistrement triplets)
- [ ] Ajouter l'onglet ML dans l'interface

### Phase D — Migration des State Machines

- [ ] Adapter `LineFollowingStateMachine` pour retourner des `MotorCommand` au lieu d'appeler le robot directement
- [ ] Adapter `StepByStepStateMachine` de la même façon
- [ ] Supprimer les appels directs `robot.control_motors()` des state machines

---

## 10. Diagramme de séquence — Un cycle de contrôle

```
ControlManager          SensorDriver          Controller           MotorDriver
     │                       │                     │                    │
     │── tick() ────────────►│                     │                    │
     │                       │── read() ──────────►│                    │
     │                       │  VisionPipeline     │                    │
     │                       │  Robot.get_angles() │                    │
     │                       │  Robot.get_ir_data()│                    │
     │                       │◄── SensorState ─────│                    │
     │◄── SensorState ───────│                     │                    │
     │                       │                     │                    │
     │── step(state) ────────────────────────────►│                    │
     │                       │                     │── compute ──────►│ │
     │◄── MotorCommand ──────────────────────────│                    │
     │                       │                     │                    │
     │── execute(cmd) ───────────────────────────────────────────────►│
     │                       │                     │    robot.turn()   │
     │                       │                     │    robot.motors() │
     │◄── done ──────────────────────────────────────────────────────│
     │                       │                     │                    │
```

---

## 11. Collecte de données pour l'imitation learning

Avec l'architecture standardisée, la collecte de données devient triviale :

```python
class DataCollector:
    """S'insère entre le SensorDriver et le MotorDriver pour enregistrer les paires."""

    def __init__(self, output_dir: str):
        self.recording = False
        self.data = []

    def record(self, state: SensorState, command: MotorCommand):
        if self.recording:
            self.data.append({
                'timestamp': state.timestamp,
                'line_offset': state.line_offset,
                'gyro_angles': state.gyro_angles,
                'ir_sensors': state.ir_sensors,
                'left_speed': command.left_speed,
                'right_speed': command.right_speed,
                'command_type': command.command_type.value,
            })
```

Le `ControlManager` peut appeler `data_collector.record(state, command)` entre le `step()` et le `execute()`, captant parfaitement les paires (état, action) nécessaires à l'apprentissage par imitation.
