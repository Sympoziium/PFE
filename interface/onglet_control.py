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

    .top-buttons-container {
        display: flex;
        gap: 10px;
        width: 85%;
        margin-bottom: 10px;
    }

    .top-buttons-container button {
        flex: 1;
    }

    .settings-menu-container {
        position: relative;
        width: 85%;
    }

    .settings-toggle-btn {
        width: 100%;
    }

    .params-card.hidden {
        display: none;
    }

    .settings-close-btn {
        position: absolute;
        top: 10px;
        right: 10px;
        background: #FF6B9D;
        color: white;
        border: none;
        border-radius: 8px;
        width: 30px;
        height: 30px;
        cursor: pointer;
        font-size: 1.2rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .settings-close-btn:hover {
        background: #FF5585;
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

    /* --- Indicateur WASD --- */
    .wasd-indicator {
        display: flex;
        gap: 4px;
        margin-top: 12px;
        justify-content: center;
    }
    .wasd-key {
        width: 36px; height: 36px;
        border: 2px solid #D0D0D0;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 0.9rem;
        color: #999;
        background: #F9F9F9;
        transition: all 0.1s;
    }
    .wasd-key.active {
        background: #87C7F1;
        color: white;
        border-color: #6BAED6;
        box-shadow: 0 2px 0 #6BAED6;
    }
    .wasd-grid {
        display: grid;
        grid-template-areas: ". w ." "a s d";
        grid-gap: 4px;
    }
    .wasd-w { grid-area: w; }
    .wasd-a { grid-area: a; }
    .wasd-s { grid-area: s; }
    .wasd-d { grid-area: d; }
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
                    <!-- Conteneur des 3 boutons en horizontal -->
                    <div class='top-buttons-container'>
                        <button class='toggle-btn' id='cameraToggleBtn'>🎥 Allume la caméra !</button>
                        <button class='toggle-btn' id='samplingToggleBtn'>Échantillonnage</button>
                        <button class='primary-btn' id='samplingDownloadBtn'>⬇️ Télécharger</button>
                    </div>

                    <div style='width:85%; margin-top:8px; display:flex; align-items:center; gap:8px;'>
                        <button class='toggle-btn' id='featureKillBtn' style='flex:1; font-size:12px; padding:6px 8px;'>
                            Détection passive : ON
                        </button>
                        <span style='font-size:11px; color:#aaa;' title='Quand actif, les features HAAR et caméra-ligne sont forcées à 0 dans les échantillons'>?</span>
                    </div>

                    <div style='width:85%; margin-top:12px;'>
                        <select id='controllerSelect' style='width:100%; padding:10px; border-radius:10px; border:2px solid #B5FFFC; font-weight:bold;'>
                            <option value='line_follower'>line_follower</option>
                            <option value='manual_controller'>manual_controller</option>
                        </select>
                    </div>
                    <button class='primary-btn' id='controllerToggleBtn' style='margin-top:10px; width:85%;'>▶ Activer le contrôleur</button>
                    <button class='toggle-btn' id='mlDebugBtn' style='margin-top:6px; width:85%; font-size:12px; padding:6px 8px;'>ML Debug: OFF</button>

                    <!-- Conteneur du menu de réglages adaptatif -->
                    <div class='settings-menu-container' style='margin-top:12px;'>
                        <button class='primary-btn settings-toggle-btn' id='settingsToggleBtn'>⚙️ Réglages</button>

                        <div class='params-card hidden' id='settingsCard'>
                            <div style='position:relative;'>
                                <div class='tab-subtitle' id='settingsTitle'>Réglages</div>
                                <button type='button' class='settings-close-btn' id='settingsCloseBtn'>✕</button>
                            </div>
                            <div id='settingsContent'>
                                <!-- Contenu généré dynamiquement par JS -->
                            </div>
                            <button class='primary-btn' id='applySettingsBtn' style='margin-top:10px; width:100%;'>Appliquer</button>
                        </div>
                    </div>

                    <!-- Menu collapsible Reset capteurs -->
                    <div class='settings-menu-container' style='margin-top:12px;'>
                        <button class='primary-btn settings-toggle-btn' id='resetToggleBtn'>Reset capteurs</button>
                        <div class='params-card hidden' id='resetCard'>
                            <div style='position:relative;'>
                                <div class='tab-subtitle'>Reset capteurs</div>
                                <button type='button' class='settings-close-btn' id='resetCloseBtn'>x</button>
                            </div>
                            <button class='toggle-btn' id='btnCalibrateAll' style='width:100%; margin-top:8px;'>Calibration complete (gyro+MPU)</button>
                            <button class='primary-btn' id='btnResetDrive' style='width:100%; margin-top:8px;'>Reset Drive State (PID+gyro)</button>
                            <button class='primary-btn' id='btnResetGyro' style='width:100%; margin-top:8px;'>Reset Gyro</button>
                            <button class='primary-btn' id='btnResetPID' style='width:100%; margin-top:8px;'>Reset PID</button>
                            <button class='primary-btn' id='btnCalibrateIR' style='width:100%; margin-top:8px;'>Calibration IR (offset capteurs)</button>
                        </div>
                    </div>

                    <!-- Sensor Profiler -->
                    <div class='panel' style='margin-top: 16px; padding: 12px; background: #1a1a2e; border-radius: 8px;'>
                        <h4 style='color: #e94560; margin: 0 0 12px 0;'>Sensor Profiler</h4>

                        <!-- Robot ID dropdown -->
                        <div style='margin-bottom: 8px;'>
                            <label style='color: #aaa; font-size: 12px;'>Robot:</label>
                            <select id='profilerRobotId' style='margin-left: 8px; padding: 4px; background: #333; color: #fff; border: 1px solid #555; border-radius: 4px;'>
                                <option value='zumi_1'>zumi_1</option>
                                <option value='zumi_2'>zumi_2</option>
                            </select>
                        </div>

                        <!-- Status display -->
                        <div id='profilerStatus' style='background: #0f0f23; padding: 8px; border-radius: 4px; margin-bottom: 8px; min-height: 60px;'>
                            <div style='color: #888; font-size: 13px;'>Profiler inactif. Sélectionnez le robot et appuyez sur Démarrer.</div>
                        </div>

                        <!-- Progress bar -->
                        <div style='background: #333; border-radius: 4px; height: 6px; margin-bottom: 8px;'>
                            <div id='profilerProgress' style='background: #e94560; height: 100%; border-radius: 4px; width: 0%; transition: width 0.3s;'></div>
                        </div>

                        <!-- Samples indicator -->
                        <div id='profilerSamples' style='display:none; text-align:center; color:#2ecc71; font-size:13px; font-weight:bold; margin-bottom:6px;'></div>

                        <!-- Single contextual button -->
                        <button id='btnProfilerAction' style='width:100%; padding:10px; font-size:14px; border:none; border-radius:6px; color:#fff; background:#27ae60; cursor:pointer;'>Démarrer le profiling</button>

                        <!-- End buttons (hidden until profiling complete) -->
                        <div id='profilerEndButtons' style='display:none; gap:6px; margin-top:6px;'>
                            <button id='btnProfilerApply' style='flex:1; padding:10px; font-size:13px; border:none; border-radius:6px; color:#fff; background:#27ae60; cursor:pointer;'>Appliquer la calibration</button>
                            <button id='btnProfilerDownload' style='flex:1; padding:10px; font-size:13px; border:none; border-radius:6px; color:#fff; background:#3498db; cursor:pointer;'>Telecharger le profil</button>
                        </div>
                    </div>
                </div>

                <div class='right-panel'>
                    <div class='driving-mode'>
                        <h3>Contrôle du Zumi (D-pad + WASD)</h3>
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
                            <button class="dpad-button dpad-center" data-direction="stop" id="dpadCenterBtn"></button>
                            <!-- DROITE -->
                            <button class="dpad-button dpad-right" data-direction="right">
                                <svg viewBox="0 0 100 100"><path d="M20 50 L80 50 M50 20 L80 50 L50 80"></path></svg>
                            </button>
                            <!-- BAS -->
                            <button class="dpad-button dpad-down" data-direction="reverse">
                                <svg viewBox="0 0 100 100"><path d="M50 80 L50 20 M20 50 L50 80 L80 50"></path></svg>
                            </button>
                        </div>

                        <!-- Indicateur visuel WASD -->
                        <div class='wasd-indicator'>
                            <div class='wasd-grid'>
                                <div class='wasd-key wasd-w' id='wasdW'>W</div>
                                <div class='wasd-key wasd-a' id='wasdA'>A</div>
                                <div class='wasd-key wasd-s' id='wasdS'>S</div>
                                <div class='wasd-key wasd-d' id='wasdD'>D</div>
                            </div>
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

            // Note: La résolution est gérée automatiquement côté serveur:
            // - 'passive' (320x240) quand un contrôleur est actif
            // - 'stream' (640x480) quand aucun contrôleur n'est actif

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

    // Modes cycliques: 0=all, 1=line only (haar killé), 2=haar only (line killé)
    var _featureKillMode = 0;
    var _featureKillModes = [
        { groups: [],               label: 'Passif: tout actif',      cls: '' },
        { groups: ['haar'],         label: 'Passif: ligne seulement', cls: 'active' },
        { groups: ['line_camera'],  label: 'Passif: HAAR seulement',  cls: 'active' }
    ];

    function toggleFeatureKill() {
        _featureKillMode = (_featureKillMode + 1) % 3;
        var mode = _featureKillModes[_featureKillMode];
        var btn = document.getElementById('featureKillBtn');
        fetch('/sampling/feature_kill', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({groups: mode.groups})
        }).then(function(r) { return r.json(); }).then(function() {
            btn.className = 'toggle-btn' + (mode.cls ? ' ' + mode.cls : '');
            btn.style.cssText = 'flex:1; font-size:12px; padding:6px 8px;';
            btn.textContent = mode.label;
        });
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
                        // Activer l'overlay FSM seulement si circuit_fsm est sélectionné
                        var overlayEnabled = (controllerName === 'circuit_fsm' || controllerName === 'ml_controller' || controllerName === 'manual_controller');
                        fetch('/set_fsm_overlay', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ enabled: overlayEnabled })
                        }).catch(function(e) { console.error('set_fsm_overlay error:', e); });
                    }
                })
                .catch(function(e) { console.error('toggleController start error:', e); });
        } else {
            fetch('/controller/stop', { method: 'POST' })
                .then(function() {
                    btn.classList.remove('active');
                    btn.textContent = '▶ Activer le contrôleur';
                    // Toujours désactiver l'overlay FSM à l'arrêt du contrôleur
                    fetch('/set_fsm_overlay', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enabled: false })
                    }).catch(function(e) { console.error('set_fsm_overlay error:', e); });
                })
                .catch(function(e) { console.error('toggleController stop error:', e); });
        }
    }

    function toggleMLDebug() {
        fetch('/controller/debug/toggle', { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var btn = document.getElementById('mlDebugBtn');
                if (data.debug) {
                    btn.classList.add('active');
                    btn.textContent = 'ML Debug: ON';
                } else {
                    btn.classList.remove('active');
                    btn.textContent = 'ML Debug: OFF';
                }
            })
            .catch(function(e) { console.error('toggleMLDebug error:', e); });
    }

    // ================================================================
    // Panneau de réglages adaptatif selon le contrôleur sélectionné
    // ================================================================

    // Définition des paramètres UI par contrôleur
    var CONTROLLER_PARAMS = {
        'manual_controller': {
            title: 'Réglages manuels',
            endpoint: '/manual/settings',
            params: [
                {key: 'drive_speed', label: 'Vitesse avant', min: 0, max: 60, step: 1, type: 'int'},
                {key: 'turn_speed', label: 'Vitesse rotation', min: 0, max: 60, step: 1, type: 'int'},
                {key: 'steering_ratio', label: 'Ratio virage arc', min: 0, max: 1, step: 0.05, type: 'float'},
                {key: 'heading_kp', label: 'PID cap Kp', min: 0, max: 5, step: 0.1, type: 'float'},
                {key: 'heading_max_correction', label: 'Correction cap max', min: 0, max: 30, step: 1, type: 'int'},
                {key: 'white_threshold', label: 'Seuil blanc (vision)', min: 100, max: 220, step: 5, type: 'int', source: 'line_detector'}
            ]
        },
        'pid_ir': {
            title: 'Réglages PID IR',
            endpoint: '/controller/params',
            params: [
                {key: 'base_speed', label: 'Vitesse de base', min: 0, max: 50, step: 1, type: 'int', input: 'number'},
                {key: 'kp', label: 'Kp (proportionnel)', min: -1, max: 1, step: 0.001, type: 'float', input: 'number'},
                {key: 'ki', label: 'Ki (intégral)', min: -0.1, max: 0.1, step: 0.0001, type: 'float', input: 'number'},
                {key: 'kd', label: 'Kd (dérivé)', min: -2, max: 2, step: 0.001, type: 'float', input: 'number'},
                {key: 'max_correction', label: 'Correction max', min: 0, max: 50, step: 1, type: 'int', input: 'number'},
                {key: 'line_lost_threshold', label: 'Seuil perte ligne (IR_sum)', min: 0, max: 255, step: 1, type: 'int', input: 'number'},
                {key: 'ir_offset', label: 'Offset IR (R-L)', min: -50, max: 50, step: 0.1, type: 'float', input: 'number'},
                {key: 'calibration_samples', label: 'Échantillons calibration', min: 5, max: 50, step: 1, type: 'int', input: 'number'},
                {key: 'gap_threshold', label: 'Seuil trou (IR_sum)', min: 150, max: 230, step: 1, type: 'float', input: 'number'},
                {key: 'heading_kp', label: 'Heading Kp (cap gyro)', min: 0, max: 10, step: 0.1, type: 'float', input: 'number'},
                {key: 'heading_max_correction', label: 'Heading correction max', min: 0, max: 30, step: 1, type: 'float', input: 'number'}
            ]
        },
        'circuit_fsm': {
            title: 'Réglages Circuit FSM',
            endpoint: '/controller/params',
            sections: [
                {
                    label: '📷 Détecteur de ligne (Vision)',
                    params: [
                        {key: 'white_threshold', label: 'Seuil blanc (0-255)', min: 0, max: 255, step: 1, type: 'int', input: 'number', source: 'line_detector'},
                        {key: 'min_area', label: 'Aire min pointillé (px)', min: 1, max: 500, step: 1, type: 'int', input: 'number', source: 'line_detector'},
                        {key: 'offset_ratio', label: 'ROI offset ratio (Début zone centre Y)', min: 0, max: 1, step: 0.05, type: 'float', input: 'number', source: 'line_detector'}
                    ]
                },
                {
                    label: '📐 Zone CENTRE (base)',
                    params: [
                        {key: 'center_zone_width_ratio', label: 'Largeur zone centre (ratio)', min: 0.1, max: 1, step: 0.05, type: 'float', input: 'number', source: 'line_detector'}
                    ]
                },
                {
                    label: '📏 Zone AVANT (alignement)',
                    params: [
                        {key: 'front_zone_x_ratio', label: 'Position X centre (ratio)', min: 0.1, max: 0.9, step: 0.05, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'front_zone_y_start', label: 'Début Y (ratio, 0=haut)', min: 0.1, max: 0.9, step: 0.05, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'front_zone_y_end', label: 'Fin Y (ratio)', min: 0.2, max: 0.95, step: 0.05, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'front_zone_width_ratio', label: 'Largeur (ratio)', min: 0.02, max: 0.3, step: 0.01, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'front_min_dashes', label: 'Min pointillés pour confirmer', min: 1, max: 10, step: 1, type: 'int', input: 'number', source: 'line_detector'}
                    ]
                },
                {
                    label: '↗️ Zones COINS (virages)',
                    params: [
                        {key: 'corner_zone_width_ratio', label: 'Largeur chaque coin (ratio)', min: 0.05, max: 0.5, step: 0.02, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'corner_zone_height_ratio', label: 'Hauteur chaque coin (ratio)', min: 0.05, max: 0.5, step: 0.02, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'corner_zone_y_start', label: 'Début Y coins (ratio)', min: 0.1, max: 0.8, step: 0.05, type: 'float', input: 'number', source: 'line_detector'},
                        {key: 'corner_slowdown_factor', label: 'Facteur ralentissement virage (0-1)', min: 0.1, max: 1, step: 0.05, type: 'float', input: 'number'},
                        {key: 'turn_min_area', label: 'Aire min virage (px²)', min: 100, max: 5000, step: 50, type: 'int', input: 'number'}
                    ]
                },
                {
                    label: '🎯 Correction PID',
                    params: [
                        {key: 'base_speed', label: 'Vitesse de base', min: 0, max: 50, step: 1, type: 'int', input: 'number'},
                        {key: 'kp', label: 'Kp (proportionnel)', min: -1, max: 1, step: 0.01, type: 'float', input: 'number'},
                        {key: 'ki', label: 'Ki (intégral)', min: -1, max: 1, step: 0.01, type: 'float', input: 'number'},
                        {key: 'kd', label: 'Kd (dérivé)', min: -2, max: 2, step: 0.01, type: 'float', input: 'number'},
                        {key: 'max_correction', label: 'Correction max', min: 0, max: 50, step: 1, type: 'int', input: 'number'},
                        {key: 'turn_threshold', label: 'Seuil rotation (px)', min: 0, max: 200, step: 5, type: 'int', input: 'number'},
                        {key: 'turn_angle_scale', label: 'Facteur angle rotation (°/px)', min: 0.01, max: 2, step: 0.01, type: 'float', input: 'number'},
                        {key: 'max_turn_angle', label: 'Angle rotation max (°)', min: 1, max: 90, step: 1, type: 'float', input: 'number'}
                    ]
                },
                {
                    label: '⏱ Timing FSM',
                    params: [
                        {key: 'line_lost_timeout', label: 'Timeout perte ligne (s)', min: 0.1, max: 5, step: 0.1, type: 'float', input: 'number'},
                        {key: 'search_timeout', label: 'Timeout recherche (s)', min: 1, max: 30, step: 1, type: 'float', input: 'number'},
                        {key: 'search_spin_speed', label: 'Vitesse pivot recherche', min: 1, max: 20, step: 1, type: 'int', input: 'number'},
                        {key: 'step_duration', label: 'Durée pas (s)', min: 0.05, max: 2, step: 0.05, type: 'float', input: 'number'},
                        {key: 'pause_duration', label: 'Durée pause capture (s)', min: 0.05, max: 2, step: 0.05, type: 'float', input: 'number'}
                    ]
                },
                {
                    label: '🔄 Manœuvre aveugle',
                    params: [
                        {key: 'maneuver_forward_cm', label: 'Distance avance (cm)', min: 0, max: 50, step: 1, type: 'float', input: 'number'},
                        {key: 'maneuver_turn_angle', label: 'Angle virage (°)', min: -180, max: 180, step: 5, type: 'float', input: 'number'},
                        {key: 'forward_speed', label: 'Vitesse avance aveugle', min: 1, max: 50, step: 1, type: 'int', input: 'number'},
                        {key: 'cm_per_second', label: 'Calibration cm/s', min: 1, max: 50, step: 0.5, type: 'float', input: 'number'}
                    ]
                },
                {
                    label: '👣 Mode pas-à-pas',
                    params: [
                        {key: 'step_by_step_mode', label: 'Activer mode pas-à-pas', min: 0, max: 1, step: 1, type: 'int', input: 'number'}
                    ],
                    extra_html: '<button id="stepNextBtn" class="step-next-btn" onclick="requestNextStep()" style="margin-top:8px; width:100%; padding:10px; font-size:16px; background:#4CAF50; color:white; border:none; border-radius:8px; cursor:pointer; display:none;">⏭️ Prochain pas</button>'
                }
            ]
        }
    };

    var settingsTimer = null;

    function toggleSettingsMenu() {
        var settingsCard = document.getElementById('settingsCard');
        var settingsToggleBtn = document.getElementById('settingsToggleBtn');

        if (settingsCard.classList.contains('hidden')) {
            settingsCard.classList.remove('hidden');
            settingsToggleBtn.textContent = '⬆️ Masquer réglages';
            loadControllerSettings();
        } else {
            settingsCard.classList.add('hidden');
            settingsToggleBtn.textContent = '⚙️ Réglages';
        }
    }

    function getSelectedController() {
        var select = document.getElementById('controllerSelect');
        return select ? select.value : 'manual_controller';
    }

    function loadControllerSettings() {
        var ctrlName = getSelectedController();
        var config = CONTROLLER_PARAMS[ctrlName];
        var container = document.getElementById('settingsContent');
        var titleEl = document.getElementById('settingsTitle');

        if (!config) {
            // Contrôleur sans config UI définie : charger les params génériques
            titleEl.textContent = 'Réglages - ' + ctrlName;
            loadGenericParams(ctrlName, container);
            return;
        }

        titleEl.textContent = config.title;

        if (ctrlName === 'manual_controller') {
            loadManualSettings(container, config);
        } else {
            loadControllerParamsFromAPI(ctrlName, container, config);
        }
    }

    function loadManualSettings(container, config) {
        // Fusionner les valeurs du controleur manuel et du line_detector
        // (certains params comme white_threshold viennent du line_detector).
        var needsLineDetector = config.params.some(function(p) { return p.source === 'line_detector'; });

        var manualPromise = fetch('/manual/settings').then(function(r) { return r.json(); });
        var linePromise = needsLineDetector
            ? fetch('/line_detector/get_params').then(function(r) { return r.json(); }).catch(function() { return {}; })
            : Promise.resolve({});

        Promise.all([manualPromise, linePromise])
            .then(function(results) {
                var merged = {};
                Object.keys(results[0]).forEach(function(k) { merged[k] = results[0][k]; });
                Object.keys(results[1]).forEach(function(k) { merged[k] = results[1][k]; });
                renderParamSliders(container, config.params, merged);
            })
            .catch(function(e) { console.error('load settings error:', e); });
    }

    function loadControllerParamsFromAPI(ctrlName, container, config) {
        fetch('/controller/params?name=' + ctrlName)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var params = data.params || data;
                // Fusionner les params du LineDetector si disponibles
                var lineParams = data.line_detector_params || {};
                var mergedValues = {};
                Object.keys(params).forEach(function(k) { mergedValues[k] = params[k]; });
                Object.keys(lineParams).forEach(function(k) { mergedValues[k] = lineParams[k]; });

                if (config.sections) {
                    renderSectionedParams(container, config.sections, mergedValues);
                } else {
                    renderParamSliders(container, config.params, mergedValues);
                }
            })
            .catch(function(e) { console.error('load controller params error:', e); });
    }

    function loadGenericParams(ctrlName, container) {
        fetch('/controller/params?name=' + ctrlName)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var params = data.params || {};
                var paramDefs = [];
                Object.keys(params).forEach(function(key) {
                    var val = params[key];
                    if (typeof val === 'number') {
                        var isFloat = !Number.isInteger(val);
                        paramDefs.push({
                            key: key, label: key,
                            min: isFloat ? -10 : -100,
                            max: isFloat ? 10 : 100,
                            step: isFloat ? 0.01 : 1,
                            type: isFloat ? 'float' : 'int'
                        });
                    }
                });
                renderParamSliders(container, paramDefs, params);
            })
            .catch(function(e) {
                container.innerHTML = '<p style="color:#999;">Aucun paramètre disponible</p>';
            });
    }

    function renderSectionedParams(container, sections, values) {
        var html = '';
        sections.forEach(function(section) {
            html += '<div style="margin-top:12px; padding:8px 0; border-top:1px solid #eee;">';
            html += '<div style="font-weight:bold; font-size:0.95rem; margin-bottom:8px; color:#555;">' + section.label + '</div>';
            section.params.forEach(function(p) {
                var val = values[p.key];
                if (val === undefined || val === null) val = p.min;
                html += '<div class="param-row">';
                html += '<label for="param_' + p.key + '">' + p.label + '</label>';
                if (p.input === 'number') {
                    html += '<input id="param_' + p.key + '" type="number"';
                    html += ' min="' + p.min + '" max="' + p.max + '" step="' + p.step + '"';
                    html += ' value="' + val + '"';
                    html += ' style="flex:2; padding:6px 8px; border-radius:8px; border:2px solid #B5FFFC; font-weight:bold; font-size:0.95rem; text-align:center;">';
                } else {
                    var displayVal = p.type === 'float' ? parseFloat(val).toFixed(3) : parseInt(val);
                    html += '<input id="param_' + p.key + '" type="range"';
                    html += ' min="' + p.min + '" max="' + p.max + '" step="' + p.step + '"';
                    html += ' value="' + val + '">';
                    html += '<span class="param-value" id="param_' + p.key + '_val">' + displayVal + '</span>';
                }
                html += '</div>';
            });
            // Extra HTML (ex: bouton pas-à-pas)
            if (section.extra_html) {
                html += section.extra_html;
            }
            html += '</div>';
        });
        container.innerHTML = html;

        // Bind live updates pour les sliders
        sections.forEach(function(section) {
            section.params.forEach(function(p) {
                if (p.input === 'number') return;
                var input = document.getElementById('param_' + p.key);
                var valEl = document.getElementById('param_' + p.key + '_val');
                if (!input || !valEl) return;
                input.addEventListener('input', function() {
                    valEl.textContent = p.type === 'float'
                        ? parseFloat(input.value).toFixed(3)
                        : parseInt(input.value);
                });
            });
        });

        // Afficher/masquer le bouton pas-à-pas selon la valeur
        var stepBtn = document.getElementById('stepNextBtn');
        var stepInput = document.getElementById('param_step_by_step_mode');
        if (stepBtn && stepInput) {
            stepBtn.style.display = parseInt(stepInput.value) ? 'block' : 'none';
            stepInput.addEventListener('change', function() {
                stepBtn.style.display = parseInt(stepInput.value) ? 'block' : 'none';
            });
        }

        // Auto-apply: chaque modification déclenche applySettings avec debounce
        _bindAutoApply(sections);
    }

    var _autoApplyTimer = null;
    var _lastAppliedValues = {};

    function _debouncedApply() {
        if (_autoApplyTimer) clearTimeout(_autoApplyTimer);
        _autoApplyTimer = setTimeout(function() {
            console.log('[AutoApply] Envoi des paramètres…');
            applySettings();
        }, 250);
    }

    function _bindAutoApply(sections) {
        // Bind sur les sections (circuit_fsm)
        if (sections) {
            sections.forEach(function(section) {
                section.params.forEach(function(p) {
                    var input = document.getElementById('param_' + p.key);
                    if (!input) return;
                    input.addEventListener('input', _debouncedApply);
                    input.addEventListener('change', _debouncedApply);
                    // Pour type="number": forcer le change sur blur
                    input.addEventListener('blur', _debouncedApply);
                });
            });
        }
    }

    function _bindAutoApplyFlat(paramDefs) {
        // Bind sur les params plats (manual_controller, pid_ir)
        paramDefs.forEach(function(p) {
            var input = document.getElementById('param_' + p.key);
            if (!input) return;
            input.addEventListener('input', _debouncedApply);
            input.addEventListener('change', _debouncedApply);
            input.addEventListener('blur', _debouncedApply);
        });
    }

    function renderParamSliders(container, paramDefs, values) {
        var html = '';
        paramDefs.forEach(function(p) {
            var val = values[p.key];
            if (val === undefined || val === null) val = p.min;
            html += '<div class="param-row">';
            html += '<label for="param_' + p.key + '">' + p.label + '</label>';
            if (p.input === 'number') {
                // Champ numérique direct (précision fine pour PID)
                html += '<input id="param_' + p.key + '" type="number"';
                html += ' min="' + p.min + '" max="' + p.max + '" step="' + p.step + '"';
                html += ' value="' + val + '"';
                html += ' style="flex:2; padding:6px 8px; border-radius:8px; border:2px solid #B5FFFC; font-weight:bold; font-size:0.95rem; text-align:center;">';
            } else {
                // Slider classique
                var displayVal = p.type === 'float' ? parseFloat(val).toFixed(3) : parseInt(val);
                html += '<input id="param_' + p.key + '" type="range"';
                html += ' min="' + p.min + '" max="' + p.max + '" step="' + p.step + '"';
                html += ' value="' + val + '">';
                html += '<span class="param-value" id="param_' + p.key + '_val">' + displayVal + '</span>';
            }
            html += '</div>';
        });
        container.innerHTML = html;

        // Bind live updates (sliders only)
        paramDefs.forEach(function(p) {
            if (p.input === 'number') return;
            var input = document.getElementById('param_' + p.key);
            var valEl = document.getElementById('param_' + p.key + '_val');
            if (!input || !valEl) return;
            input.addEventListener('input', function() {
                valEl.textContent = p.type === 'float'
                    ? parseFloat(input.value).toFixed(3)
                    : parseInt(input.value);
            });
        });

        // Auto-apply sur tous les inputs
        _bindAutoApplyFlat(paramDefs);
    }

    function applySettings() {
        var ctrlName = getSelectedController();
        var config = CONTROLLER_PARAMS[ctrlName];

        if (ctrlName === 'manual_controller' && config) {
            // Separer les params entre /manual/settings et /line_detector/update_params
            var manualPayload = {};
            var linePayload = {};
            config.params.forEach(function(p) {
                var input = document.getElementById('param_' + p.key);
                if (!input) return;
                if (p.source === 'line_detector') {
                    linePayload[p.key] = parseFloat(input.value);
                } else {
                    manualPayload[p.key] = parseFloat(input.value);
                }
            });

            // POST manual settings
            if (Object.keys(manualPayload).length > 0) {
                fetch('/manual/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(manualPayload)
                }).then(function(r) {
                    if (!r.ok) console.error('[ApplySettings] manual error HTTP', r.status);
                    return r.json();
                }).then(function(data) {
                    console.log('[ApplySettings] manual OK:', data);
                }).catch(function(e) { console.error('[ApplySettings] manual fetch error:', e); });
            }

            // POST line_detector params (white_threshold, etc.)
            if (Object.keys(linePayload).length > 0) {
                fetch('/line_detector/update_params', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(linePayload)
                }).then(function(r) {
                    if (!r.ok) console.error('[ApplySettings] line_detector error HTTP', r.status);
                    return r.json();
                }).then(function(data) {
                    console.log('[ApplySettings] line_detector OK:', data);
                }).catch(function(e) { console.error('[ApplySettings] line_detector fetch error:', e); });
            }
        } else {
            // Contrôleur générique via /controller/params
            var payload = {name: ctrlName};

            if (config && config.sections) {
                // Format sectionné (circuit_fsm)
                config.sections.forEach(function(section) {
                    section.params.forEach(function(p) {
                        var input = document.getElementById('param_' + p.key);
                        if (input) payload[p.key] = parseFloat(input.value);
                    });
                });
            } else if (config && config.params) {
                config.params.forEach(function(p) {
                    var input = document.getElementById('param_' + p.key);
                    if (input) payload[p.key] = parseFloat(input.value);
                });
            } else {
                // Params génériques : lire tous les inputs param_*
                var inputs = document.querySelectorAll('#settingsContent input[type="range"], #settingsContent input[type="number"]');
                Array.prototype.forEach.call(inputs, function(input) {
                    var key = input.id.replace('param_', '');
                    payload[key] = parseFloat(input.value);
                });
            }

            console.log('[ApplySettings] POST payload:', JSON.stringify(payload));
            fetch('/controller/params', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(function(r) {
                if (!r.ok) console.error('[ApplySettings] controller error HTTP', r.status);
                return r.json();
            }).then(function(data) {
                console.log('[ApplySettings] controller response:', data);
                // Re-synchroniser les inputs avec les valeurs retournées par le serveur
                if (data) {
                    var serverParams = data.params || {};
                    var lineParams = data.line_detector_params || {};
                    var merged = {};
                    Object.keys(serverParams).forEach(function(k) { merged[k] = serverParams[k]; });
                    Object.keys(lineParams).forEach(function(k) { merged[k] = lineParams[k]; });
                    Object.keys(merged).forEach(function(k) {
                        var input = document.getElementById('param_' + k);
                        if (input && merged[k] !== undefined) {
                            input.value = merged[k];
                            // Mettre à jour aussi le label de valeur pour les sliders
                            var valEl = document.getElementById('param_' + k + '_val');
                            if (valEl) valEl.textContent = merged[k];
                        }
                    });
                }
            }).catch(function(e) { console.error('[ApplySettings] controller fetch error:', e); });
        }
    }

    function requestNextStep() {
        fetch('/controller/step', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: 'circuit_fsm'})
        }).then(function(r) { return r.json(); })
          .then(function(data) {
              console.log('Step response:', data);
          })
          .catch(function(e) { console.error('step error:', e); });
    }

    // --- CONTRÔLE WASD (clavier) ---
    var pressedKeys = {};
    var wasdInterval = null;

    function updateWASDIndicator() {
        var keys = ['w', 'a', 's', 'd'];
        var ids = ['wasdW', 'wasdA', 'wasdS', 'wasdD'];
        for (var i = 0; i < keys.length; i++) {
            var el = document.getElementById(ids[i]);
            if (el) {
                if (pressedKeys[keys[i]]) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            }
        }
    }

    function sendWASDState() {
        fetch('/zumi/move', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({keys: Object.keys(pressedKeys)})
        }).catch(function(e) { console.error('WASD fetch error:', e); });
    }

    function onKeyDown(e) {
        // Ignorer si un input/textarea/select est focus
        var tag = document.activeElement ? document.activeElement.tagName : '';
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        var key = e.key.toLowerCase();
        if ('wasd'.indexOf(key) < 0) return;
        e.preventDefault();
        if (pressedKeys[key]) return;

        // Couper le D-pad si actif
        if (isMoving) stopMove();

        pressedKeys[key] = true;
        updateWASDIndicator();
        sendWASDState();
        if (!wasdInterval) {
            wasdInterval = setInterval(sendWASDState, 80);
        }
    }

    function onKeyUp(e) {
        var key = e.key.toLowerCase();
        if (!pressedKeys[key]) return;
        delete pressedKeys[key];
        updateWASDIndicator();
        if (Object.keys(pressedKeys).length === 0) {
            if (wasdInterval) {
                clearInterval(wasdInterval);
                wasdInterval = null;
            }
            fetch('/zumi/stop').catch(function(e) { console.error('WASD stop error:', e); });
        } else {
            sendWASDState();
        }
    }

    function stopWASD() {
        pressedKeys = {};
        updateWASDIndicator();
        if (wasdInterval) {
            clearInterval(wasdInterval);
            wasdInterval = null;
        }
    }

    // --- RESET CAPTEURS ---
    function postReset(url, btn) {
        var originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = originalText + ' ...';
        fetch(url, {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(data) {
                btn.disabled = false;
                btn.textContent = originalText;
                if (data.error) alert('Erreur: ' + data.error);
            })
            .catch(function(e) {
                btn.disabled = false;
                btn.textContent = originalText;
                alert('Erreur: ' + e.message);
            });
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
        // Couper le WASD si actif
        if (wasdInterval) stopWASD();
        isMoving = true;
                
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
        
        // 2. Démarrer un intervalle qui 'nourrit' le watchdog ~12x par seconde (80ms)
        //    Réduit de 250ms à 80ms pour une meilleure fluidité du contrôle manuel
        moveInterval = setInterval(sendMoveCommand, 80);
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

        var featureKillBtn = document.getElementById('featureKillBtn');
        if (featureKillBtn) featureKillBtn.addEventListener('click', toggleFeatureKill);
        
        // Controller toggle
        var ctrlBtn = document.getElementById('controllerToggleBtn');
        if (ctrlBtn) ctrlBtn.addEventListener('click', toggleController);

        // ML Debug toggle
        var mlDebugBtn = document.getElementById('mlDebugBtn');
        if (mlDebugBtn) mlDebugBtn.addEventListener('click', toggleMLDebug);

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

        var applySettingsBtn = document.getElementById('applySettingsBtn');
        if (applySettingsBtn) applySettingsBtn.addEventListener('click', applySettings);

        // Settings menu toggle
        var settingsToggleBtn = document.getElementById('settingsToggleBtn');
        if (settingsToggleBtn) settingsToggleBtn.addEventListener('click', toggleSettingsMenu);

        var settingsCloseBtn = document.getElementById('settingsCloseBtn');
        if (settingsCloseBtn) settingsCloseBtn.addEventListener('click', toggleSettingsMenu);

        // Recharger les réglages quand on change de contrôleur
        var controllerSelect = document.getElementById('controllerSelect');
        if (controllerSelect) {
            controllerSelect.addEventListener('change', function() {
                var card = document.getElementById('settingsCard');
                if (card && !card.classList.contains('hidden')) {
                    loadControllerSettings();
                }
            });
        }
        
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

        // --- WASD keyboard controls ---
        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('keyup', onKeyUp);
        // Nettoyer WASD si la fenêtre perd le focus (évite les touches bloquées)
        window.addEventListener('blur', function() {
            if (Object.keys(pressedKeys).length > 0) {
                stopWASD();
                fetch('/zumi/stop').catch(function() {});
            }
        });

        // --- Reset capteurs ---
        var resetToggleBtn = document.getElementById('resetToggleBtn');
        if (resetToggleBtn) {
            resetToggleBtn.addEventListener('click', function() {
                var card = document.getElementById('resetCard');
                if (card) card.classList.toggle('hidden');
            });
        }
        var resetCloseBtn = document.getElementById('resetCloseBtn');
        if (resetCloseBtn) {
            resetCloseBtn.addEventListener('click', function() {
                var card = document.getElementById('resetCard');
                if (card) card.classList.add('hidden');
            });
        }
        var btnCalibrateAll = document.getElementById('btnCalibrateAll');
        if (btnCalibrateAll) btnCalibrateAll.addEventListener('click', function() { postReset('/robot/calibrate', this); });
        var btnResetDrive = document.getElementById('btnResetDrive');
        if (btnResetDrive) btnResetDrive.addEventListener('click', function() { postReset('/robot/reset_drive', this); });
        var btnResetGyro = document.getElementById('btnResetGyro');
        if (btnResetGyro) btnResetGyro.addEventListener('click', function() { postReset('/robot/reset_gyro', this); });
        var btnResetPID = document.getElementById('btnResetPID');
        if (btnResetPID) btnResetPID.addEventListener('click', function() { postReset('/robot/reset_pid', this); });
        var btnCalibrateIR = document.getElementById('btnCalibrateIR');
        if (btnCalibrateIR) btnCalibrateIR.addEventListener('click', function() { postReset('/controller/calibrate_ir', this); });

        // === Sensor Profiler (un seul bouton contextuel) ===
        var profilerPolling = null;
        var profilerState = 'idle';
        var profilerPhaseType = 'static';

        var btnAction = document.getElementById('btnProfilerAction');
        btnAction.addEventListener('click', function() {
            if (profilerState === 'idle') {
                // Démarrer le profiling
                var robotId = document.getElementById('profilerRobotId').value;
                setBtnStyle('busy', 'Démarrage...');
                fetch('/robot/sensor_profile/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({robot_id: robotId})
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.status === 'started') {
                        profilerState = 'ready';
                        startProfilerPolling();
                        updateButtonForPhase();
                    }
                });
            }
            else if (profilerState === 'ready') {
                // Exécuter la phase courante
                profilerState = 'executing';

                if (profilerPhaseType === 'static') {
                    setBtnStyle('busy', 'Enregistrement...');
                    fetch('/robot/sensor_profile/record', {method: 'POST'})
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.error) {
                            setBtnStyle('ready', 'Erreur — Réessayer');
                            profilerState = 'ready';
                        } else {
                            profilerState = 'done';
                            showSamples(data.n_samples || 0);
                            setBtnStyle('ready', 'Suivant');
                        }
                    });
                }
                else if (profilerPhaseType.indexOf('auto_') === 0) {
                    setBtnStyle('busy', 'Manoeuvre en cours...');
                    fetch('/robot/sensor_profile/run', {method: 'POST'})
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.error) {
                            setBtnStyle('ready', 'Erreur — Réessayer');
                            profilerState = 'ready';
                            return;
                        }
                        // Poll pour détecter la fin de la manoeuvre
                        var pollTimer = setInterval(function() {
                            fetch('/robot/sensor_profile/run_status')
                            .then(function(r) { return r.json(); })
                            .then(function(rs) {
                                if (!rs.running) {
                                    clearInterval(pollTimer);
                                    profilerState = 'done';
                                    showSamples(rs.n_samples || 0);
                                    setBtnStyle('ready', 'Suivant');
                                }
                            });
                        }, 500);
                    });
                }
                else if (profilerPhaseType === 'manual_sampling') {
                    setBtnStyle('busy', 'Enregistrement... Pilotez avec WASD');
                    fetch('/robot/sensor_profile/manual_start', {method: 'POST'})
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.error) {
                            setBtnStyle('ready', 'Erreur — Réessayer');
                            profilerState = 'ready';
                        } else {
                            profilerState = 'manual_recording';
                            setBtnStyle('ready', 'Arrêter enregistrement');
                        }
                    });
                }
            }
            else if (profilerState === 'manual_recording') {
                // Arrêter l'enregistrement manuel
                setBtnStyle('busy', 'Validation...');
                fetch('/robot/sensor_profile/manual_stop', {method: 'POST'})
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    showSamples(data.n_samples || 0);
                    if (data.quality === 'valid') {
                        if (data.phase_complete) {
                            profilerState = 'done';
                            setBtnStyle('ready', 'Runs valides OK — Suivant');
                        } else {
                            profilerState = 'ready';
                            setBtnStyle('ready', 'Run valide (' + data.valid_count + '/' + data.min_valid + ') — Encore');
                        }
                    } else {
                        profilerState = 'ready';
                        setBtnStyle('ready', 'Rejeté: ' + (data.reason || '?') + ' — Réessayer');
                    }
                });
            }
            else if (profilerState === 'done') {
                // Passer à la phase suivante
                setBtnStyle('busy', 'Chargement...');
                fetch('/robot/sensor_profile/next', {method: 'POST'})
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.status === 'completed') {
                        profilerState = 'completed';
                        stopProfilerPolling();
                        document.getElementById('profilerProgress').style.width = '100%';
                        // Charger le résumé
                        fetch('/robot/sensor_profile/summary')
                        .then(function(r) { return r.json(); })
                        .then(function(s) {
                            var html = '<div style="color:#2ecc71;font-size:16px;font-weight:bold;margin-bottom:8px;">Profiling terminé!</div>';
                            html += '<div style="color:#fff;font-size:13px;">Robot: ' + (s.robot_id || '?') + ' | Phases: ' + (s.n_phases_completed || 0) + '/18 | Total: <b>' + (s.total_samples || 0) + ' echantillons</b></div>';
                            if (s.ir_offsets) {
                                html += '<div style="color:#3498db;font-size:12px;margin-top:6px;">IR offsets: bottom=' + s.ir_offsets.bottom + ', front=' + s.ir_offsets.front + ', back=' + s.ir_offsets.back + '</div>';
                            }
                            if (s.thresholds) {
                                html += '<div style="color:#e67e22;font-size:12px;">Seuils: gap=' + (s.thresholds.gap_threshold || '?') + ', off_road=' + (s.thresholds.off_road_threshold || '?') + '</div>';
                            }
                            if (s.motor_asymmetry) {
                                var speeds = Object.keys(s.motor_asymmetry);
                                html += '<div style="color:#9b59b6;font-size:12px;">Asymetrie moteur: ';
                                speeds.forEach(function(k) { html += k + '=' + s.motor_asymmetry[k].drift_deg_per_s + ' deg/s '; });
                                html += '</div>';
                            }
                            document.getElementById('profilerStatus').innerHTML = html;
                        });
                        // Afficher les deux boutons
                        hideSamples();
                        btnAction.style.display = 'none';
                        document.getElementById('profilerEndButtons').style.display = 'flex';
                    } else {
                        profilerState = 'ready';
                        hideSamples();
                        updateButtonForPhase();
                    }
                });
            }
        });

        function setBtnStyle(mode, text) {
            btnAction.textContent = text;
            if (mode === 'ready') {
                btnAction.style.background = '#27ae60';
                btnAction.disabled = false;
            } else if (mode === 'busy') {
                btnAction.style.background = '#2980b9';
                btnAction.disabled = true;
            }
        }

        function showSamples(n) {
            var el = document.getElementById('profilerSamples');
            if (el) { el.textContent = n + ' échantillons enregistrés'; el.style.display = 'block'; }
        }

        function hideSamples() {
            var el = document.getElementById('profilerSamples');
            if (el) { el.style.display = 'none'; }
        }

        function updateButtonForPhase() {
            hideSamples();
            // Cacher les boutons de fin, montrer le bouton principal
            document.getElementById('profilerEndButtons').style.display = 'none';
            btnAction.style.display = 'block';
            if (profilerPhaseType === 'static') {
                setBtnStyle('ready', 'Robot en place — Enregistrer');
            } else if (profilerPhaseType.indexOf('auto_') === 0) {
                setBtnStyle('ready', 'Robot en place — Exécuter la manoeuvre');
            } else if (profilerPhaseType === 'manual_sampling') {
                setBtnStyle('ready', 'Commencer le pilotage manuel');
            }
        }

        // Boutons de fin
        document.getElementById('btnProfilerApply').addEventListener('click', function() {
            this.textContent = 'Application...';
            this.disabled = true;
            // Relancer la calibration IR avec les données du profil
            fetch('/controller/calibrate_ir', {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(data) {
                document.getElementById('btnProfilerApply').textContent = 'Calibration appliquee!';
                // Remettre le bouton principal
                setTimeout(function() {
                    document.getElementById('profilerEndButtons').style.display = 'none';
                    btnAction.style.display = 'block';
                    profilerState = 'idle';
                    setBtnStyle('ready', 'Demarrer le profiling');
                }, 2000);
            });
        });

        document.getElementById('btnProfilerDownload').addEventListener('click', function() {
            window.location.href = '/robot/sensor_profile/download';
        });

        function startProfilerPolling() {
            if (profilerPolling) clearInterval(profilerPolling);
            profilerPolling = setInterval(updateProfilerStatus, 500);
            updateProfilerStatus();
        }

        function stopProfilerPolling() {
            if (profilerPolling) { clearInterval(profilerPolling); profilerPolling = null; }
        }

        function updateProfilerStatus() {
            fetch('/robot/sensor_profile/status')
            .then(function(r) { return r.json(); })
            .then(function(s) {
                if (!s.active) return;

                profilerPhaseType = s.phase_type || 'static';

                var pct = Math.round((s.current_phase / s.total_phases) * 100);
                document.getElementById('profilerProgress').style.width = pct + '%';

                var groupColors = {A:'#3498db', B:'#e67e22', C:'#9b59b6', D:'#2ecc71'};
                var color = groupColors[s.phase_group] || '#e94560';

                var html = '<div style="color:' + color + ';font-size:14px;font-weight:bold;">Phase ' + s.current_phase + '/' + s.total_phases + ' [' + s.phase_group + ']</div>';
                html += '<div style="color:#fff;font-size:13px;margin-top:6px;">' + s.instruction + '</div>';
                html += '<div style="color:#888;font-size:11px;margin-top:4px;">' + s.description + '</div>';

                if (s.auto_running) {
                    html += '<div style="color:#f39c12;font-size:12px;margin-top:4px;">Manoeuvre en cours... (' + (s.auto_samples || 0) + ' samples)</div>';
                }

                if (s.phase_type === 'manual_sampling') {
                    var v = s.manual_valid_runs || 0;
                    var m = s.manual_min_runs || 3;
                    var t = s.manual_total_runs || 0;
                    html += '<div style="color:#3498db;font-size:13px;margin-top:6px;font-weight:bold;">Runs valides: ' + v + '/' + m;
                    if (t > v) html += ' (' + (t - v) + ' rejetés)';
                    html += '</div>';
                }

                document.getElementById('profilerStatus').innerHTML = html;

                // Mettre à jour le texte du bouton si on est en état ready
                if (profilerState === 'ready') {
                    updateButtonForPhase();
                }
            });
        }
    });

    // Exposer les fonctions au scope global (pour les onclick inline restants)
    window.navigateTo = navigateTo;
    window.toggleCamera = toggleCamera;
    window.toggleSampling = toggleSampling;
    window.downloadSampling = downloadSampling;
    window.toggleController = toggleController;
    window.toggleSettingsMenu = toggleSettingsMenu;
    window.startMove = startMove;
    window.stopMove = stopMove;
    window.stopWASD = stopWASD;
    window.applySettings = applySettings;
    window.loadControllerSettings = loadControllerSettings;
    window.postReset = postReset;

    </script>
    </body></html>
    """

    return html.replace("{title}", title)
