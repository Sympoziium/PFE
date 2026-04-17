#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_vision.py
# ------------------
# ce module defini un onglet de l'interface web dedie au fonctionnalitees du module de vision
# ------------------

def render_vision_tab(title: str = "Vision du Zumi") -> str:
    """Retourne une page HTML complete avec les widgets pour l'onglet de vision."""

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
        background: linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%);
        color: #333; display: flex; flex-direction: column;
        overflow-y: auto;
    }

    .container {
        display: flex; justify-content: center; align-items: flex-start;
        padding: 2vh; min-height: 96vh;
    }

    .tab-shell {
        background: rgba(247, 253, 255, 0.95);
        border-radius: 20px;
        padding: 2%;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        width: 92%; max-width: 1100px;
        min-height: fit-content; margin-bottom: 4vh;
        display: flex; flex-direction: column;
    }

    .tab-header {
        display: flex; align-items: center;
        margin-bottom: 2vh;
        padding-bottom: 1vh;
        border-bottom: 2px solid #e0f4ff;
    }

    .tab-title {
        font-size: 1.8rem; font-weight: bold; color: #5A99C7; margin: 0;
    }

    .tab-nav {
        display: flex; align-items: center;
        gap: 8px;
        margin-left: auto;
    }

    .tab-content {
        border: 3px dashed #B5FFFC;
        border-radius: 15px;
        padding: 3%;
        background: #FFFDF0;
        margin-bottom: 16px;
    }

    .tab-subtitle {
        font-size: 1.3rem; font-weight: bold; color: #666; margin-bottom: 15px; margin-top: 0;
    }

    .tab-text {
        font-size: 1.1rem; color: #444;
    }

    .primary-btn {
        background: #87C7F1; color: white; border: none;
        padding: 12px 20px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        transition: transform 0.2s, background 0.2s;
        box-shadow: 0 4px 0 #6BAED6;
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
        background: #FFB7D5; color: white; border: none;
        padding: 12px 24px; border-radius: 12px;
        cursor: pointer; font-weight: bold; font-size: 1rem;
        box-shadow: 0 4px 0 #E896B9;
        transition: transform 0.2s, background 0.2s;
    }

    .toggle-btn:hover { background: #FFA3C8; transform: translateY(-2px); }
    .toggle-btn:active { transform: translateY(2px); box-shadow: 0 2px 0 #E896B9; }

    .detector-btn {
        background: #A8E6CF; color: #2d6a4f; border: none;
        padding: 12px 20px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        box-shadow: 0 4px 0 #74C69D;
        transition: transform 0.2s, background 0.2s;
    }

    .detector-btn:hover { background: #95D9C0; transform: translateY(-2px); }
    .detector-btn:active { transform: translateY(2px); box-shadow: 0 2px 0 #74C69D; }

    .remoteDL-toggle-btn {
        color: white; border: none;
        padding: 12px 18px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        transition: transform 0.2s, background 0.2s;
    }

    .remoteDL-toggle-btn.off {
        background: #F4A0A0; color: #7a1f1f;
        box-shadow: 0 4px 0 #d97070;
    }
    .remoteDL-toggle-btn.off:hover { background: #ee8a8a; transform: translateY(-2px); }

    .remoteDL-toggle-btn.on {
        background: #A8E6CF; color: #2d6a4f;
        box-shadow: 0 4px 0 #74C69D;
    }
    .remoteDL-toggle-btn.on:hover { background: #95D9C0; transform: translateY(-2px); }

    .select-detector {
        padding: 10px 14px; border-radius: 12px;
        border: 2px solid #B5FFFC;
        background: #fff; font-size: 1rem;
        color: #444;
        box-shadow: 0 2px 0 #d0d0d0;
    }

    .tab-row {
        display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap;
    }

    .tab-btn-group {
        display: flex; flex-direction: column; align-items: stretch;
        gap: 10px;
        background: rgba(247, 253, 255, 0.8);
        border: 2px solid #B5FFFC;
        border-radius: 15px;
        padding: 16px;
    }

    .live-feed {
        display: none;
        width: 100%;
        margin-top: 20px;
        padding: 10px;
        background: white;
        border-radius: 20px;
        border: 4px solid #B5FFFC;
        text-align: center;
        box-sizing: border-box;
    }

    .live-feed img {
        display: block;
        margin: 10px auto 0;
        width: auto;
        height: auto;
        max-width: 100%;
        min-height: 280px;
        border-radius: 8px; 
        border: 4px solid #00BFFF; 
    }

    .stop-detect-panel {
        display: none;
        flex: 1;
        border: 3px dashed #B5FFFC;
        border-radius: 15px;
        padding: 16px;
        background: #FFFDF0;
    }

    .indicator-and-terminal {
        flex: 1; display: flex; flex-direction: column; gap: 10px; align-items: stretch;
    }

    .detect-indicator {
        border-radius: 12px; padding: 12px; text-align: center;
        font-weight: bold; color: #fff; font-size: 1rem;
        background: #ccc;
    }

    .detect-indicator.on  { background: #A8E6CF; color: #2d6a4f; box-shadow: 0 3px 0 #74C69D; }
    .detect-indicator.off { background: #F4A0A0; color: #7a1f1f; box-shadow: 0 3px 0 #d97070; }

    .log-terminal {
        background: #1a1a2e; color: #a8d8ea;
        font-family: 'Courier New', Consolas, monospace; font-size: 13px;
        border-radius: 12px; padding: 12px;
        min-height: 200px; max-height: 50vh;
        overflow-y: auto; overflow-x: auto;
        white-space: pre-wrap; word-wrap: break-word;
        border: 2px solid #B5FFFC;
    }

    .toast-container {
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        display: flex; flex-direction: column; gap: 8px;
    }

    .toast {
        padding: 12px 20px; border-radius: 12px;
        color: #fff; font-size: 14px; font-family: 'Segoe UI', Arial, sans-serif;
        box-shadow: 0 4px 0 rgba(0,0,0,0.15);
        opacity: 0; transform: translateX(80px);
        transition: opacity 0.3s, transform 0.3s;
        max-width: 380px; word-wrap: break-word;
        font-weight: bold;
    }

    .toast.show { opacity: 1; transform: translateX(0); }
    .toast.warning { background: #FFD166; color: #7a4f00; box-shadow: 0 4px 0 #e6b800; }
    .toast.error   { background: #F4A0A0; color: #7a1f1f; box-shadow: 0 4px 0 #d97070; }
    .toast.info    { background: #87C7F1; color: #1a3a5c; box-shadow: 0 4px 0 #6BAED6; }
    .toast.success { background: #A8E6CF; color: #2d6a4f; box-shadow: 0 4px 0 #74C69D; }

    /* --- Panneau paramètres détecteur de ligne --- */
    .line-params-panel {
        border: 2px solid #3498db;
        border-radius: 12px;
        padding: 14px;
        background: #f0f8ff;
        margin-top: 8px;
    }
    .line-params-panel .param-row {
        display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
    }
    .line-params-panel label {
        min-width: 140px; font-size: 14px;
    }
    .line-params-panel input[type='range'] {
        flex: 1; max-width: 200px; cursor: pointer;
    }
    .line-params-panel input[type='number'] {
        width: 64px; padding: 4px; border-radius: 6px; border: 1px solid #aaa; font-size: 14px;
    }

    </style>
    </head>
    <body>
    <div class='container'>
        <div class='tab-shell'>
            <div class='tab-header'>
                <h2 class='tab-title'>{title}</h2>
                <div class='tab-nav'>
                    <button class='primary-btn' data-path="/" onclick="navigateTo('/')">Accueil</button>
                    <button class='primary-btn' data-path="/vision" onclick="navigateTo('/vision')">Vision</button>
                    <button class='primary-btn' data-path="/onglet_control" onclick="navigateTo('/onglet_control')">Contrôle</button>
                    <button class='primary-btn' data-path="/pid" onclick="navigateTo('/pid')">PID</button>
                    <button class='primary-btn' onclick="fetch('/exit', {method:'POST'})">EXIT</button>
                </div>
            </div>

            <div class='tab-content'>
                <h3 class='tab-subtitle'>Capture image</h3>
                <div style='display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:12px;'>
                    <button class='toggle-btn' id='cameraToggleBtn'>🎥 Start Camera</button>
                    <button class='primary-btn' id='captureImageBtn'>📸 Capture Image</button>
                    <button class='remoteDL-toggle-btn off' id='toggleDownloadCapturedBtn' aria-pressed='false'> 💾 Off</button>
                    <select id='resolutionSelect' class='select-detector' title='Résolution caméra'>
                        <option value='160x128' selected>VGA 640×480</option>
                        <option value='176x144'>QCIF 176×144</option>
                        <option value='320x240'>QVGA 320×240</option>
                        <option value='640x480'>VGA 640×480</option>
                        <option value='1296x972'>HD 1296×972</option>
                    </select>
                </div>
                <div style='display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:10px;'>
                    <label class='tab-text' style='min-width:110px;'>FPS Livefeed :</label>
                    <input type='range' id='fpsSlider' min='1' max='60' value='30' style='width:160px; cursor:pointer;'>
                    <input type='number' id='fpsNumber' min='1' max='60' value='30' style='width:58px; padding:4px; border-radius:6px; border:1px solid #aaa; font-size:14px;'>
                    <span style='font-size:13px; color:#555;'>fps</span>
                </div>
                <div style='display:flex; flex-wrap:wrap; gap:8px; align-items:center;'>
                    <button class='remoteDL-toggle-btn off' id='togglePassiveDetectionBtn' aria-pressed='false'> Start Passive Detection</button>
                    <button class='remoteDL-toggle-btn off' id='toggleMiningBtn' aria-pressed='false'>⛏️ Mining Off</button>
                    <span id='miningBadge' style='display:none; background:#c9a0dc; color:#4a1a6a; padding:5px 12px; border-radius:12px; font-size:13px; font-weight:bold; box-shadow:0 3px 0 #a76ec4;'>0 crops</span>
                    <button class='primary-btn' id='downloadMiningBtn' style='display:none;'>📦 Download Crops</button>
                </div>
                <div style='display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:6px;'>
                    <label class='tab-text' style='min-width:180px;'>Taux de détection passive :</label>
                    <input type='range' id='passiveRateSlider' min='1' max='60' value='5' style='width:160px; cursor:pointer;'>
                    <input type='number' id='passiveRateNumber' min='1' max='60' value='5' style='width:58px; padding:4px; border-radius:6px; border:1px solid #aaa; font-size:14px;'>
                    <span style='font-size:13px; color:#555;'>img/détection</span>
                    <button class='primary-btn' id='setPassiveRateBtn'>Appliquer</button>
                </div>
                <div id='zone-resultats'></div>
                <div class='live-feed' id='mainImageDisplay' style='display:none;'>
                    <img id='mainImage' alt='Image principale'>
                </div>
            </div>

            <div class='tab-content'>
                <h3 class='tab-subtitle'>Image Detection</h3>
                <div class='tab-row'>
                    <div class='tab-btn-group'>
                        <label for='detectorSelect' class='tab-text'>Choix du detecteur</label>
                        <select id='detectorSelect' class='select-detector'>
                            <!-- options remplies dynamiquement -->
                        </select>
                        <button class='detector-btn' id='runDetectionBtn'>Lancer Detection</button>
                        <button class='detector-btn' id='runDiagnosticsBtn'>Diagnostique Detecteur</button>
                    </div>
                    <div class='stop-detect-panel' id='stopDetectPanel'>
                        <div class='tab-subtitle'>Diagnostic Stop</div>
                        <div class='indicator-and-terminal'>
                            <div id='stopDetectIndicator' class='detect-indicator'>Aucune detection</div>
                            <div id='stopDetectTerminal' class='log-terminal'>Terminal vide</div>
                        </div>
                    </div>
                </div>
                <!-- Panneau paramètres du détecteur de ligne -->
                <div class='line-params-panel' id='lineParamsPanel'>
                    <h4 class='tab-subtitle' style='margin-top:0;'>Paramètres du détecteur de ligne</h4>
                    <div class='param-row'>
                        <label for='visionWhiteThreshold'>Seuil blanc :</label>
                        <input type='range' id='visionWhiteThreshold' min='0' max='255' value='150'>
                        <input type='number' id='visionWhiteThresholdNum' min='0' max='255' value='150'>
                    </div>
                    <div class='param-row'>
                        <label for='visionMinArea'>Aire minimale :</label>
                        <input type='range' id='visionMinArea' min='10' max='5000' value='300'>
                        <input type='number' id='visionMinAreaNum' min='10' max='5000' value='300'>
                    </div>
                    <div class='param-row'>
                        <label for='visionOffsetRatio'>Zone de détection :</label>
                        <input type='range' id='visionOffsetRatio' min='0' max='100' value='50'>
                        <input type='number' id='visionOffsetRatioNum' min='0' max='100' value='50' step='1'>
                        <span style='font-size:13px; color:#555;'>%</span>
                    </div>
                    <button class='primary-btn' id='applyLineParamsBtn'>Appliquer</button>
                </div>
            </div>
        </div>
    </div>

    <div class='toast-container' id='toastContainer'></div>

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

    // --- Terminal helpers: append + trim ---
    var MAX_TERMINAL_LINES = 300;
    function appendTerminalLines(lineOrLines) {
        var term = document.getElementById('stopDetectTerminal');
        if (!term) return;
        var newLines = Array.isArray(lineOrLines)
            ? lineOrLines
            : String(lineOrLines).split('\\n');
        var oldText = term.textContent || '';
        var oldLines = oldText ? oldText.split('\\n') : [];
        var combined = oldLines.concat(newLines);
        if (combined.length > MAX_TERMINAL_LINES) {
            combined = combined.slice(-MAX_TERMINAL_LINES);
        }
        term.textContent = combined.join('\\n');
        term.scrollTop = term.scrollHeight;
    }

    function clearTerminal() {
        var term = document.getElementById('stopDetectTerminal');
        if (term) term.textContent = '';
    }

    // --- Unified error logging: console + UI terminal ---
    function nowTS() { return new Date().toISOString(); }
    function logError(context, error, extra) {
        var lines = [];
        lines.push('[' + nowTS() + '] ERROR in ' + context);
        if (extra) {
            try { lines.push('Details: ' + JSON.stringify(extra)); } catch (e) {}
        }
        var msg = (error && error.message) ? error.message : String(error);
        lines.push('Message: ' + msg);
        if (error && error.stack) { lines.push('Stack: ' + error.stack); }
        appendTerminalLines(lines);
        console.error('[UI]', context, error, extra || '');
    }

    // --- Toast notification system ---
    function showToast(message, type, duration) {
        type = type || 'warning';
        duration = duration || 4000;
        var container = document.getElementById('toastContainer');
        if (!container) return;
        var toast = document.createElement('div');
        toast.className = 'toast ' + type;
        toast.textContent = message;
        container.appendChild(toast);
        // Trigger animation
        setTimeout(function() { toast.classList.add('show'); }, 10);
        // Auto-dismiss
        setTimeout(function() {
            toast.classList.remove('show');
            setTimeout(function() { container.removeChild(toast); }, 350);
        }, duration);
    }

    // Global error hooks for maximum visibility
    window.addEventListener('error', function(e) {
        logError('window.onerror', e.error || e.message);
    });
    window.addEventListener('unhandledrejection', function(e) {
        logError('window.unhandledrejection', e.reason);
    });

    // Navigation helper: close camera feed if active before redirecting
    function navigateTo(path) {
        try {
            var mainDisplay = document.getElementById('mainImageDisplay');
            var isActive = mainDisplay && mainDisplay.style.display === 'block';
            if (isActive) {
                fetch('/close_camera', { method: 'POST' })
                    .then(function() { location.href = path; })
                    .catch(function(err) { logError('navigateTo: /close_camera', err, { path: path }); location.href = path; });
            } else {
                location.href = path;
            }
        } catch (e) {
            logError('navigateTo', e, { path: path });
            location.href = path;
        }
    }

    // État global: mode d'affichage (livefeed ou captured) et état caméra
    var DISPLAY_MODE = 'livefeed'; // 'livefeed' | 'captured'
    var CAMERA_ACTIVE = false; // Track si la caméra est démarrée

    function toggleCamera() {
        console.log('toggleCamera() appelee');
        var mainDisplay = document.getElementById('mainImageDisplay');
        var mainImage = document.getElementById('mainImage');
        var btn = document.getElementById('cameraToggleBtn');
        var captureBtn = document.getElementById('captureImageBtn');
        // Stop camera should hide display regardless of whether showing livefeed or captured image
        var isActive = CAMERA_ACTIVE && mainDisplay.style.display === 'block';

        if (!isActive) {
            // Démarrer la caméra
            btn.textContent = '⛔ Stop Camera';
            fetch('/start_camera', { method: 'POST' })
                .then(function(response) {
                    if (!response.ok) throw new Error('start_camera failed: ' + response.status + ' ' + response.statusText);
                    mainDisplay.style.display = 'block';
                    mainImage.src = '/video?' + new Date().getTime();
                    DISPLAY_MODE = 'livefeed';
                    CAMERA_ACTIVE = true;
                    captureBtn.textContent = '📸 Capture Image';
                })
                .catch(function(err) {
                    logError('toggleCamera: /start_camera', err);
                    btn.textContent = '▶️ Start Camera';
                    CAMERA_ACTIVE = false;
                });
        } else {
            // Arrêter la caméra
            mainDisplay.style.display = 'none';
            btn.textContent = '▶️ Start Camera';
            mainImage.src = "";
            DISPLAY_MODE = 'livefeed';
            CAMERA_ACTIVE = false;
            captureBtn.textContent = '📸 Capture Image';
            fetch('/close_camera', { method: 'POST' }).catch(function(err) { logError('toggleCamera: /close_camera', err); });
        }
    }

    function onResolutionChange() {
        var sel = document.getElementById('resolutionSelect');
        var parts = sel.value.split('x');
        var w = parseInt(parts[0], 10);
        var h = parseInt(parts[1], 10);
        var selectedOpt = sel.options[sel.selectedIndex];
        var maxFps = selectedOpt.getAttribute('data-maxfps');
        console.log('onResolutionChange:', w, 'x', h, 'maxFps:', maxFps);

        // Appliquer la limite FPS si la résolution l'exige
        if (maxFps !== null) {
            maxFps = parseInt(maxFps, 10);
            var fpsSlider = document.getElementById('fpsSlider');
            var fpsNumber = document.getElementById('fpsNumber');
            var currentFps = parseInt(fpsSlider ? fpsSlider.value : 30, 10);
            if (currentFps > maxFps) {
                if (fpsSlider) fpsSlider.value = maxFps;
                if (fpsNumber) fpsNumber.value = maxFps;
                setLivefeedFps(maxFps);
                showToast('FPS limité à ' + maxFps + ' fps pour la résolution 1080p', 'warning', 3000);
            }
        }

        showToast('Changement de résolution: ' + w + '×' + h + '…', 'info', 2000);

        fetch('/set_resolution', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ width: w, height: h })
        })
        .then(function(r) {
            if (!r.ok) throw new Error('set_resolution failed: ' + r.status);
            return r.json();
        })
        .then(function(data) {
            showToast('Résolution appliquée: ' + data.resolution, 'success', 2000);
            // Si la caméra tournait, le serveur l'a relancée.
            // Rafraîchir le flux vidéo dans le navigateur.
            if (CAMERA_ACTIVE && DISPLAY_MODE === 'livefeed') {
                var mainImage = document.getElementById('mainImage');
                mainImage.src = '/video?' + new Date().getTime();
            }
        })
        .catch(function(err) {
            logError('onResolutionChange', err);
            showToast('Erreur résolution: ' + err.message, 'error');
        });
    }

    function togglePassiveDetection() {
        console.log('togglePassiveDetection() appelee'); // pour debug
        var btn = document.getElementById('togglePassiveDetectionBtn');
        var isActive = btn.getAttribute('aria-pressed') === 'true';
        var nextActive = !isActive;
        var endpoint = nextActive ? '/start_passive_detection' : '/stop_passive_detection';

        fetch(endpoint, { method: 'POST' })
            .then(function(response) {
                if (!response.ok) throw new Error(endpoint + ' failed: ' + response.status);
                btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
                btn.classList.toggle('on', nextActive);
                btn.classList.toggle('off', !nextActive);
                btn.textContent = nextActive ? 'Stop Passive Detection' : 'Start Passive Detection';
                showToast(nextActive ? 'Détection passive démarrée' : 'Détection passive arrêtée', nextActive ? 'success' : 'info', 2000);
            })
            .catch(function(err) {
                logError('togglePassiveDetection: ' + endpoint, err);
                showToast('Erreur: ' + err.message, 'error');
            });
    }

    function toggleDownloadCaptured() {
        console.log('toggleDownloadCaptured() appelee'); // pour debug
        var btn = document.getElementById('toggleDownloadCapturedBtn');
        var isActive = btn.getAttribute('aria-pressed') === 'true';
        var nextActive = !isActive;
        btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
        btn.classList.toggle('on', nextActive);
        btn.classList.toggle('off', !nextActive);
        btn.textContent = nextActive ? ' 💾 On' : ' 💾 Off';
    }

    function captureImage() {
        console.log('captureImage() appelee');
        var downloadEnabled = document.getElementById('toggleDownloadCapturedBtn').getAttribute('aria-pressed') === 'true';

        fetch('/capture_image', { method: 'POST' })
            .then(function(response) {
                if (!response.ok) throw new Error('capture_image failed: ' + response.status + ' ' + response.statusText);
                return response.json();
            })
            .then(function(data) {
                var file_url = data.file_url;
                var download_url = data.download_url;
                var filename = data.filename;
                var error = data.error;
                if (error) {
                    logError('captureImage: server payload error', new Error(error), { filename: filename });
                    alert('Erreur lors de la capture image : ' + error);
                    return;
                }

                // enregistrement de l'image sur le PC client si demandé
                if (downloadEnabled) {
                    var link = document.createElement('a');
                    link.href = download_url;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    showToast('Image sauvegardée: ' + filename, 'success', 2000);
                }

                // Basculer vers l'image capturée dans l'affichage principal
                var mainImage = document.getElementById('mainImage');
                var mainDisplay = document.getElementById('mainImageDisplay');
                var captureBtn = document.getElementById('captureImageBtn');

                mainImage.src = file_url;
                mainDisplay.style.display = 'block';
                DISPLAY_MODE = 'captured';
                CAMERA_ACTIVE = false; // La caméra a été stoppée par le serveur pour la capture hires
                captureBtn.textContent = '↩️ Return to Livefeed';

                // Mise à jour de la dernière image capturée (pour diagnostic)
                imageCapturedCallback(file_url);
            })
            .catch(function(err) {
                logError('captureImage: /capture_image', err);
                alert('Erreur lors de la communication avec le serveur : ' + err);
            });
    }

    function returnToLivefeed() {
        console.log('returnToLivefeed() appelee');
        var mainImage = document.getElementById('mainImage');
        var mainDisplay = document.getElementById('mainImageDisplay');
        var captureBtn = document.getElementById('captureImageBtn');

        if (CAMERA_ACTIVE) {
            // Caméra déjà active, juste basculer vers le livestream
            mainImage.src = '/video?' + new Date().getTime();
            DISPLAY_MODE = 'livefeed';
            captureBtn.textContent = '📸 Capture Image';
        } else {
            // Caméra pas active, la redémarrer
            var btn = document.getElementById('cameraToggleBtn');
            btn.textContent = '⛔ Stop Camera';
            fetch('/start_camera', { method: 'POST' })
                .then(function(response) {
                    if (!response.ok) throw new Error('start_camera failed: ' + response.status + ' ' + response.statusText);
                    mainDisplay.style.display = 'block';
                    mainImage.src = '/video?' + new Date().getTime();
                    DISPLAY_MODE = 'livefeed';
                    CAMERA_ACTIVE = true;
                    captureBtn.textContent = '📸 Capture Image';
                })
                .catch(function(err) {
                    logError('returnToLivefeed: /start_camera', err);
                    btn.textContent = '▶️ Start Camera';
                    CAMERA_ACTIVE = false;
                    alert('Erreur: impossible de redémarrer la caméra. Utilisez le bouton Start Camera.');
                });
        }
    }

    function imageCapturedCallback(imageUrl) {
        console.log("imageCapturedCallback mise a jour de l'image : " + imageUrl);

        // Mettre à jour l'affichage principal si on est en mode captured
        if (DISPLAY_MODE === 'captured') {
            var mainImage = document.getElementById('mainImage');
            mainImage.src = imageUrl;
        }
    }
    
    // --- Détecteurs: chargement, sélection et exécution ---
    var DETECTORS_MAP = {}; // index -> name
    var SELECTED_DETECTOR_NAME = null;

    function loadDetectors() {
        fetch('/detectors')
            .then(function(r) { if (!r.ok) throw new Error('detectors failed: ' + r.status + ' ' + r.statusText); return r.json(); })
            .then(function(resp) {
                var detectors = resp.detectors;
                var selected = resp.selected;
                var sel = document.getElementById('detectorSelect');
                sel.innerHTML = '';
                if (!detectors || detectors.length === 0) {
                    var opt = document.createElement('option');
                    opt.value = -1;
                    opt.textContent = 'Aucun détecteur disponible';
                    sel.appendChild(opt);
                    sel.disabled = true;
                    return;
                }
                for (var i = 0; i < detectors.length; i++) {
                    var d = detectors[i];
                    var opt2 = document.createElement('option');
                    opt2.value = d.index;
                    opt2.textContent = d.name + ' (#' + d.index + ')';
                    sel.appendChild(opt2);
                    DETECTORS_MAP[d.index] = d.name;
                    console.log('[DEBUG loadDetectors] Loaded detector:', d.index, d.name);
                }
                if (selected != null && selected >= 0) {
                    sel.value = String(selected);
                    SELECTED_DETECTOR_NAME = DETECTORS_MAP[selected] || null;
                    console.log('[DEBUG loadDetectors] Selected detector:', selected, SELECTED_DETECTOR_NAME);
                    updateDiagnosticPanelVisibility();
                }
            })
            .catch(function(err) { logError('loadDetectors: /detectors', err); });
    }

    function onDetectorChange() {
        var sel = document.getElementById('detectorSelect');
        var idx = parseInt(sel.value, 10);
        console.log('[DEBUG onDetectorChange] Selected index:', idx);
        if (isNaN(idx) || idx < 0) return;

        // Reset diagnostic panel when changing detectors
        var indicator = document.getElementById('stopDetectIndicator');
        var terminal = document.getElementById('stopDetectTerminal');
        if (indicator) {
            indicator.classList.remove('on', 'off');
            indicator.textContent = 'Aucune détection';
        }
        if (terminal) {
            terminal.textContent = 'Terminal vide';
        }

        fetch('/detector', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index: idx })
        }).catch(function(err) { logError('onDetectorChange: /detector', err, { index: idx }); });
        SELECTED_DETECTOR_NAME = DETECTORS_MAP[idx] || null;
        console.log('[DEBUG onDetectorChange] SELECTED_DETECTOR_NAME set to:', SELECTED_DETECTOR_NAME);
        updateDiagnosticPanelVisibility();
    }

    function runDetection() {
        var terminal = document.getElementById('stopDetectTerminal');
        var indicator = document.getElementById('stopDetectIndicator');
        clearTerminal();
        fetch('/run_detection', { method: 'POST' })
            .then(function(r) {
                if (!r.ok) {
                    return r.json().then(function(body) {
                        var msg = (body && body.error) ? body.error : 'run_detection failed';
                        if (msg.indexOf('capture') !== -1 || msg.indexOf('captured') !== -1) {
                            showToast('\u26a0\ufe0f Veuillez capturer une image avant de lancer la detection.', 'warning');
                        } else {
                            showToast('Erreur: ' + msg, 'error');
                        }
                        throw new Error(msg);
                    }).catch(function(parseErr) {
                        if (parseErr.message && parseErr.message.indexOf('capture') !== -1) throw parseErr;
                        showToast('Erreur serveur (' + r.status + ')', 'error');
                        throw new Error('run_detection failed: ' + r.status + ' ' + r.statusText);
                    });
                }
                return r.json();
            })
            .then(function(res) {
                if (res.logs && Array.isArray(res.logs)) {
                    appendTerminalLines(res.logs);
                } else {
                    appendTerminalLines(JSON.stringify(res, null, 2));
                }

                if (res && res.annotated_url) {
                    imageCapturedCallback(res.annotated_url);
                } else if (res && res.source_file_url) {
                    imageCapturedCallback(res.source_file_url);
                }

                indicator.classList.remove('on', 'off');
                if (res.Object_detected) {
                    indicator.classList.add('on');
                    indicator.textContent = 'Objet detecte';
                } else {
                    indicator.classList.add('off');
                    indicator.textContent = 'Aucune detection';
                }
            })
            .catch(function(err) {
                logError('runDetection: /run_detection', err);
                appendTerminalLines('Erreur: ' + err);
            });
    }

    function updateDiagnosticPanelVisibility() {
        var panel = document.getElementById('stopDetectPanel');
        // Afficher le panneau diagnostic pour tout détecteur sélectionné
        if (!SELECTED_DETECTOR_NAME) { panel.style.display = 'none'; return; }
        panel.style.display = 'block';
    }

    function runDiagnostics() {
        var detectorName = SELECTED_DETECTOR_NAME || 'Inconnu';
        console.log('[DEBUG runDiagnostics] Lancement diagnostic pour:', detectorName);

        var indicator = document.getElementById('stopDetectIndicator');
        var terminal = document.getElementById('stopDetectTerminal');
        indicator.classList.remove('on', 'off');
        indicator.textContent = 'Diagnostic en cours...';
        appendTerminalLines('Execution du diagnostic pour ' + detectorName + '...');

        fetch('/diagnose_detector', { method: 'POST' })
            .then(function(r) {
                if (!r.ok) {
                    return r.json().then(function(body) {
                        var msg = (body && body.error) ? body.error : 'diagnose_detector failed';
                        if (msg.indexOf('capture') !== -1 || msg.indexOf('captured') !== -1) {
                            showToast('\u26a0\ufe0f Veuillez capturer une image avant de lancer le diagnostic.', 'warning');
                        } else {
                            showToast('Erreur: ' + msg, 'error');
                        }
                        throw new Error(msg);
                    }).catch(function(parseErr) {
                        if (parseErr.message && parseErr.message.indexOf('capture') !== -1) throw parseErr;
                        showToast('Erreur serveur (' + r.status + ')', 'error');
                        throw new Error('diagnose_detector failed: ' + r.status + ' ' + r.statusText);
                    });
                }
                return r.json();
            })
            .then(function(payload) {
                // Afficher les logs dans le terminal
                if (payload.logs && Array.isArray(payload.logs)) {
                    appendTerminalLines(payload.logs);
                } else {
                    appendTerminalLines(JSON.stringify(payload, null, 2));
                }

                // Mettre à jour l'indicateur de détection
                indicator.classList.remove('on', 'off');
                if (payload.Object_detected) {
                    indicator.classList.add('on');
                    indicator.textContent = 'Objet detecte';
                } else {
                    indicator.classList.add('off');
                    indicator.textContent = 'Aucune detection';
                }

                // Afficher la dernière image annotée ou source
                var imgUrl = payload.annotated_url
                    || (payload.steps && payload.steps.length ? payload.steps[payload.steps.length - 1].url : null)
                    || payload.source_file_url;
                if (imgUrl) { imageCapturedCallback(imgUrl); }

                // Ouvrir la galerie des étapes dans un nouvel onglet (si disponible)
                if (payload.steps && payload.steps.length) {
                    var w = window.open('', '_blank');
                    if (w) {
                        var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Diagnostic Gallery</title></head><body style="font-family:Arial; padding:12px;">';
                        html += '<h3>Etapes du diagnostic - ' + detectorName + '</h3>';
                        for (var i = 0; i < payload.steps.length; i++) {
                            var s = payload.steps[i];
                            html += '<div style="margin-bottom:12px;"><div><b>' + s.name + '</b></div><img style="max-width:100%;border:1px solid #ccc" src="' + s.url + '"></div>';
                        }
                        html += '</body></html>';
                        w.document.write(html);
                        w.document.close();
                    }
                }
            })
            .catch(function(err) {
                logError('runDiagnostics: /diagnose_detector', err);
                indicator.classList.remove('on');
                indicator.classList.add('off');
                indicator.textContent = 'Erreur';
            });
    }

    // Charger la liste des détecteurs au chargement de la page et lier les événements
    // --- Hard Positive Mining ---
    var MINING_POLL_INTERVAL = null;

    function toggleMining() {
        var btn = document.getElementById('toggleMiningBtn');
        var isActive = btn.getAttribute('aria-pressed') === 'true';
        var nextActive = !isActive;

        fetch('/toggle_mining', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: nextActive })
        })
        .then(function(r) { if (!r.ok) throw new Error('toggle_mining failed'); return r.json(); })
        .then(function(stats) {
            btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
            btn.classList.toggle('on', nextActive);
            btn.classList.toggle('off', !nextActive);
            btn.textContent = nextActive ? '⛏️ Mining On' : '⛏️ Mining Off';
            showToast(nextActive ? 'Hard positive mining activé' : 'Mining désactivé', nextActive ? 'success' : 'info', 2000);

            if (nextActive) {
                startMiningPoll();
            } else {
                stopMiningPoll();
                updateMiningBadge(stats);
            }
        })
        .catch(function(err) {
            logError('toggleMining', err);
            showToast('Erreur mining: ' + err.message, 'error');
        });
    }

    function startMiningPoll() {
        if (MINING_POLL_INTERVAL) return;
        pollMiningStats();
        MINING_POLL_INTERVAL = setInterval(pollMiningStats, 3000);
    }

    function stopMiningPoll() {
        if (MINING_POLL_INTERVAL) {
            clearInterval(MINING_POLL_INTERVAL);
            MINING_POLL_INTERVAL = null;
        }
    }

    function pollMiningStats() {
        fetch('/mining_stats')
            .then(function(r) { if (!r.ok) throw new Error('stats failed'); return r.json(); })
            .then(function(stats) { updateMiningBadge(stats); })
            .catch(function() {});
    }

    function updateMiningBadge(stats) {
        var badge = document.getElementById('miningBadge');
        var dlBtn = document.getElementById('downloadMiningBtn');
        var total = stats.total || 0;

        if (total > 0) {
            // Construire un résumé par objet
            var parts = [];
            var perObj = stats.per_object || {};
            for (var key in perObj) {
                if (perObj.hasOwnProperty(key)) {
                    parts.push(key + ': ' + perObj[key]);
                }
            }
            badge.textContent = total + ' crops (' + parts.join(', ') + ')';
            badge.style.display = 'inline';
            dlBtn.style.display = 'inline';
        } else {
            badge.style.display = 'none';
            dlBtn.style.display = 'none';
        }
    }

    function downloadMiningCrops() {
        showToast('Préparation du ZIP …', 'info', 2000);
        // Déclencher le téléchargement via un lien caché
        var link = document.createElement('a');
        link.href = '/download_mining_crops';
        link.download = '';
        document.body.appendChild(link);
        link.click();
        link.remove();
        // Rafraîchir les stats après un court délai (le serveur supprime les crops)
        setTimeout(function() { pollMiningStats(); }, 2000);
    }

    function setLivefeedFps(fps) {
        fetch('/set_livefeed_fps', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fps: fps })
        })
        .then(function(r) { if (!r.ok) throw new Error('set_livefeed_fps failed'); return r.json(); })
        .then(function(d) { showToast('FPS livefeed: ' + d.fps, 'success', 1500); })
        .catch(function(err) { logError('setLivefeedFps', err); showToast('Erreur FPS: ' + err.message, 'error'); });
    }

    function setPassiveDetectionRate(rate) {
        fetch('/set_passive_detection_rate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ detection_rate: rate })
        })
        .then(function(r) { if (!r.ok) return r.json().then(function(b) { throw new Error(b.error || 'failed'); }); return r.json(); })
        .then(function(d) { showToast('Taux de détection: 1/' + d.detection_rate + ' images', 'success', 2000); })
        .catch(function(err) { logError('setPassiveDetectionRate', err); showToast('Erreur taux détection: ' + err.message, 'error'); });
    }

    window.addEventListener('DOMContentLoaded', function() {
        loadDetectors();
        // Camera toggle
        var camBtn = document.getElementById('cameraToggleBtn');
        if (camBtn) camBtn.addEventListener('click', toggleCamera);
        // Capture image — dispatche selon le mode d'affichage courant
        var capBtn = document.getElementById('captureImageBtn');
        if (capBtn) capBtn.addEventListener('click', function() {
            if (DISPLAY_MODE === 'captured') {
                returnToLivefeed();
            } else {
                captureImage();
            }
        });
        // Toggle download
        var dlBtn = document.getElementById('toggleDownloadCapturedBtn');
        if (dlBtn) dlBtn.addEventListener('click', toggleDownloadCaptured);
        // Resolution dropdown
        var resSelect = document.getElementById('resolutionSelect');
        if (resSelect) resSelect.addEventListener('change', onResolutionChange);
        // Toggle passive detection
        var pdBtn = document.getElementById('togglePassiveDetectionBtn');
        if (pdBtn) pdBtn.addEventListener('click', togglePassiveDetection);
        // Run detection
        var runDetBtn = document.getElementById('runDetectionBtn');
        if (runDetBtn) runDetBtn.addEventListener('click', runDetection);
        // Run diagnostics
        var runDiagBtn = document.getElementById('runDiagnosticsBtn');
        if (runDiagBtn) runDiagBtn.addEventListener('click', runDiagnostics);
        // Detector select change
        var sel = document.getElementById('detectorSelect');
        if (sel) sel.addEventListener('change', onDetectorChange);
        // Mining controls
        var minBtn = document.getElementById('toggleMiningBtn');
        if (minBtn) minBtn.addEventListener('click', toggleMining);
        var minDlBtn = document.getElementById('downloadMiningBtn');
        if (minDlBtn) minDlBtn.addEventListener('click', downloadMiningCrops);
        // FPS Livefeed slider
        var fpsSlider = document.getElementById('fpsSlider');
        var fpsNumber = document.getElementById('fpsNumber');
        if (fpsSlider && fpsNumber) {
            fpsSlider.addEventListener('change', function() {
                fpsNumber.value = fpsSlider.value;
                setLivefeedFps(parseInt(fpsSlider.value, 10));
            });
            fpsSlider.addEventListener('input', function() { fpsNumber.value = fpsSlider.value; });
            fpsNumber.addEventListener('change', function() {
                var v = Math.max(1, Math.min(60, parseInt(fpsNumber.value, 10) || 30));
                fpsNumber.value = v;
                fpsSlider.value = v;
                setLivefeedFps(v);
            });
        }
        // Passive detection rate controls
        var passiveRateSlider = document.getElementById('passiveRateSlider');
        var passiveRateNumber = document.getElementById('passiveRateNumber');
        if (passiveRateSlider && passiveRateNumber) {
            passiveRateSlider.addEventListener('input', function() { passiveRateNumber.value = passiveRateSlider.value; });
            passiveRateNumber.addEventListener('change', function() {
                var v = Math.max(1, Math.min(60, parseInt(passiveRateNumber.value, 10) || 5));
                passiveRateNumber.value = v;
                passiveRateSlider.value = v;
            });
        }
        var setRateBtn = document.getElementById('setPassiveRateBtn');
        if (setRateBtn) {
            setRateBtn.addEventListener('click', function() {
                var v = parseInt(document.getElementById('passiveRateNumber').value, 10) || 5;
                setPassiveDetectionRate(v);
            });
        }

        // --- Line detector params : sync sliders <-> number inputs ---
        function syncSliderNum(sliderId, numId) {
            var slider = document.getElementById(sliderId);
            var num = document.getElementById(numId);
            if (!slider || !num) return;
            slider.addEventListener('input', function() { num.value = slider.value; });
            num.addEventListener('change', function() {
                var lo = parseInt(slider.min, 10);
                var hi = parseInt(slider.max, 10);
                var v = Math.max(lo, Math.min(hi, parseInt(num.value, 10) || lo));
                num.value = v;
                slider.value = v;
            });
        }
        syncSliderNum('visionWhiteThreshold', 'visionWhiteThresholdNum');
        syncSliderNum('visionMinArea', 'visionMinAreaNum');
        syncSliderNum('visionOffsetRatio', 'visionOffsetRatioNum');

        // Charger les valeurs actuelles depuis le serveur
        fetch('/line_detector/get_params')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.white_threshold !== undefined) {
                    document.getElementById('visionWhiteThreshold').value = data.white_threshold;
                    document.getElementById('visionWhiteThresholdNum').value = data.white_threshold;
                }
                if (data.min_area !== undefined) {
                    document.getElementById('visionMinArea').value = data.min_area;
                    document.getElementById('visionMinAreaNum').value = data.min_area;
                }
                if (data.offset_ratio !== undefined) {
                    var pct = Math.round(data.offset_ratio * 100);
                    document.getElementById('visionOffsetRatio').value = pct;
                    document.getElementById('visionOffsetRatioNum').value = pct;
                }
            })
            .catch(function(err) { console.warn('line_detector/get_params:', err); });

        // Bouton Appliquer
        var applyBtn = document.getElementById('applyLineParamsBtn');
        if (applyBtn) {
            applyBtn.addEventListener('click', applyLineDetectorParams);
        }
    });

    function applyLineDetectorParams() {
        var params = {
            white_threshold: parseInt(document.getElementById('visionWhiteThresholdNum').value, 10),
            min_area: parseInt(document.getElementById('visionMinAreaNum').value, 10),
            offset_ratio: parseInt(document.getElementById('visionOffsetRatioNum').value, 10) / 100.0
        };
        fetch('/line_detector/update_params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        })
        .then(function(r) { if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); })
        .then(function(data) {
            showToast('Paramètres détecteur mis à jour!', 'success');
        })
        .catch(function(err) {
            showToast('Erreur: ' + err.message, 'error');
        });
    }

    // --- Exposer les fonctions au scope global pour les onclick inline ---
    window.navigateTo = navigateTo;
    window.toggleCamera = toggleCamera;
    window.toggleDownloadCaptured = toggleDownloadCaptured;
    window.onResolutionChange = onResolutionChange;
    window.togglePassiveDetection = togglePassiveDetection;
    window.captureImage = captureImage;
    window.returnToLivefeed = returnToLivefeed;
    window.runDetection = runDetection;
    window.runDiagnostics = runDiagnostics;
    window.onDetectorChange = onDetectorChange;
    window.toggleMining = toggleMining;
    window.downloadMiningCrops = downloadMiningCrops;
    window.setLivefeedFps = setLivefeedFps;
    window.setPassiveDetectionRate = setPassiveDetectionRate;
    window.applyLineDetectorParams = applyLineDetectorParams;
    </script>
    </body></html>
    """

    # Remplacer uniquement le titre sans interpreter les autres accolades
    return html.replace("{title}", title)
