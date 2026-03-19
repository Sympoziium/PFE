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
    SPEED_LIMIT_MAX, SPEED_LIMIT_MIN,
    DRIVE_SPEED_DEFAULT, TURN_SPEED_DEFAULT,
    CAMERA_PROFILES
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
        self._ml_classes = []
        self._last_debug_print_time = 0.0  # Throttle du debug à ~3 Hz
        self.manual_drive_speed = DRIVE_SPEED
        self.manual_turn_speed = TURN_SPEED

        
        # --- CONFIGURATION DU PONT ---
        # ⚠️ REMPLACE CECI PAR L'IP QUE TON ARDUINO A AFFICHÉE
        self.BRIDGE_IP = "192.168.0.158" 
        self.BRIDGE_URL = "http://{}".format(self.BRIDGE_IP)
        # Index du détecteur sélectionné côté serveur
        self.selected_detector_index = 0
        # Dernière image capturée (nom de fichier) pour la détection à la demande
        self.last_captured_filename = None

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
    
    def motor_watchdog(self):
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

            # --- Logs des ressources système toutes les 20 secondes (40 itérations * 0.5s) ---
            if iteration_count % 40 == 0:
                self._log_resource_usage_internal()

            time.sleep(0.5)

    def _sampling_callback(self, state, command):
        """
        Callback de sampling synchronisé avec la boucle de contrôle.
        Appelé à chaque tick, immédiatement après step() et avant execute().

        Args:
            state: SensorState lu au tick courant
            command: MotorCommand retournée par le contrôleur actif
        """
        if not self.sampling_active:
            return

        try:
            adapter = self._get_ml_adapter(state)
            vector = self._vectorize_state_with_adapter(state, adapter)

            # Encodage du label directement depuis la commande reçue (atomique)
            label = adapter.encode_label(command.left_speed, command.right_speed).tolist()

            if vector is None or label is None:
                return

            # Validation des données
            import numpy as np
            v_array = np.array(vector)
            l_array = np.array(label)

            if adapter.validate_state_vector(v_array) and adapter.validate_label_vector(l_array):
                self.sampling_vectors.append(vector)
                self.sampling_labels.append(label)

                # Debug throttled à ~3 Hz pour visualiser les échantillons
                if self.debug_control_sampling:
                    now = time.time()
                    if now - self._last_debug_print_time >= 0.33:
                        self._last_debug_print_time = now
                        adapter.debug_print_state(v_array, l_array)
            else:
                print("[Sampling] Échantillon rejeté lors de la validation !")

        except Exception as e:
            print("[Sampling] Erreur dans callback: {}".format(e))

    # def _encode_label_from_command(self, command, adapter):
    #     """
    #     Encode le label directement depuis la commande moteur reçue.
    #     Garantit l'atomicité entre le vecteur d'état et le label.

    #     Args:
    #         command: MotorCommand du tick courant
    #         adapter: VisionAdapter pour l'encodage

    #     Returns:
    #         list: Label encodé [left_normalized, right_normalized]
    #     """
    #     if command.command_type == CommandType.SPEED:
    #         left = command.left_speed
    #         right = command.right_speed
    #     elif command.command_type == CommandType.FORWARD_STEP:
    #         left = command.speed
    #         right = command.speed
    #     else:
    #         # STOP ou autre type
    #         left = 0.0
    #         right = 0.0

    #     return adapter.encode_label(float(left), float(right)).tolist()

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

                # --- Overlay détection passive sur la frame d'affichage ---
                display_frame = frame_bgr
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
        Helper interne: Log LÉGER des ressources du Pi (appelé par motor_watchdog toutes les 5s).
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
            print("[Zumi] CPU: {:.1f}% | RAM: {:.1f}% | Threads: {}".format(
                cpu_percent, ram.percent, num_threads))
            print("[RAM] {:.1f} MB used | {:.1f} MB free | {:.1f} MB total | IO Wait: {:.2f}s".format(
                ram_used_mb, ram_free_mb, ram_total_mb, io_wait))
            print("[Timestamp] {}".format(time.strftime('%H:%M:%S')))
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
        """Délègue la commande de mouvement au ManualController via l'orchestrateur."""
        if not self.control_manager:
            return "ControlManager missing"

        if self.control_manager.get_controller("manual_controller") is None:
            return "Manual controller missing"
            
        # Si le contrôleur manuel n'est pas le contrôleur actif
        active = self.control_manager._active_controller
        if not active or active.name != "manual_controller":
            if active:
                self.control_manager.deactivate_controller()
            # On réinitialise l'état avant pour garantir que forward_step reste droit
            self.control_manager._reset_robot_drive_state()
            self.control_manager.activate_controller("manual_controller")
            
        ctrl = self.control_manager.get_controller("manual_controller")
        if ctrl:
            ctrl.set_action(action, speed=speed)
        return "ok"

    def forward(self): 
        return self._dispatch_manual_action("forward", self.manual_drive_speed)

    def reverse(self): 
        return self._dispatch_manual_action("reverse", self.manual_drive_speed)
        
    def left(self): 
        return self._dispatch_manual_action("left", self.manual_turn_speed)
        
    def right(self): 
        return self._dispatch_manual_action("right", self.manual_turn_speed)
        
    def stop(self): 
        print("[HTTP] /zumi/stop reçu")
        try:
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
            print("[ERREUR] zumi.turn({}):", angle, e)
            return jsonify({'error': str(e)}), 500

