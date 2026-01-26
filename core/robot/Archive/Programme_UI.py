#!/usr/local/bin/python
# -*- coding: utf-8 -*-
import os
import sys

# Ensure workspace root (PFE) is on sys.path so `Module_Vision` is importable
_this_dir = os.path.dirname(os.path.abspath(__file__))
_workspace_root = os.path.dirname(_this_dir)
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

from flask import Flask, Response, request, redirect, url_for, jsonify 
# import requests 

# Import des classes du Zumi réel (commentées pour le mock)
# from zumi.zumi import Zumi 
# from zumi.util.screen import Screen                    
# from zumi.util.camera import Camera 
# from zumi.protocol import Note 
# from zumi.personality import Personality 

# Import des classes pour mocker le Zumi physique
from core.camera.picam2 import PiCam2
from Code_Zumi.Zumi_mock.SimZumi import mockZumi, mockScreen, mockPersonality


import cv2                                             
import time   
import threading 

# désactivé les lib pour la lecture des fichiers Jupiter
# import nbformat 
# from nbconvert.preprocessors import ExecutePreprocessor 

# --- NOUVEAU : Variables pour le Watchdog --- 
WATCHDOG_TIMEOUT_SECONDS = 0.8 # S'arrête si aucune commande en 0.8s 
g_last_move_time = time.time() 
g_watchdog_active = False # Ne pas arrêter le robot avant la 1ère commande 
# ------------------------------------------ 

camera_thread = None 
zumi = mockZumi() # remettre Zumi() pour le vrai robot
screen = mockScreen() # remettre Screen() pour le vrai robot
camera = None 
camera_active = False 
personality = mockPersonality.Personality(zumi, screen) # remettre Personality(zumi, screen) pour le vrai robot
app = Flask(__name__) 

#pour initialiser le zumi 
#try:    
# zumi.reset_drive()   
# zumi.calibrate_gyro() 
# zumi.mpu.calibrate_MPU() 
# zumi. update_angles() 
# print("[INIT] exécuté.") 
# #except Exception as e: 
# print("[INIT ERREUR] :", e) 

# Start the Pi camera stream 
try: 
    camera.start_camera() 
    camera_active = True 
except Exception as e: 
    print("⚠️ Impossible de démarrer la caméra au lancement :", e) 
    camera_active = False 

# États des modes (simulés pour l'instant) 
lumiereModeAuto = False 
moteurModeAuto = False 
# Vitesses pour le contrôle continu 
DRIVE_SPEED = 20 
TURN_SPEED = 15 

def run_camera(): 
    """
    Gère le cycle de vie de la caméra dans un thread.

    Cette fonction démarre la caméra, maintient une boucle d’exécution tant que le
    drapeau global `camera_active` est vrai, et garantit une fermeture propre de la
    ressource seulement si le démarrage a réellement réussi. Les exceptions sont
    interceptées et journalisées, puis l’objet global `camera` est systématiquement
    libéré (assigné à None) en fin d’exécution.

    Globals:
        camera_active (bool): Contrôle la boucle d’exécution du thread caméra.
        camera: Instance fournissant `start_camera()` et `close()`.

    Effets de bord:
        - Démarre la caméra via `camera.start_camera()`.
        - Ferme la caméra avec `camera.close()` si elle a été démarrée.
        - Met `camera` à None pour libérer la ressource.

    Returns:
        None

    Notes:
        - Conçue pour être exécutée dans un thread séparé.
        - Utilise un court sommeil (0.05 s) pour rythmer la boucle et réduire la charge CPU.
    """
    global camera_active, camera 
    # Un drapeau pour savoir si le démarrage a réussi 
    camera_successfully_started = False  
    try: 
        print("Thread caméra démarré") 
        camera.start_camera() 
        camera_successfully_started = True # <--- Le démarrage a réussi 
        print("Caméra en fonctionnement") 
        while camera_active: 
            time.sleep(0.05) 
    except Exception as e: 
        print("Erreur dans le thread caméra :", e)  
    finally: 
        try: 
            # CORRECTION: Ne ferme la caméra que si elle a été démarrée 
            if camera_successfully_started:  
                camera.close() 
                print("Caméra arrêtée (thread)") 
            else: 
                print("Démarrage caméra échoué, pas besoin de fermer.") 
        except Exception as e: 
            print("Erreur lors de camera.close() :", e) 
        finally: 
            camera = None # Destroy the object 
            print("Objet caméra détruit.") 


