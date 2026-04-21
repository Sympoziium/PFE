# Architecture du module de contrôle moteur

**État** : version finale PFE Hiver 2026 (tag `V2.0.0`)
**Objectif** : interface uniforme permettant l'ajout de contrôleurs (manuel, PID, ML, state-machine) via un manager pluggable, avec entrées et sorties standardisées.

---

## 1. Vue d'ensemble

```
┌────────────────────────────────────────────────────────────┐
│                     server_controller                       │
│                (Flask — interface opérateur)                │
│   activate_controller("pid_ir") / set_manual_override(...)  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│                     ControlManager                          │
│                 (registre + thread de boucle)               │
│                                                             │
│  register_controller(name, ctrl)                            │
│  activate_controller(name)      → start loop                │
│  deactivate_controller()        → stop loop + moteurs       │
│  set_manual_override(cmd)       → WASD sur ctrl actif       │
│  set_sampling_callback(fn)      → capture (state, cmd)      │
│                                                             │
│  Boucle : state = SensorDriver.read()                       │
│            cmd   = active_controller.step(state)            │
│            MotorDriver.execute(cmd)                         │
│  Fréquence : 30 Hz (ManualController) / 20 Hz (autres)      │
└──────┬────────────────┬────────────────────────┬──────────┘
       │                │                        │
       ▼                ▼                        ▼
 ┌──────────┐   ┌───────────────────┐   ┌──────────────┐
 │SensorDrv │   │  ControllerBase   │   │  MotorDriver │
 │ (lecture)│   │      (ABC)        │   │  (exécution) │
 └────┬─────┘   └─────────┬─────────┘   └──────┬───────┘
      │                   │                     │
      │          ┌────────┼─────────┬──────────┐│
      │          ▼        ▼         ▼          ▼│
      │   Manual      PIDIR       ML       Circuit
      │   Controller  Controller  Ctrl     FSMCtrl
      │
      ▼                                          ▼
 ┌──────────┐                             ┌──────────┐
 │Sensor    │                             │MotorCmd  │
 │State(DTO)│                             │  (DTO)   │
 └────┬─────┘                             └────┬─────┘
      │                                         │
      ▼                                         ▼
 VisionPipeline + Robot (Zumi SDK)          Robot (Zumi SDK)
```

## 2. Principes directeurs

1. **Un contrôleur = une classe héritant de `ControllerBase`** — interface uniforme `step(state) → MotorCommand`
2. **Entrées standardisées** via `SensorState` — DTO regroupant toutes les données capteur
3. **Sorties standardisées** via `MotorCommand` — DTO décrivant la commande moteur à exécuter
4. **Découplage total** — le contrôleur ne connaît ni le robot ni la caméra, il consomme `SensorState` et produit `MotorCommand`
5. **Manager pluggable** — ajouter un contrôleur = `register_controller(name, ctrl)` + `activate_controller(name)`

---

## 3. DTOs

### 3.1 `SensorState` — entrée standardisée
*Fichier : `core/control/IO_drivers/sensor_state.py`*

```python
@dataclass
class SensorState:
    timestamp: float

    # Vision — détection de ligne (zone centrale, legacy)
    frame: Optional[np.ndarray]        # Frame BGR brute
    line_offset: Optional[float]       # Offset en pixels (None si pas de ligne)
    line_detected: bool
    detections: Optional[List[dict]]   # Détections passives (Haar/LBP)

    # Vision — multi-zones (utilisé par CircuitFSMController)
    center_dash_count: int             # Nombre de tirets dans la zone centre
    front_dash_count: int
    front_line_detected: bool          # Ligne droit devant
    front_line_confirmed: bool
    front_offset: Optional[float]
    corner_left_detected: bool
    corner_right_detected: bool
    corner_left_count: int
    corner_right_count: int
    corner_left_area: float
    corner_right_area: float
    zones_result: dict                 # Résultat brut du process_zones()

    # IMU (via robot.get_angles() — 11 floats)
    gyro_angles: Optional[List[float]]
    # [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y,
    #  Rot_x, Rot_y, Rot_z, tilt_state]

    # Capteurs IR (via robot.get_ir_data() — 6 int [0-255])
    ir_sensors: Optional[List[int]]
    # [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
```