# ----------------------------------------------------------------------------
#          Fonctions pour le contrôle du pont
# ----------------------------------------------------------------------------
    def bridge_open(self):
        try:
            requests.get("{}/ouvrir".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except Exception as e:
            print("Erreur Pont:", e)
            return ("Erreur", 500)
        

    def bridge_close(self):
        try:
            requests.get("{}/fermer".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except Exception as e:
            print("Erreur Pont:", e)
            return ("Erreur", 500)
            
    def bridge_green(self):
        try:
            requests.get("{}/vert".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except: return ("", 500)

    def bridge_red(self):
        try:
            requests.get("{}/rouge".format(self.BRIDGE_URL), timeout=1)
            return ("", 204)
        except: return ("", 500)
   
    def bridge_mode_auto(self, etat):
        # etat doit être '1' (true) ou '0' (false)
        try:
            # On appelle l'URL du pont: http://192.168.X.X/majAutoMoteur?etat=1
            requests.get("{}/majAutoMoteur?etat={}".format(self.BRIDGE_URL, etat), timeout=1)
            return ("", 204)
        except Exception as e:
            print("Erreur Pont Mode Auto:", e)
            return ("Erreur", 500)


# ----------------------------------------------------------------------------
#          Fonctions de callback pour l'onglet de contrôle
# ----------------------------------------------------------------------------
    def manual_settings(self):
        if request.method == 'GET':
            payload = {
                'drive_speed': self.manual_drive_speed,
                'turn_speed': self.manual_turn_speed,
                'left_trim': getattr(self.robot, 'left_trim', None),
                'right_trim': getattr(self.robot, 'right_trim', None),
                'left_reverse_trim': getattr(self.robot, 'left_reverse_trim', None),
                'right_reverse_trim': getattr(self.robot, 'right_reverse_trim', None)
            }
            return jsonify(payload)

        data = request.get_json(silent=True) or {}
        if 'drive_speed' in data:
            self.manual_drive_speed = float(data['drive_speed'])
        if 'turn_speed' in data:
            self.manual_turn_speed = float(data['turn_speed'])

        left_trim = data.get('left_trim')
        right_trim = data.get('right_trim')
        left_reverse_trim = data.get('left_reverse_trim')
        right_reverse_trim = data.get('right_reverse_trim')
        
        if any(x is not None for x in [left_trim, right_trim, left_reverse_trim, right_reverse_trim]):
            if hasattr(self.robot, 'set_trim'):
                self.robot.set_trim(left_trim=left_trim, right_trim=right_trim, left_reverse_trim=left_reverse_trim, right_reverse_trim=right_reverse_trim)
            else:
                if left_trim is not None: self.robot.left_trim = float(left_trim)
                if right_trim is not None: self.robot.right_trim = float(right_trim)
                if left_reverse_trim is not None: self.robot.left_reverse_trim = float(left_reverse_trim)
                if right_reverse_trim is not None: self.robot.right_reverse_trim = float(right_reverse_trim)

        if self.control_manager:
            ctrl = self.control_manager.get_controller('manual_controller')
            if ctrl:
                ctrl.update_params(default_speed=self.manual_drive_speed)

        return jsonify({
            'drive_speed': self.manual_drive_speed,
            'turn_speed': self.manual_turn_speed,
            'left_trim': getattr(self.robot, 'left_trim', None),
            'right_trim': getattr(self.robot, 'right_trim', None)
        })
 
    def start_sampling(self):
        """ Démare l'échantillonnage des données des capteurs
        """
        if self.sampling_active is True:
            return jsonify({'error': 'Sampling already active'}), 400
        self.sampling_vectors = []
        self.sampling_labels = []
        self.sampling_active = True
        return jsonify({'status': 'sampling started'})
    
    def stop_sampling(self):
        """ Arrête l'échantillonnage des données des capteurs
        """
        if self.sampling_active is True:
            self.sampling_active = False
        return jsonify({'status': 'sampling stopped'})

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
            }
            if active:
                payload['controller_debug'] = active.get_debug_info()
                payload['controller_params'] = active.get_params()
            return jsonify(payload)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # def _collect_sensor_sample(self):
    #     """Collecte un échantillon de données des capteurs (vision + IMU + IR) et son label de commande moteur.
    #         Vectorisé déja ready pour l'entraînement ML"""
    #     if not self.sampling_active:
    #         return None, None, None

    #     try:
    #         state = SensorDriver(vision_pipeline=self.vision_pipeline, robot=self.robot).read()
    #         adapter = self._get_ml_adapter(state)
    #         vector = self._vectorize_state_with_adapter(state, adapter)
    #         raw_label = self._get_current_label()
    #         if vector is None or raw_label is None:
    #             return None, None, None
            
    #         # Normalisation du vecteur label de commande
    #         label = adapter.encode_label(raw_label[0], raw_label[1]).tolist()
            
    #         return vector, label, adapter
    #     except Exception as e:
    #         print("[Sampling] Erreur: {}".format(e))
    #         return None, None, None

    def _vectorize_state_with_adapter(self, state, adapter):
        if state is None:
            return None

        detections = state.detections or []
        vision_result = {'detections': detections}

        imu_data = {}
        if state.gyro_angles and len(state.gyro_angles) >= 5:
            imu_data = {
                'gx': float(state.gyro_angles[0]),
                'gy': float(state.gyro_angles[1]),
                'gz': float(state.gyro_angles[2]),
                'ax': float(state.gyro_angles[3]),
                'ay': float(state.gyro_angles[4]),
                'az': float(state.gyro_angles[5]) if len(state.gyro_angles) > 5 else 0.0,
            }

        ir_data = state.ir_sensors if state.ir_sensors is not None else None
        vector = adapter.get_state_vector(vision_result=vision_result, imu_data=imu_data, ir_data=ir_data)
        return vector.tolist()

    def _vectorize_state(self, state):
        adapter = self._get_ml_adapter(state)
        return self._vectorize_state_with_adapter(state, adapter)

    def _infer_ml_classes(self):
        """Infère dynamiquement les classes de détection disponibles à partir des détecteurs du pipeline vision."""
        classes = []
        vp = self.vision_pipeline
        if not vp:
            return classes
        try:
            for det in vp.get_detectors():
                if hasattr(det, 'classifiers') and isinstance(det.classifiers, dict):
                    for name in det.classifiers.keys():
                        if name not in classes:
                            classes.append(name)
                if getattr(det, 'name', '') == 'StopDetectorCV':
                    if 'Stop Sign' not in classes:
                        classes.append('Stop Sign')
        except Exception:
            pass
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

    # def _vectorize_state(self, state):
    #     if state is None:
    #         return None
    #     adapter = self._get_ml_adapter(state)

    #     detections = state.detections or []
    #     vision_result = {'detections': detections}

    #     imu_data = {}
    #     if state.gyro_angles and len(state.gyro_angles) >= 5:
    #         imu_data = {
    #             'gx': float(state.gyro_angles[0]),
    #             'gy': float(state.gyro_angles[1]),
    #             'gz': float(state.gyro_angles[2]),
    #             'ax': float(state.gyro_angles[3]),
    #             'ay': float(state.gyro_angles[4]),
    #             'az': float(state.gyro_angles[5]) if len(state.gyro_angles) > 5 else 0.0,
    #         }

    #     ir_data = state.ir_sensors if state.ir_sensors is not None else None
    #     vector = adapter.get_state_vector(vision_result=vision_result, imu_data=imu_data, ir_data=ir_data)
    #     return vector.tolist()

    # def _get_current_label(self):
    #     if self.control_manager and self.control_manager._motor_driver:
    #         command = self.control_manager._motor_driver.last_command
    #     else:
    #         command = None

    #     if command is None:
    #         return None

    #     if command.command_type == CommandType.SPEED:
    #         left = command.left_speed
    #         right = command.right_speed
    #     elif command.command_type == CommandType.FORWARD_STEP:
    #         left = command.speed
    #         right = command.speed
    #     else:
    #         left = 0
    #         right = 0

    #     return [float(left), float(right)]
        
