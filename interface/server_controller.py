#!/usr/bin/env python
# -*- coding: utf-8 -*-
# server_controller.py
# ------------------
"""Contrôleur backend pour les routes Flask.

Centralise la logique des endpoints; `flask_router.py` ne fait que lier les routes
à ces méthodes.
"""

import os, uuid, time, cv2, itertools, numpy as np
from flask import Flask, Response, request, jsonify, send_from_directory, url_for

from interface.onglet_acceuil import render_accueil_tab
from interface.onglet_vision import render_vision_tab
from interface.onglet_template import render_template_tab  # Exemple d'onglet template générique


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
    def capture_image(self, ConvertToRGB=False):
        vp = self.vision_pipeline
        if vp is None or not vp.is_running():
            return jsonify({'error': 'camera not running'}), 400

        # 1. Récupération de l'image actuelle sans ré-entrer dans le générateur
        #    Si le flux vidéo tourne, on utilise le dernier frame mis en buffer.
        frame = vp.get_last_frame()
        if frame is None:
            # Pas de flux actif ou pas encore d'image en buffer: on capture directement
            return jsonify({'error': 'Activer la camera car le flux est pas encore disponible'}), 400

        if ConvertToRGB:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 2. Génération d'un nom de fichier unique
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = '{}_{}.jpg'.format(ts, uuid.uuid4().hex[:6])
        save_path = os.path.join(self.CAPTURE_DIR, filename)

        # 3. Sauvegarde de l'image localement
        ok = cv2.imwrite(save_path, frame)
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

            results = vp.process_frame(frame_bgr, detetor_index=self.selected_detector_index)

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

    # Diagnostic CV du stop: export des étapes intermédiaires (HSV, masques, morpho, contours)
    def diagnose_stop_cv(self):

        print("Début du diagnostic Stop CV...")
        vp = self.vision_pipeline
        if vp is None:
            return jsonify({'error': 'Video pipeline not initialized'}), 400

        filename = getattr(self, 'last_captured_filename', None)
        if not filename:
            return jsonify({'error': 'no captured image available. Please capture an image first.'}), 400

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return jsonify({'error': 'last captured image not found on server'}), 404

        diag_dir = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(diag_dir, exist_ok=True)

        try:
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return jsonify({'error': 'failed to read captured image'}), 500

            logs = []
            steps = []

            def save_step(img, name, mode):
                """
                mode:
                'bgr'   -> image BGR OpenCV
                'gray'  -> image 1 canal
                'hsv'   -> image HSV (sera convertie pour affichage)
                sauvegarde toutes les images en RGB pour l'affichage web
                """
                print("Saving step: {} ({})".format(name, mode))

                base = 'cv_{}_{}'.format(name, uuid.uuid4().hex[:6])
                out_name = base + '.jpg'
                out_path = os.path.join(diag_dir, out_name)

                if mode == 'bgr':
                    to_save = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                elif mode == 'gray':
                    to_save = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

                elif mode == 'hsv':
                    to_save = cv2.cvtColor(img, cv2.COLOR_HSV2RGB)

                elif mode == 'RGB':
                    to_save = img

                else:
                    raise ValueError("Unknown save mode: {}".format(mode))

                cv2.imwrite(out_path, to_save)
                url = url_for('static', filename='captured_images/diagnostics/{}'.format(out_name))
                steps.append({"name": name, "url": url})

            save_step(frame_bgr.copy(), 'original_bgr', mode='bgr')

            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)


            # visualisation saturation image initiale
            sat_overlay = frame_bgr.copy()
            sat_overlay[s < 60] = (0, 0, 0)
            save_step(sat_overlay, 'pixels_with_s_gt_60_overlay', 'bgr') # on suprime les pixels peu saturés de l'image
            
            print("Canal HSV stats:")
            print("H min/max:", h.min(), h.max())
            print("S min/max:", s.min(), s.max())
            print("V min/max:", v.min(), v.max())
            print("Moyennes: H {:.2f}, S {:.2f}, V {:.2f}".format(np.mean(h), np.mean(s), np.mean(v)))
            print("Écarts-types: H {:.2f}, S {:.2f}, V {:.2f}".format(np.std(h), np.std(s), np.std(v)))

            print("Histogrammes:")
            h_valide = h[(s > 60)]
            h_hist_valide, _ = np.histogram(h_valide, bins=180, range=(0, 180))
            h_hist, _ = np.histogram(h, bins=256, range=(0, 256))
            s_hist, _ = np.histogram(s, bins=256, range=(60, 256))
            v_hist, _ = np.histogram(v, bins=256, range=(0, 256))
            print("H histogramme:", h_hist)
            print("H histogramme (s>30):", h_hist_valide)
            print("S histogramme:", s_hist)
            print("V histogramme:", v_hist)
            print("Nb pixels totaux:", h.size)

            print("Extremums des canaux:")
            print("Nb pixels saturés H=0:", np.sum(h == 0), "H=255:", np.sum(h == 255))
            print("Nb pixels saturés S=0:", np.sum(s == 0), "S=255:", np.sum(s == 255))
            print("Nb pixels saturés V=0:", np.sum(v == 0), "V=255:", np.sum(v == 255)) 



            save_step(h, 'h_channel', mode='gray')
            save_step(s, 's_channel', mode='gray')
            save_step(v, 'v_channel', mode='gray')
            print("Converted to HSV; channels extracted.")

            # Test de validation du seuil de saturationq (on cherche les pixels suffisament saturés)
            # Conclusion du test. en variant l'éclairage le seuil de détection du stop demeur < 60
            print("Test filtrage par saturation...")
            s_mask = cv2.inRange(s, 60, 255)
            save_step(s_mask, 's_gt_60', 'gray')

            # test saturation supplémentaire
            s_mask2 = cv2.inRange(s, 70, 255)
            save_step(s_mask2, 's_gt_70', 'gray')

            s_mask3 = cv2.inRange(s, 80, 255)
            save_step(s_mask3, 's_gt_80', 'gray')

            s_mask4 = cv2.inRange(s, 90, 255)
            save_step(s_mask4, 's_gt_90', 'gray')

            

            # Masque des hue ou la saturation est suffisante
            h_mask = np.zeros_like(h, dtype=np.uint8)
            h_mask[s > 60] = h[s > 60]
            save_step(h_mask, 'h_where_s_gt_60', 'gray')
            # ici on isole bien le panneau et le chat, reste plus qu'a filtrer pour la vibrance

            print("Test filtrage par hue...")
            h_mask2 = cv2.inRange(h, 0, 255)
            save_step(h_mask2, 'h_mask_allin', 'gray')

            h_mask3 = cv2.inRange(h, 30, 255)
            save_step(h_mask3, 'h_mask_30', 'gray')

            h_mask4 = cv2.inRange(h, 50, 255)
            save_step(h_mask4, 'h_mask_50', 'gray')

            h_mask5 = cv2.inRange(h, 80, 255)
            save_step(h_mask5, 'h_mask_80', 'gray')

            print("Test filtrage par value...")

            v_mask = np.zeros_like(v, dtype=np.uint8)
            v_mask[s > 60] = v[s > 60]
            save_step(v_mask, 'v_where_s_gt_60', 'gray')

            v_mask2 = cv2.inRange(v, 30, 255)
            save_step(v_mask2, 'v_mask_30', 'gray')

            v_mask3 = cv2.inRange(v, 60, 255)
            save_step(v_mask3, 'v_mask_60', 'gray')

            v_mask4 = cv2.inRange(v, 80, 255)
            save_step(v_mask4, 'v_mask_80', 'gray')


            # combiner les masques h, s, v
            hsv_combined_mask = cv2.bitwise_and(h_mask, cv2.bitwise_and(s_mask, v_mask))
            print("Combining H, S, V masks...")
            print("Valeur moyenne des pixels de chaque canal dans le masque combiné HSV:")
            print("H channel average value : {}".format(np.mean(h_mask)))
            print("S channel average value : {}".format(np.mean(s_mask)))
            print("V channel average value : {}".format(np.mean(v_mask)))
            print("pixels avrege value combiné : {}".format(np.mean(hsv_combined_mask)))
            print("Nb pixels dans le masque combiné HSV:", cv2.countNonZero(hsv_combined_mask))
            save_step(hsv_combined_mask, 'hsv_combined_mask', 'gray')

            print("binariser le masque combiné HSV...")
            average_val = np.mean(hsv_combined_mask) 
            min_val = average_val
            max_val = 255
            print("Threshold values: min {:.2f}, max {:.2f}".format(min_val, max_val))
            _, hsv_combined_binary = cv2.threshold(hsv_combined_mask, min_val, max_val, cv2.THRESH_BINARY)
            save_step(hsv_combined_binary, 'hsv_combined_binary', 'gray')

            # Test de différentes préconfig
            red_configs = [
                ((0, 60, 40), (20, 255, 255), 'red_cfg_1'),
                ((160, 60, 10), (15, 255, 255), 'red_cfg_2'),
                ((155, 60, 40), (179, 255, 255), 'red_cfg_3'),
            ]


            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

            for low, high, name in red_configs:
                mask = cv2.inRange(hsv, low, high)
                save_step(mask, name, 'gray')
                print(name, "pixels:", cv2.countNonZero(mask))

            
            # lower1 = (0, 15, 15)
            # upper1 = (15, 255, 255)

            # lower2 = (165, 15, 15)
            # upper2 = (179, 255, 255)


            # mask1 = cv2.inRange(hsv, lower1, upper1)
            # mask2 = cv2.inRange(hsv, lower2, upper2)
            # mask = cv2.bitwise_or(mask1, mask2)
            # save_step(cv2.cvtColor(mask1, cv2.COLOR_GRAY2RGB), 'mask1_red_low', is_bgr=False)
            # save_step(cv2.cvtColor(mask2, cv2.COLOR_GRAY2RGB), 'mask2_red_high', is_bgr=False)
            # save_step(cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB), 'mask_combined', is_bgr=False)
            
            # pour debug les mask
            # limite de couleur 2
            # low1 = np.array([0,50,50])
            # up1 = np.array([10,255,255])
            # mask_low_red = cv2.inRange(hsv, low1, up1)

            # low2 =  np.array([170,50,50])
            # up2 = np.array([180,255,255])
            # mask_high_red = cv2.inRange(hsv, low2, up2)

            # # combine les deux masques 
            # mask_test = cv2.bitwise_or(mask_low_red, mask_high_red)
            # save_step(mask_test, 'mask_test', is_bgr=False)
            # save_step(mask_low_red, 'mask_low_red', is_bgr=False)
            # save_step(mask_high_red, 'mask_high_red', is_bgr=False)
            


            # l'image est reçue en BRG, convertie en HSV. il est possible
            # la méthode save_step convertit mal les masques
            
            
            combined_pixels = int(mask.sum() / 255)
            print("Masks created for red ranges; combined mask pixels: {}".format(combined_pixels))

            threshold_sparse = max(50, (frame_bgr.shape[0] * frame_bgr.shape[1]) // 500)
            if combined_pixels < threshold_sparse:
                b, g, r = cv2.split(frame_bgr)
                r16 = r.astype(np.int16)
                g16 = g.astype(np.int16)
                b16 = b.astype(np.int16)
                ratio_mask = ((r16 > g16 + 10) & (r16 > b16 + 10) & (r > 60)).astype(np.uint8) * 255
                save_step(ratio_mask, 'mask_red_ratio', mode='gray')
                mask = ratio_mask
                logs.append('HSV mask sparse; using RGB ratio fallback.')
                print('HSV mask sparse; using RGB ratio fallback.')

            kernel3 = np.ones((3, 3), np.uint8)
            kernel5 = np.ones((5, 5), np.uint8)
            mask_open = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel3, iterations=1)
            mask_close = cv2.morphologyEx(mask_open, cv2.MORPH_CLOSE, kernel5, iterations=2)
            save_step(mask_open, 'mask_open', mode='gray')
            save_step(mask_close, 'mask_close', mode='gray')
            logs.append('Applied morphology (open + close).')
            print("Applied morphology (open + close).")

            cnts = cv2.findContours(mask_close, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            logs.append('Contours found: {}'.format(len(cnts)))
            print("Contours found: {}".format(len(cnts)))

            overlay = frame_bgr.copy()
            best = None
            best_area = 0
            for idx, c in enumerate(cnts):
                area = cv2.contourArea(c)
                if area < 1:
                    continue
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                vtx = len(approx)
                x, y, w, h = cv2.boundingRect(approx)
                ratio = float(w) / float(h) if h != 0 else 0.0
                rect_area = float(w * h)
                fill_ratio = float(area) / rect_area if rect_area > 0 else 0.0
                convex = cv2.isContourConvex(approx)
                logs.append('C{}: area={} vtx={} ratio={:.2f} fill={:.2f} convex={}'.format(idx, int(area), vtx, ratio, fill_ratio, bool(convex)))
                print('C{}: area={} vtx={} ratio={:.2f} fill={:.2f} convex={}'.format(idx, int(area), vtx, ratio, fill_ratio, bool(convex)))
                # draw approx for visualization
                cv2.drawContours(overlay, [approx], -1, (255, 0, 0), 2)
                # apply filters similar to detector
                if area <  self._safe_int(self, 'min_area', 500):
                    continue
                if vtx < self._safe_int(self, 'poly_min', 6) or vtx > self._safe_int(self, 'poly_max', 10):
                    continue
                if not convex:
                    continue
                if h == 0 or w == 0:
                    continue
                aspect_tol = getattr(vp.get_detectors()[self.selected_detector_index], 'aspect_tol', 0.4)
                if abs(ratio - 1.0) > float(aspect_tol):
                    continue
                if fill_ratio < 0.30:
                    continue
                if area > best_area:
                    best_area = area
                    best = (x, y, w, h)

            save_step(overlay, 'contours_overlay', mode='bgr')

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            payload = {
                'source_file_url': source_url,
                'steps': steps,
                'logs': logs,
                'best': { 'bbox': best, 'area': int(best_area) }
            }
            return jsonify(payload)
        except Exception as e:
            return jsonify({'error': 'diagnose_stop_cv failed', 'details': str(e)}), 500

    # util: safe int attr
    @staticmethod
    def _safe_int(obj, name, default):
        try:
            return int(getattr(obj, name))
        except Exception:
            return int(default)

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
                    vp.update_last_frame(frame_bgr)
                except Exception:
                    time.sleep(0.1)
                    break
                # Conversion en RGB pour l'affichage web
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                ret, jpeg = cv2.imencode('.jpg', frame_rgb)
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