> **Note** : il n'y a pas de `to_vector()` sur `SensorState`. La vectorisation pour le MLP se fait dans `core/vision/vision_adapter.py` (classe `VisionAdapter`) puis dans `MLController._build_step_vector()`.

### 3.2 `MotorCommand` — sortie standardisée
*Fichier : `core/control/IO_drivers/motor_command.py`*

```python
class CommandType(Enum):
    STOP = 'stop'
    SPEED = 'speed'                # Contrôle direct vitesses G/D
    TURN = 'turn'                  # Rotation d'un angle
    FORWARD_STEP = 'forward_step'  # Pas en avant avec correction heading

@dataclass
class MotorCommand:
    command_type: CommandType
    left_speed: int = 0            # [-127, 127]
    right_speed: int = 0
    angle: float = 0.0             # Degrés (TURN)
    speed: int = 0                 # FORWARD_STEP
    desired_angle: Optional[float] = None
    duration: float = 0.0

    @staticmethod
    def stop() -> 'MotorCommand'
    @staticmethod
    def make_speed(left, right) -> 'MotorCommand'          # Clamp auto
    @staticmethod
    def make_turn(angle) -> 'MotorCommand'
    @staticmethod
    def make_forward_step(speed, desired_angle) -> 'MotorCommand'
```

---

## 4. Interface `ControllerBase`
*Fichier : `core/control/controlers/controller_base.py`*

```python
class ControllerBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Identifiant unique du contrôleur (ex: 'manual', 'pid_ir', 'ml', 'circuit_fsm')."""

    @abstractmethod
    def step(self, state: SensorState) -> MotorCommand:
        """Calcule la prochaine commande moteur à partir de l'état capteur."""

    def start(self) -> None:
        """Appelé quand ce contrôleur devient actif (reset d'état)."""

    def stop(self) -> None:
        """Appelé quand ce contrôleur est désactivé."""

    def get_debug_info(self) -> dict:
        """Données de monitoring pour l'UI opérateur."""

    def get_params(self) -> dict:
        """Paramètres réglables du contrôleur."""

    def update_params(self, **kwargs) -> None:
        """Mise à jour runtime des paramètres (depuis l'UI)."""
```

---

## 5. Drivers

### 5.1 `SensorDriver` — lecture des capteurs
*Fichier : `core/control/IO_drivers/sensor_driver.py`*

`SensorDriver(vision_pipeline, robot)` expose `read(Line_detection=True) → SensorState`. Il agrège :
- Frame + détections passives depuis `VisionPipeline`
- Multi-zones via `vision_pipeline.process_zones()` (centre, avant, coins gauche/droite)
- IMU via `robot.get_angles()`
- IR via `robot.get_ir_data()`

### 5.2 `MotorDriver` — exécution des commandes
*Fichier : `core/control/IO_drivers/motor_driver.py`*

`MotorDriver(robot)` expose `execute(command: MotorCommand)`. Dispatch :

| CommandType | Appel robot |
|-------------|-------------|
| `STOP` | `robot.stop()` |
| `SPEED` | `robot.control_motors(left, right)` |
| `TURN` | `robot.turn(angle)` (wrapper `turn_left` / `turn_right`) |
| `FORWARD_STEP` | `robot.forward_step(speed, desired_angle)` avec fallback `control_motors()` |

Property `last_command` pour diagnostic.

---

## 6. Contrôleurs concrets

### 6.1 `ManualController` — pilotage opérateur
*Fichier : `core/control/controlers/manual_controller.py`*

Interface WASD / D-pad du serveur Flask. État composé `throttle ∈ {-1, 0, +1}` × `steering ∈ {-1, 0, +1}` via `set_compound_action()` / `set_action()`.

