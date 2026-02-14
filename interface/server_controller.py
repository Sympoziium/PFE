#!/usr/bin/env python
# -*- coding: utf-8 -*-
# server_controller.py
# ------------------
"""Contrôleur backend pour les routes Flask.

Centralise la logique des endpoints; `flask_router.py` ne fait que lier les routes
à ces méthodes.
"""

import os, uuid, time, cv2, numpy as np
from flask import Flask, Response, request, jsonify, send_from_directory, url_for

from interface.onglet_acceuil import render_accueil_tab
from interface.onglet_vision import render_vision_tab
from interface.onglet_template import render_template_tab  # Exemple d'onglet template générique
from core.robot.pid_controller import PIDController

# --- Fonction helper pour formater les résultats de détection ---
def format_detection_result(results, detector_name="Détecteur"):
    """
    Formate les résultats de détection pour un affichage lisible dans les logs.

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

    # Détection générale (clé standardisée + fallbacks legacy)
    detected = results.get('Object_detected',
        results.get('Stop_detected',
        results.get('Object detected', False)))
    lines.append('Objet détecté: {}'.format('OUI' if detected else 'NON'))

    # Boîte de détection (clé standardisée + fallback legacy)
    bbox = results.get('detection_box') or results.get('Object coordinates')
    if bbox:
        if len(bbox) == 4:  # (x, y, w, h)
            x, y, w, h = bbox
            lines.append('Position: x={}, y={}'.format(int(x), int(y)))
            lines.append('Taille: largeur={}, hauteur={}'.format(int(w), int(h)))
        elif len(bbox) == 2:  # (x, y)
            x, y = bbox
            lines.append('Position: x={}, y={}'.format(int(x), int(y)))
            size = results.get('Object size')
            if size and len(size) == 2:
                w, h = size
                lines.append('Taille: largeur={}, hauteur={}'.format(int(w), int(h)))

    # Confiance (si disponible)
    conf = results.get('confidence')
    if conf is not None and conf > 0:
        lines.append('Confiance: {:.1%}'.format(float(conf)))

    # Aire (si disponible)
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

# --- Variables pour le Watchdog ---
WATCHDOG_TIMEOUT_SECONDS = 0.8 # S'arrête si aucune commande en 0.8s

class controller:
    def __init__(self, zumi):
        self.app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        self.robot = zumi # référence au robot Zumi a remplacer plus tard par la classe robot
        self.vision_pipeline = None
        self.last_move_time = time.time()
        self.watchdog_active = False
        self.pid_controller = PIDController()
        self.pid_active = False
        self.pid_thread = None
        self.last_line_offset = 0
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0
        # Dossier pour sauvegarder les captures d'images
        self.CAPTURE_DIR = os.path.join(self.app.static_folder, 'captured_images')
        os.makedirs(self.CAPTURE_DIR, exist_ok=True)
        # Index du détecteur sélectionné côté serveur
        self.selected_detector_index = 0
        # Dernière image capturée (nom de fichier) pour la détection à la demande
        self.last_captured_filename = None

    # Attache le pipeline de vision
    def attach_pipeline_vision(self, pipeline):
        pipeline.attach_capture_dir(self.CAPTURE_DIR)
        self.vision_pipeline = pipeline

# ----------------------------------------------------------------------------
#                       Navigation entre onglets
# ----------------------------------------------------------------------------

    # Pages
    def home(self):
        return render_accueil_tab("Accueil")

    def vision(self):
        return render_vision_tab("Vision du Zumi")

    def onglet_template(self):
        return render_template_tab("Mon onglet perso")
    
# ----------------------------------------------------------------------------
#                       fonctions utilitaires
# ----------------------------------------------------------------------------
    # Arrêt du serveur
    def exit_server(self):
        vp = self.vision_pipeline
        try:
            if vp and vp.is_running():
                vp.stop()
        except Exception:
            pass

        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            return jsonify({"error": "shutdown unavailable"}), 500
        self.app.logger.info("Arrêt du serveur Flask demandé via /exit")
        func()  # Le serveur s'arrêtera après cette requête
        return ('', 204)
    
    def motor_watchdog(self):
        """
        Thread qui s'exécute en arrière-plan.
        Arrête les moteurs si la dernière commande de mouvement
        est trop ancienne (ex: le client s'est déconnecté).
        """
        print("[Watchdog] Démarré (en attente d'activation).")
        
        while True:
            # Ne pas s'activer avant la première commande de mouvement
            if not self.watchdog_active:
                time.sleep(0.5)
                continue
            
            # Calculer le temps écoulé
            time_since_last_move = time.time() - self.last_move_time
            
            if time_since_last_move > WATCHDOG_TIMEOUT_SECONDS:
                try:
                    # S'assurer que zumi existe avant de l'appeler
                    if self.robot: 
                        self.robot.stop()
                    # Réinitialiser pour ne pas 'spammer' la commande stop
                    self.last_move_time = time.time() 
                except Exception as e:
                    pass # Erreur silencieuse (ex: zumi déconnecté)
            
            time.sleep(0.5) # Vérifier 2x par seconde


# ----------------------------------------------------------------------------
#            Fonctions de callback pour les actions de vision
# ----------------------------------------------------------------------------

    # Téléchargement d'une image capturée
    def download_image(self, filename):
        full_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(full_path):
            return "File not found", 404
        return send_from_directory(self.CAPTURE_DIR, filename, as_attachment=True)

    # Capture d'image
    def capture_image(self):
        vp = self.vision_pipeline
        if vp is None or not vp.is_running():
            return jsonify({'error': 'camera not running'}), 400

        # 1. Récupération de l'image actuelle sans ré-entrer dans le générateur
        #    Si le flux vidéo tourne, on utilise le dernier frame mis en buffer.
        frame = vp.get_last_frame()
        if frame is None:
            # Pas de flux actif ou pas encore d'image en buffer: on capture directement
            return jsonify({'error': 'Activer la camera car le flux est pas encore disponible'}), 400

        frame_to_save = frame.copy()  # Toujours en BGR

        # 2. Génération d'un nom de fichier unique
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = '{}_{}.jpg'.format(ts, uuid.uuid4().hex[:6])
        save_path = os.path.join(self.CAPTURE_DIR, filename)

        # 3. Sauvegarde directe en BGR (format natif OpenCV)
        ok = cv2.imwrite(save_path, frame_to_save)
        if not ok:
            return jsonify({'error': 'write failed'}), 500

        # 4. URL de téléchargement
        file_url = url_for('static', filename='captured_images/{}'.format(filename))
        download_url = '/download_image/{}'.format(filename)
        # Mémoriser la dernière image capturée pour une détection à la demande
        self.last_captured_filename = filename
        return jsonify({'filename': filename, 'file_url': file_url, 'download_url': download_url})

    # Statut
    def status(self):
        vp = self.vision_pipeline
        return jsonify({
            "camera_running": bool(vp and vp.is_running())
        })

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
        Le détecteur se charge de l'annotation et retourne un payload
        standardisé (Object_detected, detection_box, annotated_url, etc.).
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

            # Inclure les URLs utiles pour l'interface
            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            payload = dict(results)
            payload['source_filename'] = filename
            # S'assurer que les clés standardisées sont présentes
            if 'source_file_url' not in payload:
                payload['source_file_url'] = source_url

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
        if not vp or not vp.is_running():
            return "Camera not running", 503
        if vp.get_camera() is None:
            return "Camera not running", 503

        def generate():
            while vp.is_running():
                try:
                    # Capture du frame depuis la caméra
                    frame_bgr = vp.get_last_frame()
                    # Mettre à jour le buffer pour les captures instantanées
                    vp.update_last_frame(frame_bgr)
                except Exception:
                    time.sleep(0.1)
                    break
                # Encodage direct en JPEG depuis BGR
                ret, jpeg = cv2.imencode('.jpg', frame_bgr)
                if not ret:
                    continue
                yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.05)

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    # Caméra: stop/start
    def close_camera(self):
        vp = self.vision_pipeline
        if not vp or not vp.is_running():
            return ("", 204)
        vp.stop()
        return ("", 204)

    def start_camera(self):
        vp = self.vision_pipeline
        if vp and vp.is_running():
            return ("", 204)
        vp.start()
        return ("", 204)
    
# ----------------------------------------------------------------------------
#          Fonctions de callback pour les actions moteur du robot
# ----------------------------------------------------------------------------
    
    def forward(self): 
        self.last_move_time = time.time()              
        self.watchdog_active = True                    
        print("[HTTP] /zumi/forward reçu") 
        try: 
            self.robot.control_motors(DRIVE_SPEED, DRIVE_SPEED) 
            print("[ACTION] zumi.control_motors({}, {}) exécuté".format(DRIVE_SPEED, DRIVE_SPEED)) 
            return "ok" 
        except Exception as e: 
            print("[ERREUR] zumi.control_motors(forward):", e) 
            return "error", 500 

    
    def reverse(self): 
        self.last_move_time = time.time()              
        self.watchdog_active = True                    
        print("[HTTP] /zumi/reverse reçu") 
        try: 
            self.robot.control_motors(-DRIVE_SPEED, -DRIVE_SPEED) 
            print("[ACTION] zumi.control_motors({}, {}) exécuté".format(-DRIVE_SPEED, -DRIVE_SPEED)) 
            return "ok" 
        except Exception as e: 
            print("[ERREUR] zumi.control_motors(reverse):", e) 
            return "error", 500 
        
    
    def left(self): 
        self.last_move_time = time.time()              
        self.watchdog_active = True                    
        print("[HTTP] /zumi/left reçu") 
        try: 
            self.robot.control_motors(-TURN_SPEED, TURN_SPEED)  
            print("[ACTION] zumi.control_motors({}, {}) exécuté".format(-TURN_SPEED, TURN_SPEED)) 
            return "ok" 
        except Exception as e: 
            print("[ERREUR] zumi.control_motors(left):", e) 
            return "error", 500 
        
    
    def right(self): 
        self.last_move_time = time.time()              
        self.watchdog_active = True                    
        print("[HTTP] /zumi/right reçu") 
        try: 
            self.robot.control_motors(TURN_SPEED, -TURN_SPEED) 
            print("[ACTION] zumi.control_motors({}, {}) exécuté".format(TURN_SPEED, -TURN_SPEED)) 
            return "ok" 
        except Exception as e: 
            print("[ERREUR] zumi.control_motors(right):", e) 
            return "error", 500 
        
    
    def stop(self): 
        print("[HTTP] /zumi/stop reçu") 
        try: 
            self.robot.stop() 
            print("[ACTION] zumi.stop() exécuté") 
            return "ok" 
        except Exception as e: 
            print("[ERREUR] zumi.stop():", e) 
            return "error", 500

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
            rotation_mode = bool(data.get('rotation_mode', self.pid_controller.rotation_mode))  # NOUVEAU
            
            self.pid_controller.update_params(kp=kp, ki=ki, kd=kd, 
                                            base_speed=base_speed, 
                                            max_correction=max_correction,
                                            rotation_mode=rotation_mode)  # NOUVEAU
            
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
            
            # Vérifier si un PID est déjà actif
            if self.pid_active:
                print("[WARNING] PID déjà actif")
                return jsonify({'error': 'PID already running'}), 400
            
            # Vérifier si un thread PID existe encore
            if self.pid_thread and self.pid_thread.is_alive():
                print("[WARNING] Thread PID encore actif, arrêt forcé")
                self.pid_active = False
                self.pid_thread.join(timeout=2.0)
                self.pid_thread = None
            
            vp = self.vision_pipeline
            print("[DEBUG] Vision pipeline: {}".format(vp))
            
            if not vp:
                print("[DEBUG] Vision pipeline est None")
                return jsonify({'error': 'Vision pipeline not initialized'}), 400
                
            if not vp.is_running():
                print("[DEBUG] Vision pipeline n'est pas en cours d'exécution")
                return jsonify({'error': 'Camera not running. Please start camera first.'}), 400
            
            print("[DEBUG] Vérification du PID controller")
            if not hasattr(self, 'pid_controller') or self.pid_controller is None:
                print("[ERROR] pid_controller n'existe pas!")
                return jsonify({'error': 'PID controller not initialized'}), 500
            
            print("[DEBUG] Réinitialisation du PID")
            self.pid_controller.reset()
            self.pid_active = True
            
            print("[DEBUG] Création du thread PID")
            import threading
            def pid_loop():
                print("[PID_LOOP] Démarrage du pid_loop")
                loop_count = 0
                while self.pid_active:
                    try:
                        loop_count += 1
                        
                        # CHANGEMENT: Récupérer l'offset déjà calculé par control_loop
                        line_offset = getattr(vp, 'last_line_offset', None)
                        
                        if line_offset is None:
                            # Pas de ligne détectée, arrêter les moteurs
                            self.robot.stop()
                            time.sleep(0.05)
                            continue
                        
                        # Debug tous les 20 cycles
                        if loop_count % 20 == 0:
                            print("[PID_LOOP] Offset: {}, PID actif: {}".format(line_offset, self.pid_active))
                        
                        # Calculer la correction PID
                        left_speed, right_speed = self.pid_controller.compute(line_offset)
                        
                        # Appliquer aux moteurs
                        self.robot.control_motors(left_speed, right_speed)
                        
                        # Sauvegarder pour l'affichage
                        self.last_line_offset = line_offset
                        self.last_correction = self.pid_controller.correction_history[-1] if self.pid_controller.correction_history else 0
                        self.last_left_speed = left_speed
                        self.last_right_speed = right_speed
                        
                        time.sleep(0.05)  # 20 Hz
                        
                    except Exception as e:
                        print("[ERROR] Erreur dans pid_loop: {}".format(e))
                        import traceback
                        traceback.print_exc()
                        time.sleep(0.1)
                
                print("[PID_LOOP] Arrêt du pid_loop (loops effectués: {})".format(loop_count))
                # Arrêter les moteurs à la fin
                self.robot.stop()
            
            self.pid_thread = threading.Thread(target=pid_loop)
            self.pid_thread.daemon = True
            self.pid_thread.start()
            
            print("[DEBUG] PID démarré avec succès, thread ID: {}".format(self.pid_thread.ident))
            return jsonify({'status': 'started'})
            
        except Exception as e:
            print("[ERROR] Exception dans pid_start(): {}".format(e))
            import traceback
            traceback.print_exc()
            self.pid_active = False
            return jsonify({'error': 'Failed to start PID: {}'.format(str(e))}), 500

    def pid_stop(self):
        """Arrête le contrôle PID."""
        print("[DEBUG] pid_stop() appelé")
        print("[DEBUG] pid_active avant arrêt: {}".format(self.pid_active))
        
        # Marquer le PID comme inactif
        self.pid_active = False
        
        # Attendre que le thread se termine
        if self.pid_thread and self.pid_thread.is_alive():
            print("[DEBUG] Attente de la fin du thread PID...")
            self.pid_thread.join(timeout=2.0)  # Augmenté à 2 secondes
            if self.pid_thread.is_alive():
                print("[WARNING] Le thread PID n'a pas terminé dans le délai")
            else:
                print("[DEBUG] Thread PID terminé proprement")
        
        # Nettoyer le thread
        self.pid_thread = None
        
        # Arrêter les moteurs
        self.robot.stop()
        
        # Réinitialiser les valeurs affichées
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