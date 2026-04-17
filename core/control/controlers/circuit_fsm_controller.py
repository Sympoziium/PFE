#!/usr/bin/env python
# -*- coding: utf-8 -*-
# circuit_fsm_controller.py
# ------------------
"""Contrôleur FSM pour la navigation autonome sur circuit (Zumi Driving School).

Implémente ControllerBase. Utilise la caméra (LineDetector) avec 3 zones de
détection pour naviguer le circuit via une machine à états finis.

Zones de détection :
    - CENTRE : Rectangle en bas de l'image (largeur modulable).
      → Détecte l'offset latéral du robot par rapport à la ligne.
    - AVANT : Rectangle vertical fin et long au milieu.
      → Confirme que la ligne continue droit devant (alignement).
    - COINS (gauche + droit) : Rectangles dans les coins.
      → Anticipent les virages en détectant la ligne qui s'en va sur le côté.

Navigation step-by-step :
    Le robot s'arrête pour capturer une frame stable, analyse les 3 zones,
    prend une décision éclairée, avance d'un petit pas, puis s'arrête à nouveau.

Mode pas-à-pas interactif :
    Quand activé, le robot attend un signal explicite (bouton UI) avant
    chaque mouvement. Permet de vérifier visuellement ce que le robot voit.

États de l'automate :
    INIT → CHERCHER_POINTILLES → SUIVRE_POINTILLES → PREVOIR_MANOEUVRE
    → EXECUTER_MANOEUVRE → CHERCHER_POINTILLES (boucle)
    CHERCHER_POINTILLES → RECUPERATION_ECHOUEE → ARRET (sécurité)
    + ATTENTE_STEP (mode pas-à-pas)

Contexte physique :
    Route NOIRE, pointillés BLANCS.
"""

import time

from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand


# ──────────────────────────────────────────────────────────────
#  Enum des états
# ──────────────────────────────────────────────────────────────
class FSMState:
    """États de l'automate du circuit."""
    INIT = "INIT"
    CHERCHER_POINTILLES = "CHERCHER_POINTILLES"
    SUIVRE_POINTILLES = "SUIVRE_POINTILLES"
    PREVOIR_MANOEUVRE = "PREVOIR_MANOEUVRE"
    EXECUTER_MANOEUVRE = "EXECUTER_MANOEUVRE"
    RECUPERATION_ECHOUEE = "RECUPERATION_ECHOUEE"
    ARRET = "ARRET"
    ATTENTE_STEP = "ATTENTE_STEP"  # Mode pas-à-pas


# ──────────────────────────────────────────────────────────────
#  Sous-états pour la navigation step-by-step
# ──────────────────────────────────────────────────────────────
class StepPhase:
    """Phases du cycle step-by-step dans SUIVRE_POINTILLES."""
    PAUSE_CAPTURE = "PAUSE_CAPTURE"   # À l'arrêt, en train de capturer
    MOVING = "MOVING"                  # En mouvement vers la cible