# def run_jupiterFiles(path): 
#     with open(path) as f: 
#         nb = nbformat.read(f, as_version=4) 
#         ep = ExecutePreprocessor(timeout=600, kernel_name='python3') 
#         ep.preprocess(nb) 
#         #print("Fichier Jupiter {path} exécuté avec succès !")        

def motor_watchdog(): 
    """ 
    Thread qui s'exécute en arrière-plan. 
    Arrête les moteurs si la dernière commande de mouvement 
    est trop ancienne (ex: le client s'est déconnecté). 
    """ 
    global g_last_move_time, g_watchdog_active, zumi 
    print("[Watchdog] Démarré (en attente d'activation).") 
    
    while True: 
        # Ne pas s'activer avant la première commande de mouvement 
        if not g_watchdog_active: 
            time.sleep(0.5) 
            continue 

        # Calculer le temps écoulé 
        time_since_last_move = time.time() - g_last_move_time 
        
        if time_since_last_move > WATCHDOG_TIMEOUT_SECONDS: 
            try: 
                # S'assurer que zumi existe avant de l'appeler 
                if zumi:  
                    zumi.stop() 
                # Réinitialiser pour ne pas 'spammer' la commande stop 
                g_last_move_time = time.time()  
            except Exception as e: 
                pass # Erreur silencieuse (ex: zumi déconnecté)

        time.sleep(0.1) # Vérifier 10x par seconde 

# === PAGE PRINCIPALE === 
@app.route('/') 
def home(): 
    global lumiereModeAuto, moteurModeAuto 
    return PageWeb(lumiereModeAuto, moteurModeAuto) 


# === COMMANDES === 
@app.route('/majAutoLed') 
def maj_auto_led(): 
    global lumiereModeAuto 
    etat = request.args.get('etat', '0') == '1' 
    lumiereModeAuto = etat 
    return ("", 204)        

@app.route('/majAutoMoteur') 
def maj_auto_moteur(): 
    global moteurModeAuto 
    etat = request.args.get('etat', '0') == '1' 
    moteurModeAuto = etat 
    return ("", 204) 

@app.route('/vert') 
def activer_vert(): 
    print("LED verte activée") 
    return ("", 204) 

@app.route('/rouge') 
def activer_rouge(): 
    print("LED rouge activée") 
    return ("", 204) 

# Commandes pour le pont levi
@app.route('/ouvrir') 
def ouvrir_pont(): 
    print("Pont ouvert") 
    return ("", 204) 

@app.route('/fermer') 
def fermer_pont(): 
    print("Pont fermé") 
    return ("", 204) 

# Commandes de mouvement du Zumi
@app.route('/zumi/forward') 
def forward(): 
    global g_last_move_time, g_watchdog_active  
    g_last_move_time = time.time()              
    g_watchdog_active = True                    
    print("[HTTP] /zumi/forward reçu") 
    try: 
        zumi.control_motors(DRIVE_SPEED, DRIVE_SPEED) 
        print("[ACTION] zumi.control_motors({}, {}) exécuté".format(DRIVE_SPEED, DRIVE_SPEED)) 
        return "ok" 
    except Exception as e: 
        print("[ERREUR] zumi.control_motors(forward):", e) 
        return "error", 500 

