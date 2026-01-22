# flask_server.py
# ------------------
# Module pour gérer le serveur Flask pour l'interface web du robot

from fileinput import filename
from flask import Flask, Response, request, redirect, url_for, jsonify, send_from_directory
import time, cv2
import threading
from core.vision.vision_pipeline import VisionPipeline

# Import des autres onglets de l'interface
from interface.onglet_vision import render_vision_tab
from interface.TemplateOnglet import render_template_tab # Exemple d'onglet template générique supprimer quand il y en aura d'autres


import os, uuid # Pour la sauvegarde des images capturées

# Initialisation de l'instance du serveur Flask
app = Flask(__name__, static_folder = os.path.join(os.path.dirname(__file__), 'static'))

# Instance globale du pipeline de vision
vision_pipeline = None

# Path pour sauvegarder les images capturées
CAPTURE_DIR = os.path.join(app.static_folder, 'captured_images')
os.makedirs(CAPTURE_DIR, exist_ok=True)  # Crée le dossier s'il n'existe pas

# Fonction pour attacher le pipeline de vision global
def attach_pipeline(pipeline):
    global vision_pipeline
    vision_pipeline = pipeline

# ----------------------------------------------------------------------------
#                       Pages de l'interface web
# ----------------------------------------------------------------------------
# Route pour la page d'accueil
# @app.route('/')
# def home():
    # return page_accueil()

# Route pour l'onglet de vision
# @app.route('/onglet_vision')
# def onglet_vision():
@app.route('/')
def home():
    html = render_vision_tab("Vision du Zumi")
    return html

@app.route('/onglet_template')
def onglet_template():
    html = render_template_tab("Mon onglet perso")
    return html


# ----------------------------------------------------------------------------
#                       Fonctions de callback pour les actions web
# ----------------------------------------------------------------------------

# Fonction pour télécharger une image capturée (Appelé automatiquement après capture)
@app.route('/download_image/<filename>')
def download_image(filename):
    print("Downloading:", filename, "from", CAPTURE_DIR)
    full_path = os.path.join(CAPTURE_DIR, filename)
    if not os.path.exists(full_path):
        print("File not found:", full_path)
        return "File not found", 404
    return send_from_directory(CAPTURE_DIR, filename, as_attachment=True)

# Fonction pour générer la page d'accueil HTML
@app.route('/capture_image', methods=['POST'])
def capture_image():
    global vision_pipeline # l'instance du pipeline de vision est déclarée globalement et intialisé dans le main
    
    if vision_pipeline is None or not vision_pipeline.is_running():
        return jsonify({'error': 'camera not running'}), 400
    
    # 1. Capture de l'image actuelle
    frame_brg = vision_pipeline.capture_frame()
    
    # 2. Génération d'un nom de fichier unique
    ts = time.strftime("%Y%m%d-%H%M%S")
    filename = f'{ts}_{uuid.uuid4().hex[:6]}.jpg'
    save_path = os.path.join(CAPTURE_DIR, filename)
    
    # 3. Sauvegarde de l'image localement
    ok = cv2.imwrite(save_path, frame_brg)
    if not ok:
        return jsonify({'error': 'write failed'}), 500
    
    # 4. Validation de la sauvegarde
    print("Saved image to:", save_path, "exists?", os.path.exists(save_path))

    # 5. Génération d'un URL pour accéder à l'image sauvegardée via le PC
    image_url = f'/download_image/{filename}'
    return jsonify({'filename': filename, 'file_url':  image_url})

# Fonction pour vérifier le statut de la caméra 
@app.route('/status')
def status():
    return jsonify({
        "camera_running": vision_pipeline.is_running()
    })

# Fonction pour le flux vidéo en direct
@app.route('/video') 
def video_feed(): 
    global vision_pipeline

    if not vision_pipeline or not vision_pipeline.is_running(): 
        print("Video feed requested but video pipeline not running") 
        return "Camera not running", 503

    if vision_pipeline.get_camera() is None:
        print("Video feed requested but camera not initialized")
        return "Camera not running", 503

    # Générateur de flux vidéo Attention: le livefeed consume 1 thread CPU
    def generate(): 
        while vision_pipeline.is_running(): 
            try: 
                frame_bgr = vision_pipeline.capture_frame() 
            except Exception as e: 
                print("Erreur de capture:", e) 
                time.sleep(0.1) 
                break # sortir de la boucle si erreur 

            # Convertir l'image BGR en JPEG
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
    
    vision_pipeline.stop()  
   
    print("Camera stop signal accepted.") 
    return redirect(url_for('home')) 

@app.route('/start_camera', methods=['POST']) 
def start_camera(): 
    global vision_pipeline, vision_thread 
    
    if vision_pipeline.is_running(): 
        print("Camera already active") 
        return redirect(url_for('home'))
     
    # --- CREATE A NEW CAMERA OBJECT --- 
    vision_pipeline.start()
    print("Caméra en fonctionnement")
    return redirect(url_for('home'))



def page_accueil():
    print("Génération de la page d'accueil HTML") # pour debug
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

    print("Ajout du panneau de contrôle de la caméra") # pour debug

    # --- Panneau de contrôle de la caméra ---
    html += "<div class='camera-controls'>" 
    html += "<h2>Contrôle de la caméra</h2>"
    # --- Ajout des boutons pour le flux vidéo ---
    html += "<button class='toggle-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>" 
    
    html += "<button class='capture-btn' id='cameraCaptureBtn' onclick='captureImage()'>📸 Capture Image</button>" 

    #--- Conteneur pour le flux vidéo en direct (état display:none par défaut) ---
    html += "<div class='live-feed' id='liveFeed' style = 'display:none;'><img id='videoStream' alt='Flux vidéo en direct'></div>" 
    
    html += "</div>" 

    print("Fin de la génération de la page d'accueil HTML") # pour debug


    # --- Fonctions JavaScript pour gérer le livefeed vidéo --- 
    # WARNING: On a pas de façon dirècte pour débugger le script JS. Si il brise
    # La page HTML va chargé mais resté bloqué, les action des boutons ne répondront pas.
    # Utiliser la console du navigateur pour debuguer le JS en faisant F12 sur la page web.
    # La console affichera les erreurs JS et permet d'exécuter des commandes JS manuellement pour tester.
    html += """ 
    <script> 

    function toggleCamera() { 
        console.log("toggleCamera() appelée"); // pour debug

        const liveFeed = document.getElementById('liveFeed'); 
        const btn = document.getElementById('cameraToggleBtn'); 
        const img = liveFeed.querySelector('img'); 

        const isActive = liveFeed.style.display === 'block';

        if (!isActive) {  
            // 1. Affiche le conteneur et change le bouton (pour la réactivité)  
            btn.textContent = '⛔ Stop Camera'; 

            // 2. Envoie la commande de démarrage au serveur 
            fetch('/start_camera', { method: 'POST' }) 
                .then(() => { 
                // 3. ATTEND que le serveur ait confirmé le démarrage avant de demander le flux vidéo. 
                liveFeed.style.display = 'block';
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
        console.log("captureImage() appelée"); // pour debug

        fetch('/capture_image', { method: 'POST' })
            .then(response => response.json())
            .then(({ file_url, filename, error }) => {
                if (error) {
                    alert('Erreur lors de la capture image : ' + error);
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
                // window.open(file_url, '_blank');
            })
            .catch(err => { alert('Erreur lors de la communication avec le serveur : ' + err);
                console.log("Erreur lors de la communication avec le serveur : " + err); // pour debug
            });
    }

    </script> 
    </body></html> 
    """

    print("Fonction JS ajoutée à la page d'accueil") # pour debug

    return html