class CircuitFSMController(ControllerBase):
    """Contrôleur FSM pour navigation autonome avec détection multi-zones.

    Utilise le LineDetector (caméra) avec 3 zones pour la détection de ligne.
    
    Logique de décision :
        1. CENTRE détecte → on sait où on est
        2. AVANT confirme → la ligne continue droit, on peut avancer
        3. COINS détectent → un virage approche, on ralentit/prépare
        4. Combinaison → décision éclairée avant chaque mouvement

    Args:
        base_speed (int): Vitesse de base pour les pas [1-50].
        kp (float): Gain proportionnel (offset pixels → correction).
        ki (float): Gain intégral.
        kd (float): Gain dérivé.
        max_correction (int): Correction différentielle maximale.
        turn_threshold (int): Offset pixels au-delà duquel faire une rotation pure.
        turn_angle_scale (float): Facteur offset → angle de rotation (degrés/pixel).
        max_turn_angle (float): Angle maximum de rotation de centrage (degrés).
        line_lost_timeout (float): Secondes sans ligne → PREVOIR_MANOEUVRE.
        search_timeout (float): Secondes en CHERCHER sans succès → RECUPERATION.
        search_spin_speed (int): Vitesse de pivot pendant la recherche.
        init_stabilize_ticks (int): Nombre de ticks pour stabiliser la caméra.
        maneuver_forward_cm (float): Distance à avancer avant le virage aveugle.
        maneuver_turn_angle (float): Angle du virage aveugle (négatif = droite).
        forward_speed (int): Vitesse pendant l'avance aveugle.
        cm_per_second (float): Calibration vitesse → distance (cm/s).
        step_duration (float): Durée d'un pas en secondes.
        pause_duration (float): Durée de pause entre les pas (pour capture).
        corner_slowdown_factor (float): Facteur de ralentissement quand coin détecté (0-1).
        turn_min_area (int): Superficie min dans un coin pour confirmer un vrai virage.
        step_by_step_mode (bool): Mode pas-à-pas interactif.
    """

    MOTOR_SPEED_MAX = 50

    def __init__(
        self,
        base_speed=20,
        kp=0.2,
        ki=0.2,
        kd=0.0,
        max_correction=25,
        turn_threshold=60,
        turn_angle_scale=0.25,
        max_turn_angle=30.0,
        line_lost_timeout=1.0,
        search_timeout=5.0,
        search_spin_speed=3,
        init_stabilize_ticks=10,
        maneuver_forward_cm=15.0,
        maneuver_turn_angle=-90.0,
        forward_speed=20,
        cm_per_second=10.0,
        step_duration=0.3,
        pause_duration=0.2,
        corner_slowdown_factor=0.5,
        turn_min_area=800,
        step_by_step_mode=False,
    ):
        # PID (correction step-by-step)
        self._base_speed = base_speed
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._max_correction = max_correction
        self._turn_threshold = turn_threshold
        self._turn_angle_scale = turn_angle_scale
        self._max_turn_angle = max_turn_angle

        # FSM timing
        self._line_lost_timeout = line_lost_timeout
        self._search_timeout = search_timeout
        self._search_spin_speed = search_spin_speed
        self._init_stabilize_ticks = init_stabilize_ticks

        # Manœuvre aveugle
        self._maneuver_forward_cm = maneuver_forward_cm
        self._maneuver_turn_angle = maneuver_turn_angle
        self._forward_speed = forward_speed
        self._cm_per_second = cm_per_second

        # Step-by-step
        self._step_duration = step_duration
        self._pause_duration = pause_duration

        # Multi-zones
        self._corner_slowdown_factor = corner_slowdown_factor
        self._turn_min_area = turn_min_area

        # Mode pas-à-pas interactif
        self._step_by_step_mode = step_by_step_mode
        self._step_requested = False  # Signal du frontend

        # ── État interne ──
        self._state = FSMState.INIT
        self._prev_state = None

        # PID state
        self._integral = 0.0
        self._prev_error = 0.0

        # Timing
        self._init_tick_count = 0
        self._line_lost_time = None       # Timestamp quand la ligne a été perdue
        self._search_start_time = None    # Timestamp du début de la recherche
        self._last_line_offset = 0.0      # Dernier offset valide observé

        # Step-by-step state
        self._step_phase = StepPhase.PAUSE_CAPTURE
        self._phase_start_time = 0.0
        self._step_correction = 0.0       # Correction calculée pendant la pause

        # Manœuvre aveugle state
        self._maneuver_phase = "forward"  # "forward" ou "turn"
        self._maneuver_start_time = 0.0
        self._maneuver_forward_duration = 0.0  # Calculé dans PREVOIR

        # Flag post-manœuvre (pour distinguer CHERCHER après manœuvre)
        self._post_maneuver = False

        # Multi-zone state (dernière décision)
        self._last_decision = "none"
        self._corner_detected_side = None  # "left", "right", ou None
        self._turn_detected = False        # Virage confirmé (aire suffisante)
        self._turn_direction = None        # "left" ou "right"

        # Debug
        self._last_command_type = "none"

    # ------------------------------------------------------------------
    #  Interface ControllerBase
    # ------------------------------------------------------------------

    @property
    def name(self):
        return "circuit_fsm"

    def start(self):
        """Réinitialise la FSM à l'activation."""
        self._state = FSMState.INIT
        self._prev_state = None
        self._integral = 0.0
        self._prev_error = 0.0
        self._init_tick_count = 0
        self._line_lost_time = None
        self._search_start_time = None
        self._last_line_offset = 0.0
        self._step_phase = StepPhase.PAUSE_CAPTURE
        self._phase_start_time = 0.0
        self._step_correction = 0.0
        self._maneuver_phase = "forward"
        self._maneuver_start_time = 0.0
        self._post_maneuver = False
        self._last_command_type = "none"
        self._last_decision = "none"
        self._corner_detected_side = None
        self._turn_detected = False
        self._turn_direction = None
        self._step_requested = False
        print("[CIRCUIT_FSM] Démarré — état: INIT (pas-à-pas: {})".format(
            "OUI" if self._step_by_step_mode else "NON"))

    def stop(self):
        """Appelé à la désactivation."""
        self._state = FSMState.ARRET
        print("[CIRCUIT_FSM] Arrêté")

    def step(self, state):
        """Exécute un tick de la FSM.

        Args:
            state (SensorState): État capteur courant.

        Returns:
            MotorCommand: Commande moteur à exécuter.
        """
        # Détection de changement d'état (pour les logs)
        if self._state != self._prev_state:
            print("[CIRCUIT_FSM] Transition: {} -> {}".format(
                self._prev_state or "NONE", self._state))
            self._prev_state = self._state

        # Dispatch vers le handler de l'état courant
        if self._state == FSMState.INIT:
            return self._handle_init(state)
        elif self._state == FSMState.CHERCHER_POINTILLES:
            return self._handle_chercher(state)
        elif self._state == FSMState.SUIVRE_POINTILLES:
            return self._handle_suivre(state)
        elif self._state == FSMState.PREVOIR_MANOEUVRE:
            return self._handle_prevoir(state)
        elif self._state == FSMState.EXECUTER_MANOEUVRE:
            return self._handle_executer(state)
        elif self._state == FSMState.RECUPERATION_ECHOUEE:
            return self._handle_recuperation(state)
        elif self._state == FSMState.ATTENTE_STEP:
            return self._handle_attente_step(state)
        elif self._state == FSMState.ARRET:
            return self._handle_arret(state)
        else:
            print("[CIRCUIT_FSM] État inconnu: {}".format(self._state))
            return MotorCommand.stop()

    # ------------------------------------------------------------------
    #  Mode pas-à-pas
    # ------------------------------------------------------------------

    def request_step(self):
        """Appelé par le frontend pour autoriser un pas en mode pas-à-pas."""
        self._step_requested = True
        print("[CIRCUIT_FSM] Step demandé par l'utilisateur")

    # ------------------------------------------------------------------
    #  Handlers d'état
    # ------------------------------------------------------------------

    def _handle_init(self, state):
        """INIT : Stabiliser la caméra (attendre N ticks)."""
        self._init_tick_count += 1
        self._last_command_type = "init_wait"

        if self._init_tick_count >= self._init_stabilize_ticks:
            print("[CIRCUIT_FSM] Calibration terminée ({} ticks)".format(
                self._init_tick_count))
            self._state = FSMState.CHERCHER_POINTILLES
            self._search_start_time = time.time()

        return MotorCommand.stop()

    def _handle_chercher(self, state):
        """CHERCHER_POINTILLES : Pivoter pour trouver la ligne."""
        now = time.time()

        # Initialiser le timer de recherche si nécessaire
        if self._search_start_time is None:
            self._search_start_time = now

        # Vérifier le timeout de recherche
        elapsed = now - self._search_start_time
        if elapsed > self._search_timeout:
            print("[CIRCUIT_FSM] Recherche échouée après {:.1f}s".format(elapsed))
            self._state = FSMState.RECUPERATION_ECHOUEE
            return MotorCommand.stop()

        # Vérifier si la ligne est détectée (zone centre)
        if state.line_detected and state.line_offset is not None:
            print("[CIRCUIT_FSM] Ligne trouvée! offset={:.1f}px".format(
                state.line_offset))
            self._state = FSMState.SUIVRE_POINTILLES
            self._search_start_time = None
            self._line_lost_time = None
            self._post_maneuver = False
            # Réinitialiser le step-by-step
            self._step_phase = StepPhase.PAUSE_CAPTURE
            self._phase_start_time = time.time()
            self._integral = 0.0
            self._prev_error = 0.0
            self._last_line_offset = state.line_offset
            return MotorCommand.stop()

        # Pivoter lentement pour chercher la ligne
        self._last_command_type = "search_spin"
        return MotorCommand.make_speed(
            self._search_spin_speed,
            -self._search_spin_speed
        )

    def _handle_suivre(self, state):
        """SUIVRE_POINTILLES : Navigation step-by-step avec multi-zones.

        Cycle :
          1. PAUSE_CAPTURE — robot à l'arrêt, capture frame, analyse 3 zones
          2. Décision multi-zones :
             a. Zone AVANT confirme la ligne droit devant → confiance haute
             b. Zones COINS détectent un virage → ralentir / anticiper
             c. Zone CENTRE donne l'offset → correction PID
          3. Si mode pas-à-pas → ATTENTE_STEP
          4. MOVING — avance pendant step_duration, puis retour en PAUSE_CAPTURE
        """
        now = time.time()

        # ── Vérifier la perte de ligne ──
        if state.line_detected and state.line_offset is not None:
            self._line_lost_time = None  # Reset du timer de perte
            self._last_line_offset = state.line_offset
        else:
            # Ligne perdue
            if self._line_lost_time is None:
                self._line_lost_time = now
            elif (now - self._line_lost_time) > self._line_lost_timeout:
                print("[CIRCUIT_FSM] Ligne perdue depuis {:.1f}s → PREVOIR_MANOEUVRE".format(
                    now - self._line_lost_time))
                self._state = FSMState.PREVOIR_MANOEUVRE
                return MotorCommand.stop()

        # ── Analyser les zones pour la décision ──
        self._analyze_zones(state)

        # ── Phase PAUSE_CAPTURE : à l'arrêt, capturer et décider ──
        if self._step_phase == StepPhase.PAUSE_CAPTURE:
            elapsed = now - self._phase_start_time

            if elapsed < self._pause_duration:
                # Attendre la stabilisation
                self._last_command_type = "pause_capture"
                return MotorCommand.stop()

            # Pause terminée → capturer l'offset et calculer la correction
            if state.line_detected and state.line_offset is not None:
                self._last_line_offset = state.line_offset
                self._step_correction = self._compute_pid_correction(state.line_offset)
                
                # Log enrichi avec les 3 zones
                print("[CIRCUIT_FSM] CAPTURE: offset={:.1f}px correction={:.1f} | "
                      "front={} coins=L:{} R:{} | décision={} | areaL={} areaR={}".format(
                    state.line_offset, self._step_correction,
                    "OUI" if state.front_line_confirmed else "non",
                    state.corner_left_count, state.corner_right_count,
                    self._last_decision,
                    getattr(state, 'corner_left_area', 0),
                    getattr(state, 'corner_right_area', 0)))
            else:
                # Pas de détection, avancer droit
                self._step_correction = 0.0

            # Virage détecté → transition immédiate vers PREVOIR_MANOEUVRE
            # (vérifié AVANT le mode pas-à-pas pour ne pas rater de virage)
            if self._turn_detected:
                print("[CIRCUIT_FSM] VIRAGE DÉTECTÉ: direction={} area_L={} area_R={} → PREVOIR_MANOEUVRE".format(
                    self._turn_direction,
                    getattr(state, 'corner_left_area', 0),
                    getattr(state, 'corner_right_area', 0)))
                self._corner_detected_side = self._turn_direction
                self._state = FSMState.PREVOIR_MANOEUVRE
                return MotorCommand.stop()

            # Mode pas-à-pas : attendre le signal
            if self._step_by_step_mode:
                self._state = FSMState.ATTENTE_STEP
                self._last_command_type = "waiting_step"
                return MotorCommand.stop()

            self._step_phase = StepPhase.MOVING
            self._phase_start_time = now
            self._last_command_type = "step_start"
            # Ne pas tomber dans MOVING immédiatement — attendre le prochain tick
            return MotorCommand.stop()

        # ── Phase MOVING : avancer d'un pas avec la correction calculée ──
        if self._step_phase == StepPhase.MOVING:
            elapsed = now - self._phase_start_time

            if elapsed >= self._step_duration:
                # Pas terminé → revenir en pause
                self._step_phase = StepPhase.PAUSE_CAPTURE
                self._phase_start_time = now
                self._last_command_type = "step_done"
                return MotorCommand.stop()

            # Vérifier si l'offset capturé nécessite une rotation pure
            if abs(self._last_line_offset) > self._turn_threshold:
                # Rotation proportionnelle à l'offset
                angle = -self._last_line_offset * self._turn_angle_scale
                angle = max(-self._max_turn_angle, min(self._max_turn_angle, angle))
                self._last_command_type = "step_turn"
                print("[CIRCUIT_FSM] TURN: offset={:.1f} → angle={:.1f}°".format(
                    self._last_line_offset, angle))
                return MotorCommand.make_turn(angle)

            # Calculer la vitesse effective (ralentir si virage détecté dans les coins)
            effective_speed = self._base_speed
            if self._corner_detected_side is not None:
                effective_speed = int(self._base_speed * self._corner_slowdown_factor)
                effective_speed = max(1, effective_speed)

            # Avance différentielle avec correction
            correction = self._step_correction
            left_speed = effective_speed + correction
            right_speed = effective_speed - correction

            # Clamp aux limites
            left_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, left_speed))
            right_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, right_speed))

            self._last_command_type = "step_move"
            return MotorCommand.make_speed(left_speed, right_speed)

        # Fallback
        return MotorCommand.stop()

    def _handle_attente_step(self, state):
        """ATTENTE_STEP : Mode pas-à-pas — attendre le signal utilisateur."""
        if self._step_requested:
            self._step_requested = False
            # Reprendre le mouvement
            self._state = FSMState.SUIVRE_POINTILLES
            self._step_phase = StepPhase.MOVING
            self._phase_start_time = time.time()
            self._last_command_type = "step_resume"
            print("[CIRCUIT_FSM] Pas autorisé par l'utilisateur → MOVING")
            return MotorCommand.stop()

        # En attente — rester immobile
        self._last_command_type = "waiting_user"
        return MotorCommand.stop()

    def _handle_prevoir(self, state):
        """PREVOIR_MANOEUVRE : Calculer la manœuvre aveugle."""
        # Utiliser les coins pour décider la direction du virage
        turn_angle = self._maneuver_turn_angle
        if self._corner_detected_side == "left":
            turn_angle = abs(turn_angle)  # Virage à gauche (angle positif)
        elif self._corner_detected_side == "right":
            turn_angle = -abs(turn_angle)  # Virage à droite (angle négatif)
        # else: utiliser l'angle par défaut

        # Calculer la durée de l'avance en fonction de la distance
        if self._cm_per_second > 0:
            self._maneuver_forward_duration = self._maneuver_forward_cm / self._cm_per_second
        else:
            self._maneuver_forward_duration = 1.0

        print("[CIRCUIT_FSM] Manœuvre planifiée: avancer {:.1f}cm ({:.2f}s) puis tourner {:.1f}° "
              "(coin détecté: {})".format(
            self._maneuver_forward_cm,
            self._maneuver_forward_duration,
            turn_angle,
            self._corner_detected_side or "aucun"))

        self._maneuver_turn_angle_effective = turn_angle
        self._maneuver_phase = "forward"
        self._maneuver_start_time = time.time()
        self._state = FSMState.EXECUTER_MANOEUVRE

        return MotorCommand.stop()  # Un tick de transition

    def _handle_executer(self, state):
        """EXECUTER_MANOEUVRE : Exécuter la manœuvre à l'aveugle."""
        now = time.time()

        if self._maneuver_phase == "forward":
            # Phase d'avance en ligne droite
            elapsed = now - self._maneuver_start_time

            if elapsed >= self._maneuver_forward_duration:
                # Avance terminée → passer à la rotation
                print("[CIRCUIT_FSM] Avance terminée ({:.2f}s) → rotation".format(elapsed))
                self._maneuver_phase = "turn"
                self._last_command_type = "maneuver_turn"
                turn_angle = getattr(self, '_maneuver_turn_angle_effective', self._maneuver_turn_angle)
                return MotorCommand.make_turn(turn_angle)

            # Avancer tout droit
            self._last_command_type = "maneuver_forward"
            return MotorCommand.make_speed(self._forward_speed, self._forward_speed)

        elif self._maneuver_phase == "turn":
            # La rotation est bloquante (exécutée par robot.turn()),
            # donc quand on arrive ici, elle est terminée.
            print("[CIRCUIT_FSM] Manœuvre complète → CHERCHER_POINTILLES")
            self._state = FSMState.CHERCHER_POINTILLES
            self._search_start_time = time.time()
            self._post_maneuver = True
            self._last_command_type = "maneuver_done"
            self._corner_detected_side = None
            return MotorCommand.stop()

        return MotorCommand.stop()

    def _handle_recuperation(self, state):
        """RECUPERATION_ECHOUEE : Arrêt d'urgence."""
        print("[CIRCUIT_FSM] RÉCUPÉRATION ÉCHOUÉE — arrêt de sécurité")
        self._state = FSMState.ARRET
        self._last_command_type = "recovery_fail"
        return MotorCommand.stop()

    def _handle_arret(self, state):
        """ARRET : État terminal."""
        self._last_command_type = "stopped"
        return MotorCommand.stop()

    # ------------------------------------------------------------------
    #  Analyse multi-zones
    # ------------------------------------------------------------------

    def _analyze_zones(self, state):
        """Analyse les zones et met à jour la dernière décision.
        
        Décisions possibles :
            - "avance_confiant" : AVANT confirmé, ligne droit devant
            - "avance_prudent" : CENTRE détecté mais AVANT pas confirmé
            - "virage_gauche" : Coin gauche détecté avec aire suffisante
            - "virage_droit" : Coin droit détecté avec aire suffisante
            - "virage_imminent" : Les deux coins détectés
            - "coin_gauche" : Coin gauche détecté (aire insuffisante pour virage)
            - "coin_droit" : Coin droit détecté (aire insuffisante pour virage)
            - "perdu" : Rien détecté
        """
        center_ok = state.line_detected
        front_ok = state.front_line_confirmed
        corner_l = state.corner_left_detected
        corner_r = state.corner_right_detected
        corner_l_area = getattr(state, 'corner_left_area', 0)
        corner_r_area = getattr(state, 'corner_right_area', 0)

        # Reset virage
        self._turn_detected = False
        self._turn_direction = None

        if corner_l and corner_r:
            self._last_decision = "virage_imminent"
            self._corner_detected_side = "left" if state.corner_left_count > state.corner_right_count else "right"
            # Vérifier si c'est un vrai virage (aire suffisante)
            if corner_l_area >= self._turn_min_area or corner_r_area >= self._turn_min_area:
                self._turn_detected = True
                self._turn_direction = "left" if corner_l_area > corner_r_area else "right"
        elif corner_l:
            if corner_l_area >= self._turn_min_area and not front_ok:
                self._last_decision = "virage_gauche"
                self._corner_detected_side = "left"
                self._turn_detected = True
                self._turn_direction = "left"
            else:
                self._last_decision = "coin_gauche"
                self._corner_detected_side = "left"
        elif corner_r:
            if corner_r_area >= self._turn_min_area and not front_ok:
                self._last_decision = "virage_droit"
                self._corner_detected_side = "right"
                self._turn_detected = True
                self._turn_direction = "right"
            else:
                self._last_decision = "coin_droit"
                self._corner_detected_side = "right"
        elif center_ok and front_ok:
            self._last_decision = "avance_confiant"
            self._corner_detected_side = None
        elif center_ok:
            self._last_decision = "avance_prudent"
            self._corner_detected_side = None
        else:
            self._last_decision = "perdu"

    # ------------------------------------------------------------------
    #  PID (correction step-by-step)
    # ------------------------------------------------------------------

    def _compute_pid_correction(self, line_offset):
        """Calcule la correction PID à partir de l'offset de ligne.

        Args:
            line_offset (float): Offset en pixels (négatif=gauche, positif=droite).

        Returns:
            float: Correction différentielle à appliquer aux moteurs.
        """
        error = line_offset
        self._integral += error
        derivative = error - self._prev_error
        self._prev_error = error

        # Anti-windup
        max_integral = self._max_correction / max(self._ki, 1e-6)
        self._integral = max(-max_integral, min(max_integral, self._integral))

        correction = (
            self._kp * error
            + self._ki * self._integral
            + self._kd * derivative
        )

        # Limiter la correction
        correction = max(-self._max_correction, min(self._max_correction, correction))

        return correction

    # ------------------------------------------------------------------
    #  Debug & tuning
    # ------------------------------------------------------------------

    def get_debug_info(self):
        """Retourne les informations de debug pour l'interface."""
        return {
            "fsm_state": self._state,
            "step_phase": self._step_phase if self._state == FSMState.SUIVRE_POINTILLES else "N/A",
            "last_line_offset": self._last_line_offset,
            "last_correction": self._step_correction,
            "last_command_type": self._last_command_type,
            "last_decision": self._last_decision,
            "corner_detected_side": self._corner_detected_side,
            "turn_detected": self._turn_detected,
            "turn_direction": self._turn_direction,
            "integral": self._integral,
            "post_maneuver": self._post_maneuver,
            "maneuver_phase": self._maneuver_phase if self._state == FSMState.EXECUTER_MANOEUVRE else "N/A",
            "step_by_step_mode": self._step_by_step_mode,
            "step_requested": self._step_requested,
        }

    def get_params(self):
        """Retourne les paramètres réglables."""
        return {
            "base_speed": self._base_speed,
            "kp": self._kp,
            "ki": self._ki,
            "kd": self._kd,
            "max_correction": self._max_correction,
            "turn_threshold": self._turn_threshold,
            "turn_angle_scale": self._turn_angle_scale,
            "max_turn_angle": self._max_turn_angle,
            "line_lost_timeout": self._line_lost_timeout,
            "search_timeout": self._search_timeout,
            "search_spin_speed": self._search_spin_speed,
            "init_stabilize_ticks": self._init_stabilize_ticks,
            "maneuver_forward_cm": self._maneuver_forward_cm,
            "maneuver_turn_angle": self._maneuver_turn_angle,
            "forward_speed": self._forward_speed,
            "cm_per_second": self._cm_per_second,
            "step_duration": self._step_duration,
            "pause_duration": self._pause_duration,
            "corner_slowdown_factor": self._corner_slowdown_factor,
            "turn_min_area": self._turn_min_area,
            "step_by_step_mode": self._step_by_step_mode,
        }

    def update_params(self, **kwargs):
        """Met à jour les paramètres en runtime."""
        updated = []
        if "base_speed" in kwargs:
            self._base_speed = int(kwargs["base_speed"])
            updated.append("base_speed={}".format(self._base_speed))
        if "kp" in kwargs:
            self._kp = float(kwargs["kp"])
            updated.append("kp={}".format(self._kp))
        if "ki" in kwargs:
            self._ki = float(kwargs["ki"])
            updated.append("ki={}".format(self._ki))
        if "kd" in kwargs:
            self._kd = float(kwargs["kd"])
            updated.append("kd={}".format(self._kd))
        if "max_correction" in kwargs:
            self._max_correction = int(kwargs["max_correction"])
            updated.append("max_correction={}".format(self._max_correction))
        if "turn_threshold" in kwargs:
            self._turn_threshold = int(kwargs["turn_threshold"])
            updated.append("turn_threshold={}".format(self._turn_threshold))
        if "turn_angle_scale" in kwargs:
            self._turn_angle_scale = float(kwargs["turn_angle_scale"])
            updated.append("turn_angle_scale={}".format(self._turn_angle_scale))
        if "max_turn_angle" in kwargs:
            self._max_turn_angle = float(kwargs["max_turn_angle"])
            updated.append("max_turn_angle={}".format(self._max_turn_angle))
        if "line_lost_timeout" in kwargs:
            self._line_lost_timeout = float(kwargs["line_lost_timeout"])
            updated.append("line_lost_timeout={}".format(self._line_lost_timeout))
        if "search_timeout" in kwargs:
            self._search_timeout = float(kwargs["search_timeout"])
            updated.append("search_timeout={}".format(self._search_timeout))
        if "search_spin_speed" in kwargs:
            self._search_spin_speed = int(kwargs["search_spin_speed"])
            updated.append("search_spin_speed={}".format(self._search_spin_speed))
        if "init_stabilize_ticks" in kwargs:
            self._init_stabilize_ticks = int(kwargs["init_stabilize_ticks"])
            updated.append("init_stabilize_ticks={}".format(self._init_stabilize_ticks))
        if "maneuver_forward_cm" in kwargs:
            self._maneuver_forward_cm = float(kwargs["maneuver_forward_cm"])
            updated.append("maneuver_forward_cm={}".format(self._maneuver_forward_cm))
        if "maneuver_turn_angle" in kwargs:
            self._maneuver_turn_angle = float(kwargs["maneuver_turn_angle"])
            updated.append("maneuver_turn_angle={}".format(self._maneuver_turn_angle))
        if "forward_speed" in kwargs:
            self._forward_speed = int(kwargs["forward_speed"])
            updated.append("forward_speed={}".format(self._forward_speed))
        if "cm_per_second" in kwargs:
            self._cm_per_second = float(kwargs["cm_per_second"])
            updated.append("cm_per_second={}".format(self._cm_per_second))
        if "step_duration" in kwargs:
            self._step_duration = float(kwargs["step_duration"])
            updated.append("step_duration={}".format(self._step_duration))
        if "pause_duration" in kwargs:
            self._pause_duration = float(kwargs["pause_duration"])
            updated.append("pause_duration={}".format(self._pause_duration))

        if "corner_slowdown_factor" in kwargs:
            self._corner_slowdown_factor = float(kwargs["corner_slowdown_factor"])
            updated.append("corner_slowdown_factor={}".format(self._corner_slowdown_factor))
        if "turn_min_area" in kwargs:
            self._turn_min_area = int(kwargs["turn_min_area"])
            updated.append("turn_min_area={}".format(self._turn_min_area))
        if "step_by_step_mode" in kwargs:
            self._step_by_step_mode = bool(int(kwargs["step_by_step_mode"]))
            updated.append("step_by_step_mode={}".format(self._step_by_step_mode))
        if updated:
            print("[CIRCUIT_FSM] Params mis à jour: {}".format(", ".join(updated)))