@app.route('/zumi/reverse') 
def reverse(): 
    global g_last_move_time, g_watchdog_active  
    g_last_move_time = time.time()              
    g_watchdog_active = True                    
    print("[HTTP] /zumi/reverse reçu") 
    try: 
        zumi.control_motors(-DRIVE_SPEED, -DRIVE_SPEED) 
        print("[ACTION] zumi.control_motors({}, {}) exécuté".format(-DRIVE_SPEED, -DRIVE_SPEED)) 
        return "ok" 
    except Exception as e: 
        print("[ERREUR] zumi.control_motors(reverse):", e) 
        return "error", 500 
    
@app.route('/zumi/left') 
def left(): 
    global g_last_move_time, g_watchdog_active  
    g_last_move_time = time.time()              
    g_watchdog_active = True                    
    print("[HTTP] /zumi/left reçu") 
    try: 
        zumi.control_motors(-TURN_SPEED, TURN_SPEED)  
        print("[ACTION] zumi.control_motors({}, {}) exécuté".format(-TURN_SPEED, TURN_SPEED)) 
        return "ok" 
    except Exception as e: 
        print("[ERREUR] zumi.control_motors(left):", e) 
        return "error", 500 
    
@app.route('/zumi/right') 
def right(): 
    global g_last_move_time, g_watchdog_active  
    g_last_move_time = time.time()              
    g_watchdog_active = True                    
    print("[HTTP] /zumi/right reçu") 
    try: 
        zumi.control_motors(TURN_SPEED, -TURN_SPEED) 
        print("[ACTION] zumi.control_motors({}, {}) exécuté".format(TURN_SPEED, -TURN_SPEED)) 
        return "ok" 
    except Exception as e: 
        print("[ERREUR] zumi.control_motors(right):", e) 
        return "error", 500 
    
@app.route('/zumi/stop') 
def stop(): 
    print("[HTTP] /zumi/stop reçu") 
    try: 
        zumi.stop() 
        print("[ACTION] zumi.stop() exécuté") 
        return "ok" 
    except Exception as e: 
        print("[ERREUR] zumi.stop():", e) 
        return "error", 500 
    
@app.route('/video') 
def video_feed(): 
    def generate(): 
        while camera_active: 
            # attend si l'objet camera n'existe pas 
            if camera is None: 
                time.sleep(0.1) 
                continue 
            try: 
                frame = camera.capture() 
            except Exception as e: 
                # Si erreur de capture pedant startup/shutdown, skip 
                # CORRECTION: Affiche l'erreur correctement 
                print("Erreur de capture:", e) 
                time.sleep(0.1) 
                continue 

            # Convertie de RGB (camera) à BGR (OpenCV) 
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) 
            ret, jpeg = cv2.imencode('.jpg', frame_bgr) 
            if not ret: 
                continue 
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n') 
            time.sleep(0.05)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame') 

@app.route('/close_camera', methods=['POST']) 
def close_camera(): 
    global camera_active 
    if not camera_active:
        print("Camera not active") 
        return redirect(url_for('home')) 
    
    print("Stopping camera (signal sent)...") 
    # Set flag to False. The 'run_camera' thread will detect this, 
    # exit its loop, and call camera.close() safely. 
    camera_active = False  
    # --- REMOVE THE DUPLICATE CLOSE CALL --- 
    # try:     
    # camera.close_camera() # THIS CAUSED THE RACE CONDITION 
    # except Exception as e: 
    #     
    # print("Erreur lors de l'arrêt de la caméra :", e) 

    print("Camera stop signal accepted.") 
    return redirect(url_for('home')) 

@app.route('/start_camera', methods=['POST']) 
def start_camera(): 
    global camera_active, camera_thread, camera # Add 'camera' 
    if camera_active: 
        print("Camera already active") 
        return redirect(url_for('home')) 
    print("Thread caméra démarré") 
    # --- CREATE A NEW CAMERA OBJECT --- 
    camera = PiCam2() # MODIFIER POUR FONCTIONNER AVEC LES TESTS
    camera_active = True 
    camera_thread = threading.Thread(target=run_camera) 
    camera_thread.daemon = True 
    camera_thread.start() 
    print("Caméra en fonctionnement") 
    return redirect(url_for('home')) 

