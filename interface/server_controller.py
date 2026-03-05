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

from flask import Flask, Response, request, jsonify, send_from_directory, url_for

from interface.onglet_acceuil import render_accueil_tab
from interface.onglet_vision import render_vision_tab
from interface.onglet_template import render_template_tab  # Exemple d'onglet template générique
from core.control.pid_controller import PIDController
from core.control.line_following_state_machine import StepByStepStateMachine
from core.control.control_manager import ControlManager, MODE_IDLE, MODE_PID, MODE_STATE_MACHINE, MODE_STEP_BY_STEP

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


# --- Variables pour le contrôle des moteurs ---
DRIVE_SPEED = 20
TURN_SPEED = 15
WATCHDOG_TIMEOUT_SECONDS = 0.8

class controller:
    def __init__(self, zumi):
        self.app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        self.robot = zumi
        self.vision_pipeline = None
        self.control_manager = None  # Initialisé via attach_control_manager()
        self.last_move_time = time.time()
        self.watchdog_active = False
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

    def attach_control_manager(self, control_manager):
        """Attache le ControlManager (orchestrateur de contrôle).

        Quand un ControlManager est attaché, les routes PID/step délèguent
        au manager plutôt que de gérer les threads en interne.
        """
        self.control_manager = control_manager
        # Utiliser le PID du ControlManager comme référence unique
        if control_manager.pid_controller is not None:
            self.pid_controller = control_manager.pid_controller

    # --- Navigation ---
    def home(self):
        return render_accueil_tab("Accueil")

    def vision(self):
        return render_vision_tab("Vision du Zumi")

    def onglet_template(self):
        return render_template_tab("Template")
    
    # --- Système ---
    def exit_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None: return jsonify({"error": "shutdown unavailable"}), 500
        func()
        return ('', 204)
    
    def motor_watchdog(self):
        """
        Thread qui s'exécute en arrière-plan.
        Arrête les moteurs si la dernière commande de mouvement
        est trop ancienne (ex: le client s'est déconnecté).
        
        *** AUSSI: Log les ressources du Pi toutes les 5 secondes ***
        (10 itérations * 0.5s = 5s) sans thread additionnel.
        """
        print("[Watchdog] Démarré (en attente d'activation).")
        iteration_count = 0
        
        while True:
            iteration_count += 1
            
            # --- Watchdog moteur ---
            if self.watchdog_active:
                time_since_last_move = time.time() - self.last_move_time
                if time_since_last_move > WATCHDOG_TIMEOUT_SECONDS:
                    try:
                        if self.robot: 
                            self.robot.stop()
                        self.last_move_time = time.time() 
                    except Exception as e:
                        pass
            
            # --- Log ressources toutes les 40s (40 itérations * 0.5s) ---
            if iteration_count % 40 == 0:
                self._log_resource_usage_internal()
            
            time.sleep(0.5)


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

            results = vp.process_frame(frame_bgr, detetor_index=self.selected_detector_index, filename=filename)

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


    # Flux vidéo
    def video_feed(self):
        vp = self.vision_pipeline
        if not vp or not vp.is_running(): return "Camera OFF", 503
        def generate():
            while vp.is_running():
                try:
                    # Capture directe depuis la caméra
                    # (get_last_frame ne fonctionne que si un contrôleur
                    #  peuple le buffer via vp.step(); ici on capture nous-mêmes)
                    frame_bgr = vp.camera.capture()
                    if frame_bgr is None:
                        time.sleep(0.1)
                        continue
                    # Mettre à jour le buffer pour les captures instantanées
                    # NOTE: on stocke la frame BRUTE (sans annotations) pour que
                    # le thread de détection passive travaille sur une image propre.
                    vp.update_last_frame(frame_bgr)
                except Exception:
                    time.sleep(0.1)
                    continue

                # --- Overlay détection passive sur la frame d'affichage ---
                display_frame = frame_bgr
                if vp._passive_running:
                    result = vp.get_last_detection_result()
                    if result and result.get('Object_detected'):
                        # Dessiner sur une copie pour ne pas polluer le buffer brut
                        display_frame = self._draw_passive_overlay(frame_bgr.copy(), result)

                # Encodage direct en JPEG depuis BGR
                ret, jpeg = cv2.imencode('.jpg', display_frame)
                if not ret:
                    continue
                yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.05) ### on impose une limite du livefeed a 20fps si on veux faire de la détection passive sa pourrais bloquer le Pi

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    # --- Helper: dessiner les résultats de détection passive sur une frame ---
    def _draw_passive_overlay(self, frame, result):
        """
        Dessine les bounding boxes et labels de la détection passive
        directement sur *frame* (qui doit être une copie).

        Utilise VisionPipeline.annotate_frame() pour garder un seul
        point de dessin dans tout le projet.
        Ajoute un petit badge indiquant le nombre de détections.

        :param frame: image BGR (copie) sur laquelle dessiner.
        :param result: dict retourné par process_passive() du détecteur,
                       contenant 'detections' -> list[{object, detection_box}].
        :return: frame annotée.
        """
        from core.vision.vision_pipeline import VisionPipeline
        detections = result.get('detections', [])
        if not detections:
            return frame
        annotated = VisionPipeline.annotate_frame(frame, detections)

        return annotated
    
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
            ram_available_mb = round(ram.available / (1024 * 1024), 1)
            io_wait = psutil.Process().cpu_times().iowait if hasattr(psutil.Process().cpu_times(), 'iowait') else 0
            # Format compact pour vision rapide dans le terminal
            print("[Zumi] CPU: {:.1f}% | RAM: {:.1f}% | Threads: {}".format(
                cpu_percent, ram.percent, num_threads))
            print("[Other] RAM Usage: {}/{} MB | IO Wait: {:.2f}s".format(ram_used_mb, ram_available_mb, io_wait))
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
    
    def forward(self): 
        self.last_move_time = time.time(); self.watchdog_active = True
        self.robot.control_motors(DRIVE_SPEED, DRIVE_SPEED)
        return "ok"

    def reverse(self): 
        self.last_move_time = time.time(); self.watchdog_active = True
        self.robot.control_motors(-DRIVE_SPEED, -DRIVE_SPEED)
        return "ok"
        
    def left(self): 
        self.last_move_time = time.time(); self.watchdog_active = True
        self.robot.control_motors(-TURN_SPEED, TURN_SPEED)
        return "ok"
        
    def right(self): 
        self.last_move_time = time.time(); self.watchdog_active = True
        self.robot.control_motors(TURN_SPEED, -TURN_SPEED)
        return "ok"
        
    def stop(self): 
        print("[HTTP] /zumi/stop reçu") 
        try: 
            self.robot.stop() 
            print("[ACTION] zumi.stop() exécuté") 
            return "ok" 
        except Exception as e: 
            print("[ERREUR] zumi.stop():", e) 
            return "error", 500
      

    def manual_turn(self):
        """
        Fait tourner le Zumi d'un angle spécifié (rotation précise avec gyroscope).
        Attend un JSON avec la clé 'angle' (en degrés).
        Angle positif = rotation à gauche, angle négatif = rotation à droite.
        """
        data = request.get_json(silent=True) or {}
        angle = data.get('angle', 0)
        
        print("[HTTP] /zumi/turn reçu - angle: {}°".format(angle))
        
        try:
            angle_float = float(angle)
            
            if angle_float == 0:
                return jsonify({'status': 'ok', 'message': 'Angle nul, aucune rotation'}), 200
            
            if not hasattr(self.robot, 'turn'):
                return jsonify({'error': 'La méthode turn() n\'est pas disponible sur ce robot'}), 400
            
            self.robot.turn(angle_float)
            direction = "gauche" if angle_float > 0 else "droite"
            print("[ACTION] zumi.turn({}) exécuté - Rotation de {} degrés vers la {}".format(angle_float, abs(angle_float), direction))
            
            return jsonify({
                'status': 'ok', 
                'angle': angle_float, 
                'direction': direction,
                'message': 'Rotation de {} degrés vers la {} complétée'.format(abs(angle_float), direction)
            }), 200
            
        except ValueError:
            print("[ERREUR] Angle invalide: {}".format(angle))
            return jsonify({'error': 'Angle invalide: doit être un nombre'}), 400
        except Exception as e:
            print("[ERREUR] zumi.turn({}):", angle, e)
            return jsonify({'error': str(e)}), 500

