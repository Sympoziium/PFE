#!/usr/bin/env python
# -*- coding: utf-8 -*-
# server_controller.py
# ------------------
"""Contrôleur backend pour les routes Flask.

    Centralise la logique des endpoints; `flask_router.py` ne fait que lier les routes
    à ces méthodes.
"""

import requests  # <--- IMPORTANT : Pour communiquer avec le pont
import os, uuid, time, cv2, itertools, numpy as np
import json

from flask import Flask, Response, request, jsonify, send_from_directory, url_for


from interface.onglet_acceuil import render_accueil_tab
from interface.onglet_control import render_control_tab
from interface.onglet_vision import render_vision_tab
from interface.onglet_pid import render_pid_tab
from interface.onglet_template import render_template_tab  # Exemple d'onglet template générique
from core.control.legacy.line_following_pid import PIDController
from core.control.legacy.line_following_state_machine import StepByStepStateMachine
from core.control.control_manager import ControlManager
from core.control.controlers.manual_controller import ManualController
from core.control.IO_drivers.motor_command import MotorCommand
from core.control.IO_drivers.sensor_driver import SensorDriver # test du nouveau driver de capteurs
from core.control.IO_drivers.motor_command import CommandType
from core.vision.vision_adapter import VisionAdapter

# --- Fonction helper pour formater les résultats de détection ---
def format_detection_result(results, detector_name="Détecteur"):
    """
    Formate les résultats de détection pour un affichage lisible dans les logs.

    Supporte le format standardisé (clé 'detections') ainsi que les
    anciens formats legacy ('detection_box', 'Object coordinates', etc.).

    Args:
        results (dict): Résultats de détection du détecteur
        detector_name (str): Nom du détecteur

    Returns:
        str: Résultats formatés pour affichage
    """
    lines = []
    lines.append('=' * 60)
    lines.append('RÉSULTATS DE DÉTECTION - {}'.format(detector_name))
    lines.append('=' * 60)

    # Détection générale
    detected = results.get('Object_detected', False)
    lines.append('Objet détecté: {}'.format('OUI' if detected else 'NON'))

    # --- Format standardisé : liste 'detections' ---
    detections = results.get('detections', [])
    if detections:
        lines.append('Nombre de détections: {}'.format(len(detections)))
        for i, det in enumerate(detections):
            bbox = det.get('detection_box')
            label = det.get('object', '?')
            conf = det.get('confidence', '?')
            if bbox and len(bbox) == 4:
                x, y, w, h = bbox
                line = '  #{} [{}]: pos=({},{}) taille={}x{} aire={}'.format(
                    i + 1, label, int(x), int(y), int(w), int(h), int(w) * int(h))
                if conf is not None and conf != '?':
                    line += ' conf={:.1%}'.format(float(conf))
                lines.append(line)
    else:
        # Fallback legacy (pour diagnostic ou ancien code)
        bbox = results.get('detection_box') or results.get('Object coordinates')
        if bbox:
            if len(bbox) == 4:
                x, y, w, h = bbox
                lines.append('Position: x={}, y={}'.format(int(x), int(y)))
                lines.append('Taille: largeur={}, hauteur={}'.format(int(w), int(h)))

        conf = results.get('confidence')
        if conf is not None and conf > 0:
            lines.append('Confiance: {:.1%}'.format(float(conf)))

        area = results.get('area')
        if area is not None and area > 0:
            lines.append('Aire du contour: {} pixels'.format(int(area)))

    # Temps de traitement
    proc_time = results.get('Processing time')
    if proc_time:
        lines.append('Temps de traitement: {:.3f}s'.format(float(proc_time)))

    # Logs du détecteur (si disponibles)
    logs = results.get('logs')
    if logs and len(logs) > 0:
        lines.append('')
        lines.append('--- Détails du traitement ---')
        for log in logs:
            lines.append(log)

    # Erreurs
    error = results.get('error')
    if error:
        lines.append('')
        lines.append('ERREUR: {}'.format(error))
        details = results.get('details')
        if details:
            lines.append('Détails: {}'.format(details))

    lines.append('=' * 60)
    return '\n'.join(lines)


# --- Constantes de contrôle importées depuis robot_zumi (source unique) ---
from core.robot.robot_zumi import (
    DRIVE_SPEED_DEFAULT, TURN_SPEED_DEFAULT,
    CAMERA_PROFILES, BATTERY_VOLTAGE_MAX, BATTERY_VOLTAGE_MIN
)
# Alias pour compatibilité avec le code existant
DRIVE_SPEED = DRIVE_SPEED_DEFAULT
TURN_SPEED = TURN_SPEED_DEFAULT
WATCHDOG_TIMEOUT_SECONDS = 0.8

class controller:
    def __init__(self, zumi, debug=False):
        self.app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        self.robot = zumi
        self.vision_pipeline = None
        self.control_manager = None  # Initialisé via attach_control_manager()
        self.last_move_time = time.time()
        self.debug = debug
        self.watchdog_active = False
        self.livefeed_fps = 30
        # Rétro-compatibilité : pid_controller local utilisé seulement
        # quand aucun ControlManager n'est attaché.
        self.pid_controller = PIDController()
        self.pid_active = False
        self.pid_thread = None
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        # Mode step-by-step (rétro-compatibilité)
        self.step_machine = None
        self.step_mode_active = False
        self.step_mode_thread = None
        # Dossier pour sauvegarder les captures d'images
        self.CAPTURE_DIR = os.path.join(self.app.static_folder, 'captured_images')
        os.makedirs(self.CAPTURE_DIR, exist_ok=True)
        # Échantillonnage des données des capteurs
        self.debug_control_sampling = False  # Désactivé par défaut pour réduire l'overhead CPU
        self.sampling_active = False
        self.sampling_vectors = [] # Vecteurs d'entrées (NDJSON)
        self.sampling_labels = []  # Vecteurs labels (NDJSON)
        self.sampling_zeroed_groups = set()  # Groupes de features forcés à 0 pendant l'échantillonnage
        self._ml_classes = []
        self._last_debug_print_time = 0.0  # Throttle du debug à ~3 Hz
        self.manual_drive_speed = DRIVE_SPEED
        self.manual_turn_speed = TURN_SPEED
        self.last_action = None  # Pour mémoriser la dernière action de contrôle (pour le sampling)
        self.battery_level = None  # Niveau de batterie (si disponible via SensorDriver)
        
        # --- CONFIGURATION DU PONT ---
        # ⚠️ REMPLACE CECI PAR L'IP QUE TON ARDUINO A AFFICHÉE
        self.BRIDGE_IP = "192.168.0.218" 
        self.BRIDGE_URL = "http://{}".format(self.BRIDGE_IP)
        # Index du détecteur sélectionné côté serveur
        self.selected_detector_index = 0
        # Dernière image capturée (nom de fichier) pour la détection à la demande
        self.last_captured_filename = None
        # Overlay FSM dans le flux vidéo : activé seulement depuis l'onglet contrôle FSM
        self.fsm_overlay_enabled = False

    def attach_pipeline_vision(self, pipeline):
        pipeline.attach_capture_dir(self.CAPTURE_DIR)
        self.vision_pipeline = pipeline
        self.vision_pipeline.debug = self.debug
        self._ml_classes = self._infer_ml_classes()

    def attach_control_manager(self, control_manager):
        """Attache le ControlManager (orchestrateur de contrôle)."""
        self.control_manager = control_manager

        # --- Enregistrement du contrôleur manuel ---
        # Si le contrôleur manuel n'est pas encore enregistré dans le ControlManager, on le fait ici.
        if "manual_controller" not in self.control_manager._controllers:
            self.control_manager.register_controller("manual_controller", ManualController(default_speed=self.manual_drive_speed))

        # Hook pour l'échantillonnage de données synchronisé avec la boucle de contrôle
        self.control_manager.set_sampling_callback(self._sampling_callback)

    # --- Navigation ---
    def home(self):
        return render_accueil_tab("Accueil")

    def vision(self):
        return render_vision_tab("Vision du Zumi")

    def onglet_template(self):
        return render_template_tab("Template")
    
    def onglet_control(self):
        return render_control_tab("Contrôle du Zumi")
    
    def pid_page(self):
        return render_pid_tab("Asservissement PID")
    
    # --- Système ---
    def exit_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None: return jsonify({"error": "shutdown unavailable"}), 500
        func()
        return ('', 204)
    
    def Log_watchdog(self):
        """
        Thread qui s'exécute en arrière-plan.
        Gère les logs ressources système.
        Note: L'échantillonnage est maintenant synchronisé dans _sampling_callback via ControlManager.
        Le watchdog moteur est géré par le ManualController.
        """
        print("[Watchdog] Démarré.")
        iteration_count = 0

        while True:
            iteration_count += 1

            # --- Logs du controleur actif toutes les 3 secondes (6 itérations * 0.5s) ---
            if self.control_manager and iteration_count % 6 == 0:
                active = self.control_manager._active_controller
                if active:
                    print(f"[Watchdog] Contrôleur actif: {active.name}")
                    if hasattr(active, 'get_debug_info'):
                        debug_info = active.get_debug_info()
                        print(f"[Watchdog] {active.name}: {json.dumps(debug_info, indent=2)}")

            # --- Logs des ressources système toutes les 20 secondes (40 itérations * 0.5s) ---
            if iteration_count % 40 == 0:
                self._log_resource_usage_internal()

            time.sleep(0.5)

    def _sampling_callback(self, state, command):
        """
        Callback synchronisé avec la boucle de contrôle (appelé à chaque tick).

        Échantillonne quand sampling_active est True ET qu'un contrôleur est actif.
        Le command reçu est la sortie de step() = commande POST-PID.

        Filtre les samples idle (0,0 prolongés) pour éviter de bruiter le dataset
        avec des échantillons sans mouvement. Les premiers samples d'arrêt après
        un mouvement sont conservés (arrêt intentionnel).
        """
        if not self.sampling_active:
            return

        active = self.control_manager._active_controller
        if active is None:
            return

        # Filtrer l'idle prolongé: garder max 10 samples consécutifs à (0,0)
        # pour représenter un arrêt intentionnel sans flood le dataset
        is_stop = (command.left_speed == 0 and command.right_speed == 0)
        if is_stop:
            if not hasattr(self, '_consecutive_stop_samples'):
                self._consecutive_stop_samples = 0
            self._consecutive_stop_samples += 1
            if self._consecutive_stop_samples > 10:
                return  # Skip l'idle prolongé
        else:
            self._consecutive_stop_samples = 0

        try:
            adapter = self._get_ml_adapter(state)
            vector = self._vectorize_state_with_adapter(state, adapter)
            label = adapter.encode_label(
                command.left_speed, command.right_speed
            ).tolist()

            if vector is None or label is None:
                return

            import numpy as np
            v_array = np.array(vector)
            l_array = np.array(label)
            v_array = self._apply_sampling_kill(v_array, adapter)

            if adapter.validate_state_vector(v_array) and adapter.validate_label_vector(l_array):
                self.sampling_vectors.append(v_array.tolist())
                self.sampling_labels.append(label)
        except Exception as e:
            print("[Sampling] Erreur callback contrôleur auto: {}".format(e))

