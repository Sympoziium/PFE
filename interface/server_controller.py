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

# --- Variables pour le Watchdog ---
WATCHDOG_TIMEOUT_SECONDS = 0.8 # S'arrête si aucune commande en 0.8s

class controller:
    def __init__(self, zumi):
        self.app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        self.robot = zumi # référence au robot Zumi a remplacer plus tard par la classe robot
        self.vision_pipeline = None
        self.last_move_time = time.time()
        self.watchdog_active = False
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

        # ── Mode haute résolution (optionnel) ──
        # Si ?hires=1 est passé en query param, on capture en haute résolution
        # pour améliorer la qualité de détection (surtout pour les petits objets).
        # La résolution par défaut est 320×240 mais peut être personnalisée via
        # ?hires_w=640&hires_h=480
        use_hires = request.args.get('hires', '0') == '1'
        
        if use_hires and vp.has_hires_capture():
            hires_w = int(request.args.get('hires_w', '320'))
            hires_h = int(request.args.get('hires_h', '240'))
            frame = vp.capture_hires_frame(width=hires_w, height=hires_h)
            if frame is None:
                return jsonify({'error': 'hires capture failed, try normal capture'}), 500
        else:
            # 1. Récupération de l'image actuelle sans ré-entrer dans le générateur
            #    Si le flux vidéo tourne, on utilise le dernier frame mis en buffer.
            frame = vp.get_last_frame()
            if frame is None:
                return jsonify({'error': 'Activer la camera car le flux est pas encore disponible'}), 400

        frame_to_save = frame.copy()  # Toujours en BGR

        # 2. Génération d'un nom de fichier unique
        ts = time.strftime("%Y%m%d-%H%M%S")
        hires_tag = '_hires' if use_hires else ''
        filename = '{}{}_{}.jpg'.format(ts, hires_tag, uuid.uuid4().hex[:6])
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
        hires_info = {'hires': True, 'resolution': '{}x{}'.format(hires_w, hires_h)} if use_hires else {'hires': False}
        return jsonify({'filename': filename, 'file_url': file_url, 'download_url': download_url, **hires_info})

    def capture_image_hires(self):
        """
        Capture dédiée en haute résolution.
        
        Interrompt brièvement le flux vidéo pour capturer une seule image
        à résolution supérieure (défaut 640×480). L'image est sauvegardée
        et prête pour la détection.
        
        Query params optionnels :
        - hires_w : largeur (défaut 640)
        - hires_h : hauteur (défaut 480)
        """
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'pipeline not initialized'}), 400

        if not vp.has_hires_capture():
            return jsonify({'error': 'hires capture not available on this camera'}), 400

        hires_w = int(request.args.get('hires_w', '640'))
        hires_h = int(request.args.get('hires_h', '480'))

        # Stopper le flux vidéo pour libérer la caméra
        was_running = vp.is_running()
        if was_running:
            vp.stop()
            import time as _t
            _t.sleep(0.2)

        frame = vp.capture_hires_frame(width=hires_w, height=hires_h)

        # NE PAS relancer le flux vidéo ici.
        # Le JS affiche une image statique après la capture, donc la caméra
        # n'a pas besoin de tourner. Elle sera redémarrée quand l'utilisateur
        # clique "Return to Livefeed" (via /start_camera).

        if frame is None:
            return jsonify({'error': 'hires capture returned no image'}), 500

        frame_to_save = frame.copy()

        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = '{}_hires_{}x{}_{}.jpg'.format(ts, hires_w, hires_h, uuid.uuid4().hex[:6])
        save_path = os.path.join(self.CAPTURE_DIR, filename)

        ok = cv2.imwrite(save_path, frame_to_save)
        if not ok:
            return jsonify({'error': 'write failed'}), 500

        file_url = url_for('static', filename='captured_images/{}'.format(filename))
        download_url = '/download_image/{}'.format(filename)
        self.last_captured_filename = filename

        h_actual, w_actual = frame_to_save.shape[:2]
        return jsonify({
            'filename': filename,
            'file_url': file_url,
            'download_url': download_url,
            'hires': True,
            'resolution': '{}x{}'.format(w_actual, h_actual)
        })

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
        if not vp or not vp.is_running():
            return "Camera not running", 503
        if vp.get_camera() is None:
            return "Camera not running", 503

        def generate():
            while vp.is_running():
                try:
                    # Capture du frame depuis la caméra
                    frame_bgr = vp.capture_frame()
                    # Mettre à jour le buffer pour les captures instantanées
                    # NOTE: on stocke la frame BRUTE (sans annotations) pour que
                    # le thread de détection passive travaille sur une image propre.
                    vp.update_last_frame(frame_bgr)
                except Exception:
                    time.sleep(0.1)
                    break

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

        # --- Badge compteur de détections (coin supérieur gauche) ---
        count = len(detections)
        badge_text = str(count)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        thickness = 2
        (tw, th), baseline = cv2.getTextSize(badge_text, font, font_scale, thickness)
        pad = 4
        bx, by = 4, 4
        # Fond du badge (vert)
        cv2.rectangle(annotated, (bx, by), (bx + tw + pad * 2, by + th + pad * 2 + baseline),
                      (0, 180, 0), cv2.FILLED)
        # Texte du badge (blanc)
        cv2.putText(annotated, badge_text, (bx + pad, by + th + pad),
                    font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        return annotated

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
        vp.start_passive_detection(detector_index=self.selected_detector_index)
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

