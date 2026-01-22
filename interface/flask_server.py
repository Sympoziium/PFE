# flask_server.py
# ------------------
# Module pour gérer le serveur Flask pour l'interface web du robot

from flask import Flask, Response, request, redirect, url_for, jsonify 
import time, cv2
import threading
from core.vision.vision_pipeline import VisionPipeline

# Initialisation de l'instance du serveur Flask
app = Flask(__name__)


# Page principale de l'interface web
@app.route('/')
def home():
    return page_accueil()

# Fonction pour générer la page d'accueil HTML
@app.route('/capture_image', methods=['POST'])
def capture_image():
    global vision_pipeline # l'instance du pipeline de vision est déclarée globalement et intialisé dans le main
    filename = vision_pipeline.step()
    return jsonify({'filename': filename})

@app.route('/video') 
def video_feed(): 
    global vision_pipeline
    def generate(): 
        while vision_pipeline.is_running(): 
            # attend si l'objet camera n'existe pas 
            if vision_pipeline.get_camera() is None: 
                time.sleep(0.1) 
                continue 
            try: 
                frame = vision_pipeline.capture_frame() 
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
    global vision_pipeline, vision_thread 
    if vision_pipeline.is_running(): 
        print("Camera already active") 
        return redirect(url_for('home')) 
    print("Thread caméra démarré") 
    # --- CREATE A NEW CAMERA OBJECT --- 
    vision_pipeline.start()
    vision_thread = threading.Thread(target=vision_pipeline.run_camera()) 
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
        color: #255; display: flex; flex-direction: column; 
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
            .then(data => {
                alert('Image capturée et enregistrée sur le serveur : ' + data['filename']);
            });
    }

    </script> 
    </body></html> 
    """

    return html


# === LANCEMENT DU SERVEUR === 
if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=5000, threaded=True) 