# ----------------------------------------------------------------------------
#            Fonctions de callback pour les actions de vision
# ----------------------------------------------------------------------------

    # Téléchargement d'une image capturée
    def download_image(self, filename):
        return send_from_directory(self.CAPTURE_DIR, filename, as_attachment=True)

    def capture_image(self):
        vp = self.vision_pipeline
        if vp is None or not vp.is_running():
            return jsonify({'error': 'camera not running'}), 400

        # Récupération de l'image actuelle sans ré-entrer dans le générateur
        # Si le flux vidéo tourne, on utilise le dernier frame mis en buffer.
        frame = vp.get_last_frame()
        if frame is None:
            return jsonify({'error': 'Activer la camera car le flux est pas encore disponible'}), 400

        frame_to_save = frame.copy()  # Toujours en BGR

        # Génération d'un nom de fichier unique
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = '{}_{}.jpg'.format(ts, uuid.uuid4().hex[:6])
        save_path = os.path.join(self.CAPTURE_DIR, filename)

        # Sauvegarde directe en BGR (format natif OpenCV)
        ok = cv2.imwrite(save_path, frame_to_save)
        if not ok:
            return jsonify({'error': 'write failed'}), 500

        # URL de téléchargement
        file_url = url_for('static', filename='captured_images/{}'.format(filename))
        download_url = '/download_image/{}'.format(filename)
        # Mémoriser la dernière image capturée pour une détection à la demande
        self.last_captured_filename = filename
        return jsonify({'filename': filename, 'file_url': file_url, 'download_url': download_url})

    # SUPPRIMÉ: capture_image_hires() - utiliser set_resolution() pour changer la résolution caméra

    def status(self):
        vp = self.vision_pipeline
        return jsonify({"camera_running": bool(vp and vp.is_running())})

    # Liste des détecteurs disponibles + index sélectionné
    def detectors(self):
        vp = self.vision_pipeline
        detectors_info = []
        selected = self.selected_detector_index
        if vp:
            try:
                for i, det in enumerate(vp.get_detectors()):
                    # Nom lisible du détecteur
                    name = det.name if hasattr(det, 'name') else str(det)
                    detectors_info.append({"index": i, "name": name})
                # Clamp de l'index sélectionné si hors bornes
                if len(detectors_info) == 0:
                    selected = -1
                else:
                    selected = max(0, min(selected, len(detectors_info) - 1))
                    self.selected_detector_index = selected
            except Exception:
                pass
        return jsonify({"detectors": detectors_info, "selected": selected})

    # Sélectionner le détecteur actif
    def set_detector(self):
        vp = self.vision_pipeline
        data = request.get_json(silent=True) or request.form or {}
        try:
            idx = data.get('index')
            if idx is None:
                idx = data.get('detector_index')
            if idx is None:
                return jsonify({"error": "index manquant"}), 400
            idx = int(idx)
        except Exception:
            return jsonify({"error": "index invalide"}), 400

        if not vp or idx < 0 or idx >= len(vp.get_detectors()):
            return jsonify({"error": "index hors bornes"}), 400

        self.selected_detector_index = idx
        return ('', 204)

    # Exécuter la détection sur la dernière image capturée
    def run_detection(self):
        """
        Exécute le détecteur sélectionné sur la dernière image capturée.
        Le détecteur retourne les données de détection, puis le contrôleur
        se charge de l'annotation et de la sauvegarde de l'image annotée.
        """
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'Video pipeline not initialized'}), 400

        # Récupérer l'image capturée la plus récente depuis le disque
        filename = getattr(self, 'last_captured_filename', None)
        if not filename:
            return jsonify({'error': 'no captured image available. Please capture an image first.'}), 400

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return jsonify({'error': 'last captured image not found on server'}), 404

        try:
            # Charger l'image en BGR pour la détection
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return jsonify({'error': 'failed to read captured image'}), 500

            results = vp.process_frame(frame_bgr, detector_index=self.selected_detector_index, filename=filename)

            # Afficher les résultats formatés dans les logs
            detector_name = vp.get_detectors()[self.selected_detector_index].name if hasattr(vp.get_detectors()[self.selected_detector_index], 'name') else 'Unknown'
            print(format_detection_result(results, detector_name))

            # --- Annotation centralisée ---
            detections = results.get('detections', [])
            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            annotated_url = None

            if detections:
                ann_name, ann_rel_url = vp.save_annotated_image(frame_bgr, detections, filename)
                if ann_rel_url:
                    annotated_url = url_for('static', filename=ann_rel_url)
            elif results.get('Object_detected'):
                # Détecteurs spécialisés (ex. LineDetector) sans bboxes standard
                from core.vision.vision_pipeline import VisionPipeline
                detector = vp.get_detectors()[self.selected_detector_index]
                annotated, _ = VisionPipeline.annotate_detection_result(frame_bgr, detector, approximate_distance=True, detection_result = results)
                base, ext = os.path.splitext(filename)
                ann_name = '{}_det_{}{}'.format(base, uuid.uuid4().hex[:6], ext or '.jpg')
                cv2.imwrite(os.path.join(self.CAPTURE_DIR, ann_name), annotated)
                annotated_url = url_for('static', filename='captured_images/{}'.format(ann_name))

            # Construire le payload pour le frontend
            # On extrait la plus grande bbox comme détection principale (indicateur UI)
            best_box = None
            best_area = 0
            for det in detections:
                bbox = det.get('detection_box')
                if bbox and len(bbox) == 4:
                    a = int(bbox[2]) * int(bbox[3])
                    if a > best_area:
                        best_area = a
                        best_box = bbox

            payload = {
                'Object_detected': results.get('Object_detected', False),
                'detection_box': best_box,
                'detections': detections,
                'confidence': 1.0 if detections else 0.0,
                'area': best_area if best_area > 0 else None,
                'logs': results.get('logs', []),
                'source_filename': filename,
                'source_file_url': source_url,
                'annotated_url': annotated_url,
                'Processing time': results.get('Processing time'),
            }

            return jsonify(payload)
        except IndexError:
            return jsonify({'error': 'invalid detector index'}), 400
        except Exception as e:
            return jsonify({'error': 'processing failed', 'details': str(e)}), 500

    # Diagnostic générique: appelle la méthode diagnostique_detecteur() du détecteur sélectionné
    def diagnose_detector(self):
        """Route générique pour diagnostiquer n'importe quel détecteur.
        Délègue l'opération au détecteur actuellement sélectionné via son index."""

        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'Video pipeline not initialized'}), 400

        filename = getattr(self, 'last_captured_filename', None)
        if not filename:
            return jsonify({'error': 'no captured image available. Please capture an image first.'}), 400

        try:
            diagnostic = vp.get_current_detector_diagnostic(filename=filename, detector_index=self.selected_detector_index)

            # Afficher les résultats formatés dans les logs
            detector_name = vp.get_detectors()[self.selected_detector_index].name if hasattr(vp.get_detectors()[self.selected_detector_index], 'name') else 'Unknown'
            print(format_detection_result(diagnostic, detector_name + ' (Diagnostic)'))

            return jsonify(diagnostic)
        except Exception as e:
            print("Erreur lors du diagnostic: {}".format(str(e)))
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'diagnose_detector failed', 'details': str(e)}), 500

    def set_livefeed_fps(self, fps=None):
        """Met à jour le framerate du flux vidéo en direct.
        
        Le FPS est contrôlé par le sleep_time dans la boucle du générateur vidéo.
        Pas besoin de toucher à la caméra — la valeur est lue dynamiquement à chaque itération.
        """
        if fps is None:
            data = request.get_json(silent=True) or {}
            fps = data.get('fps')
        try:
            fps = int(fps)
            if fps < 1 or fps > 60:
                return jsonify({'error': 'FPS doit être entre 1 et 60'}), 400
            self.livefeed_fps = fps
            print("FPS du flux vidéo mis à jour: {} FPS".format(self.livefeed_fps))
            return jsonify({'ok': True, 'fps': fps})
        except (ValueError, TypeError):
            return jsonify({'error': 'FPS doit être un entier valide'}), 400
        
    # Flux vidéo
    def video_feed(self):
        vp = self.vision_pipeline
        if not vp or not vp.is_running(): return "Camera OFF", 503
        
        overlay_mode = request.args.get('overlay', '')
        
        def generate():
            frame_counter  = 0
            previous_distance = None
            
            while vp.is_running():
                try:
                    frame_bgr = vp.camera.capture()
                    if frame_bgr is None:
                        time.sleep(0.1)
                        continue
                    vp.update_last_frame(frame_bgr)
                except Exception:
                    time.sleep(0.1)
                    continue

                # --- Déclencher la détection passive selon detection_rate ---
                if vp._passive_running:
                    frame_counter += 1
                    if frame_counter % vp._detection_rate == 0:
                        vp._detection_trigger.set()  # signal au thread de détection

                # --- Overlay FSM (zones + état) : actif seulement si activé depuis l'onglet contrôle ---
                display_frame = frame_bgr

                if self.fsm_overlay_enabled:
                    # Trouver le contrôleur circuit_fsm actif
                    fsm_ctrl = None
                    if self.control_manager and self.control_manager._active_controller:
                        ctrl = self.control_manager._active_controller
                        if ctrl.name == "circuit_fsm":
                            fsm_ctrl = ctrl

                    # Trouver le LineDetector dans le pipeline
                    line_det = None
                    if vp:
                        for det in vp.get_detectors():
                            if getattr(det, 'name', '') == 'line':
                                line_det = det
                                break

                    if line_det is not None:
                        try:
                            # Exécuter la détection multi-zones sur chaque frame
                            zones_result = line_det.process_zones(frame_bgr.copy())
                            display_frame = line_det.annotate_zones(frame_bgr.copy(), zones_result)

                            if fsm_ctrl is not None:
                                # Ajouter l'état FSM en overlay
                                fsm_debug = fsm_ctrl.get_debug_info()
                                fsm_text = "FSM: {} | {}".format(
                                    fsm_debug.get('fsm_state', '?'),
                                    fsm_debug.get('last_decision', '?'))
                                cv2.putText(display_frame, fsm_text,
                                            (10, display_frame.shape[0] - 10),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
                                # Indicateur mode pas-à-pas
                                if fsm_debug.get('step_by_step_mode'):
                                    step_text = "PAS-A-PAS: {}".format(
                                        "EN ATTENTE" if fsm_debug.get('fsm_state') == 'ATTENTE_STEP' else "ACTIF")
                                    cv2.putText(display_frame, step_text,
                                                (10, display_frame.shape[0] - 30),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1)
                        except Exception as e:
                            if self.debug:
                                print("[VideoFeed] Erreur overlay zones: {}".format(e))
                elif overlay_mode == 'pid' or getattr(self, 'pid_active', False) or getattr(self, 'step_mode_active', False):
                    # Overlay spécifique pour l'onglet PID et tuning
                    line_det = self._get_line_detector()
                    if line_det is not None:
                        try:
                            # Si le PID n'est pas actif (tuning à l'arrêt), on force process() 
                            # pour avoir les données d'annotation actuelles pour affichage
                            if not getattr(self, 'pid_active', False) and not getattr(self, 'step_mode_active', False):
                                line_det.process(frame_bgr.copy())
                            display_frame = line_det.annotate_detection(frame_bgr.copy())
                            
                            # Texte overlay
                            mode_str = "ROTATION" if self.pid_controller.rotation_mode else "AVANCE"
                            cv2.putText(display_frame, f"PID TUNING : {mode_str}", (10, 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        except Exception as e:
                            if self.debug:
                                print("[VideoFeed] Erreur overlay PID: {}".format(e))

                # --- Overlay détection passive sur la frame d'affichage ---
                if vp._passive_running:
                    result = vp.get_last_detection_result()
                    now = time.time()

                    # vérifier que la détection est récente (ex: dans les 2-5 dernières Frames)
                    max_age = (vp._detection_rate / self.livefeed_fps) * 2
                    result_age = now - result.get('timestamp', 0) if result else float('inf')

                    # On annote seulement si la détection est récente pour éviter d'afficher des résultats obsolètes
                    if result and result.get('Object_detected') and result_age <= max_age:
                        # Calcul de distance seulement toutes les 3 frames pour économiser le CPU
                        if frame_counter % 3 == 0:
                            display_frame, previous_distance = self._draw_passive_overlay(
                                frame_bgr.copy(), result,
                                approximate_distance=True,
                                previous_distance=previous_distance,
                                debug=self.debug
                            )
                        else:
                            display_frame, _ = self._draw_passive_overlay(
                                frame_bgr.copy(), result,
                                approximate_distance=False,
                                previous_distance=previous_distance,
                                debug=self.debug
                            )

                # Encodage direct en JPEG depuis BGR
                ret, jpeg = cv2.imencode('.jpg', display_frame)
                if not ret:
                    continue
                yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                
                time.sleep(1.0 / self.livefeed_fps)

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    def set_fsm_overlay(self):
        """Active ou désactive l'overlay FSM dans le flux vidéo.
        
        Appelé par l'onglet contrôle quand le contrôleur circuit_fsm est sélectionné
        dans la vue control. Les autres onglets ne touchent jamais à ce flag.
        
        Body JSON: {"enabled": true|false}
        """
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get('enabled', False))
        self.fsm_overlay_enabled = enabled
        print("[ServerController] FSM overlay: {}".format("activé" if enabled else "désactivé"))
        return ('', 204)

    def _draw_passive_overlay(self, frame, result, approximate_distance=False, previous_distance=None, debug=False):

        """
        Dessine les bounding boxes et labels de la détection passive
        directement sur *frame* (qui doit être une copie).

        Utilise VisionPipeline.annotate_detection_result() pour gérer tous les types
        de détecteurs (standard avec bboxes et spécialisés comme LineDetector).

        :param frame: image BGR (copie) sur laquelle dessiner.
        :param result: dict retourné par process_passive() du détecteur.
        :param approximate_distance: Si True, calcule distance pour objets bbox.
        :param previous_distance: Distance précédente (pour stabilité).
        :param debug: Mode debug.
        :return: (frame annotée, distance_cm)
        """
        from core.vision.vision_pipeline import VisionPipeline
        
        # Obtenir le détecteur associé au résultat
        # NOTE: _passive_detection_loop stocke str(detector) (repr Python), pas det.name
        vp = self.vision_pipeline
        detector = None
        for det in vp._passive_detectors:
            if str(det) == result.get('Detector', ''):
                detector = det
                break

        # Fallback: si un seul détecteur passif, l'utiliser directement
        if detector is None and len(vp._passive_detectors) == 1:
            detector = vp._passive_detectors[0]

        # Utiliser la nouvelle méthode générique d'annotation
        if detector:
            annotated, distance_cm = VisionPipeline.annotate_detection_result(
                frame, 
                detector, 
                result,
                approximate_distance=approximate_distance,
                previous_distance=previous_distance,
                debug=debug
            )
        else:
            # Fallback: utiliser ancienne méthode si pas de détecteur
            detections = result.get('detections', [])
            if not detections:
                return frame, previous_distance
            annotated, distance_cm = VisionPipeline.annotate_frame(
                frame, 
                detections, 
                approximate_distance=approximate_distance, 
                previous_distance=previous_distance, 
                debug=debug
            )
        
        return annotated, distance_cm
    
    def approximate_object_distance(self):
        """
        Fonction servant a approximer la distance du robot à l'objet détecté en utilisant la taille de la bounding box.
        """

    def _log_resource_usage_internal(self):
        """
        Helper interne: Log LÉGER des ressources du Pi (appelé par Log_watchdog toutes les 5s).
        Optimisé pour Pi Zero V1 - zéro overhead, directement dans stdout du serveur.
        """
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking
            ram = psutil.virtual_memory()
            num_threads = psutil.Process().num_threads()
            ram_used_mb = round(ram.used / (1024 * 1024), 1)
            ram_free_mb = round(ram.available / (1024 * 1024), 1)
            ram_total_mb = round(ram.total / (1024 * 1024), 1)
            io_wait = psutil.Process().cpu_times().iowait if hasattr(psutil.Process().cpu_times(), 'iowait') else 0
            # Format compact pour vision rapide dans le terminal
            print("\n" + "-" * 60)
            print("[Zumi] CPU: {:.1f}% | RAM: {:.1f}% | Threads: {}".format(
                cpu_percent, ram.percent, num_threads))
            print("[RAM] {:.1f} MB used | {:.1f} MB free | {:.1f} MB total | IO Wait: {:.2f}s".format(
                ram_used_mb, ram_free_mb, ram_total_mb, io_wait))
            print("[Timestamp] {}".format(time.strftime('%H:%M:%S')))
            # Battery level
            if self.robot and hasattr(self.robot, 'get_battery_voltage'):
                try:
                    raw_voltage = self.robot.get_battery_voltage()
                    
                    # Initialisation au premier appel
                    if getattr(self, 'battery_ema', None) is None:
                        self.battery_ema = raw_voltage
                    else:
                        # Calcul EMA : (nouvelle_lecture * alpha) + (ancienne_moyenne * (1 - alpha))
                        # Alpha = 0.2 (20% de la nouvelle valeur, 80% de l'ancienne)
                        alpha = 0.15
                        self.battery_ema = (raw_voltage * alpha) + (self.battery_ema * (1.0 - alpha))
                    
                    # Arrondi pour un affichage propre
                    smoothed_voltage = round(self.battery_ema, 3)
                    
                    # Calcul sur la tension lissée
                    battery_percent = max(0, min(100, int((smoothed_voltage - BATTERY_VOLTAGE_MIN) / (BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN) * 100)))
                    print("[Battery] Level: {}V ({:.1f}%)".format(smoothed_voltage, battery_percent))
                except Exception as e:
                    print("[Battery] Error reading battery level: {}".format(e))
        except Exception as e:
            pass  # Silencieux si psutil indisponible

    def get_resource_usage(self):
        """
        Route HTTP GET pour obtenir les stats ressources à la demande (JSON).
        Peut être appelée avec: curl http://localhost:5000/resource_usage
        ou en polling continu: watch -n 5 'curl http://localhost:5000/resource_usage'
        """
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            num_threads = psutil.Process().num_threads()
            return jsonify({
                'cpu_percent': round(cpu_percent, 1),
                'ram_percent': round(ram.percent, 1),
                'ram_used_mb': round(ram.used / (1024 * 1024), 1),
                'ram_available_mb': round(ram.available / (1024 * 1024), 1),
                'num_threads': num_threads,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Caméra: stop/start
    def close_camera(self):
        if self.vision_pipeline: self.vision_pipeline.stop()
        return ("", 204)

    def start_camera(self):
        if self.vision_pipeline: self.vision_pipeline.start()
        return ("", 204)

    def set_resolution(self):
        """Change la résolution de la caméra (QCIF / QVGA / VGA).

        Le JS envoie un JSON {width, height}. On ferme la caméra,
        on recrée l'instance à la nouvelle résolution, et on relance
        le flux si celui-ci était actif.
        """
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline not initialized'}), 400

        data = request.get_json(silent=True) or {}
        try:
            w = int(data.get('width', 320))
            h = int(data.get('height', 240))
        except (TypeError, ValueError):
            return jsonify({'error': 'invalid width/height'}), 400

        was_running = vp.is_running()
        was_passive = vp._passive_running

        # Arrêter la détection passive avant de toucher à la caméra
        if was_passive:
            vp.pause_passive_detection()

        # Arrêter le flux vidéo
        if was_running:
            vp.stop()
            time.sleep(0.2)

        try:
            vp.change_camera_resolution(w, h)
        except Exception as e:
            return jsonify({'error': 'resolution change failed', 'details': str(e)}), 500

        # Relancer le flux si il était actif
        if was_running:
            vp.start()

        # Reprendre la détection passive si elle était active
        if was_passive:
            vp.resume_passive_detection()

        return jsonify({'ok': True, 'resolution': '{}x{}'.format(w, h)})

    def _apply_camera_profile(self, profile_name):
        """Applique un profil de caméra (résolution) de façon transparente.

        Utilisé automatiquement lors de l'activation/désactivation des contrôleurs
        pour optimiser les ressources CPU selon le mode actif.

        Args:
            profile_name: 'passive' (320x240) ou 'stream' (640x480)
        """
        if profile_name not in CAMERA_PROFILES:
            print("[ServerController] Profil caméra inconnu: {}".format(profile_name))
            return

        vp = self.vision_pipeline
        if vp is None:
            return

        profile = CAMERA_PROFILES[profile_name]
        w, h, fps = profile['width'], profile['height'], profile['fps']

        # Vérifier si on est déjà à cette résolution (éviter changement inutile)
        if hasattr(vp, 'camera') and vp.camera is not None:
            current_w = getattr(vp.camera, '_width', None)
            current_h = getattr(vp.camera, '_height', None)
            if current_w == w and current_h == h:
                return  # Déjà à la bonne résolution

        was_running = vp.is_running()
        was_passive = vp._passive_running

        if was_passive:
            vp.pause_passive_detection()
        if was_running:
            vp.stop()
            time.sleep(0.2)

        try:
            vp.set_passive_detection_FPS(1) # on souhaite trigger la détection sur chaque frame du livefeed
            self.set_livefeed_fps(fps) # mettre à jour le FPS du livefeed pour correspondre au profil
            vp.change_camera_resolution(w, h)
            print("[ServerController] Profil caméra '{}' Résolution appliqué: {}x{} @ {} FPS".format(profile_name, w, h, fps))
        except Exception as e:
            print("[ServerController] Erreur changement profil caméra: {}".format(e))

        if was_running:
            vp.start()
        if was_passive:
            vp.resume_passive_detection()

# ----------------------------------------------------------------------------
#          Fonctions de callback pour les actions moteur du robot
# ----------------------------------------------------------------------------
    def start_passive_detection(self):
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline vision non initialisé'}), 400
        if vp._passive_running: # éviter de lancer plusieurs fois le mode passif
            return ("", 204)

        # Si pas de contrôleur actif → mode Vision → Haar classifiers seulement
        # Si contrôleur actif → Line detector déjà configuré par start_controller()
        if hasattr(vp, 'set_passive_detectors'):
            is_controller_active = (self.control_manager is not None
                                    and self.control_manager._active_controller is not None)
            if not is_controller_active:
                haar_dets = [d for d in vp.detectors if getattr(d, 'name', '') != 'line']
                vp.set_passive_detectors(haar_dets)

        vp.start_passive_detection()
        return ("", 204)
    
    def stop_passive_detection(self):
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline vision non initialisé'}), 400
        if not vp._passive_running:
            return ("", 204)
        vp.stop_passive_detection()
        return ("", 204)
    
    def pause_passive_detection(self):
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline vision non initialisé'}), 400
        if not vp._passive_running:
            return ("", 204)
        vp.pause_passive_detection()
        return ("", 204)
    
    def resume_passive_detection(self):
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline vision non initialisé'}), 400
        if vp._passive_running:
            return ("", 204)
        vp.resume_passive_detection()
        return ("", 204)
    
    def set_passive_detection_rate(self, detection_rate=None):
        if detection_rate is None:
            data = request.get_json(silent=True) or {}
            detection_rate = data.get('detection_rate')
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline vision non initialisé'}), 400
        try:
            detection_rate = int(detection_rate)
            if detection_rate < 1 or detection_rate > 60:
                return jsonify({'error': 'detection_rate doit être supérieur a 0 (ex: 1 = une détection par image du livefeed)'}), 400
            vp.set_passive_detection_FPS(detection_rate)
            return jsonify({'ok': True, 'detection_rate': detection_rate})
        except (ValueError, TypeError):
            return jsonify({'error': 'detection_rate doit être un entier valide'}), 400
    
    def get_passive_detection(self):
        """
        Retourne le dernier résultat de détection passive.
        Route appelable en polling depuis le JS (ex: toutes les 2s).
        """
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline not initialized'}), 400
        result = vp.get_last_detection_result()
        if result is None:
            return jsonify({'Object_detected': False, 'detections': [], 'ready': False})
        return jsonify({**result, 'ready': True})

# ----------------------------------------------------------------------------
#          Hard Positive Mining
# ----------------------------------------------------------------------------
    def toggle_mining(self):
        """Active ou désactive le hard positive mining."""
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline not initialized'}), 400

        data = request.get_json(silent=True) or {}
        enable = data.get('enable', True)

        if enable:
            vp.enable_mining()
        else:
            vp.disable_mining()

        stats = vp.get_mining_stats()
        return jsonify(stats)

    def mining_stats(self):
        """Retourne les statistiques courantes du mining."""
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline not initialized'}), 400
        return jsonify(vp.get_mining_stats())

    def download_mining_crops(self):
        """
        Crée un ZIP de tous les crops minés et l'envoie au client.
        Après le téléchargement, supprime les crops du robot.
        """
        import zipfile
        import io

        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline not initialized'}), 400

        files = vp.collect_mining_crops()
        if not files:
            return jsonify({'error': 'no crops to download'}), 404

        # Construire le ZIP en mémoire
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fpath in files:
                arcname = os.path.basename(fpath)
                zf.write(fpath, arcname)
        buf.seek(0)

        # Supprimer les crops du robot après création du ZIP
        vp.clear_mining_crops()

        ts = time.strftime('%Y%m%d_%H%M%S')
        zip_name = 'mining_crops_{}.zip'.format(ts)

        return Response(
            buf.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': 'attachment; filename={}'.format(zip_name)
            }
        )
# ----------------------------------------------------------------------------
#          Fonctions de callback pour les actions moteur du robot
# ----------------------------------------------------------------------------
    
    def _dispatch_manual_action(self, action, speed=DRIVE_SPEED):
        """Délègue la commande de mouvement au ManualController via l'orchestrateur.

        Si un contrôleur automatique (PID, etc.) est actif, utilise l'override
        temporaire pour envoyer les commandes moteur sans changer de contrôleur.
        Quand les touches sont relâchées, le contrôleur actif reprend automatiquement.

        Si aucun contrôleur n'est actif, active le contrôleur manuel normalement.
        """
        if not self.control_manager:
            return "ControlManager missing"

        if self.control_manager.get_controller("manual_controller") is None:
            return "Manual controller missing"

        active = self.control_manager._active_controller

        # --- Override temporaire si un contrôleur auto est actif ---
        if active and active.name != "manual_controller":
            if action == "stop":
                # Relâchement des touches : annuler l'override, le contrôleur reprend
                self.control_manager.clear_manual_override()
                return "ok"

            # Calculer la commande moteur et l'injecter en override
            from core.control.controlers.manual_controller import _ACTION_MAP
            throttle, steering = _ACTION_MAP.get(action, (0, 0))
            left, right = ManualController.compute_speeds(
                throttle, steering, speed, speed)
            self.control_manager.set_manual_override(
                MotorCommand.make_speed(left, right))

            if self.sampling_active and action in ("forward", "left", "right", "reverse"):
                self._sample_on_command(action, speed)
            return "ok"

        # --- Pas de contrôleur actif : commande directe avec PID de cap ---
        if not active:
            from core.control.controlers.manual_controller import _ACTION_MAP
            throttle, steering = _ACTION_MAP.get(action, (0, 0))
            if action == "stop" or (throttle == 0 and steering == 0):
                self.robot.stop()
                ctrl = self.control_manager.get_controller("manual_controller")
                if ctrl:
                    ctrl._heading_hold_active = False
            else:
                left, right = ManualController.compute_speeds(
                    throttle, steering, speed, speed)
                # Appliquer le PID de cap si on avance tout droit
                ctrl = self.control_manager.get_controller("manual_controller")
                if ctrl and throttle != 0 and steering == 0:
                    state = self.control_manager.get_last_sensor_data()
                    left, right = ctrl.apply_heading_correction(state, left, right)
                elif ctrl and steering != 0:
                    ctrl._heading_hold_active = False
                self.robot.control_motors(left, right)
            return "ok"

        # Échantillonnage événementiel
        if self.sampling_active and action in ("forward", "left", "right", "reverse", "stop"):
            self._sample_on_command(action, speed)

        ctrl = self.control_manager.get_controller("manual_controller")
        if ctrl:
            ctrl.set_action(action, speed=speed)
        return "ok"

    def _sample_on_command(self, action, speed):
        """Échantillonne l'état capteur et la commande au moment de la réception.

        Convertit l'action (forward/left/right/reverse/stop) en vitesses gauche/droite
        et enregistre l'échantillon (vecteur état → label vitesses).
        """
        try:
            # Récupérer l'état capteur le plus récent
            state = self.control_manager.get_last_sensor_data()
            if state is None:
                return

            # Convertir action → (left_speed, right_speed)
            left_speed, right_speed = self._action_to_speeds(action, speed)
            if left_speed == 0 and right_speed == 0:
                print(f"[DEBUG] Zero speeds! action={action}, speed={speed}")
            # Encoder via l'adapter ML
            adapter = self._get_ml_adapter(state)
            vector = self._vectorize_state_with_adapter(state, adapter)
            label = adapter.encode_label(left_speed, right_speed).tolist()

            if vector is None or label is None:
                return

            # Validation des données
            import numpy as np
            v_array = np.array(vector)
            l_array = np.array(label)
            v_array = self._apply_sampling_kill(v_array, adapter)

            if adapter.validate_state_vector(v_array) and adapter.validate_label_vector(l_array):
                self.sampling_vectors.append(v_array.tolist())
                self.sampling_labels.append(label)

                if self.debug_control_sampling:
                    now = time.time()
                    if now - self._last_debug_print_time >= 0.33:
                        self._last_debug_print_time = now
                        adapter.debug_print_state(v_array, l_array)
            else:
                print("[Sampling] Échantillon rejeté lors de la validation !")

        except Exception as e:
            print("[Sampling] Erreur dans échantillonnage événementiel: {}".format(e))

    def _action_to_speeds(self, action, speed):
        """Convertit une action simple (D-pad) en vitesses gauche/droite.

        Délègue à ManualController.compute_speeds() pour garantir la cohérence
        entre le sampling et l'exécution moteur.

        Returns:
            tuple: (left_speed, right_speed)
        """
        from core.control.controlers.manual_controller import _ACTION_MAP
        throttle, steering = _ACTION_MAP.get(action, (0, 0))
        # Pour les actions simples du D-pad, on utilise speed comme drive_speed
        # et self.manual_turn_speed pour les rotations
        if action in ("left", "right"):
            return ManualController.compute_speeds(throttle, steering, speed, speed)
        return ManualController.compute_speeds(throttle, steering, speed, speed)

    def forward(self): 
        return self._dispatch_manual_action("forward", self.manual_drive_speed)

    def reverse(self): 
        return self._dispatch_manual_action("reverse", self.manual_drive_speed)
        
    def left(self): 
        return self._dispatch_manual_action("left", self.manual_turn_speed)
        
    def right(self): 
        return self._dispatch_manual_action("right", self.manual_turn_speed)
        
    def stop(self):
        try:
            # Si un override est actif, le nettoyer directement
            # pour que le contrôleur auto reprenne immédiatement
            if self.control_manager and self.control_manager.manual_override_active:
                self.control_manager.clear_manual_override()
                return "ok"
            return self._dispatch_manual_action("stop", 0)
        except Exception as e:
            print("[ERREUR] _dispatch_manual_action(stop):", e)
            return "error", 500

    def manual_turn(self):
        """
        Fait tourner le Zumi d'un angle spécifié (rotation précise).
        """
        data = request.get_json(silent=True) or {}
        angle = data.get('angle', 0)
        print("[HTTP] /zumi/turn reçu - angle: {}°".format(angle))

        try:
            angle_float = float(angle)
            if angle_float == 0:
                return jsonify({'status': 'ok', 'message': 'Angle nul'}), 200

            # On utilise le MotorDriver existant via le controleur manuel s'il est là, 
            # ou on délègue temporairement :
            # L'idéal est de créer une MotorCommand.TURN et l'exécuter via _motor_driver de ControlManager
            # Mais comme la rotation est synchrone (bloquante), le plus simple est de réutiliser notre _dispatch:
            
            if not self.control_manager:
                return jsonify({'error': 'ControlManager missing'}), 500
                
            self._dispatch_manual_action("stop", 0) # Assurer l'arrêt d'abord
            
            if self.control_manager._motor_driver:
                self.control_manager._motor_driver.execute(MotorCommand.make_turn(angle_float))
                
            direction = "gauche" if angle_float > 0 else "droite"
            return jsonify({
                'status': 'ok',
                'message': 'Rotation de {} degrés vers la {}'.format(abs(angle_float), direction)
            }), 200
            
        except ValueError:
            print("[ERREUR] Angle invalide: {}".format(angle))
            return jsonify({'error': 'Angle invalide: doit être un nombre'}), 400
        except Exception as e:
            print("[ERREUR] zumi.turn({}):".format(angle), e)
            return jsonify({'error': str(e)}), 500

    # ------------------------------------------------------------------
    #  Contrôle composé WASD (touches simultanées)
    # ------------------------------------------------------------------

    def move(self):
        """Endpoint POST /zumi/move pour le contrôle WASD composé.

        Reçoit un JSON {"keys": ["w", "a"]} et convertit en throttle/steering.
        """
        data = request.get_json(silent=True) or {}
        keys = set(data.get('keys', []))
        throttle, steering = self._keys_to_throttle_steering(keys)
        return self._dispatch_compound_action(throttle, steering)

    def _keys_to_throttle_steering(self, keys):
        """Convertit un set de touches WASD en (throttle, steering).

        Returns:
            tuple: (throttle, steering) chacun dans {-1, 0, +1}
        """
        throttle = (1 if 'w' in keys else 0) + (-1 if 's' in keys else 0)
        steering = (-1 if 'a' in keys else 0) + (1 if 'd' in keys else 0)
        return throttle, steering

    def _dispatch_compound_action(self, throttle, steering):
        """Dispatch une action composée (throttle+steering).

        Si un contrôleur auto est actif, utilise l'override temporaire.
        Le contrôleur reprend automatiquement quand les touches sont relâchées.
        """
        if not self.control_manager:
            return "ControlManager missing"

        if self.control_manager.get_controller("manual_controller") is None:
            return "Manual controller missing"

        active = self.control_manager._active_controller

        # --- Override temporaire si un contrôleur auto est actif ---
        if active and active.name != "manual_controller":
            if throttle == 0 and steering == 0:
                self.control_manager.clear_manual_override()
                return "ok"

            ctrl = self.control_manager.get_controller("manual_controller")
            left, right = ManualController.compute_speeds(
                throttle, steering,
                self.manual_drive_speed, self.manual_turn_speed,
                ctrl.steering_ratio)
            self.control_manager.set_manual_override(
                MotorCommand.make_speed(left, right))
            # Sampling géré par _sampling_callback (labels post-PID)
            return "ok"

        # --- Pas de contrôleur actif : commande directe avec PID de cap ---
        if not active:
            if throttle == 0 and steering == 0:
                self.robot.stop()
                ctrl = self.control_manager.get_controller("manual_controller")
                if ctrl:
                    ctrl._heading_hold_active = False
            else:
                ctrl = self.control_manager.get_controller("manual_controller")
                left, right = ManualController.compute_speeds(
                    throttle, steering, self.manual_drive_speed,
                    self.manual_turn_speed, ctrl.steering_ratio if ctrl else 0.5)
                # PID de cap si ligne droite (throttle sans steering)
                if ctrl and throttle != 0 and steering == 0:
                    state = self.control_manager.get_last_sensor_data()
                    left, right = ctrl.apply_heading_correction(state, left, right)
                elif ctrl and steering != 0:
                    ctrl._heading_hold_active = False
                self.robot.control_motors(left, right)
            return "ok"

        ctrl = self.control_manager.get_controller("manual_controller")
        ctrl.set_compound_action(throttle, steering,
                                 drive_speed=self.manual_drive_speed,
                                 turn_speed=self.manual_turn_speed)

        # Sampling géré par _sampling_callback (labels post-PID)
        return "ok"

    def _sample_compound(self, left_speed, right_speed):
        """Échantillonne l'état capteur avec des vitesses pré-calculées.

        Utilise les vitesses intentionnelles (de compute_speeds), pas les vitesses
        PWM-modulées, pour des labels d'entraînement propres.
        """
        try:
            state = self.control_manager.get_last_sensor_data()
            if state is None:
                return

            adapter = self._get_ml_adapter(state)
            vector = self._vectorize_state_with_adapter(state, adapter)
            label = adapter.encode_label(left_speed, right_speed).tolist()

            if vector is None or label is None:
                return

            import numpy as np
            v_array = np.array(vector)
            l_array = np.array(label)
            v_array = self._apply_sampling_kill(v_array, adapter)

            if adapter.validate_state_vector(v_array) and adapter.validate_label_vector(l_array):
                self.sampling_vectors.append(v_array.tolist())
                self.sampling_labels.append(label)

                if self.debug_control_sampling:
                    now = time.time()
                    if now - self._last_debug_print_time >= 0.33:
                        self._last_debug_print_time = now
                        adapter.debug_print_state(v_array, l_array)
            else:
                print("[Sampling] Échantillon rejeté lors de la validation !")

        except Exception as e:
            print("[Sampling] Erreur dans échantillonnage composé: {}".format(e))

    # ------------------------------------------------------------------
    #  Reset capteurs / PID
    # ------------------------------------------------------------------

    def robot_calibrate(self):
        """Calibration complete: gyro + MPU + IR heavy (~3-5s bloquant)."""
        try:
            self.robot.calibrate_sensors()
            # Heavy IR calibration en plus (calibrate_sensors fait light=50)
            self.robot.calibrate_ir(n_samples=200)
            return jsonify({'status': 'ok', 'message': 'Calibration complete (MPU + IR)'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def robot_reset_drive(self):
        """Reset PIDs + gyro (reset_drive_state)."""
        try:
            self.robot.reset_drive_state()
            return jsonify({'status': 'ok', 'message': 'Drive state reset'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def robot_reset_gyro(self):
        """Reset gyro uniquement."""
        try:
            self.robot._reset_gyro()
            return jsonify({'status': 'ok', 'message': 'Gyro reset'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def robot_reset_pid(self):
        """Reset PID uniquement."""
        try:
            self.robot._reset_PID()
            return jsonify({'status': 'ok', 'message': 'PID reset'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def calibrate_ir(self):
        """Calibration IR complete (mode heavy, N=200). Mesure les baselines
        et offsets de tous les capteurs IR. Le robot doit etre immobile
        sur la route noire (sans ligne)."""
        try:
            if self.robot is None:
                return jsonify({'error': 'Robot non initialisé'}), 400
            result = self.robot.calibrate_ir(n_samples=200)
            if result is None:
                return jsonify({'error': 'Calibration IR echouee'}), 500
            return jsonify({'status': 'ok', 'message': 'Calibration IR terminee', 'calibration': result})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ============================================================
    #  Sensor Profiler
    # ============================================================

    def sensor_profile_start(self):
        """Démarre le wizard de profiling."""
        from core.control.sensor_profiler import SensorProfiler
        data = request.get_json(silent=True) or {}
        robot_id = data.get('robot_id', 'zumi_1')

        if not hasattr(self, '_sensor_profiler') or self._sensor_profiler is None:
            self._sensor_profiler = SensorProfiler(self.robot)

        self._sensor_profiler.start(robot_id)
        return jsonify({'status': 'started', 'robot_id': robot_id})

    def sensor_profile_status(self):
        """Retourne l'état actuel du profiler."""
        if not hasattr(self, '_sensor_profiler') or self._sensor_profiler is None:
            return jsonify({'active': False})
        return jsonify(self._sensor_profiler.get_status())

    def sensor_profile_record(self):
        """Enregistre les données de la phase statique courante."""
        if not hasattr(self, '_sensor_profiler') or not self._sensor_profiler.is_active:
            return jsonify({'error': 'Profiler non actif'}), 400
        result = self._sensor_profiler.record_static()
        if 'error' in result:
            return jsonify(result), 400
        return jsonify({'status': 'recorded', 'phase': result.get('description', ''), 'n_samples': result.get('n_samples', 0)})

    def sensor_profile_run(self):
        """Lance la manoeuvre auto (non-bloquant).

        Active le CalibrationController et retourne immédiatement.
        Le UI poll /status pour détecter quand auto_running passe à false,
        puis appelle /run_complete pour collecter les résultats.
        """
        import threading

        if not hasattr(self, '_sensor_profiler') or not self._sensor_profiler.is_active:
            return jsonify({'error': 'Profiler non actif'}), 400

        result = self._sensor_profiler.run_auto_phase()
        if 'error' in result:
            return jsonify(result), 400

        action = result.get('action')
        phase_id = result.get('phase_id', '')
        duration = result.get('duration', 3.0)

        if action == 'activate_calibration_controller':
            ctrl = self._sensor_profiler.get_controller()
            if self.control_manager.get_controller('calibration_controller') is None:
                self.control_manager.register_controller('calibration_controller', ctrl)
            if self.control_manager._active_controller is not None:
                self.control_manager.deactivate_controller()

            self.control_manager.activate_controller('calibration_controller')

            # Thread de surveillance: attend la fin, puis cleanup
            def _wait_and_cleanup():
                import time as _time
                timeout = _time.time() + duration + 5.0
                while not ctrl.is_done and _time.time() < timeout:
                    _time.sleep(0.1)
                self.control_manager.deactivate_controller()
                ctrl.clear_maneuver()
                self._sensor_profiler.collect_auto_results()

            threading.Thread(target=_wait_and_cleanup, daemon=True).start()

            return jsonify({'status': 'running', 'phase_id': phase_id})

        return jsonify(result)

    def sensor_profile_run_status(self):
        """Vérifie si la manoeuvre auto est terminée et retourne les résultats."""
        if not hasattr(self, '_sensor_profiler') or not self._sensor_profiler.is_active:
            return jsonify({'error': 'Profiler non actif'}), 400

        ctrl = self._sensor_profiler.get_controller()
        running = ctrl._maneuver is not None and not ctrl.is_done
        n_samples = len(ctrl.get_samples())
        return jsonify({'running': running, 'n_samples': n_samples})

    def sensor_profile_manual_start(self):
        """Démarre l'enregistrement pour une phase manuelle (D).
        L'utilisateur pilote en WASD pendant que les capteurs sont enregistrés."""
        if not hasattr(self, '_sensor_profiler') or not self._sensor_profiler.is_active:
            return jsonify({'error': 'Profiler non actif'}), 400
        result = self._sensor_profiler.start_manual_recording()
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)

    def sensor_profile_manual_stop(self):
        """Arrête l'enregistrement manuel et retourne la validation du run."""
        if not hasattr(self, '_sensor_profiler') or not self._sensor_profiler.is_active:
            return jsonify({'error': 'Profiler non actif'}), 400
        result = self._sensor_profiler.stop_manual_recording()
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)

    def sensor_profile_next(self):
        """Passe à la phase suivante."""
        if not hasattr(self, '_sensor_profiler') or not self._sensor_profiler.is_active:
            return jsonify({'error': 'Profiler non actif'}), 400

        # Finaliser la phase manuelle si c'est une phase D
        sp = self._sensor_profiler
        phase_idx = sp.current_phase_idx
        if phase_idx < len(sp.phases) and sp.phases[phase_idx]["type"] == "manual_sampling":
            sp.finalize_manual_phase()

        # Collect auto results if any
        if hasattr(sp, '_controller') and sp._controller.is_done:
            sp.collect_auto_results()

        # Deactivate any running controller
        if self.control_manager._active_controller is not None:
            self.control_manager.deactivate_controller()

        result = self._sensor_profiler.next_phase()

        if result.get('completed'):
            path = self._sensor_profiler.save_profile()
            return jsonify({'status': 'completed', 'saved': str(path)})

        return jsonify({'status': 'next', **result})

    def sensor_profile_stop(self):
        """Arrête le profiling et sauvegarde."""
        if not hasattr(self, '_sensor_profiler'):
            return jsonify({'error': 'Profiler non initialisé'}), 400

        # Stop any running controller
        if self.control_manager._active_controller is not None:
            self.control_manager.deactivate_controller()

        result = self._sensor_profiler.stop_and_save()
        return jsonify({'status': 'stopped', **result})

    def sensor_profile_results(self):
        """Retourne le profil complet."""
        if not hasattr(self, '_sensor_profiler') or self._sensor_profiler is None:
            return jsonify({'error': 'Profiler non initialisé'}), 400
        return jsonify(self._sensor_profiler.profile_data)

    def sensor_profile_summary(self):
        """Retourne un résumé des résultats pour l'écran de fin."""
        if not hasattr(self, '_sensor_profiler') or self._sensor_profiler is None:
            return jsonify({'error': 'Profiler non initialisé'}), 400
        return jsonify(self._sensor_profiler.get_summary())

    def sensor_profile_download(self):
        """Télécharge le profil JSON + calibration IR en ZIP."""
        from flask import send_file
        import zipfile
        import io

        if not hasattr(self, '_sensor_profiler') or self._sensor_profiler is None:
            return jsonify({'error': 'Profiler non initialisé'}), 400

        sp = self._sensor_profiler
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Profil complet
            import json
            profile_json = json.dumps(sp.profile_data, indent=2, default=str)
            zf.writestr('sensor_profile_{}.json'.format(sp.robot_id), profile_json)

            # Calibration IR si disponible
            from pathlib import Path
            ir_cal_path = Path(__file__).parent.parent / 'core' / 'robot' / 'ir_calibration.json'
            if ir_cal_path.exists():
                zf.write(str(ir_cal_path), 'ir_calibration.json')

        buf.seek(0)
        return send_file(buf, mimetype='application/zip',
                        as_attachment=True,
                        download_name='sensor_profile_{}.zip'.format(sp.robot_id))

# ----------------------------------------------------------------------------
#          Fonctions PID legacy (onglet PID — tuning rotation)
# ----------------------------------------------------------------------------

    def _get_line_detector(self):
        """Retourne l'instance du LineDetector dans le pipeline vision, ou None."""
        vp = self.vision_pipeline
        if vp is None:
            return None
        for det in vp.get_detectors():
            if getattr(det, 'name', '') == 'line':
                return det
        return None

    # --- Line Detector params ---------------------------------------------------

    def line_detector_update_params(self):
        """POST /line_detector/update_params — met à jour les paramètres du détecteur de ligne."""
        data = request.get_json(silent=True) or {}
        det = self._get_line_detector()
        if det is None:
            return jsonify({'error': 'LineDetector introuvable dans le pipeline'}), 404
        try:
            det.update_params(**data)
            print("[LineDetector] Params mis à jour: {}".format(data))
            return jsonify(det.get_params())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def line_detector_get_params(self):
        """GET /line_detector/get_params — retourne les paramètres actuels du détecteur de ligne."""
        det = self._get_line_detector()
        if det is None:
            return jsonify({'error': 'LineDetector introuvable dans le pipeline'}), 404
        return jsonify(det.get_params())

    # --- PID params -------------------------------------------------------------

    def pid_update_params(self):
        """POST /pid/update_params — met à jour les paramètres du PIDController legacy."""
        data = request.get_json(silent=True) or {}
        try:
            self.pid_controller.update_params(**data)
            print("[PID] Params mis à jour: {}".format(data))
            return jsonify(self.pid_controller.get_params())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def pid_get_params(self):
        """GET /pid/get_params — retourne les paramètres actuels du PID."""
        return jsonify(self.pid_controller.get_params())

    # --- PID start / stop / reset / status --------------------------------------

    def pid_start(self):
        """POST /pid/start — démarre la boucle PID de tuning (rotation ou avance)."""
        if self.pid_active:
            return jsonify({'status': 'already_running'})

        vp = self.vision_pipeline
        if not vp or not vp.is_running():
            if vp:
                vp.start()
                time.sleep(0.3)
            else:
                return jsonify({'error': 'Vision pipeline non initialisé'}), 400

        self.pid_active = True
        self.pid_controller.reset()

        import threading
        self.pid_thread = threading.Thread(target=self._pid_loop, daemon=True)
        self.pid_thread.start()
        print("[PID] Boucle de tuning démarrée (rotation_mode={})".format(self.pid_controller.rotation_mode))
        return jsonify({'status': 'started', 'rotation_mode': self.pid_controller.rotation_mode})

    def pid_stop(self):
        """POST /pid/stop — arrête la boucle PID."""
        self.pid_active = False
        # Arrêter les moteurs immédiatement
        if self.control_manager and self.control_manager._motor_driver:
            self.control_manager._motor_driver.execute(MotorCommand.stop())
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        print("[PID] Boucle arrêtée")
        return jsonify({'status': 'stopped'})

    def pid_reset(self):
        """POST /pid/reset — réinitialise l'état interne du PID."""
        self.pid_controller.reset()
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        print("[PID] Reset effectué")
        return jsonify({'status': 'reset'})

    def pid_status(self):
        """GET /pid/status — retourne l'état courant (offset, correction, vitesses)."""
        return jsonify({
            'active': self.pid_active,
            'error': self.last_line_offset,
            'correction': self.last_correction,
            'left_speed': self.last_left_speed,
            'right_speed': self.last_right_speed,
            'rotation_mode': self.pid_controller.rotation_mode,
        })

    def _pid_loop(self):
        """Boucle de fond pour le tuning PID (rotation ou avance).

        En mode rotation : calcule un angle via compute_rotation_angle() et envoie
        un MotorCommand.make_turn().
        En mode avance : calcule left/right via compute() et envoie
        un MotorCommand.make_speed().
        """
        vp = self.vision_pipeline
        det = self._get_line_detector()
        if det is None:
            print("[PID] Aucun LineDetector — boucle abandonnée")
            self.pid_active = False
            return

        print("[PID] Boucle PID démarrée — mode={}".format(
            'ROTATION' if self.pid_controller.rotation_mode else 'AVANCE'))

        while self.pid_active:
            try:
                frame = vp.get_last_frame()
                if frame is None:
                    time.sleep(0.05)
                    continue

                result = det.process(frame.copy())
                line_offset = result.get('line_offset')

                if line_offset is None:
                    # Ligne perdue — arrêter les moteurs
                    if self.control_manager and self.control_manager._motor_driver:
                        self.control_manager._motor_driver.execute(MotorCommand.stop())
                    self.last_line_offset = 0
                    time.sleep(0.05)
                    continue

                self.last_line_offset = line_offset

                if self.pid_controller.rotation_mode:
                    # --- Mode rotation (tuning) ---
                    angle = self.pid_controller.compute_rotation_angle(line_offset)
                    if angle is not None and self.control_manager and self.control_manager._motor_driver:
                        self.last_correction = angle
                        self.last_left_speed = 0
                        self.last_right_speed = 0
                        self.control_manager._motor_driver.execute(MotorCommand.make_turn(angle))
                        # Petite pause après la rotation pour laisser le robot se stabiliser
                        time.sleep(0.15)
                    else:
                        self.last_correction = 0
                else:
                    # --- Mode avance ---
                    left, right = self.pid_controller.compute(line_offset)
                    self.last_correction = left - right
                    self.last_left_speed = left
                    self.last_right_speed = right
                    if self.control_manager and self.control_manager._motor_driver:
                        self.control_manager._motor_driver.execute(MotorCommand.make_speed(left, right))

                time.sleep(0.05)  # ~20 Hz

            except Exception as e:
                print("[PID] Erreur dans la boucle: {}".format(e))
                import traceback
                traceback.print_exc()
                time.sleep(0.1)

        # Nettoyage à la sortie
        if self.control_manager and self.control_manager._motor_driver:
            self.control_manager._motor_driver.execute(MotorCommand.stop())
        print("[PID] Boucle de fond terminée")

    # --- Mode Step-by-Step (legacy) -------------------------------------------

    def pid_step_start(self):
        """POST /pid/step_mode/start — démarre la machine step-by-step."""
        if self.step_mode_active:
            return jsonify({'status': 'already_running'})

        vp = self.vision_pipeline
        if not vp or not vp.is_running():
            if vp:
                vp.start()
                time.sleep(0.3)
            else:
                return jsonify({'error': 'Vision pipeline non initialisé'}), 400

        self.step_machine = StepByStepStateMachine(self.robot, vp, self.pid_controller)
        self.step_machine.start()
        self.step_mode_active = True

        import threading
        self.step_mode_thread = threading.Thread(target=self._step_mode_loop, daemon=True)
        self.step_mode_thread.start()
        print("[StepMode] Démarré")
        return jsonify({'status': 'started'})

    def pid_step_stop(self):
        """POST /pid/step_mode/stop — arrête la machine step-by-step."""
        self.step_mode_active = False
        if self.step_machine:
            self.step_machine.stop()
        print("[StepMode] Arrêté")
        return jsonify({'status': 'stopped'})

    def pid_step_approve(self):
        """POST /pid/step_mode/approve — autorise le prochain pas."""
        if self.step_machine:
            self.step_machine.approve_next_step()
            return jsonify({'status': 'approved'})
        return jsonify({'error': 'Step machine non active'}), 400

    def pid_step_status(self):
        """GET /pid/step_mode/status — retourne l'état de la machine step-by-step."""
        if not self.step_machine:
            return jsonify({
                'active': False,
                'state': 'IDLE',
                'step_count': 0,
                'waiting_approval': False,
            })
        sm = self.step_machine
        return jsonify({
            'active': self.step_mode_active,
            'state': sm.state.name,
            'step_count': sm.step_count,
            'waiting_approval': not sm.approved_to_move and sm.state.name == 'WAITING_APPROVAL',
            'line_offset': sm.last_line_offset,
            'left_speed': sm.straight_speed if hasattr(sm, 'straight_speed') else 0,
            'right_speed': sm.straight_speed if hasattr(sm, 'straight_speed') else 0,
            'message': getattr(sm, 'current_action_message', ''),
        })

    def _step_mode_loop(self):
        """Boucle de fond pour le mode step-by-step."""
        vp = self.vision_pipeline
        while self.step_mode_active and self.step_machine:
            try:
                frame = vp.get_last_frame() if vp else None
                if frame is None:
                    time.sleep(0.05)
                    continue
                self.step_machine.step(frame.copy())
                time.sleep(0.05)
            except Exception as e:
                print("[StepMode] Erreur: {}".format(e))
                time.sleep(0.1)
        print("[StepMode] Boucle de fond terminée")

# ----------------------------------------------------------------------------
#          Fonctions pour le contrôle du pont
# ----------------------------------------------------------------------------
    def bridge_open(self):
        try:
            requests.get("{}/ouvrir".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except Exception as e:
            print("[ERREUR] Pont ouvrir:", e)
            return ("Erreur", 500)
        

    def bridge_close(self):
        try:
            requests.get("{}/fermer".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except Exception as e:
            print("[ERREUR] Pont fermer:", e)
            return ("Erreur", 500)
            
    def bridge_green(self):
        try:
            requests.get("{}/vert".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except Exception as e:
            print("[ERREUR] Pont vert:", e)
            return ("Erreur", 500)

    def bridge_red(self):
        try:
            requests.get("{}/rouge".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except Exception as e:
            print("[ERREUR] Pont rouge:", e)
            return ("Erreur", 500)

    def bridge_mode_auto(self, etat):
        # etat doit être '1' (true) ou '0' (false)
        try:
            # On désactive/active le mode auto du moteur ET des lumières
            requests.get("{}/majAutoMoteur?etat={}".format(self.BRIDGE_URL, etat), timeout=1)
            requests.get("{}/majAutoLed?etat={}".format(self.BRIDGE_URL, etat), timeout=1)
            return ("", 204)
        except Exception as e:
            print("[ERREUR] Pont Mode Auto:", e)
            return ("Erreur", 500)


# ----------------------------------------------------------------------------
#          Fonctions de callback pour l'onglet de contrôle
# ----------------------------------------------------------------------------
    def manual_settings(self):
        """GET/POST des réglages manuels (vitesses, steering_ratio, PID de cap)."""
        ctrl = self.control_manager.get_controller('manual_controller') if self.control_manager else None

        if request.method == 'GET':
            payload = {
                'drive_speed': self.manual_drive_speed,
                'turn_speed': self.manual_turn_speed,
                'steering_ratio': ctrl.steering_ratio if ctrl else 0.5,
                'heading_kp': ctrl.heading_kp if ctrl else 1.5,
                'heading_max_correction': ctrl.heading_max_correction if ctrl else 15,
            }
            return jsonify(payload)

        data = request.get_json(silent=True) or {}
        if 'drive_speed' in data:
            self.manual_drive_speed = float(data['drive_speed'])
        if 'turn_speed' in data:
            self.manual_turn_speed = float(data['turn_speed'])

        if ctrl:
            update_kwargs = {'default_speed': self.manual_drive_speed}
            if 'steering_ratio' in data:
                update_kwargs['steering_ratio'] = float(data['steering_ratio'])
            if 'heading_kp' in data:
                update_kwargs['heading_kp'] = float(data['heading_kp'])
            if 'heading_max_correction' in data:
                update_kwargs['heading_max_correction'] = float(data['heading_max_correction'])
            ctrl.update_params(**update_kwargs)

        return jsonify({
            'drive_speed': self.manual_drive_speed,
            'turn_speed': self.manual_turn_speed,
            'steering_ratio': ctrl.steering_ratio if ctrl else 0.5,
            'heading_kp': ctrl.heading_kp if ctrl else 1.5,
            'heading_max_correction': ctrl.heading_max_correction if ctrl else 15,
        })
 
    def start_sampling(self):
        """ Démare l'échantillonnage des données des capteurs.
        Recalibre le gyroscope avant chaque séquence pour éviter
        l'accumulation d'angles entre les séquences d'échantillonnage.
        """
        if self.sampling_active is True:
            return jsonify({'error': 'Sampling already active'}), 400
        # Reset gyro avant chaque séquence pour que les angles IMU
        # repartent de zéro (évite le biais cumulatif de gyro_z)
        try:
            self.robot.reset_drive_state()
        except Exception as e:
            print("[Sampling] Erreur reset gyro avant echantillonnage: {}".format(e))
        self.sampling_vectors = []
        self.sampling_labels = []
        self.sampling_active = True

        # Log de la dimension attendue pour validation rapide
        try:
            state = self.sensor_driver.read()
            adapter = self._get_ml_adapter(state)
            expected_dim = adapter.state_dim
            test_vec = self._vectorize_state_with_adapter(state, adapter)
            actual_dim = len(test_vec) if test_vec else 0
            status = "OK" if actual_dim == expected_dim else "MISMATCH"
            print(f"[Sampling] Demarre. Dim attendue: {expected_dim}, "
                  f"dim actuelle: {actual_dim} [{status}]")
            if actual_dim == expected_dim and actual_dim == 38:
                print(f"[Sampling] Format 38-dim confirme (9 zone features dont dash counts)")
        except Exception as e:
            print(f"[Sampling] Erreur validation dim: {e}")

        return jsonify({'status': 'sampling started'})
    
    def stop_sampling(self):
        """ Arrête l'échantillonnage des données des capteurs
        """
        if self.sampling_active is True:
            self.sampling_active = False
        return jsonify({'status': 'sampling stopped'})

    def sampling_feature_kill(self):
        """Configure les groupes de features forcés à 0 pendant l'échantillonnage.

        GET  → retourne l'état courant
        POST → body JSON {"groups": ["haar", "line_camera"]}
                          [] pour désactiver le kill (revenir au comportement normal)

        Groupes disponibles:
          "haar"        : detection_flag + class_onehot + bbox (indices 8..12+N)
          "line_camera" : line_camera_offset + line_camera_detected (indices 24+N, 25+N)
        """
        if request.method == 'GET':
            return jsonify({"zeroed_groups": sorted(self.sampling_zeroed_groups)})

        data = request.get_json(silent=True) or {}
        groups = set(data.get("groups", []))
        valid_groups = {"haar", "line_camera"}
        invalid = groups - valid_groups
        if invalid:
            return jsonify({"error": "Groupes invalides: {}. Valides: {}".format(
                sorted(invalid), sorted(valid_groups))}), 400
        self.sampling_zeroed_groups = groups
        return jsonify({"status": "ok", "zeroed_groups": sorted(self.sampling_zeroed_groups)})

    def controller_list(self):
        """Retourne la liste des contrôleurs enregistrés."""
        if self.control_manager is None:
            return jsonify({'controllers': []})
        return jsonify({'controllers': sorted(self.control_manager._controllers.keys())})

    def download_sampling(self):
        """Crée un ZIP avec captures.jsonl et labels.jsonl des échantillons."""
        if not self.sampling_vectors or not self.sampling_labels:
            return jsonify({'error': 'no samples'}), 404

        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            captures_lines = [json.dumps(v) for v in self.sampling_vectors]
            labels_lines = [json.dumps(v) for v in self.sampling_labels]
            zf.writestr('captures.jsonl', '\n'.join(captures_lines))
            zf.writestr('labels.jsonl', '\n'.join(labels_lines))

        # Pour des fin de validation on s'attend a un vecteur capteur de 20 et un vecteur de label de 2
        print("[Exception][ServerController] Dimension vecteur de capteurs {}".format(len(self.sampling_vectors[0]) if self.sampling_vectors else 0))
        print("[Exception][ServerController] Dimension vecteur de labels {}".format(len(self.sampling_labels[0]) if self.sampling_labels else 0))
        print("[Exception][ServerController] Nombre d'échantillons capturés: {}".format(len(self.sampling_vectors)))

        buf.seek(0)
        ts = time.strftime('%Y%m%d_%H%M%S')
        zip_name = 'sampling_{}.zip'.format(ts)

        return Response(
            buf.getvalue(),
            mimetype='application/zip',
            headers={'Content-Disposition': 'attachment; filename={}'.format(zip_name)}
        )

    def start_controller(self):
        """Démarre le contrôleur LineFollower (nouvelle architecture standardisée)."""
        try:
            data = request.get_json(silent=True) or {}
            controller_name = data.get('name') or data.get('controller') or 'line_follower'

            vp = self.vision_pipeline
            if not vp:
                return jsonify({'error': 'Vision pipeline non initialisé'}), 400
            if not vp.is_running():
                vp.start()
                time.sleep(0.3)
            if self.control_manager is None:
                return jsonify({'error': 'ControlManager non attaché'}), 400
            if self.control_manager.get_controller(controller_name) is None:
                return jsonify({'error': 'Contrôleur inconnu : {}'.format(controller_name)}), 400

            active = self.control_manager._active_controller
            if active is not None:
                if active.name == controller_name:
                    return jsonify({'status': 'already_running', 'controller': controller_name})
                return jsonify({'error': 'Un autre contrôleur est déjà actif : {}'.format(active.name)}), 400

            # Auto-switch: appliquer le profil caméra 'passive' (320x240) pour économiser le CPU
            self._apply_camera_profile('passive')

            # Passive detection: Line detector seulement en mode contrôleur (pas de Haar = économie CPU)
            vp = self.vision_pipeline
            if vp and hasattr(vp, 'set_passive_detectors'):
                line_dets = [d for d in vp.detectors if getattr(d, 'name', '') == 'line']
                vp.set_passive_detectors(line_dets)

            self.robot.reset_drive_state() # reset gyro + PID pour des conditions de contrôle optimales au démarrage

            self.control_manager.activate_controller(controller_name)
            return jsonify({'status': 'started', 'controller': controller_name})
        except Exception as e:
            print("[ERROR] start_controller: {}".format(e))
            return jsonify({'error': str(e)}), 500

    def stop_controller(self):
        """Arrête le contrôleur actif (nouvelle architecture)."""
        try:
            if self.control_manager is None:
                return jsonify({'error': 'ControlManager non attaché'}), 400
            active = self.control_manager._active_controller
            if active is not None:
                name = active.name
                self.control_manager.deactivate_controller()

                # Auto-switch: revenir au profil caméra 'stream' (640x480) pour le streaming
                self._apply_camera_profile('stream')

                # Restaurer Haar classifiers pour la détection passive en mode Vision
                vp = self.vision_pipeline
                if vp and hasattr(vp, 'set_passive_detectors'):
                    haar_dets = [d for d in vp.detectors if getattr(d, 'name', '') != 'line']
                    vp.set_passive_detectors(haar_dets)

                return jsonify({'status': 'stopped', 'controller': name})
            return jsonify({'status': 'stopped', 'controller': None})
        except Exception as e:
            print("[ERROR] stop_controller: {}".format(e))
            return jsonify({'error': str(e)}), 500

    def controller_status(self):
        """Retourne l'état courant du contrôleur actif."""
        try:
            if self.control_manager is None:
                return jsonify({'active': False})
            active = self.control_manager._active_controller
            payload = {
                'active': bool(active),
                'controller': active.name if active else None,
                'running': self.control_manager._running,
                'manual_override': self.control_manager.manual_override_active,
            }
            if active:
                payload['controller_debug'] = active.get_debug_info()
                payload['controller_params'] = active.get_params()
                # Ajouter les params du LineDetector quand circuit_fsm est actif
                if active.name == 'circuit_fsm' and self.vision_pipeline:
                    for det in self.vision_pipeline.get_detectors():
                        if getattr(det, 'name', '') == 'line' and hasattr(det, 'get_params'):
                            payload['line_detector_params'] = det.get_params()
                            break
            return jsonify(payload)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def toggle_ml_debug(self):
        """Active/désactive le debug logging du MLController."""
        try:
            if self.control_manager is None:
                return jsonify({'error': 'ControlManager non attaché'}), 400
            ml_ctrl = self.control_manager.get_controller('ml_controller')
            if ml_ctrl is None:
                return jsonify({'error': 'MLController non trouvé'}), 400
            new_state = not ml_ctrl._debug_enabled
            ml_ctrl.set_debug(new_state)
            return jsonify({'debug': new_state})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def controller_params(self):
        """GET/POST les paramètres d'un contrôleur par nom.

        GET  /controller/params?name=pid_ir  → retourne les params
        POST /controller/params  {"name": "pid_ir", "kp": 0.2, ...}  → met à jour
        """
        if self.control_manager is None:
            return jsonify({'error': 'ControlManager non attaché'}), 400

        if request.method == 'GET':
            ctrl_name = request.args.get('name')
            if not ctrl_name:
                return jsonify({'error': 'name parameter required'}), 400
            ctrl = self.control_manager.get_controller(ctrl_name)
            if ctrl is None:
                return jsonify({'error': 'Contrôleur inconnu: {}'.format(ctrl_name)}), 404
            result = {'name': ctrl_name, 'params': ctrl.get_params()}
            # Ajouter les params du LineDetector pour circuit_fsm
            if ctrl_name == 'circuit_fsm' and self.vision_pipeline:
                for det in self.vision_pipeline.get_detectors():
                    if getattr(det, 'name', '') == 'line' and hasattr(det, 'get_params'):
                        result['line_detector_params'] = det.get_params()
                        break
            return jsonify(result)

        # POST: mise à jour des paramètres
        data = request.get_json(silent=True) or {}
        ctrl_name = data.pop('name', None)
        if not ctrl_name:
            return jsonify({'error': 'name field required'}), 400
        ctrl = self.control_manager.get_controller(ctrl_name)
        if ctrl is None:
            return jsonify({'error': 'Contrôleur inconnu: {}'.format(ctrl_name)}), 404

        # Séparer les params du LineDetector de ceux du contrôleur
        line_detector_keys = {
            'white_threshold', 'min_area', 'offset_ratio',
            'center_zone_width_ratio',
            'front_zone_x_ratio', 'front_zone_y_start', 'front_zone_y_end',
            'front_zone_width_ratio', 'front_min_dashes',
            'corner_zone_width_ratio', 'corner_zone_height_ratio',
            'corner_zone_y_start',
        }
        line_params = {}
        ctrl_params = {}
        for k, v in data.items():
            if k in line_detector_keys:
                line_params[k] = v
            else:
                ctrl_params[k] = v

        print("[DEBUG controller_params POST] ctrl={} ctrl_params={} line_params={}".format(
            ctrl_name, ctrl_params, line_params))

        # Mettre à jour les params du contrôleur
        try:
            if ctrl_params:
                ctrl.update_params(**ctrl_params)
                print("[DEBUG] ctrl.update_params OK")
        except Exception as e:
            print("[ERROR] ctrl.update_params failed: {}".format(e))
            return jsonify({'error': 'ctrl update_params error: {}'.format(str(e))}), 500

        # Mettre à jour les params du LineDetector si applicable
        try:
            if line_params and ctrl_name == 'circuit_fsm':
                vp = self.vision_pipeline
                if vp:
                    found_det = False
                    for det in vp.get_detectors():
                        if getattr(det, 'name', '') == 'line' and hasattr(det, 'update_params'):
                            det.update_params(**line_params)
                            found_det = True
                            print("[DEBUG] line_detector.update_params OK: {}".format(line_params))
                            break
                    if not found_det:
                        print("[WARNING] LineDetector introuvable dans le pipeline!")
                else:
                    print("[WARNING] vision_pipeline est None, line_params ignorés!")
        except Exception as e:
            print("[ERROR] line_detector.update_params failed: {}".format(e))
            return jsonify({'error': 'line_detector update_params error: {}'.format(str(e))}), 500

        result = {'name': ctrl_name, 'params': ctrl.get_params()}
        if ctrl_name == 'circuit_fsm' and self.vision_pipeline:
            for det in self.vision_pipeline.get_detectors():
                if getattr(det, 'name', '') == 'line' and hasattr(det, 'get_params'):
                    result['line_detector_params'] = det.get_params()
                    break
        return jsonify(result)

    def controller_step(self):
        """POST /controller/step — Déclenche un pas en mode pas-à-pas.
        
        Body JSON: {"name": "circuit_fsm"}
        """
        if self.control_manager is None:
            return jsonify({'error': 'ControlManager non attaché'}), 400

        data = request.get_json(silent=True) or {}
        ctrl_name = data.get('name', 'circuit_fsm')
        ctrl = self.control_manager.get_controller(ctrl_name)
        if ctrl is None:
            return jsonify({'error': 'Contrôleur inconnu: {}'.format(ctrl_name)}), 404

        if hasattr(ctrl, 'request_step'):
            ctrl.request_step()
            return jsonify({'ok': True, 'message': 'Step requested'})
        else:
            return jsonify({'error': 'Ce contrôleur ne supporte pas le mode pas-à-pas'}), 400

    def _apply_sampling_kill(self, v_array, adapter):
        """Force les groupes de features killés à 0 dans le vecteur d'échantillonnage.

        Opère in-place sur v_array. Les indices dépendent du nombre de classes HAAR (N).
        Les validations restent cohérentes car 0.0 est valide pour tous ces champs.
        """
        if not self.sampling_zeroed_groups:
            return v_array
        N = len(adapter.classes)
        if "haar" in self.sampling_zeroed_groups:
            # detection_flag (8) + class_onehot (9..8+N) + bbox cx,cy,w,h (9+N..12+N)
            v_array[8 : 13 + N] = 0.0
        if "line_camera" in self.sampling_zeroed_groups:
            # line_camera_offset (24+N) + line_camera_detected (25+N)
            v_array[24 + N] = 0.0
            v_array[25 + N] = 0.0
        return v_array

    def _vectorize_state_with_adapter(self, state, adapter):
        if state is None:
            return None

        detections = state.detections or []
        vision_result = {'detections': detections}

        imu_data = {}
        if state.gyro_angles and len(state.gyro_angles) >= 11:
            # zumi.update_angles() retourne 11 valeurs:
            # [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]
            a = state.gyro_angles
            imu_data = {
                'gyro_x': float(a[0]),
                'gyro_y': float(a[1]),
                'gyro_z': float(a[2]),
                'acc_x':  float(a[3]),
                'acc_y':  float(a[4]),
                'comp_x': float(a[5]),
                'comp_y': float(a[6]),
                'rot_x':  float(a[7]),
                'rot_y':  float(a[8]),
                'rot_z':  float(a[9]),
                'tilt_state': float(a[10]),
            }

        ir_data = state.ir_sensors if state.ir_sensors is not None else None
        line_off = state.line_offset if hasattr(state, 'line_offset') else None
        vector = adapter.get_state_vector(
            vision_result=vision_result, imu_data=imu_data, ir_data=ir_data,
            line_offset=line_off,
            front_line_detected=getattr(state, 'front_line_detected', False),
            front_line_confirmed=getattr(state, 'front_line_confirmed', False),
            front_offset=getattr(state, 'front_offset', None),
            front_dash_count=getattr(state, 'front_dash_count', 0),
            corner_left_detected=getattr(state, 'corner_left_detected', False),
            corner_right_detected=getattr(state, 'corner_right_detected', False),
            corner_left_area=getattr(state, 'corner_left_area', 0),
            corner_right_area=getattr(state, 'corner_right_area', 0),
            center_dash_count=getattr(state, 'center_dash_count', 0),
        )
        return vector.tolist()

    def _infer_ml_classes(self):
        """Infère dynamiquement les classes de détection disponibles à partir des détecteurs du pipeline vision."""
        classes = []
        vp = self.vision_pipeline
        if not vp:
            return classes
        try:
            for det in vp.get_passive_detectors():
                if getattr(det, 'name', '') == 'HaarDetector' and hasattr(det, 'classes'):
                    for class_name in det.classes:  # Utilise la propriété .classes qui est déjà fournie
                        if class_name not in classes:
                            classes.append(class_name)
        except Exception:
            pass

        print(f"[DEBUG] ML Classes inférées: {classes}")
        return classes

    def _get_ml_adapter(self, state):
        """Crée une instance de VisionAdapter avec les dimensions d'image et les classes de détection actuelles."""
        if state and state.frame is not None:
            h, w = state.frame.shape[:2]
        else:
            frame = self.vision_pipeline.get_last_frame() if self.vision_pipeline else None
            if frame is not None:
                h, w = frame.shape[:2]
            else:
                w, h = 640, 480 # résolution par défaut
        if not self._ml_classes:
            self._ml_classes = self._infer_ml_classes()
        return VisionAdapter(image_width=w, image_height=h, classes=self._ml_classes)