@app.route('/zumi/battery') 
def battery(): 
    try: 
        level = int(zumi.get_battery_percent()) 
        return jsonify({'battery': level}) 
    except Exception as e: 
        print("Erreur lecture batterie :", e) 
        return jsonify({'battery': None}) 

# === FONCTION DE PAGE WEB === 
def PageWeb(lumiereModeAuto, moteurModeAuto): 
    html = """<!DOCTYPE html><html lang="fr"> 

    <div id='battery-container' style='position:absolute; top:10px; right:20px; font-weight:bold; font-size:18px;'> 

    Batterie : <span id='battery-level'>--%</span> 
    </div> 
    
    <head> 
    <meta charset="UTF-8"> 
    <meta name="viewport" content="width=device-width, initial-scale=1"> 
    <title>Interface Zumi</title> 
    <link rel="icon" href="data:,"> 
    <style> 
    body { 
        margin: 0; padding: 0; 
        width: 100vw; height: 100vh; 
        font-family: Arial, sans-serif; 
        background: linear-gradient(135deg, #40E0D0, #00BFFF); 
        color: #333; display: flex; flex-direction: column; 
    }

    h1, h2, h3 { margin: 10px 0; text-align: center; } 

    .container { 
        display: flex; justify-content: space-between; 
        padding: 20px; height: calc(100vh - 60px); 
    } 

    .left-panel, .right-panel { 
        background: white; 
        border-radius: 20px; 
        padding: 20px; 
        box-shadow: 0 0 15px rgba(0,0,0,0.2); 
        flex: 1; 
    } 

    .left-panel { 
        margin-right: 20px; 
        display: flex; 
        flex-direction: column; 
        align-items: center; 
    } 

    .right-panel { overflow-y: auto; } 
    
    .button-choix-scenario { 
        margin: 5px; 
        padding: 10px 20px; 
        background: #00BFFF; 
        border: none; 
        border-radius: 10px; 
        color: white; 
        font-weight: bold; 
        cursor: pointer; 
        transition: background 0.3s; 
    } 

    .button-choix-scenario:hover { background: #0080ff; } 
    
    .live-feed { 
        display: none; 
        width: 100%; 
        margin-top: 20px; 
        padding: 10px; 
        background-color: #f0f8ff; 
        border-radius: 20px; 
        box-shadow: 0 0 10px rgba(0,0,0,0.15); 
        text-align: center; 
    } 

    .live-feed img { 
        width: 50%; 
        max-width: 650px; 
        height: auto; 
        border-radius: 8px; 
        border: 4px solid #00BFFF; 
        margin-top: 10px; 
    } 

    .toggle-btn { 
        background: #007acc; 
        color: white; 
        border: none; 
        padding: 12px 25px; 
        border-radius: 10px; 
        cursor: pointer; 
        margin-top: 15px; 
        font-size: 16px;
    } 

    .toggle-btn:hover { background: #005fa3; } 

    .command-button { 
        margin: 5px; 
        padding: 10px 15px; 
        border: none; 
        border-radius: 8px; 
        font-weight: bold; 
        cursor: pointer; 
    } 

        .driving-mode { 
            background-color: #e0f7fa; 
            padding: 15px; 
            border-radius: 15px; 
            text-align: center; 
            margin-top: 20px; 
            box-shadow: 0 4px 8px rgba(0,0,0,0.1); 
            display: flex; 
            flex-direction: column; 
            align-items: center; /* Centre le D-pad */ 
        } 

        .driving-mode h3 { 
            margin-bottom: 10px; 
        } 

        /* Conteneur principal pour le D-pad */ 
        
        .dpad-container { 
            display: grid; 
            /* Définit la disposition en 3x3 */ 
            grid-template-areas: 
            ". up ." 
            "left  center right" 
            ". down ."; 
            grid-gap: 8px; /* Espace entre les boutons */ 
            width: 180px;  /* Taille réduite pour s'adapter */ 
            height: 180px; /* Taille réduite pour s'adapter */ 
        } 

        .dpad-button { 
            background-color: #e0e0e0; /* Gris clair */ 
            border: none; 
            border-radius: 20px; /* Coins arrondis */ 
            cursor: pointer; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            transition: all 0.15s ease-out; 
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1),  
            inset 0 1px 1px rgba(255, 255, 255, 0.7); 
            user-select: none; /* Empêche la sélection de texte/icône */ 
        } 

        .dpad-button:hover { 
            background-color: #d0d0d0; 
        } 
        
        /* Effet d'enfoncement au clic/toucher */ 
        
        .dpad-button:active { 
            background-color: #c0c0c0; 
            transform: scale(0.95); 
            box-shadow: 0 2px 3px rgba(0, 0, 0, 0.1); 
        } 

        /* Icônes SVG pour les flèches (couleur #555) */

        .dpad-button svg { 
            width: 50%; 
            height: 50%; 
            stroke: #555; 
            stroke-width: 12; 
            stroke-linecap: round; 
            stroke-linejoin: round; 
            fill: none; 
        } 

        /* Assignation aux zones de la grille */ 
        .dpad-up { grid-area: up; } 
        .dpad-down { grid-area: down; } 
        .dpad-left { grid-area: left; } 
        .dpad-right { grid-area: right; } 
        
        .dpad-center { 
            grid-area: center; 
            background-color: #ffffff; /* Centre blanc */ 
            border: 3px solid #e0e0e0; 
        } 
        .dpad-center:hover { background-color: #f0f0f0; } 
        .dpad-center:active { background-color: #e0e0e0; } 
    
    .camera-controls { 
        margin-top: 15px; 
        text-align: center; 
    } 

    .camera-controls button { 
        background-color: #0288d1; 
        color: white; 
        border: none; 
        border-radius: 10px; 
        padding: 10px 20px; 
        cursor: pointer; 
        font-size: 16px; 
    } 

    .camera-controls button:hover { 
        background-color: #0277bd; 
    } 

    .scenario-buttons { 
        display: flex; 
        justify-content: center; 
        gap: 10px; 
        margin-bottom: 15px; 
        flex-wrap: wrap; /* utile si la fenêtre est petite */ 
    } 

    .button-light-green { background: #32CD32; color: white; } 
    .button-light-red { background: #DC143C; color: white; } 
    .button-bridge { background: #4682B4; color: white; } 

    .disabled { opacity: 0.5; cursor: not-allowed; } 

    .command-category { margin-bottom: 20px; } 
    .check-switch { margin-left: 8px; font-weight: bold; } 
    </style> 
    </head> 
    <body> 
    """ 
    html += "<div class='container'>"
    
    # --- Panneau gauche (scénarios + caméra) 
    html += "<div class='left-panel'>" 
    html += "<h2>Scénarios</h2>" 
    html += "<div class='scenario-buttons'>" 
    for i in range(1, 5): 
        html += "<button class='button-choix-scenario' onclick='runScenario({})'>Scénario {}</button>".format(i, i) 
    html += "</div>" 
    
    html += "<button class='toggle-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>" 
   
    html += "<div class='live-feed' id='liveFeed'><img src='/video' alt='Flux vidéo en direct'></div>" 
    
    html += "</div>" 
    
    # --- Panneau droit (commandes) 
    html += "<div class='right-panel'>" 
    html += "<h1>Zumi - Commandes</h1>" 
    
    # Lumières 
    html += "<div class='command-category'>" 
    html += "<h3>Lumières</h3>" 
    checked = "checked" if lumiereModeAuto else "" 
    html += "<label><input type='checkbox' id='autoLed' onchange='majModeLed(this.checked)' {}><span class='check-switch'>auto</span></label>".format(checked) 
    if lumiereModeAuto: 
        html += "<button class='command-button button-light-green disabled'>Vert</button>" 
        html += "<button class='command-button button-light-red disabled'>Rouge</button>" 
    else: 
        html += "<a href='/vert'><button class='command-button button-light-green'>Vert</button></a>" 
        html += "<a href='/rouge'><button class='command-button button-light-red'>Rouge</button></a>" 
    html += "</div>" 
    
    # Pont 
    html += "<div class='command-category'>" 
    html += "<h3>Pont</h3>" 
    checked = "checked" if moteurModeAuto else "" 
    html += "<label><input type='checkbox' id='autoMoteur' onchange='majModeMoteur(this.checked)' {}><span class='check-switch'>auto</span></label>".format(checked) 
    
    if moteurModeAuto: 
        html += "<button class='command-button button-bridge disabled'>Ouvrir</button>" 
        html += "<button class='command-button button-bridge disabled'>Fermer</button>" 
    else: 
        html += "<a href='/ouvrir'><button class='command-button button-bridge'>Ouvrir</button></a>" 
        html += "<a href='/fermer'><button class='command-button button-bridge'>Fermer</button></a>" 
    
        html += """ 
        <div class='driving-mode'> 
        <h3>Driving Mode</h3> 
        <div class="dpad-container"> 
            <!-- HAUT --> 
            <button  
                class="dpad-button dpad-up"  
                onmousedown="startMove('forward')" onmouseup="stopMove()" onmouseleave="stopMove()" 
                ontouchstart="startMove('forward')" ontouchend="stopMove()"> 
                <svg viewBox="0 0 100 100"><path d="M50 20 L50 80 M20 50 L50 20 L80 50"></path></svg> 
            </button> 
            <!-- GAUCHE --> 
            <button  
                class="dpad-button dpad-left" 
                onmousedown="startMove('left')" onmouseup="stopMove()" onmouseleave="stopMove()" 
                ontouchstart="startMove('left')" ontouchend="stopMove()"> 
                <svg viewBox="0 0 100 100"><path d="M80 50 L20 50 M50 20 L20 50 L50 80"></path></svg> 
            </button> 
            <!-- CENTRE (Stop) --> 
            <button class="dpad-button dpad-center" onclick="stopMove()"></button> 
            <!-- DROITE --> 
            <button  
                class="dpad-button dpad-right" 
                onmousedown="startMove('right')" onmouseup="stopMove()" onmouseleave="stopMove()" 
                ontouchstart="startMove('right')" ontouchend="stopMove()"> 
                <svg viewBox="0 0 100 100"><path d="M20 50 L80 50 M50 20 L80 50 L50 80"></path></svg> 
            </button> 
            <!-- BAS --> 
            <button  
                class="dpad-button dpad-down" 
                onmousedown="startMove('reverse')" onmouseup="stopMove()" onmouseleave="stopMove()" 
                ontouchstart="startMove('reverse')" ontouchend="stopMove()"> 
                <svg viewBox="0 0 100 100"><path d="M50 80 L50 20 M20 50 L50 80 L80 50"></path></svg> 
            </button> 
        </div> 
    </div> 
    """ 
    html += "</div>" 

    html += "</div></div>" 

    # --- Script JS 
    html += """ 
    <script> 
    function majModeLed(etat) { 
        fetch('/majAutoLed?etat=' + (etat ? '1' : '0')).then(() => location.reload()); 
    } 

    function majModeMoteur(etat) { 
        fetch('/majAutoMoteur?etat=' + (etat ? '1' : '0')).then(() => location.reload()); 
    } 

    function toggleCamera() { 
        const liveFeed = document.getElementById('liveFeed'); 
        const btn = document.getElementById('cameraToggleBtn'); 
        const img = liveFeed.querySelector('img'); 

        if (liveFeed.style.display === 'none' || liveFeed.style.display === '') { 
            // --- CORRECTION --- 
            // 1. Affiche le conteneur et change le bouton (pour la réactivité) 
            liveFeed.style.display = 'block'; 
            btn.textContent = '⛔ Stop Camera'; 

            // 2. Envoie la commande de démarrage au serveur 
            fetch('/start_camera', { method: 'POST' }) 
                .then(() => { 
                // 3. ATTEND que le serveur ait confirmé le démarrage... 
                //    ...avant de demander le flux vidéo. 
                img.src = '/video?' + new Date().getTime(); 
            }); 
            
            // ------------------ 
        
        } else { 
            // --- CORRECTION --- 
            // 1. Cache le conteneur et change le bouton 
            liveFeed.style.display = 'none'; 
            btn.textContent = '▶️ Start Camera'; 
            
            // 2. Vide la source de l'image (arrête le flux gelé) 
            img.src = "";  
            
            // 3. Envoie la commande d'arrêt au serveur 
            fetch('/close_camera', { method: 'POST' }); 
            // ------------------ 
        } 
    } 

    function runScenario(num) { 
        var url = 'http://zumidashboard.ai:5555/notebooks/My_Projects/Jupyter/Scenario' + num + '.ipynb'; 
        window.open(url, '_blank'); 
    } 

// --- NOUVEAU : Modifications pour le Watchdog --- 
    let isMoving = false; 
    let moveInterval = null; // Variable pour stocker notre 'setInterval' 

    function startMove(direction) { 
        if (isMoving) return; // Évite les commandes multiples 
        isMoving = true; 

        // Fonction interne pour envoyer la commande 
        const sendMoveCommand = () => { 
        fetch('/zumi/' + direction) 
            .then(response => { if (!response.ok) console.error('Error starting move: ' + direction); }) 
            .catch(error => console.error('Fetch error:', error)); 
        }; 

        // 1. Envoyer la commande 1x immédiatement pour la réactivité 
        sendMoveCommand();  

        // 2. Démarrer un intervalle qui 'nourrit' le watchdog 4x par seconde (250ms) 
        moveInterval = setInterval(sendMoveCommand, 250); 
    }

    function stopMove() { 
        if (!isMoving) return; // Évite les 'stop' inutiles 
        isMoving = false; 
        
        // 1. Arrêter l'envoi de commandes en continu 
        if (moveInterval) { 
            clearInterval(moveInterval); 
            moveInterval = null; 
        } 
    
        // 2. Envoyer la commande d'arrêt explicite 
        fetch('/zumi/stop') 
            .then(response => { if (!response.ok) console.error('Error stopping move'); }) 
            .catch(error => console.error('Fetch error:', error)); 
    } 
    // --- FIN DES MODIFICATIONS WATCHDOG --- 
    
    // Sécurité : si l'utilisateur relâche le clic n'importe où sur la page 
    window.addEventListener('mouseup', stopMove); 
    window.addEventListener('touchend', stopMove); 
     
    // --- Lecture du niveau de batterie --- 
    async function updateBattery() { 
      try { 
        const response = await fetch('/zumi/battery'); 
        const data = await response.json(); 
        if (data.battery !== null) { 
          document.getElementById('battery-level').innerText = data.battery.toFixed(1) + "%"; 
        } else { 
          document.getElementById('battery-level').innerText = "Erreur"; 
        } 
      } catch (e) { 
        document.getElementById('battery-level').innerText = "N/A"; 
      } 
    } 

    setInterval(updateBattery, 40000); // mise à jour toutes les 40 secondes 
    updateBattery(); // première lecture immédiate 
 
     
    </script> 
    </body></html> 
    """ 
 
    return html 
 
print("Programme is running") 
 
# === LANCEMENT DU SERVEUR === 
if __name__ == '__main__': 
    # --- NOUVEAU : Démarrer le thread watchdog --- 
    watchdog_thread = threading.Thread(target=motor_watchdog) 
    watchdog_thread.daemon = True # S'assure qu'il s'arrête avec le script 
    watchdog_thread.start() 
    # ------------------------------------------ 
     
    print("Programme is running") # Vous pouvez garder votre print 
    app.run(host='0.0.0.0', port=5000, threaded=True) 