# ----------------------------------------------------------------------------
#          Fonctions pour le contrôle PID du suivi de ligne
# ----------------------------------------------------------------------------

    def pid_page(self):
        from interface.onglet_pid import render_pid_tab
        return render_pid_tab("Asservissement PID")

    def pid_update_params(self):
        """Met à jour les paramètres du PID."""
        data = request.get_json(silent=True) or {}
        try:
            kp = float(data.get('kp', self.pid_controller.kp))
            ki = float(data.get('ki', self.pid_controller.ki))
            kd = float(data.get('kd', self.pid_controller.kd))
            base_speed = int(data.get('base_speed', self.pid_controller.base_speed))
            max_correction = int(data.get('max_correction', self.pid_controller.max_correction))
            rotation_mode = bool(data.get('rotation_mode', self.pid_controller.rotation_mode))
            
            # Nouveaux paramètres pour le calcul d'angle
            angle_scale = float(data.get('angle_scale', self.pid_controller.angle_scale))
            max_angle = float(data.get('max_angle', self.pid_controller.max_angle))
            min_angle_threshold = float(data.get('min_angle_threshold', self.pid_controller.min_angle_threshold))
            
            self.pid_controller.update_params(kp=kp, ki=ki, kd=kd, 
                                            base_speed=base_speed, 
                                            max_correction=max_correction,
                                            rotation_mode=rotation_mode,
                                            angle_scale=angle_scale,
                                            max_angle=max_angle,
                                            min_angle_threshold=min_angle_threshold)
            
            return jsonify({'status': 'ok', 'params': self.pid_controller.get_params()})
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    def pid_get_params(self):
        """Retourne les paramètres actuels du PID."""
        return jsonify(self.pid_controller.get_params())

    def pid_start(self):
        """Démarre le contrôle PID."""
        try:
            print("[DEBUG] pid_start() appelé")

            vp = self.vision_pipeline
            if not vp:
                return jsonify({'error': 'Vision pipeline not initialized'}), 400
            # Auto-start caméra si nécessaire
            if not vp.is_running():
                print("[INFO] pid_start: caméra inactive, démarrage automatique...")
                vp.start()
                time.sleep(0.3)  # laisser le temps à la caméra de s'initialiser

            # --- Via ControlManager (nouvelle architecture) ---
            if self.control_manager is not None:
                if self.control_manager.mode != MODE_IDLE:
                    return jsonify({'error': 'Un autre mode est déjà actif: {}'.format(self.control_manager.mode)}), 400
                self.control_manager.activate(MODE_PID)
                self.pid_active = True
                return jsonify({'status': 'started'})

            # --- Fallback legacy (sans ControlManager) ---
            if self.pid_active:
                return jsonify({'error': 'PID already running'}), 400

            if self.pid_thread and self.pid_thread.is_alive():
                print("[WARNING] Thread PID encore actif, arrêt forcé")
                self.pid_active = False
                self.pid_thread.join(timeout=2.0)
                self.pid_thread = None

            self.pid_controller.reset()
            self.pid_active = True

            import threading
            def pid_loop():
                loop_count = 0
                while self.pid_active:
                    try:
                        line_offset = getattr(vp, 'last_line_offset', None)
                        if line_offset is None:
                            self.robot.stop()
                            time.sleep(0.05)
                            continue

                        if self.pid_controller.rotation_mode:
                            angle = self.pid_controller.compute_rotation_angle(line_offset)
                            if angle is not None:
                                self.robot.turn(angle)
                                self.last_line_offset = line_offset
                                self.last_correction = angle
                            else:
                                self.robot.stop()
                                self.last_line_offset = line_offset
                                self.last_correction = 0
                            time.sleep(0.2)
                        else:
                            left_speed, right_speed = self.pid_controller.compute(line_offset)
                            self.robot.control_motors(left_speed, right_speed)
                            self.last_line_offset = line_offset
                            self.last_correction = self.pid_controller.correction_history[-1] if self.pid_controller.correction_history else 0
                            self.last_left_speed = left_speed
                            self.last_right_speed = right_speed
                            time.sleep(0.05)

                    except Exception as e:
                        print("[ERROR] pid_loop: {}".format(e))
                        time.sleep(0.1)
                self.robot.stop()

            self.pid_thread = threading.Thread(target=pid_loop, daemon=True)
            self.pid_thread.start()
            return jsonify({'status': 'started'})

        except Exception as e:
            print("[ERROR] pid_start(): {}".format(e))
            import traceback
            traceback.print_exc()
            self.pid_active = False
            return jsonify({'error': 'Failed to start PID: {}'.format(str(e))}), 500

    def pid_stop(self):
        """Arrête le contrôle PID."""
        print("[DEBUG] pid_stop() appelé")

        # --- Via ControlManager ---
        if self.control_manager is not None and self.control_manager.mode == MODE_PID:
            self.control_manager.deactivate()
            self.pid_active = False
            self.last_line_offset = 0
            self.last_correction = 0
            self.last_left_speed = 0
            self.last_right_speed = 0
            return jsonify({'status': 'stopped'})

        # --- Fallback legacy ---
        self.pid_active = False

        if self.pid_thread and self.pid_thread.is_alive():
            self.pid_thread.join(timeout=2.0)
        self.pid_thread = None

        self.robot.stop()
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        
        print("[DEBUG] PID arrêté avec succès")
        return jsonify({'status': 'stopped'})

    def pid_reset(self):
        """Réinitialise le PID."""
        self.pid_controller.reset()
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        return jsonify({'status': 'reset'})

    def pid_status(self):
        """Retourne le statut actuel du PID."""
        # --- Via ControlManager ---
        if self.control_manager is not None:
            cm = self.control_manager
            with cm._data_lock:
                return jsonify({
                    'active': cm.mode == MODE_PID,
                    'mode': cm.mode,
                    'error': cm.last_line_offset,
                    'correction': cm.last_correction,
                    'left_speed': cm.last_left_speed,
                    'right_speed': cm.last_right_speed,
                    'debug': self.pid_controller.get_debug_info()
                })

        # --- Fallback legacy ---
        return jsonify({
            'active': self.pid_active,
            'error': self.last_line_offset,
            'correction': self.last_correction,
            'left_speed': self.last_left_speed,
            'right_speed': self.last_right_speed,
            'debug': self.pid_controller.get_debug_info()
        })
    
    def line_detector_update_params(self):
        """Met à jour les paramètres du détecteur de ligne."""
        vp = self.vision_pipeline
        if not vp:
            return jsonify({'error': 'Vision pipeline not initialized'}), 400
        
        # Trouver le détecteur de ligne
        line_detector = None
        for detector in vp.get_detectors():
            if hasattr(detector, 'white_threshold'):  # C'est le LineDetector
                line_detector = detector
                break
        
        if not line_detector:
            return jsonify({'error': 'Line detector not found'}), 404
        
        data = request.get_json(silent=True) or {}
        try:
            white_threshold = data.get('white_threshold')
            min_area = data.get('min_area')
            offset_ratio = data.get('offset_ratio')
            
            line_detector.update_params(
                white_threshold=white_threshold,
                min_area=min_area,
                offset_ratio=offset_ratio
            )
            
            return jsonify({'status': 'ok', 'params': line_detector.get_params()})
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    def line_detector_get_params(self):
        """Retourne les paramètres actuels du détecteur de ligne."""
        vp = self.vision_pipeline
        if not vp:
            return jsonify({'error': 'Vision pipeline not initialized'}), 400
        
        # Trouver le détecteur de ligne
        line_detector = None
        for detector in vp.get_detectors():
            if hasattr(detector, 'white_threshold'):
                line_detector = detector
                break
        
        if not line_detector:
            return jsonify({'error': 'Line detector not found'}), 404
        
        return jsonify(line_detector.get_params())
    
    def state_machine_start(self):
        """Démarre la machine à états."""
        # Auto-start caméra si nécessaire
        vp = self.vision_pipeline
        if vp and not vp.is_running():
            print("[INFO] state_machine_start: caméra inactive, démarrage automatique...")
            vp.start()
            time.sleep(0.3)

        # --- Via ControlManager ---
        if self.control_manager is not None:
            if self.control_manager.state_machine is None:
                return jsonify({'error': 'State machine not registered in ControlManager'}), 400
            if self.control_manager.mode != MODE_IDLE:
                return jsonify({'error': 'Un autre mode est déjà actif: {}'.format(self.control_manager.mode)}), 400
            self.control_manager.activate(MODE_STATE_MACHINE)
            return jsonify({'status': 'started', 'state': self.control_manager.state_machine.get_state().name})

        # --- Fallback legacy ---
        if not hasattr(self, 'state_machine'):
            return jsonify({'error': 'State machine not initialized'}), 400
        self.state_machine.start()
        return jsonify({'status': 'started', 'state': self.state_machine.get_state().name})

    def state_machine_stop(self):
        """Arrête la machine à états."""
        # --- Via ControlManager ---
        if self.control_manager is not None and self.control_manager.mode == MODE_STATE_MACHINE:
            self.control_manager.deactivate()
            return jsonify({'status': 'stopped'})

        # --- Fallback legacy ---
        if not hasattr(self, 'state_machine'):
            return jsonify({'error': 'State machine not initialized'}), 400
        self.state_machine.stop()
        return jsonify({'status': 'stopped'})

    def state_machine_status(self):
        """Retourne le statut de la machine à états."""
        # --- Via ControlManager ---
        sm = None
        if self.control_manager is not None and self.control_manager.state_machine is not None:
            sm = self.control_manager.state_machine
        elif hasattr(self, 'state_machine'):
            sm = self.state_machine

        if sm is None:
            return jsonify({'error': 'State machine not initialized'}), 400

        return jsonify({
            'running': sm.is_running(),
            'state': sm.get_state().name,
            'photos_taken': len(sm.photos_taken),
            'rotation_count': sm.rotation_count
        })
    
    # ===== MODE STEP-BY-STEP =====
    
    def pid_step_start(self):
        """Démarre le mode step-by-step."""
        try:
            print("[DEBUG] pid_step_start() appelé")

            vp = self.vision_pipeline
            if not vp:
                return jsonify({'error': 'Vision pipeline not initialized'}), 400
            # Auto-start caméra si nécessaire
            if not vp.is_running():
                print("[INFO] pid_step_start: caméra inactive, démarrage automatique...")
                vp.start()
                time.sleep(0.3)

            # --- Via ControlManager ---
            if self.control_manager is not None:
                if self.control_manager.mode != MODE_IDLE:
                    return jsonify({'error': 'Un autre mode est déjà actif: {}'.format(self.control_manager.mode)}), 400
                self.control_manager.activate(MODE_STEP_BY_STEP)
                self.step_mode_active = True
                # Garder une référence locale pour les routes status/approve
                self.step_machine = self.control_manager.step_machine
                return jsonify({'status': 'started'})

            # --- Fallback legacy ---
            if self.step_mode_active:
                return jsonify({'error': 'Step mode already running'}), 400
            if self.pid_active:
                return jsonify({'error': 'Normal PID is running. Stop it first.'}), 400

            # Trouver le détecteur de ligne
            line_detector = None
            for detector in vp.get_detectors():
                if hasattr(detector, 'white_threshold'):
                    line_detector = detector
                    break
            if not line_detector:
                return jsonify({'error': 'Line detector not found'}), 404

            if self.step_machine is None:
                self.step_machine = StepByStepStateMachine(
                    robot=self.robot,
                    camera=vp.camera,
                    pid_controller=self.pid_controller,
                    line_detector=line_detector
                )

            self.step_machine.start()
            self.step_mode_active = True

            import threading
            def step_loop():
                while self.step_mode_active:
                    try:
                        # Capture directe depuis la caméra pas 
                        frame = vp.camera.capture()
                        if frame is None:
                            time.sleep(0.05)
                            continue
                        vp.update_last_frame(frame)
                        result = self.step_machine.step(frame)
                        self.last_line_offset = result.get('line_offset', 0)
                        self.last_left_speed = result.get('left_speed', 0)
                        self.last_right_speed = result.get('right_speed', 0)
                        time.sleep(0.05)
                    except Exception as e:
                        print("[ERROR] step_loop: {}".format(e))
                        time.sleep(0.1)
                self.robot.stop()

            self.step_mode_thread = threading.Thread(target=step_loop, daemon=True)
            self.step_mode_thread.start()
            return jsonify({'status': 'started'})

        except Exception as e:
            print("[ERROR] pid_step_start(): {}".format(e))
            import traceback
            traceback.print_exc()
            self.step_mode_active = False
            return jsonify({'error': 'Failed to start step mode: {}'.format(str(e))}), 500
    
    def pid_step_stop(self):
        """Arrête le mode step-by-step."""
        print("[DEBUG] pid_step_stop() appelé")

        # --- Via ControlManager ---
        if self.control_manager is not None and self.control_manager.mode == MODE_STEP_BY_STEP:
            self.control_manager.deactivate()
            self.step_mode_active = False
            self.last_line_offset = 0
            self.last_correction = 0
            self.last_left_speed = 0
            self.last_right_speed = 0
            return jsonify({'status': 'stopped'})

        # --- Fallback legacy ---
        if self.step_machine:
            self.step_machine.stop()
        self.step_mode_active = False

        if self.step_mode_thread and self.step_mode_thread.is_alive():
            self.step_mode_thread.join(timeout=2.0)
        self.step_mode_thread = None

        self.robot.stop()
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        return jsonify({'status': 'stopped'})
    
    def pid_step_approve(self):
        """Approuve la prochaine étape."""
        # Via ControlManager ou référence locale
        sm = None
        if self.control_manager is not None and self.control_manager.step_machine is not None:
            sm = self.control_manager.step_machine
        elif self.step_machine:
            sm = self.step_machine

        if sm is None or not (self.step_mode_active or
                              (self.control_manager and self.control_manager.mode == MODE_STEP_BY_STEP)):
            return jsonify({'error': 'Step mode not running'}), 400

        sm.approve_next_step()
        return jsonify({'status': 'approved'})

    def pid_step_status(self):
        """Retourne le statut du mode step-by-step."""
        # Via ControlManager ou référence locale
        sm = None
        active = False
        if self.control_manager is not None and self.control_manager.step_machine is not None:
            sm = self.control_manager.step_machine
            active = self.control_manager.mode == MODE_STEP_BY_STEP
        elif self.step_machine:
            sm = self.step_machine
            active = self.step_mode_active

        if sm is None:
            return jsonify({
                'active': False,
                'state': 'IDLE',
                'waiting_approval': False
            })

        # Lire les données depuis le ControlManager si disponible
        line_offset = self.last_line_offset
        left_speed = self.last_left_speed
        right_speed = self.last_right_speed
        if self.control_manager is not None:
            with self.control_manager._data_lock:
                line_offset = self.control_manager.last_line_offset or 0
                left_speed = self.control_manager.last_left_speed
                right_speed = self.control_manager.last_right_speed

        return jsonify({
            'active': active,
            'state': sm.get_state().name,
            'waiting_approval': sm.is_waiting_approval(),
            'step_count': sm.step_count,
            'line_offset': line_offset,
            'left_speed': left_speed,
            'right_speed': right_speed
        })
    # --- PONT (Nouvelles fonctions) ---
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
