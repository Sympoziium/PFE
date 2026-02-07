#!/usr/bin/env python
# -*- coding: utf-8 -*-
# server_controller.py

import requests  # <--- IMPORTANT : Pour communiquer avec le pont
import os, uuid, time, cv2, itertools, numpy as np
from flask import Flask, Response, request, jsonify, send_from_directory, url_for

from interface.onglet_acceuil import render_accueil_tab
from interface.onglet_vision import render_vision_tab
from interface.onglet_template import render_template_tab

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

    # Détection générale
    detected = results.get('Stop_detected', results.get('Object detected', False))
    lines.append('Objet détecté: {}'.format('OUI' if detected else 'NON'))

    # Boîte de détection
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
WATCHDOG_TIMEOUT_SECONDS = 0.8

class controller:
    def __init__(self, zumi):
        self.app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        self.robot = zumi
        self.vision_pipeline = None
        self.last_move_time = time.time()
        self.watchdog_active = False
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
        pipeline.atach_capture_dir(self.CAPTURE_DIR)
        self.vision_pipeline = pipeline

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
        print("[Watchdog] Démarré.")
        while True:
            if self.watchdog_active:
                if time.time() - self.last_move_time > WATCHDOG_TIMEOUT_SECONDS:
                    try:
                        if self.robot: self.robot.stop()
                        self.last_move_time = time.time()
                    except: pass
            time.sleep(0.5)

    # --- Vision ---
    def download_image(self, filename):
        return send_from_directory(self.CAPTURE_DIR, filename, as_attachment=True)

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
        Cette fonction exécute le détecteur sélectionné elle devrait servir à
        - charger le détecteur sélectionné
        - charger la dernière image capturée

        
        :param self: Description
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

            # Si détection, créer et sauvegarder une version annotée
            annotated_url = None
            annotated_filename = None
            if results and results.get('Object detected'):
                coords = results.get('Object coordinates')
                size = results.get('Object size')
                if coords and size:
                    x, y = int(coords[0]), int(coords[1])
                    w, h = int(size[0]), int(size[1])
                    # Dessiner sur une copie pour ne pas modifier l'originale
                    annotated = frame_bgr.copy()
                    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(annotated, 'STOP', (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    base, ext = os.path.splitext(filename)
                    annotated_filename = '{}_det{}'.format(base, ext or '.jpg')
                    annotated_path = os.path.join(self.CAPTURE_DIR, annotated_filename)
                    cv2.imwrite(annotated_path, annotated)
                    annotated_url = url_for('static', filename='captured_images/{}'.format(annotated_filename))

            # Inclure les URLs utiles pour l'interface
            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            payload = dict(results)
            payload.update({
                'source_filename': filename,
                'source_file_url': source_url,
                'annotated_filename': annotated_filename,
                'annotated_file_url': annotated_url,
            })
            return jsonify(payload)
        except IndexError:
            return jsonify({'error': 'invalid detector index'}), 400
        except Exception as e:
            return jsonify({'error': 'processing failed', 'details': str(e)}), 500

    # Diagnostic stop: balayage des paramètres et sauvegarde d'overlays
    def diagnose_stop(self):
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

        # Dossier diagnostics
        diag_dir = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(diag_dir, exist_ok=True)

        try:
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return jsonify({'error': 'failed to read captured image'}), 500

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # Paramètres à balayer
            scale_factors = [1.03, 1.05, 1.08, 1.12, 1.15, 1.20]
            min_neighbors = [5, 7, 8, 10, 12]
            min_sizes = [24, 32, 40, 56, 80]

            detector = vp.get_detectors()[self.selected_detector_index]

            logs = []
            detections = []
            best = {"space": None, "sf": None, "mn": None, "ms": None, "bbox": None, "area": 0, "file_url": None}

            def normalize(det):
                if det is None:
                    return None
                # list/tuple single bbox
                if isinstance(det, (list, tuple)):
                    if len(det) >= 4 and all(isinstance(v, (int, float)) for v in det[:4]):
                        return [int(det[0]), int(det[1]), int(det[2]), int(det[3])]
                    # list of bboxes
                    if len(det) > 0 and isinstance(det[0], (list, tuple)) and len(det[0]) >= 4:
                        cands = [[int(d[0]), int(d[1]), int(d[2]), int(d[3])] for d in det if len(d) >= 4]
                        if cands:
                            return max(cands, key=lambda b: b[2]*b[3])
                        return None
                # dict formats
                if isinstance(det, dict):
                    for keys in (("x","y","w","h"), ("left","top","width","height")):
                        if all(k in det for k in keys):
                            return [int(det[keys[0]]), int(det[keys[1]]), int(det[keys[2]]), int(det[keys[3]])]
                    rects = det.get("rects")
                    if isinstance(rects, (list, tuple)) and rects:
                        cands = [[int(d[0]), int(d[1]), int(d[2]), int(d[3])] for d in rects if len(d) >= 4]
                        if cands:
                            return max(cands, key=lambda b: b[2]*b[3])
                return None

            def draw_and_save(img, bbox, label, fname_base):
                x, y, w, h = [int(v) for v in bbox]
                overlay = img.copy()
                cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(overlay, label, (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                # Sauvegarde en BGR
                save_bgr = overlay if label.startswith('BGR') else cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
                out_name = '{}.jpg'.format(fname_base)
                out_path = os.path.join(diag_dir, out_name)
                cv2.imwrite(out_path, save_bgr)
                out_url = url_for('static', filename='captured_images/diagnostics/{}'.format(out_name))
                return out_url

            # Balayage
            for sf, mn, ms in itertools.product(scale_factors, min_neighbors, min_sizes):
                for space_tag, img in (("BGR", frame_bgr), ("RGB", frame_rgb)):
                    try:
                        # Forcer paramètres du détecteur courant sans modifier l'instance définitivement
                        # On appelle directement la fonction Vision si disponible (dans StopDetector)
                        det_raw = None
                        if hasattr(detector, 'zumi_vision'):
                            det_raw = detector.zumi_vision.find_stop_sign(
                                img,
                                scale_factor=sf,
                                min_neighbors=mn,
                                min_size=(ms, ms),
                            )
                        else:
                            # Fallback: utiliser detector.process si pas d'accès direct
                            # (dans ce cas, on ne peut pas forcer les paramètres)
                            det_raw = detector.process(img)
                        bbox = normalize(det_raw)
                        logs.append("{} sf={} mn={} ms={} -> {}".format(space_tag, sf, mn, ms, "bbox" if bbox else "None"))
                        entry = {"space": space_tag, "sf": sf, "mn": mn, "ms": ms, "bbox": bbox, "area": 0, "file_url": None}
                        if bbox:
                            area = int(bbox[2]) * int(bbox[3])
                            entry["area"] = area
                            base = 'stop_{}_sf{}_mn{}_ms{}_a{}'.format(space_tag, str(sf).replace('.', '_'), mn, ms, area)
                            entry["file_url"] = draw_and_save(img, bbox, '{} STOP'.format(space_tag), base)
                            if area > best["area"]:
                                best.update({"space": space_tag, "sf": sf, "mn": mn, "ms": ms, "bbox": bbox, "area": area, "file_url": entry["file_url"]})
                        detections.append(entry)
                    except Exception as e:
                        logs.append("ERROR {} sf={} mn={} ms={}: {}".format(space_tag, sf, mn, ms, str(e)))

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            payload = {
                "source_filename": filename,
                "source_file_url": source_url,
                "best": best,
                "detections": detections,
                "logs": logs,
            }
            return jsonify(payload)
        except Exception as e:
            return jsonify({'error': 'diagnostics failed', 'details': str(e)}), 500

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
                    # Capture du frame depuis la caméra
                    frame_bgr = vp.capture_frame()
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

    def close_camera(self):
        if self.vision_pipeline: self.vision_pipeline.stop()
        return ("", 204)

    def start_camera(self):
        if self.vision_pipeline: self.vision_pipeline.start()
        return ("", 204)
    
    # --- Moteurs Zumi ---
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