# flask_server.py
# ------------------
# Module pour gérer le serveur Flask pour l'interface web du robot

from fileinput import filename
from flask import Flask, Response, request, redirect, url_for, jsonify 
import time, cv2
import threading
from core.vision.vision_pipeline import VisionPipeline

import os, uuid # Pour la sauvegarde des images capturées

# Initialisation de l'instance du serveur Flask
app = Flask(__name__)

vision_pipeline = None

# Fonction pour attacher le pipeline de vision global
def attach_pipeline(pipeline):
    global vision_pipeline
    vision_pipeline = pipeline


# Page principale de l'interface web
@app.route('/')
def home():
    return page_accueil()

# Fonction pour générer la page d'accueil HTML
@app.route('/capture_image', methods=['POST'])
def capture_image():
    print("POST /capture_image reçu") # pour debug
    global vision_pipeline # l'instance du pipeline de vision est déclarée globalement et intialisé dans le main
    
    if vision_pipeline is None or not vision_pipeline.is_running():
        return jsonify({'error': 'camera not running'}), 400
    
    # 1. Capture de l'image actuelle
    frame_brg = vision_pipeline.capture_frame()
    
    # 2. Conception du PATH pour sauvegarder l'image
    save_dir = os.path.join(app.static_folder, 'captured_images') # Dossier pour sauvegarder les images capturées
    os.makedirs(save_dir, exist_ok=True) # Crée le dossier s'il n'existe pas

    # 3. Génération d'un nom de fichier unique
    ts = time.strftime("%Y%m%d-%H%M%S")
    filename = f'{ts}_{uuid.uuid4().hex[:6]}.jpg'
    save_path = os.path.join(save_dir, filename)
    
    # 4. Sauvegarde de l'image localement
    ok = cv2.imwrite(save_path, frame_brg)
    if not ok:
        return jsonify({'error': 'write failed'}), 500
    
    # 5. Génération d'un URL pour accéder à l'image sauvegardée via le PC
    image_url = url_for('static', filename=f'captured_images/{filename}', _external=True)
    return jsonify({'filename': filename, 'url': image_url})

@app.route('/status')
def status():
    return jsonify({
        "camera_running": vision_pipeline.is_running()
    })


@app.route('/video') 
def video_feed(): 
    global vision_pipeline

    if vision_pipeline.get_camera() is None:
        print("Video feed requested but camera not initialized")
        return "Camera not running", 503

    def generate(): 
        while True: 
            # attend si l'objet camera est activé 
            if not vision_pipeline.is_running(): 
                time.sleep(0.1) 
                continue 
            try: 
                frame_bgr = vision_pipeline.capture_frame() 
            except Exception as e: 
                # Si erreur de capture pedant startup/shutdown, skip 
                # CORRECTION: Affiche l'erreur correctement 
                print("Erreur de capture:", e) 
                time.sleep(0.1) 
                continue 

            # Convertir l'image BGR en JPEG
            ret, jpeg = cv2.imencode('.jpg', frame_bgr) 
            if not ret: 
                continue 

            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n') 
            
            time.sleep(0.05)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame') 

@app.route('/close_camera', methods=['POST']) 
def close_camera(): 
    print("POST /close_camera reçu") # pour debug
    global vision_pipeline
    if not vision_pipeline.is_running():
        print("Camera not active") 
        return redirect(url_for('home')) 
    
    print("Stopping camera (signal sent)...") 
    # Set flag to False. The 'run_camera' thread will detect this, 
    # exit its loop, and call camera.close() safely. 
    vision_pipeline.stop()  
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
    print("POST /start_camera reçu") # pour debug
    global vision_pipeline, vision_thread 
    if vision_pipeline.is_running(): 
        print("Camera already active") 
        return redirect(url_for('home')) 
    print("Thread caméra démarré") 
    # --- CREATE A NEW CAMERA OBJECT --- 
    vision_pipeline.start()
    vision_thread = threading.Thread(target=vision_pipeline.run_camera) 
    vision_thread.daemon = True
    vision_thread.start()
    print("Caméra en fonctionnement")
    return redirect(url_for('home'))


def page_accueil():
    html = """<!DOCTYPE html><html lang="fr"> 

    /* Styles CSS pour l'interface web */
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

    /* Styles pour le conteneur principal et les sections */
    .container { 
        display: flex; justify-content: space-between; 
        padding: 20px; height: calc(100vh - 60px); 
    } 

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

    /* Ajout du bouton de capture d'image */
    .capture-btn {
        background-color: #4caf50;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        cursor: pointer;
        font-size: 16px;
    }
        
    .capture-btn:hover {
        background-color: #388e3c;
    }


    .disabled { opacity: 0.5; cursor: not-allowed; } 

    .command-category { margin-bottom: 20px; } 
    .check-switch { margin-left: 8px; font-weight: bold; } 
    </style> 
    </head> 
    <body> 
    """
    html += "<div class='container'>"
    
    # --- Panneau de contrôle de la caméra ---
    html += "<div class='camera-controls'>" 
    html += "<h2>Contrôle de la caméra</h2>"
    # --- Ajout des boutons et du conteneur pour le flux vidéo ---
    html += "<button class='toggle-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>" 
    
    html += "<button class='capture-btn' id='cameraCaptureBtn' onclick='captureImage()'>📸 Capture Image</button>" 

    html += "<div class='live-feed' id='liveFeed'><img src='/video' alt='Flux vidéo en direct'></div>" 
    
    html += "</div>" 

    # --- Fonctions JavaScript pour gérer le livefeed vidéo --- 
    html += """ 
    <script> 

    function toggleCamera() { 
        const liveFeed = document.getElementById('liveFeed'); 
        const btn = document.getElementById('cameraToggleBtn'); 
        const img = liveFeed.querySelector('img'); 

        if (liveFeed.style.display === 'none' || liveFeed.style.display === '') {  
            // 1. Affiche le conteneur et change le bouton (pour la réactivité) 
            liveFeed.style.display = 'block'; 
            btn.textContent = '⛔ Stop Camera'; 

            // 2. Envoie la commande de démarrage au serveur 
            fetch('/start_camera', { method: 'POST' }) 
                .then(() => { 
                // 3. ATTEND que le serveur ait confirmé le démarrage avant de demander le flux vidéo. 
                img.src = '/video?' + new Date().getTime(); 
            }); 
        
        } else { 
            // 1. Cache le conteneur et change le bouton 
            liveFeed.style.display = 'none'; 
            btn.textContent = '▶️ Start Camera'; 
            
            // 2. Vide la source de l'image (arrête le flux gelé) 
            img.src = "";  
            
            // 3. Envoie la commande d'arrêt au serveur 
            fetch('/close_camera', { method: 'POST' }); 
        } 
    } 

    function captureImage() {
        fetch('/capture_image', { method: 'POST' })
            .then(response => response.json())
            .then(({ file_url, filename, error }) => {
                if (error) {
                    alert('Erreur lors de la capture de l\'image : ' + error);
                    return;
                }
                alert('Image capturée et enregistrée sur le serveur : ' + file_url);
                // enregistrement de l'image sur le PC
                const link = document.createElement('a');
                link.href = file_url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                link.remove();
                // Ouverture d'un preview dans un nouvel onglet
                window.open(file_url, '_blank');
            })
            .catch(err => { alert('Erreur lors de la communication avec le serveur : ' + err);
            });
    }

    </script> 
    </body></html> 
    """

    return html
