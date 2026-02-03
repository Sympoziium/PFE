#!/usr/bin/env python
# -*- coding: utf-8 -*-
# server_controller.py

import os, uuid, time, cv2
import requests  # <--- IMPORTANT : Pour communiquer avec le pont
from flask import Flask, Response, request, jsonify, send_from_directory, url_for

from interface.onglet_acceuil import render_accueil_tab
from interface.onglet_vision import render_vision_tab
from interface.onglet_template import render_template_tab

# --- Variables ---
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

    def attach_pipeline_vision(self, pipeline):
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
        if not vp or not vp.is_running(): return jsonify({'error': 'camera not running'}), 400
        frame = vp.get_last_frame()
        if frame is None: frame = vp.capture_frame()
        
        filename = '{}_{}.jpg'.format(time.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:6])
        cv2.imwrite(os.path.join(self.CAPTURE_DIR, filename), frame)
        return jsonify({'file_url': url_for('static', filename='captured_images/'+filename)})

    def status(self):
        vp = self.vision_pipeline
        return jsonify({"camera_running": bool(vp and vp.is_running())})

    def video_feed(self):
        vp = self.vision_pipeline
        if not vp or not vp.is_running(): return "Camera OFF", 503
        def generate():
            while vp.is_running():
                try:
                    frame = vp.capture_frame()
                    vp.update_last_frame(frame)
                    ret, jpeg = cv2.imencode('.jpg', frame)
                    if ret: yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                except: pass
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
        self.robot.stop()
        return "ok"

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