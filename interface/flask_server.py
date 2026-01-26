# flask_server.py
# ------------------
# Module pour de gestion des routes du serveur Flask pour l'interface web du robot
# on déclare ici uniquement les routes et callbacks pour le backend du serveur Flask
# l'interface web est défini dans des fichiers dédiés pour chaque onglet.

from flask import Flask
import os

from main import ctrl

# Initialisation de l'instance du serveur Flask
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))




# ----------------------------------------------------------------------------
#                       Pages de l'interface web
# ----------------------------------------------------------------------------
@app.route('/')
def home():
    return ctrl.home()

@app.route('/vision')
def vision():
    return ctrl.vision()

@app.route('/onglet_template')
def onglet_template():
    return ctrl.onglet_template()

# ----------------------------------------------------------------------------
#            Fonctions de callback pour les actions de vision
# ----------------------------------------------------------------------------

@app.route('/download_image/<filename>')
def download_image(filename):
    return ctrl.download_image(filename)

# Fonction pour générer la page d'accueil HTML
@app.route('/capture_image', methods=['POST'])
def capture_image():
    return ctrl.capture_image()

# Fonction pour vérifier le statut de la caméra 
@app.route('/status')
def status():
    return ctrl.status()

@app.route('/EXIT', methods=['POST'])
def exit_server():
    return ctrl.exit_server()

# Fonction pour le flux vidéo en direct
@app.route('/video')
def video_feed():
    return ctrl.video_feed()

@app.route('/close_camera', methods=['POST'])
def close_camera():
    return ctrl.close_camera()

@app.route('/start_camera', methods=['POST'])
def start_camera():
    return ctrl.start_camera()

# ----------------------------------------------------------------------------
#          Fonctions de callback pour les actions moteur du robot
# ----------------------------------------------------------------------------
@app.route('/zumi/forward') 
def forward(): 
    return ctrl.forward() 

@app.route('/zumi/reverse') 
def reverse(): 
    return ctrl.reverse()
    
@app.route('/zumi/left') 
def left(): 
    return ctrl.left()
    
@app.route('/zumi/right') 
def right(): 
    return ctrl.right()
    
@app.route('/zumi/stop') 
def stop(): 
    return ctrl.stop()

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

    /* Nav d'onglets en haut */
    .tab-header { display: flex; align-items: center; gap: 12px; padding: 12px 20px; }
    .tab-title { font-size: 22px; font-weight: bold; margin: 0; }
    .tab-nav { display: flex; align-items: center; gap: 4px; margin-left: auto; }
    .primary-btn { background: #007acc; color: white; border: none; padding: 10px 18px; border-radius: 10px; cursor: pointer; font-size: 15px; }
    .primary-btn:hover { background: #005fa3; }
    .primary-btn.active { background: #00528a; box-shadow: 0 0 0 2px rgba(0,0,0,0.06) inset; }

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

    html += """
    <div class='tab-header'>
        <h2 class='tab-title'>Accueil</h2>
        <div class='tab-nav'>
            <button class='primary-btn' data-path='/' onclick="location.href='/'">Accueil</button>
            <button class='primary-btn' data-path='/vision' onclick="location.href='/vision'">Vision</button>
            <button class='primary-btn' data-path='/onglet_template' onclick="location.href='/onglet_template'">Template</button>
        </div>
    </div>
    """

    # --- Panneau de contrôle de la caméra ---
    html += "<div class='camera-controls'>" 
    html += "<h2>Contrôle de la caméra</h2>"
    # Ajout d'une barre de navigation d'onglets en haut
    
    # --- Ajout des boutons pour le flux vidéo ---
    html += "<button class='toggle-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>" 
    
    html += "<button class='capture-btn' id='cameraCaptureBtn' onclick='captureImage()'>📸 Capture Image</button>" 

    #--- Conteneur pour le flux vidéo en direct (état display:none par défaut) ---
    html += "<div class='live-feed' id='liveFeed' style = 'display:none;'><img id='videoStream' alt='Flux vidéo en direct'></div>" 
    
    html += "</div>" 


    # --- Fonctions JavaScript pour gérer le livefeed vidéo --- 
    # WARNING: On a pas de façon dirècte pour débugger le script JS. Si il brise
    # La page HTML va chargé mais resté bloqué, les action des boutons ne répondront pas.
    # Utiliser la console du navigateur pour debuguer le JS en faisant F12 sur la page web.
    # La console affichera les erreurs JS et permet d'exécuter des commandes JS manuellement pour tester.
    html += """ 
    <script> 

    // Active l'état du bouton d'onglet selon l'URL courante
    (function() {
        const norm = p => (p || '').replace(/\/+$/,'') || '/';
        const here = norm(location.pathname);
        document.querySelectorAll('.tab-nav .primary-btn').forEach(btn => {
            const p = norm(btn.dataset?.path || btn.getAttribute('data-path'));
            if (p === here) btn.classList.add('active');
        });
    })();

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