Particularités :
- **`compute_speeds(throttle, steering, drive_speed, turn_speed, steering_ratio)`** (statique) : source unique de vérité pour le calcul des vitesses — utilisée par `step()` **et** par le sampling de données d'entraînement (garantit que les labels correspondent aux commandes réellement envoyées)
- **Correction de cap légère** par `Gyro_z` (index 2) quand on avance en ligne droite
- **Watchdog** (défaut 0.3 s) : arrêt automatique si aucune entrée récente
- **Rotation sur place** avec PWM logiciel (`turn_duty_on` / `turn_duty_off`) pour les robots avec asymétrie moteur forte

### 6.2 `PIDIRController` — suivi de ligne par IR
*Fichier : `core/control/controlers/pid_ir_controller.py`*

Signal d'erreur : `IR_bottom_right - IR_bottom_left - ir_offset` (offset auto-calibré sur les `calibration_samples` premiers ticks).

Deux modes alternés :
- **Mode IR** (ligne visible, `ir_sum < gap_threshold`) : PID différentiel sur l'erreur IR
- **Mode heading-hold** (trou entre tirets, `ir_sum > gap_threshold`) : maintien de cap via `Gyro_z`

Autres features :
- Détection d'oscillation via zero-crossings → calcul de `Tu` (utile pour tuning Ziegler-Nichols)
- Arrêt de sécurité si `ir_sum < line_lost_threshold` (plus aucune ligne détectée)

### 6.3 `MLController` — imitation learning (TFLite)
*Fichier : `core/control/controlers/ml_controller.py`*

Charge un modèle TFLite depuis `core/control/controlers/models/zumi_mlp.tflite` avec préférence pour `tflite_runtime` (léger sur Pi) et fallback sur `tensorflow.lite`. Config runtime optionnelle via `environment_config.json` (threads, allow_fp16).

Pipeline à chaque `step()` :
1. **`_build_step_vector(state)`** — `VisionAdapter` produit un vecteur de 38 dims brutes, puis 41 features ingénierées (voir ci-dessous)
2. **`_build_state_vector(state)`** — fenêtre glissante `WINDOW_SIZE=25` pas (1.25 s à 20 Hz), decay temporel `TEMPORAL_DECAY=0.85`, normalisation z-score via `normalization_stats.json`
3. **Inférence TFLite** — sortie 2 dims ∈ [-1, 1], dénormalisée vers `[-MOTOR_SPEED_MAX, +MOTOR_SPEED_MAX]` (max = 50)

Features ingénierées (inspirées du PID) :
- `calibrated_error` (offset IR bottom), `cal_error_norm`, `ir_error_derivative`, `ir_error_integral`, `ir_sum_accel`
- `gyro_z_rate`, `gyro_z_accel`, `heading_drift`, `lookahead_delta`
- `line_visible`, `line_lost_duration`

Debug logging activable via `set_debug(True)` → `debug_log.json`.

### 6.4 `CircuitFSMController` — parcours autonome par FSM
*Fichier : `core/control/controlers/circuit_fsm_controller.py`*

Parcourt le circuit Zumi Driving School via une state machine qui exploite la vision multi-zones.

États principaux :

```
INIT → CHERCHER_POINTILLES → SUIVRE_POINTILLES ⇄ PREVOIR_MANOEUVRE
                                    ↓                      ↓
                              ATTENTE_STEP           EXECUTER_MANOEUVRE
                              (pas-à-pas)                  ↓
                                                   (retour CHERCHER)
États sécurité : RECUPERATION_ECHOUEE, ARRET
```

