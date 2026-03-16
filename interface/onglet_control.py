#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_control.py
# ------------------
# ce module défini un onglet de l'interface web dédié au contrôle automatique du robot.
# il permet nottament d'activer les systèmes de contrôle et d'échantillonner les capteurs
# pour l'entrainement du MLP.

def render_control_tab(title: str = "Contrôle") -> str:
    """Retourne la page HTML complète de l'onglet de contrôle."""
    
    html = """<!DOCTYPE html><html lang='fr'>
    <head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>{title}</title>
    <link rel='icon' href='data:,'>
    <style>
    body {
        margin: 0; padding: 0;
        width: 100vw; height: 100vh;
        font-family: 'Segoe UI', Arial, sans-serif;
        /* Ton background préféré rose et bleu pastel */
        background: linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%);
        color: #333; display: flex; flex-direction: column;
        overflow: hidden;
    }

    .container {
        display: flex; justify-content: center; align-items: flex-start;
        padding: 2vh; height: 96vh;
    }

    .tab-shell {
        /* Un blanc très légèrement bleuté pour la douceur */
        background: rgba(247, 253, 255, 0.95);
        border-radius: 20px;
        padding: 2%;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        width: 90%; 
        max-width: 1100px;
        height: 85%;
        display: flex;
        flex-direction: column;
    }

    .tab-header {
        display: flex; align-items: center;
        margin-bottom: 2vh;
        padding-bottom: 1vh;
        border-bottom: 2px solid #e0f4ff;
    }

    .tab-nav {
        display: flex; align-items: center;
        gap: 8px;
        margin-left: auto;
    }

    .tab-content {
        /* Bordure bleue plus douce et fond jaune crème très léger */
        border: 3px dashed #B5FFFC;
        border-radius: 15px;
        padding: 3%;
        flex-grow: 1;
        background: #FFFDF0; 
        display: flex;
        gap: 3%;
        overflow-y: auto;
    }

    .left-panel, .right-panel {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    
        #log-box {
        background: #FFFFFF; 
        border-radius: 15px;
        padding: 15px;
        width: 85%; /* Occupe presque toute la largeur du panneau */
        
        height: 60px;          /* On force une hauteur fixe */
        display: flex;         /* Utilise Flexbox pour centrer le texte */
        align-items: center;   /* Centre le texte verticalement */
        justify-content: center; /* Centre le texte horizontalement */
        overflow: hidden;      /* Empêche le texte de dépasser si c'est trop long */
        
        margin-bottom: 2vh;
        text-align: center;
        font-size: 1.1rem;
        font-weight: bold;
        border: 3px solid #87C7F1; 
        box-shadow: 0 4px 0 #D0D0D0;
        color: #555;
    }

    /* --- Styles pour les textes --- */
    
    .tab-title {
        font-size: 1.8rem; font-weight: bold; color: #5A99C7; margin: 0;
    }

    .tab-subtitle {
        font-size: 1.3rem; font-weight: bold; color: #666; margin-bottom: 15px;
    }

    .tab-text {
        font-size: 1.1rem; color: #444;
    }

    /* --- Boutons Pastels --- */

    .primary-btn {
        /* Bleu ciel doux */
        background: #87C7F1; color: white; border: none;
        padding: 12px 20px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        transition: transform 0.2s, background 0.2s;
        box-shadow: 0 4px 0 #6BAED6; /* Effet 3D léger */
    }

    .primary-btn:hover { 
        background: #76B9E4; 
        transform: translateY(-2px);
    }

    .primary-btn:active {
        transform: translateY(2px);
        box-shadow: 0 2px 0 #6BAED6;
    }

    .primary-btn.active {
        background: #5A99C7;
        box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
    }

    .toggle-btn {
        background: #FFB7D5; /* Rose pastel pour la caméra */
        color: white; border: none; 
        padding: 12px 24px; border-radius: 12px; 
        cursor: pointer; font-weight: bold;
        box-shadow: 0 4px 0 #E896B9;
    }

    .toggle-btn:hover { background: #FFA3C8; }

    .params-card {
        width: 85%;
        margin-top: 12px;
        background: #FFFFFF;
        border-radius: 14px;
        padding: 12px;
        border: 2px solid #B5FFFC;
        box-shadow: 0 4px 0 #D0D0D0;
    }

    .param-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
    }

    .param-row label {
        flex: 1;
        font-weight: bold;
        color: #555;
        font-size: 0.95rem;
    }

    .param-row input[type='range'] {
        flex: 2;
    }

    .param-value {
        width: 48px;
        text-align: right;
        font-weight: bold;
        color: #5A99C7;
    }

    /* --- Le D-Pad (Contrôle Robot) --- */

    .driving-mode {
        background-color: #E0F7FA;
        padding: 20px;
        border-radius: 20px;
        width: 80%;
        display: flex;
        flex-direction: column;
        align-items: center;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05);
    }

    /* --- Le D-Pad en Croix (Étoile) --- */
    .dpad-container {
        display: grid;
        /* Ici on définit la grille 3x3 pour faire la croix */
        grid-template-areas: 
            ".     up     ."
            "left  center right"
            ".     down   .";
        grid-gap: 12px;
        width: 25vh; 
        height: 25vh;
    }

    .dpad-button {
        background: #FFFFFF; 
        border-radius: 15px;
        border: none; 
        cursor: pointer;
        box-shadow: 0 4px 0 #D0D0D0;
        display: flex; 
        justify-content: center; 
        align-items: center;
        transition: all 0.1s;
    }

    /* Assignation des boutons aux zones de la grille */
    .dpad-up    { grid-area: up; }
    .dpad-down  { grid-area: down; }
    .dpad-left  { grid-area: left; }
    .dpad-right { grid-area: right; }
    .dpad-center { 
        grid-area: center; 
        background: #FFF; /* Le bouton STOP au milieu */
        border: 2px dashed #87C7F1;
    }
    .dpad-button:hover { background: #F9F9F9; }
    .dpad-button:active { transform: translateY(3px); box-shadow: 0 1px 0 #D0D0D0; }
    .dpad-button svg { width: 50%; height: 50%; stroke: #87C7F1; stroke-width: 10; }

    /* --- Live Feed --- */

    .live-feed {
        display: none; 
        width: 90%; 
        margin-top: 2vh; 
        padding: 10px; 
        background: white;
        border-radius: 20px; 
        border: 4px solid #B5FFFC;
        text-align: center; 
    }

    .live-feed img {
        width: 100%; border-radius: 10px;
    }
    </style>

    </style>
    </head>
    <body>
    <div class='container'>
        <div class='tab-shell'>
            <div class='tab-header'>
                <h2 class='tab-title'>{title}</h2>
                <div class='tab-nav'>
                <!-- Boutons de navigation entre onglets -->
                <button class='primary-btn' data-path="/">Accueil</button>
                <button class='primary-btn' data-path="/vision">Vision</button>
                <button class='primary-btn' data-path="/onglet_control">Contrôle</button>
        		<button class='primary-btn' data-path="/pid">PID</button>
                <button class='primary-btn' onclick="fetch('/exit', {method:'POST'})">EXIT</button>
                </div>
            </div>

            <div class='tab-content'>
                <!-- AJOUTER VOS BOUTONS ICI -->
                <div class='left-panel'>
                    <button class='toggle-btn' id='cameraToggleBtn'>🎥 Allume la caméra !</button>
                    <button class='toggle-btn' id='samplingToggleBtn'>Échantillonnage</button>
                    <button class='primary-btn' id='samplingDownloadBtn' style='margin-top:10px; width:85%;'>⬇️ Télécharger échantillons</button>

                    <div style='width:85%; margin-top:12px;'>
                        <select id='controllerSelect' style='width:100%; padding:10px; border-radius:10px; border:2px solid #B5FFFC; font-weight:bold;'>
                            <option value='line_follower'>line_follower</option>
                            <option value='manual_controller'>manual_controller</option>
                        </select>
                    </div>
                    <button class='primary-btn' id='controllerToggleBtn' style='margin-top:10px; width:85%;'>▶ Activer le contrôleur</button>

                    <div class='params-card'>
                        <div class='tab-subtitle'>Réglages manuels</div>
                        <div class='param-row'>
                            <label for='trimLeft'>Trim gauche</label>
                            <input id='trimLeft' type='range' min='-20' max='20' step='1' value='0'>
                            <span class='param-value' id='trimLeftVal'>0</span>
                        </div>
                        <div class='param-row'>
                            <label for='trimRight'>Trim droit</label>
                            <input id='trimRight' type='range' min='-20' max='20' step='1' value='0'>
                            <span class='param-value' id='trimRightVal'>0</span>
                        </div>
                        <div class='param-row'>
                            <label for='driveSpeed'>Vitesse manuelle</label>
                            <input id='driveSpeed' type='range' min='0' max='60' step='1' value='20'>
                            <span class='param-value' id='driveSpeedVal'>20</span>
                        </div>
                        <div class='param-row'>
                            <label for='turnSpeed'>Vitesse rotation</label>
                            <input id='turnSpeed' type='range' min='0' max='60' step='1' value='15'>
                            <span class='param-value' id='turnSpeedVal'>15</span>
                        </div>
                        <button class='primary-btn' id='applyManualSettingsBtn' style='margin-top:10px; width:100%;'>Appliquer</button>
                    </div>

                    <div id='zone-resultats'>
                        <!-- Conteneur du flux vidéo en direct -->
                        
                    </div>
                </div>

                <div class='right-panel'>
                    <div class='driving-mode'>
                        <h3>Contrôle du Zumi</h3>
                        <!-- La boîte apparaît grâces à cette ligne -->
                        <div class='live-feed' id='liveFeed' style = 'display:none;'>
                            <img id='videoStream' alt='Flux vidéo en direct'>
                        </div>
                        
                        <div class="dpad-container">
                            <!-- HAUT -->
                            <button class="dpad-button dpad-up" data-direction="forward">
                                <svg viewBox="0 0 100 100"><path d="M50 20 L50 80 M20 50 L50 20 L80 50"></path></svg>
                            </button>
                            <!-- GAUCHE -->
                            <button class="dpad-button dpad-left" data-direction="left">
                                <svg viewBox="0 0 100 100"><path d="M80 50 L20 50 M50 20 L20 50 L50 80"></path></svg>
                            </button>
                            <!-- CENTRE (Stop) -->
                            <button class="dpad-button dpad-center" id="dpadCenterBtn"></button>
                            <!-- DROITE -->
                            <button class="dpad-button dpad-right" data-direction="right">
                                <svg viewBox="0 0 100 100"><path d="M20 50 L80 50 M50 20 L80 50 L50 80"></path></svg>
                            </button>
                            <!-- BAS -->
                            <button class="dpad-button dpad-down" data-direction="reverse">
                                <svg viewBox="0 0 100 100"><path d="M50 80 L50 20 M20 50 L50 80 L80 50"></path></svg>
                            </button>
                        </div>
                    </div>
                    <hr style="width:100%; margin: 20px 0; border: 1px solid #ccc;">
                </div>    
            </div>
        </div>
    </div>
    

    <!-- --- Scripts JavaScript pour les interactions --- -->

    <script>
    // Active l'état du bouton d'onglet selon l'URL courante (compat ES5)
    (function() {
        var norm = function(p) { return (p || '').replace(/\/+$/,'') || '/'; };
        var here = norm(location.pathname);
        var btns = document.querySelectorAll('.tab-nav .primary-btn');
        Array.prototype.forEach.call(btns, function(btn) {
            var p = norm(btn.getAttribute('data-path'));
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
            btn.textContent = '⏹️ Éteint la caméra'; 

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
            btn.textContent = '🎥 Allume la caméra !'; 
            
            // 2. Vide la source de l'image (arrête le flux gelé) 
            img.src = "";  
            
            // 3. Envoie la commande d'arrêt au serveur 
            fetch('/close_camera', { method: 'POST' }); 
        }
    }

    function toggleSampling() {
        console.log("toggleSampling() appelée"); // pour debug
        const btn = document.getElementById('samplingToggleBtn');
        const isActive = btn.classList.contains('active');

        if (!isActive) {
            btn.classList.add('active');
            btn.textContent = '⏹️ Arrête échantillonnage';
            fetch('/start_sampling', { method: 'POST' });
        } else {
            btn.classList.remove('active');
            btn.textContent = 'Échantillonnage';
            fetch('/stop_sampling', { method: 'POST' });
        }
    }

    function downloadSampling() {
        fetch('/sampling/download')
            .then(function(resp) {
                if (!resp.ok) {
                    return resp.json().then(function(data) {
                        throw new Error(data.error || 'Download failed');
                    });
                }
                return resp.blob();
            })
            .then(function(blob) {
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'sampling.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            })
            .catch(function(e) { alert('Erreur download: ' + e.message); });
    }

    function toggleController() {
        const btn = document.getElementById('controllerToggleBtn');
        const select = document.getElementById('controllerSelect');
        const controllerName = select ? select.value : 'line_follower';
        const isActive = btn.classList.contains('active');
        if (!isActive) {
            fetch('/controller/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: controllerName })
            })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) {
                        alert('Erreur : ' + data.error);
                    } else {
                        btn.classList.add('active');
                        btn.textContent = '⏹ Arrêter le contrôleur';
                        document.getElementById('log-box').innerText = '🤖 Contrôleur actif : ' + (data.controller || 'line_follower');
                    }
                })
                .catch(function(e) { console.error('toggleController start error:', e); });
        } else {
            fetch('/controller/stop', { method: 'POST' })
                .then(function() {
                    btn.classList.remove('active');
                    btn.textContent = '▶ Activer le contrôleur';
                    document.getElementById('log-box').innerText = 'Contrôleur arrêté. 🛑';
                })
                .catch(function(e) { console.error('toggleController stop error:', e); });
        }
    }

    var manualSettingsTimer = null;

    function applyManualSettings() {
        var payload = {
            left_trim: parseFloat(document.getElementById('trimLeft').value),
            right_trim: parseFloat(document.getElementById('trimRight').value),
            drive_speed: parseFloat(document.getElementById('driveSpeed').value),
            turn_speed: parseFloat(document.getElementById('turnSpeed').value)
        };

        fetch('/manual/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) console.error('manual settings error:', data.error);
            })
            .catch(function(e) { console.error('manual settings fetch error:', e); });
    }

    function scheduleManualSettingsUpdate() {
        if (manualSettingsTimer) clearTimeout(manualSettingsTimer);
        manualSettingsTimer = setTimeout(applyManualSettings, 250);
    }

    function bindRange(id) {
        var input = document.getElementById(id);
        var valueEl = document.getElementById(id + 'Val');
        if (!input || !valueEl) return;
        var update = function() { valueEl.textContent = input.value; };
        input.addEventListener('input', function() {
            update();
            scheduleManualSettingsUpdate();
        });
        update();
    }

    function loadManualSettings() {
        fetch('/manual/settings')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.left_trim !== null && data.left_trim !== undefined) {
                    document.getElementById('trimLeft').value = data.left_trim;
                }
                if (data.right_trim !== null && data.right_trim !== undefined) {
                    document.getElementById('trimRight').value = data.right_trim;
                }
                if (data.drive_speed !== null && data.drive_speed !== undefined) {
                    document.getElementById('driveSpeed').value = data.drive_speed;
                }
                if (data.turn_speed !== null && data.turn_speed !== undefined) {
                    document.getElementById('turnSpeed').value = data.turn_speed;
                }
                bindRange('trimLeft');
                bindRange('trimRight');
                bindRange('driveSpeed');
                bindRange('turnSpeed');
            })
            .catch(function(e) { console.error('load manual settings error:', e); });
    }
    
    // Helper de navigation pour fermer la caméra avant de changer d'onglet
    function navigateTo(path) {
        try {
            var liveFeed = document.getElementById('liveFeed');
            var isActive = liveFeed && liveFeed.style.display === 'block';
            if (isActive) {
                fetch('/close_camera', { method: 'POST' })
                    .then(function() { location.href = path; })
                    .catch(function() { location.href = path; });
            } else {
                location.href = path;
            }
        } catch (e) {
            console.error('navigateTo error:', e);
            location.href = path;
        }
    }

        
    // --- FONCTIONS DE MOUVEMENT ---
    var isMoving = false;
    var moveInterval = null;

    function startMove(direction) {
        if (isMoving) return;
        isMoving = true;
           
        // --- NOUVEAU : Texte affiche pour etat du robot ---
        //document.getElementById('log-box').innerText = "🤖 État : " + direction;
        
        const log = document.getElementById('log-box');
        log.style.color = "#000000"; // Couleur de texte par défaut (noir)

        // Logique pour afficher le message approprié
        switch (direction)
        {
            case 'forward':
                log.innerText = "En avant ! 🚀";
                log.style.color = "#28a745"; // Vert pour avancer
                break;
            case 'reverse':
                log.innerText = "En arrière ! ⏪";
                log.style.color = "#dc3545"; // Rouge pour reculer
                break;
            case 'left':
                log.innerText = "À gauche toute ! ↪️";
                log.style.color = "#007bff"; // Bleu pour tourner
                break;
            case 'right':
                log.innerText = "À droite ! ↩️";
                log.style.color = "#007bff"; // Bleu pour tourner
                break;
        }

                
        // Fonction interne pour envoyer la commande
        const sendMoveCommand = () => {
            fetch('/zumi/' + direction)
                .then(response => {
                    if (!response.ok) console.error('Error starting move: ' + direction);
                })
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
        
        
        // --- NOUVEAU : Ajout du message d'arret ---
        const log = document.getElementById('log-box');
        log.innerText = "Ouf, je fais une pause. 🛑";
        log.style.color = "#6c757d"; // Gris neutre pour la pause
        
        
        // 1. Arrêter l'envoi de commandes en continu
        if (moveInterval) {
            clearInterval(moveInterval);
            moveInterval = null;            
        }
        
        // 2. Envoyer la commande d'arrêt explicite
        fetch('/zumi/stop')
            .then(response => {
                if (!response.ok) console.error('Error stopping move');
            })
            .catch(error => console.error('Fetch error:', error));
    }

    // --- Charger les événements au DOMContentLoaded ---
    window.addEventListener('DOMContentLoaded', function() {
        // Navigation buttons (utilise data-path pour déterminer la destination)
        var navBtns = document.querySelectorAll('.tab-nav .primary-btn');
        Array.prototype.forEach.call(navBtns, function(btn) {
            var path = btn.getAttribute('data-path');
            if (path) {
                btn.addEventListener('click', function() { navigateTo(path); });
            }
        });

        // Camera toggle
        var camBtn = document.getElementById('cameraToggleBtn');
        if (camBtn) camBtn.addEventListener('click', toggleCamera);

        // Sampling toggle
        var samplingBtn = document.getElementById('samplingToggleBtn');
        if (samplingBtn) samplingBtn.addEventListener('click', toggleSampling);

        var samplingDownloadBtn = document.getElementById('samplingDownloadBtn');
        if (samplingDownloadBtn) samplingDownloadBtn.addEventListener('click', downloadSampling);
        
        // Controller toggle
        var ctrlBtn = document.getElementById('controllerToggleBtn');
        if (ctrlBtn) ctrlBtn.addEventListener('click', toggleController);

        var controllerSelect = document.getElementById('controllerSelect');
        if (controllerSelect) {
            fetch('/controller/list')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (!data.controllers || data.controllers.length === 0) return;
                    controllerSelect.innerHTML = '';
                    data.controllers.forEach(function(name) {
                        var opt = document.createElement('option');
                        opt.value = name;
                        opt.textContent = name;
                        controllerSelect.appendChild(opt);
                    });
                })
                .catch(function(e) { console.error('controller list error:', e); });
        }

        var applyManualBtn = document.getElementById('applyManualSettingsBtn');
        if (applyManualBtn) applyManualBtn.addEventListener('click', applyManualSettings);

        loadManualSettings();
        
        // D-pad: register mouse + passive touch events
        var dpadButtons = document.querySelectorAll('.dpad-button[data-direction]');
        Array.prototype.forEach.call(dpadButtons, function(btn) {
            var dir = btn.getAttribute('data-direction');
            btn.addEventListener('mousedown', function() { startMove(dir); });
            btn.addEventListener('mouseup', stopMove);
            btn.addEventListener('mouseleave', stopMove);
            btn.addEventListener('touchstart', function() { startMove(dir); }, { passive: true });
            btn.addEventListener('touchend', stopMove, { passive: true });
        });

        // D-pad center button (stop)
        var centerBtn = document.getElementById('dpadCenterBtn');
        if (centerBtn) centerBtn.addEventListener('click', stopMove);
    });

    // Exposer les fonctions au scope global (pour les onclick inline restants)
    window.navigateTo = navigateTo;
    window.toggleCamera = toggleCamera;
    window.toggleSampling = toggleSampling;
    window.downloadSampling = downloadSampling;
    window.toggleController = toggleController;
    window.startMove = startMove;
    window.stopMove = stopMove;
    window.applyManualSettings = applyManualSettings;

    </script>
    </body></html>
    """

    return html.replace("{title}", title)
