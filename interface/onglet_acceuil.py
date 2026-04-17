#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_acceuil.py
# ------------------
# ce module défini un onglet de l'interface web dédié à l'accueil
# on y trouve notamment des boutons pour naviguer vers les autres onglets,
# un livefeed de la caméra, les boutons de contrôle du Zumi, les boutons de
# choix de scénarios et les boutons de contrôle du pont levis.

def render_accueil_tab(title: str = "Accueil") -> str:
	"""Retourne la page HTML complète de l'onglet d'accueil."""

	html = """<!DOCTYPE html><html lang='fr'>
	<head>
	<meta charset='UTF-8'>
	<meta name='viewport' content='width=device-width, initial-scale=1'>
	<title>{title}</title>
	<link rel='icon' href='data:,'>
	<style>
    body {
        margin: 0; padding: 0;
        width: 100vw; min-height: 100vh;
        font-family: 'Segoe UI', Arial, sans-serif;
        /* Ton background préféré rose et bleu pastel */
        background: linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%);
        color: #333; display: flex; flex-direction: column;
        overflow-y: auto;
    }

    .container {
        display: flex; justify-content: center; align-items: flex-start;
        padding: 2vh; min-height: 96vh;
    }

    .tab-shell {
        /* Un blanc très légèrement bleuté pour la douceur */
        background: rgba(247, 253, 255, 0.95);
        border-radius: 20px;
        padding: 2%;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        width: 90%; 
        max-width: 1100px;
        min-height: fit-content;
        margin-bottom: 4vh;
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
        background: #FFFDF0; 
        display: flex;
        gap: 3%;
    }

    .left-panel, .right-panel {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 0; /* force flex child to respect flex:1 without overflow */
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
        width: 92%;
        margin-top: 2vh;
        padding: 10px;
        background: white;
        border-radius: 20px;
        border: 4px solid #B5FFFC;
        text-align: center;
        box-sizing: border-box;
    }

    .live-feed img {
        width: 100%; border-radius: 10px;
        display: block;
    }

    /* --- QR Code popover --- */
    .qr-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        margin-right: 20px; /* gap plus grand que les 8px entre boutons */
    }

    .qr-icon-btn {
        background: rgba(247, 253, 255, 0.9);
        border: 2px solid #B5FFFC;
        border-radius: 12px;
        width: 42px; height: 42px;
        cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 0 #9be8e4;
        transition: transform 0.15s;
        font-size: 20px;
        flex-shrink: 0;
    }

    .qr-icon-btn:hover { transform: translateY(-2px); }
    .qr-icon-btn:active { transform: translateY(2px); box-shadow: 0 2px 0 #9be8e4; }

    .qr-popover {
        display: none;
        position: absolute;
        top: calc(100% + 10px);
        left: 0;
        background: rgba(247, 253, 255, 0.98);
        border: 2px solid #B5FFFC;
        border-radius: 16px;
        padding: 14px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        z-index: 100;
        text-align: center;
        width: 180px;
    }

    .qr-popover.visible { display: block; }

    .qr-popover p {
        margin: 8px 0 0 0;
        font-size: 12px;
        color: #888;
        line-height: 1.4;
    }

    #qrCanvas, #qrCanvas img, #qrCanvas canvas {
        display: block;
        margin: 0 auto;
    }

    /* Petite flèche vers le haut, alignée sur l'icône */
    .qr-popover::before {
        content: '';
        position: absolute;
        top: -8px; left: 13px;
        border-left: 8px solid transparent;
        border-right: 8px solid transparent;
        border-bottom: 8px solid #B5FFFC;
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
                <!-- QR Code popover — dans le tab-nav, avant le premier bouton -->
                <div class='qr-wrapper' id='qrWrapper'>
                    <button class='qr-icon-btn' id='qrIconBtn' title='Scanner pour se connecter'>&#x1F4F1;</button>
                    <div class='qr-popover' id='qrPopover'>
                        <div id='qrCanvas'></div>
                        <p>Scanner pour<br>ouvrir l'interface</p>
                    </div>
                </div>
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
                    <div id='zone-resultats'>
                        <!-- Conteneur du flux vidéo en direct -->
                        <div class='live-feed' id='liveFeed' style = 'display:none;'>
                            <img id='videoStream' alt='Flux vidéo en direct'>
                        </div>
                    </div>
                </div>

                <div class='right-panel'>
                    <div class='driving-mode'>
                        <h3>Contrôle du Zumi</h3>
                        <!-- La boîte apparaît grâces à cette ligne -->
                        <div id="log-box">Coucou ! Je suis prêt à rouler ! 🤖</div>
                        
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
                    <div class='driving-mode' style='margin-top: 20px;'>
                        <h3 style='margin: 0 0 16px 0;'>🌉 Pont Levis</h3>

                        <!-- Grille 2x2 : [Toggle Auto | Bouton pont] / [Feu Vert | Feu Rouge] -->
                        <div style='display:grid; grid-template-columns:1fr 1fr; gap:10px; width:100%;'>

                            <!-- Ligne 1 col 1 : Toggle Mode Auto -->
                            <div style='display:flex; align-items:center; justify-content:center; gap:8px;
                                        background:rgba(247,253,255,0.6); border-radius:12px; padding:10px;
                                        border:2px solid #B5FFFC;'>
                                <span style='font-weight:bold; color:#555; font-size:0.9rem; white-space:nowrap;'>Mode Auto</span>
                                <div id='autoToggle' onclick='toggleAuto(!autoIsOn)' style='
                                    width:52px; height:28px; border-radius:14px; flex-shrink:0;
                                    background:#A8E6CF; cursor:pointer; position:relative;
                                    box-shadow:0 3px 0 #74C69D; transition:background 0.2s;'>
                                    <div id='autoToggleThumb' style='
                                        position:absolute; top:4px; left:28px;
                                        width:20px; height:20px; border-radius:50%;
                                        background:white; box-shadow:0 2px 4px rgba(0,0,0,0.2);
                                        transition:left 0.2s;'></div>
                                </div>
                                <span id='autoToggleLabel' style='font-size:0.9rem; color:#2d6a4f; font-weight:bold;'>ON</span>
                                <input type='checkbox' id='autoCheck' checked style='display:none;'>
                            </div>

                            <!-- Ligne 1 col 2 : Bouton pont -->
                            <button class='toggle-btn' id='bridgeToggleBtn' onclick='toggleBridge()'
                                    style='width:100%; white-space:nowrap;'>
                                🌉 Ouvrir le pont
                            </button>

                            <!-- Ligne 2 col 1 : Feu Vert -->
                            <button class='primary-btn' style='background:#A8E6CF; color:#2d6a4f;
                                box-shadow:0 4px 0 #74C69D; white-space:nowrap;'
                                onclick="fetch('/bridge/green', {method:'POST'})">🟢 Feu Vert</button>

                            <!-- Ligne 2 col 2 : Feu Rouge -->
                            <button class='primary-btn' style='background:#F4A0A0; color:#7a1f1f;
                                box-shadow:0 4px 0 #d97070; white-space:nowrap;'
                                onclick="fetch('/bridge/red', {method:'POST'})">🔴 Feu Rouge</button>

                        </div>
                    </div>
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

    // --- MODE AUTO, PONT LEVIS ET GESTION UI ---
    var autoIsOn = true;   // mode auto ON par defaut
    var bridgeIsOpen = false; // pont ferme par defaut

    function toggleAuto(isAuto) {
        autoIsOn = isAuto;
        var val = isAuto ? '1' : '0';
        fetch('/bridge/mode_auto/' + val, { method: 'POST' })
            .catch(function(err) { console.error('toggleAuto error:', err); });

        // Mise a jour du toggle visuel
        var track = document.getElementById('autoToggle');
        var thumb = document.getElementById('autoToggleThumb');
        var label = document.getElementById('autoToggleLabel');
        var check = document.getElementById('autoCheck');
        if (isAuto) {
            track.style.background = '#A8E6CF';
            track.style.boxShadow = '0 3px 0 #74C69D';
            thumb.style.left = '28px';
            label.textContent = 'ON';
            label.style.color = '#2d6a4f';
            check.checked = true;
        } else {
            track.style.background = '#F4A0A0';
            track.style.boxShadow = '0 3px 0 #d97070';
            thumb.style.left = '4px';
            label.textContent = 'OFF';
            label.style.color = '#7a1f1f';
            check.checked = false;
        }

        // Activer/desactiver le bouton pont manuel
        var btn = document.getElementById('bridgeToggleBtn');
        if (btn) {
            btn.style.opacity = isAuto ? '0.4' : '1';
            btn.style.cursor  = isAuto ? 'not-allowed' : 'pointer';
        }
    }

    function toggleBridge() {
        if (autoIsOn) return; // bloque si mode auto actif
        var btn = document.getElementById('bridgeToggleBtn');
        if (bridgeIsOpen) {
            // Fermer le pont
            fetch('/bridge/close', { method: 'POST' });
            bridgeIsOpen = false;
            btn.textContent = '🌉 Ouvrir le pont';
        } else {
            // Ouvrir le pont
            fetch('/bridge/open', { method: 'POST' });
            bridgeIsOpen = true;
            btn.textContent = '🌉 Fermer le pont';
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

        // Auto check (pont levis)
        var autoCheck = document.getElementById('autoCheck');
        if (autoCheck) autoCheck.addEventListener('change', function() { toggleAuto(this.checked); });

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

    // --- QR Code ---
    (function() {
        var btn = document.getElementById('qrIconBtn');
        var popover = document.getElementById('qrPopover');
        var generated = false;

        function generateQR() {
            if (generated) return;
            generated = true;
            var url = window.location.origin + '/';
            var script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
            script.onload = function() {
                new QRCode(document.getElementById('qrCanvas'), {
                    text: url,
                    width: 148,
                    height: 148,
                    colorDark: '#5A99C7',
                    colorLight: '#FFFDF0',
                    correctLevel: QRCode.CorrectLevel.M
                });
            };
            document.head.appendChild(script);
        }

        // Survol souris
        btn.addEventListener('mouseenter', function() {
            generateQR();
            popover.classList.add('visible');
        });
        document.getElementById('qrWrapper').addEventListener('mouseleave', function() {
            popover.classList.remove('visible');
        });

        // Clic (mobile / toggle)
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            generateQR();
            popover.classList.toggle('visible');
        });
        document.addEventListener('click', function() {
            popover.classList.remove('visible');
        });
    })();

    // Exposer les fonctions au scope global (pour les onclick inline restants)
    window.navigateTo = navigateTo;
    window.toggleCamera = toggleCamera;
    window.toggleAuto = toggleAuto;
    window.startMove = startMove;
    window.stopMove = stopMove;

    </script>
    </body></html>
    """
	return html.replace("{title}", title)