Logique `SUIVRE_POINTILLES` (pas-à-pas) :
1. **PAUSE_CAPTURE** : frame stable, analyse des 3 zones, calcul correction PID
2. Si virage détecté (aire d'un coin > `turn_min_area`) → `PREVOIR_MANOEUVRE`
3. Sinon avance pendant `step_duration` avec correction → retour PAUSE_CAPTURE

Manœuvre aveugle (PREVOIR + EXECUTER) : avance `maneuver_forward_cm` (durée calculée via `cm_per_second`), tourne `maneuver_turn_angle` (-90° par défaut), puis retour à CHERCHER.

---

## 7. `ControlManager`
*Fichier : `core/control/control_manager.py`*

### API publique

```python
register_controller(name: str, controller: ControllerBase)
get_controller(name) -> ControllerBase
activate_controller(name)           # Démarre la boucle + ctrl.start()
deactivate_controller()             # Arrête la boucle + ctrl.stop() + moteurs
set_manual_override(command)        # WASD par-dessus le ctrl actif
clear_manual_override()
set_sampling_callback(fn)           # fn(state, command) appelée entre step et execute
update_sensors()                    # Lecture directe (ex: UI de diagnostic)
get_status() -> dict                # running, speeds, ctrl_name, debug, params
```

### Threading

Boucle dans un thread daemon unique (`_control_loop`). Fréquence : 30 Hz pour `ManualController`, 20 Hz (configurable via `_loop_delay`) pour les autres contrôleurs.

État partagé protégé par `_data_lock` : `last_sensor_data`, `last_motor_command`, `last_left_speed`, `last_right_speed`.

### Ajout d'un contrôleur

```python
# Zéro modification au manager — pluggable
manager.register_controller("mon_ctrl", MonControleur(...))
manager.activate_controller("mon_ctrl")
```

---

## 8. Utilitaire — `SensorProfiler`
*Fichier : `core/control/sensor_profiler.py`*

Orchestrateur d'une séquence interactive en 18 phases qui caractérise les réponses capteurs d'un robot donné (baselines IR, réponse gyro à la rotation, asymétrie moteur, profil de traversée de ligne). Produit un fichier de profil JSON par robot.

Le profiler utilise un `CalibrationController` (helper qui hérite de `ControllerBase`) pour s'intégrer proprement dans la boucle du `ControlManager` plutôt que de bypasser l'infrastructure.

---

## 9. Structure des fichiers

```
core/control/
├── __init__.py
├── control_manager.py              # Orchestrateur pluggable (thread + registre)
├── sensor_profiler.py              # Caractérisation capteurs (utilitaire)
├── IO_drivers/
│   ├── sensor_state.py             # DTO — entrée
│   ├── motor_command.py            # DTO — sortie
│   ├── sensor_driver.py            # Lecture capteurs → SensorState
│   └── motor_driver.py             # MotorCommand → appels robot
└── controlers/
    ├── controller_base.py          # ABC — ControllerBase
    ├── manual_controller.py        # Pilotage WASD/D-pad
    ├── pid_ir_controller.py        # PID sur capteurs IR + heading-hold
    ├── ml_controller.py            # Inférence MLP (TFLite)
    ├── circuit_fsm_controller.py   # Parcours autonome FSM multi-zones
    └── models/                     # Artefacts déploiement ML
        ├── zumi_mlp.tflite
        ├── normalization_stats.json
        └── environment_config.json
```

---

## 10. Diagramme de séquence — un cycle de contrôle

```
ControlManager       SensorDriver       Controller          MotorDriver
     │                    │                 │                    │
     ├── tick() ─────────▶│                 │                    │
     │                    ├─ read() ───────▶│                    │
     │                    │  VisionPipeline │                    │
     │                    │  process_zones()│                    │
     │                    │  robot.get_angles()                  │
     │                    │  robot.get_ir_data()                 │
     │                    │◀─ SensorState ──┤                    │
     │◀─ SensorState ─────┤                 │                    │
     │                                                           │
     ├── step(state) ─────────────────────▶│                    │
     │                                      ├─ compute ───┐      │
     │                                      │            │      │
     │◀─ MotorCommand ─────────────────────┤◀───────────┘      │
     │                                                           │
     ├── sampling_callback(state, cmd)  (optionnel)              │
     │                                                           │
     ├── execute(cmd) ────────────────────────────────────────▶│
     │                                                   robot.turn() /
     │                                                   robot.control_motors()
     │◀─ done ─────────────────────────────────────────────────┤
```
