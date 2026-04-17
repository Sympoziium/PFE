#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_pid.py
# ------------------
"""Page web pour le controle PID du suivi de ligne."""

def render_pid_tab(title="Asservissement PID"):
    """Retourne une page HTML complete pour le controle PID."""

    html = """<!DOCTYPE html><html lang='fr'>
    <head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>{title}</title>
    <link rel='icon' href='data:,'>
    <style>
    body {{
        margin: 0; padding: 0;
        width: 100vw; min-height: 100vh;
        font-family: 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%);
        color: #333; display: flex; flex-direction: column;
        overflow-y: auto;
    }}

    .container {{
        display: flex; justify-content: center; align-items: flex-start;
        padding: 2vh; min-height: 96vh;
    }}

    .tab-shell {{
        background: rgba(247, 253, 255, 0.95);
        border-radius: 20px;
        padding: 2%;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        width: min(1100px, 92%);
        min-height: fit-content; margin-bottom: 4vh;
        display: flex; flex-direction: column;
    }}

    .tab-header {{
        display: flex; align-items: center;
        margin-bottom: 2vh;
        padding-bottom: 1vh;
        border-bottom: 2px solid #e0f4ff;
    }}

    .tab-nav {{
        display: flex; align-items: center;
        gap: 8px;
        margin-left: auto;
    }}

    .tab-content {{
        border: 3px dashed #B5FFFC;
        border-radius: 15px;
        padding: 3%;
        background: #FFFDF0;
        margin-bottom: 16px;
    }}

    /* Variante alerte (section step-by-step) */
    .tab-content.accent {{
        border: 3px dashed #FFD166;
        background: #fffbf0;
    }}

    .tab-title {{
        font-size: 1.8rem; font-weight: bold; color: #5A99C7; margin: 0;
    }}

    .tab-subtitle {{
        font-size: 1.3rem; font-weight: bold; color: #666; margin-bottom: 15px; margin-top: 0;
    }}

    .tab-text {{
        font-size: 1.1rem; color: #444;
    }}

    /* --- Boutons Pastels (style accueil) --- */

    .primary-btn {{
        background: #87C7F1; color: white; border: none;
        padding: 12px 20px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        transition: transform 0.2s, background 0.2s;
        box-shadow: 0 4px 0 #6BAED6;
    }}

    .primary-btn:hover {{
        background: #76B9E4;
        transform: translateY(-2px);
    }}

    .primary-btn:active {{
        transform: translateY(2px);
        box-shadow: 0 2px 0 #6BAED6;
    }}

    .primary-btn.active {{
        background: #5A99C7;
        box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
    }}

    /* Bouton control vert pastel */
    .control-btn {{
        background: #A8E6CF; color: #2d6a4f; border: none;
        padding: 12px 24px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        box-shadow: 0 4px 0 #74C69D;
        transition: transform 0.2s, background 0.2s;
        margin: 5px;
    }}

    .control-btn:hover {{ background: #95D9C0; transform: translateY(-2px); }}
    .control-btn:active {{ transform: translateY(2px); box-shadow: 0 2px 0 #74C69D; }}

    .control-btn.stop {{
        background: #F4A0A0; color: #7a1f1f;
        box-shadow: 0 4px 0 #d97070;
    }}

    .control-btn.stop:hover {{ background: #ee8a8a; transform: translateY(-2px); }}

    .control-btn:disabled {{
        background: #ccc; color: #999;
        box-shadow: none; cursor: not-allowed;
        transform: none;
    }}

    /* Bouton d'approbation step (special) */
    .approve-btn {{
        background: #fff; color: #2d6a4f;
        font-size: 1.2rem; font-weight: bold;
        padding: 20px 40px; border: 4px solid #A8E6CF;
        border-radius: 15px; cursor: pointer;
        box-shadow: 0 6px 0 #74C69D;
        transition: transform 0.2s;
    }}

    .approve-btn:hover:not(:disabled) {{ background: #f0fff4; transform: translateY(-2px); }}
    .approve-btn:active:not(:disabled) {{ transform: translateY(4px); box-shadow: 0 2px 0 #74C69D; }}
    .approve-btn:disabled {{ background: #eee; color: #999; border-color: #ccc; box-shadow: none; cursor: not-allowed; }}

    /* --- Paramètres --- */

    .param-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin: 15px 0;
    }}

    .param-item {{
        display: flex;
        flex-direction: column;
        gap: 5px;
    }}

    .param-label {{
        font-weight: bold;
        font-size: 0.95rem;
        color: #555;
    }}

    .param-input {{
        padding: 10px;
        border: 2px solid #B5FFFC;
        border-radius: 12px;
        font-size: 1rem;
        background: #fff;
        color: #333;
        transition: border-color 0.2s;
    }}

    .param-input:focus {{
        outline: none;
        border-color: #87C7F1;
        box-shadow: 0 0 0 3px rgba(135, 199, 241, 0.2);
    }}

    /* --- Panneau de mode --- */
    .mode-panel {{
        background: rgba(181, 255, 252, 0.2);
        border: 2px solid #B5FFFC;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 20px;
    }}

    /* --- Panneau rotation --- */
    .rotation-panel {{
        background: rgba(255, 209, 102, 0.15);
        border: 2px solid #FFD166;
        border-radius: 15px;
        padding: 15px;
        margin-top: 20px;
    }}

    /* --- Statut --- */
    .status-panel {{
        background: rgba(247, 253, 255, 0.8);
        border: 2px solid #B5FFFC;
        border-radius: 15px;
        padding: 15px;
        margin: 15px 0;
    }}

    .status-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 10px;
    }}

    .status-item {{
        background: white;
        padding: 12px;
        border-radius: 12px;
        text-align: center;
        border: 2px solid #e0f4ff;
        box-shadow: 0 3px 0 #d0eeff;
    }}

    .status-label {{
        font-size: 12px;
        color: #888;
        margin-bottom: 4px;
    }}

    .status-value {{
        font-size: 1.2rem;
        font-weight: bold;
        color: #5A99C7;
    }}

    /* --- Terminal --- */
    .log-terminal {{
        background: #1a1a2e;
        color: #a8d8ea;
        font-family: 'Courier New', Consolas, monospace;
        font-size: 13px;
        border-radius: 12px;
        padding: 12px;
        height: 200px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
        border: 2px solid #B5FFFC;
    }}

    /* --- Live Feed --- */
    .live-feed {{
        width: 100%;
        margin-top: 15px;
        text-align: center;
    }}

    .live-feed img {{
        width: 70%;
        max-width: 640px;
        height: auto;
        border-radius: 12px;
        border: 4px solid #87C7F1;
    }}

    /* --- Step-by-step approve zone --- */
    .approve-zone {{
        background: rgba(168, 230, 207, 0.3);
        border: 2px solid #A8E6CF;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        margin-top: 15px;
    }}

    /* --- Toast notifications --- */
    .toast-container {{
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }}

    .toast {{
        padding: 12px 20px;
        border-radius: 12px;
        color: #fff;
        font-size: 14px;
        font-weight: bold;
        box-shadow: 0 4px 0 rgba(0,0,0,0.15);
        opacity: 0;
        transform: translateX(80px);
        transition: opacity 0.3s, transform 0.3s;
        max-width: 380px; word-wrap: break-word;
    }}

    .toast.show {{ opacity: 1; transform: translateX(0); }}
    .toast.warning {{ background: #FFD166; color: #7a4f00; }}
    .toast.error   {{ background: #F4A0A0; color: #7a1f1f; }}
    .toast.info    {{ background: #87C7F1; color: #1a3a5c; }}
    .toast.success {{ background: #A8E6CF; color: #2d6a4f; }}

    @keyframes pulse {{
        0%   {{ transform: scale(1);    box-shadow: 0 6px 0 #74C69D; }}
        50%  {{ transform: scale(1.04); box-shadow: 0 8px 20px rgba(168,230,207,0.6); }}
        100% {{ transform: scale(1);    box-shadow: 0 6px 0 #74C69D; }}
    }}

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
                    <button class='primary-btn' onclick="fetch('/exit', {{method:'POST'}})">EXIT</button>                
                </div>
            </div>

            <!-- Parametres PID -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Parametres PID</h3>

                <div class='mode-panel'>
                    <label style='font-weight: bold; font-size: 1rem; display: block; margin-bottom: 10px; color: #555;'>
                        Mode de controle
                    </label>
                    <div style='display: flex; gap: 10px;'>
                        <button class='control-btn' id='rotationModeBtn' style='flex: 1;'>
                            🔄 Mode Rotation (Tuning)
                        </button>
                        <button class='control-btn' id='driveModeBtn' style='flex: 1; background: #ccc; color: #888; box-shadow: 0 4px 0 #bbb;'>
                            ➡️ Mode Avance (Suivi)
                        </button>
                    </div>
                    <p style='margin-top: 10px; font-size: 13px; color: #888;'>
                        <strong>Mode Rotation:</strong> Le Zumi tourne sur place pour centrer la ligne (ideal pour regler Kp, Ki, Kd).<br>
                        <strong>Mode Avance:</strong> Le Zumi avance en suivant la ligne.
                    </p>
                </div>

                <div class='param-grid'>
                    <div class='param-item'>
                        <label class='param-label'>Kp (Proportionnel)</label>
                        <input type='number' step='0.01' class='param-input' id='kpInput' value='0.1'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Ki (Integral)</label>
                        <input type='number' step='0.001' class='param-input' id='kiInput' value='0.0'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Kd (Derive)</label>
                        <input type='number' step='0.01' class='param-input' id='kdInput' value='0.05'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Vitesse de base</label>
                        <input type='number' step='1' class='param-input' id='baseSpeedInput' value='20'>
                        <small style='color: #888;'>(utilise uniquement en mode avance)</small>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Correction max</label>
                        <input type='number' step='1' class='param-input' id='maxCorrectionInput' value='30'>
                    </div>
                </div>

                <div class='rotation-panel'>
                    <h4 style='margin: 0 0 10px 0; color: #856404;'>⚙️ Parametres de rotation (Mode Rotation uniquement)</h4>
                    <p style='font-size: 13px; color: #856404; margin-bottom: 15px;'>
                        Ces parametres controlent le calcul de l'angle lorsque le mode rotation est active.
                    </p>
                    <div class='param-grid'>
                        <div class='param-item'>
                            <label class='param-label'>Echelle d'angle (angle_scale)</label>
                            <input type='number' step='0.01' class='param-input' id='angleScaleInput' value='0.3'>
                            <small style='color: #888;'>Conversion erreur -> angle (0.3 = 100px -> 30 deg)</small>
                        </div>
                        <div class='param-item'>
                            <label class='param-label'>Angle maximal (degres)</label>
                            <input type='number' step='1' class='param-input' id='maxAngleInput' value='45'>
                            <small style='color: #888;'>Limite les rotations brusques</small>
                        </div>
                        <div class='param-item'>
                            <label class='param-label'>Seuil minimal (degres)</label>
                            <input type='number' step='0.5' class='param-input' id='minAngleThresholdInput' value='2'>
                            <small style='color: #888;'>Angle minimum pour declencher une rotation</small>
                        </div>
                    </div>
                </div>

                <div style='margin-top: 15px;'>
                    <button class='primary-btn' id='updateParamsBtn'>🔍 Mettre a jour les parametres</button>
                </div>
            </div>

            <!-- Parametres du detecteur de ligne -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Parametres du detecteur de ligne</h3>
                <div class='param-grid'>
                    <div class='param-item'>
                        <label class='param-label'>Seuil blanc (0-255)</label>
                        <input type='number' min='0' max='255' step='5' class='param-input' id='whiteThresholdInput' value='200'>
                        <small style='color: #888;'>Plus eleve = detecte seulement le blanc pur</small>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Aire minimale (pixels)</label>
                        <input type='number' min='100' max='1000' step='50' class='param-input' id='minAreaInput' value='300'>
                        <small style='color: #888;'>Ignore les petits objets blancs</small>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Zone de detection (0.0-1.0)</label>
                        <input type='number' min='0' max='1' step='0.05' class='param-input' id='offsetRatioInput' value='0.6'>
                        <small style='color: #888;'>0.6 = cherche dans les 40% inferieurs</small>
                    </div>
                </div>
                <div style='margin-top: 15px;'>
                    <button class='primary-btn' id='updateLineDetectorBtn'>🔍 Mettre a jour le detecteur</button>
                </div>
            </div>

            <!-- Controle Manuel de Rotation -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>🎮 Controle Manuel de Rotation</h3>
                <p class='tab-text' style='margin-bottom: 15px; color: #888;'>
                    Utilisez la fonction turn() du Zumi pour effectuer des rotations precises avec le gyroscope.
                </p>
                <div class='mode-panel'>
                    <div style='display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;'>
                        <div style='flex: 1; min-width: 200px;'>
                            <label class='param-label'>Angle de rotation (degres)</label>
                            <input type='number' step='1' class='param-input' id='manualAngleInput' value='90'
                                   style='font-size: 1.1rem; font-weight: bold;'>
                            <small style='color: #888;'>Positif = gauche, Negatif = droite</small>
                        </div>
                        <div style='display: flex; gap: 10px;'>
                            <button class='control-btn' id='turnLeftBtn'>
                                ↺ Tourner a gauche
                            </button>
                            <button class='control-btn' id='turnRightBtn'>
                                ↻ Tourner a droite
                            </button>
                        </div>
                    </div>
                </div>
                <div style='margin-top: 15px;'>
                    <p class='param-label' style='margin-bottom: 8px;'>Rotations rapides :</p>
                    <div style='display: flex; gap: 8px; flex-wrap: wrap;'>
                        <button class='primary-btn' onclick='quickTurn(45)'>↺ 45° G</button>
                        <button class='primary-btn' onclick='quickTurn(90)'>↺ 90° G</button>
                        <button class='primary-btn' onclick='quickTurn(180)'>↺ 180°</button>
                        <button class='primary-btn' onclick='quickTurn(-90)'>↻ 90° D</button>
                        <button class='primary-btn' onclick='quickTurn(-45)'>↻ 45° D</button>
                    </div>
                </div>
            </div>

            <!-- Controles -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Controle</h3>
                <div style='text-align: center;'>
                    <button class='control-btn' id='startPidBtn'>▶️ Demarrer PID</button>
                    <button class='control-btn stop' id='stopPidBtn'>⛔ Arreter PID</button>
                    <button class='primary-btn' id='resetPidBtn'>🔄 Reinitialiser PID</button>
                </div>
            </div>

            <!-- Mode Step-by-Step -->
            <div class='tab-content accent'>
                <h3 class='tab-subtitle' style='color: #856404;'>🚶 Mode Avance: Step-by-Step</h3>
                <p class='tab-text' style='margin-bottom: 15px; color: #856404;'>
                    <strong>Mode pas a pas :</strong> Le robot avance par etapes, s'arrete pour que l'image soit nette,
                    puis attend votre autorisation pour continuer. Si la ligne est perdue, il la cherche automatiquement.
                </p>

                <div style='background: white; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 2px solid #FFD166;'>
                    <div style='display: flex; gap: 15px; align-items: center; margin-bottom: 15px;'>
                        <div style='flex: 1;'>
                            <div class='status-label'>Etat du mode Step</div>
                            <div class='status-value' id='stepModeStatus' style='color: #ccc;'>Arrete</div>
                        </div>
                        <div style='flex: 1;'>
                            <div class='status-label'>Etat de la machine</div>
                            <div class='status-value' id='stepMachineState' style='font-size: 14px;'>IDLE</div>
                        </div>
                        <div style='flex: 1;'>
                            <div class='status-label'>Etapes completees</div>
                            <div class='status-value' id='stepCount'>0</div>
                        </div>
                    </div>
                    <div style='display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;'>
                        <button class='control-btn' id='startStepModeBtn' style='background: #FFD166; color: #7a4f00; box-shadow: 0 4px 0 #c9a200;'>
                            ▶️ Demarrer Mode Step
                        </button>
                        <button class='control-btn stop' id='stopStepModeBtn'>
                            ⛔ Arreter Mode Step
                        </button>
                    </div>
                </div>

                <div class='approve-zone'>
                    <button class='approve-btn' id='approveStepBtn' disabled>
                        ✅ AUTORISER LA PROCHAINE ETAPE
                    </button>
                    <p style='margin-top: 10px; color: #555; font-size: 14px;'>
                        Cliquez pour permettre au robot d'avancer a la prochaine position
                    </p>
                    <div id='stepWaitingIndicator' style='margin-top: 10px; color: #2d6a4f; font-weight: bold; display: none;'>
                        ⏸️ En attente de votre autorisation...
                    </div>
                </div>
            </div>

            <!-- Statut temps reel -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Statut temps reel</h3>
                <div class='status-panel'>
                    <div class='status-grid'>
                        <div class='status-item'>
                            <div class='status-label'>Etat</div>
                            <div class='status-value' id='pidStatus'>Arrete</div>
                        </div>
                        <div class='status-item'>
                            <div class='status-label'>Erreur actuelle</div>
                            <div class='status-value' id='currentError'>0</div>
                        </div>
                        <div class='status-item'>
                            <div class='status-label'>Correction</div>
                            <div class='status-value' id='currentCorrection'>0</div>
                        </div>
                        <div class='status-item'>
                            <div class='status-label'>Vitesse G</div>
                            <div class='status-value' id='leftSpeed'>0</div>
                        </div>
                        <div class='status-item'>
                            <div class='status-label'>Vitesse D</div>
                            <div class='status-value' id='rightSpeed'>0</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Terminal de logs -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Logs</h3>
                <div class='log-terminal' id='logTerminal'>Terminal PID...</div>
            </div>

            <!-- Flux video -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Flux video</h3>
                <div class='live-feed'>
                    <p id='videoPlaceholder' style='color:#888; font-style:italic;'>Camera inactive — demarrez le PID ou le mode Step pour activer le flux.</p>
                    <img id='videoFeed' src='' alt='Flux video' style='display:none;'
                         onerror="this.style.display='none'; document.getElementById('videoPlaceholder').style.display='block';">
                </div>
            </div>
        </div>
    </div>

    <div class='toast-container' id='toastContainer'></div>

    <script>
    // Variables globales
    var pidRunning = false;
    var statusInterval = null;
    var rotationMode = true;

    // Rafraîchir le flux vidéo (après démarrage caméra)
    function refreshVideoFeed() {{
        var img = document.getElementById('videoFeed');
        var placeholder = document.getElementById('videoPlaceholder');
        if (img) {{
            setTimeout(function() {{
                img.src = '/video?overlay=pid&_=' + Date.now();
                img.style.display = '';
                if (placeholder) placeholder.style.display = 'none';
            }}, 500);
        }}
    }}

    // Toast notifications
    function showToast(message, type, duration) {{
        type = type || 'info';
        duration = duration || 4000;
        var container = document.getElementById('toastContainer');
        if (!container) return;
        var toast = document.createElement('div');
        toast.className = 'toast ' + type;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(function() {{ toast.classList.add('show'); }}, 10);
        setTimeout(function() {{
            toast.classList.remove('show');
            setTimeout(function() {{ container.removeChild(toast); }}, 350);
        }}, duration);
    }}

    // Ajouter une ligne au terminal
    function appendLog(message) {{
        var terminal = document.getElementById('logTerminal');
        if (!terminal) return;
        var timestamp = new Date().toLocaleTimeString();
        terminal.textContent += '[' + timestamp + '] ' + message + '\\n';
        terminal.scrollTop = terminal.scrollHeight;
    }}

    // Basculer en mode rotation
    function setRotationMode() {{
        rotationMode = true;
        document.getElementById('rotationModeBtn').style.background = '#A8E6CF';
        document.getElementById('driveModeBtn').style.background = '#ccc';
        updateParams();
        appendLog('Mode ROTATION activé - Le Zumi tourne sur place');
        showToast('Mode Rotation activé', 'info');
    }}

    // Basculer en mode avance
    function setDriveMode() {{
        rotationMode = false;
        document.getElementById('rotationModeBtn').style.background = '#ccc';
        document.getElementById('driveModeBtn').style.background = '#A8E6CF';
        updateParams();
        appendLog('Mode AVANCE activé - Le Zumi suit la ligne');
        showToast('Mode Avance activé', 'info');
    }}

    // Mettre à jour les paramètres PID
    function updateParams() {{
        var params = {{
            kp: parseFloat(document.getElementById('kpInput').value),
            ki: parseFloat(document.getElementById('kiInput').value),
            kd: parseFloat(document.getElementById('kdInput').value),
            base_speed: parseInt(document.getElementById('baseSpeedInput').value),
            max_correction: parseInt(document.getElementById('maxCorrectionInput').value),
            rotation_mode: rotationMode,
            angle_scale: parseFloat(document.getElementById('angleScaleInput').value),
            max_angle: parseFloat(document.getElementById('maxAngleInput').value),
            min_angle_threshold: parseFloat(document.getElementById('minAngleThresholdInput').value)
        }};

        fetch('/pid/update_params', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(params)
        }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            var mode = rotationMode? 'ROTATION' : 'AVANCE';
            appendLog('Paramètres mis à jour: Kp=' + params.kp + ', Ki=' + params.ki + ', Kd=' + params.kd + ', Mode=' + mode);
            if (rotationMode) {{
                appendLog('  Angle: scale=' + params.angle_scale + ', max=' + params.max_angle + '°, min=' + params.min_angle_threshold + '°');
            }}
            showToast('Paramètres PID mis à jour!', 'success');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la mise à jour', 'error');
        }});
    }}

    // Mettre à jour les paramètres du détecteur de ligne
    function updateLineDetectorParams() {{
        var params = {{
            white_threshold: parseInt(document.getElementById('whiteThresholdInput').value),
            min_area: parseInt(document.getElementById('minAreaInput').value),
            offset_ratio: parseFloat(document.getElementById('offsetRatioInput').value)
        }};

        fetch('/line_detector/update_params', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(params)
        }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            appendLog('Détecteur de ligne mis à jour: Seuil=' + params.white_threshold + ', Aire=' + params.min_area);
            showToast('Paramètres du détecteur mis à jour!', 'success');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la mise à jour', 'error');
        }});
    }}

    // Démarrer le PID
    function startPid() {{
        fetch('/pid/start', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            pidRunning = true;
            document.getElementById('pidStatus').textContent = 'Actif';
            document.getElementById('pidStatus').style.color = '#2d6a4f';
            appendLog('PID démarré');
            showToast('PID démarré!', 'success');
            refreshVideoFeed();
            startStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors du démarrage', 'error');
        }});
    }}

    // Arrêter le PID
    function stopPid() {{
        fetch('/pid/stop', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            pidRunning = false;
            document.getElementById('pidStatus').textContent = 'Arrêté';
            document.getElementById('pidStatus').style.color = '#7a1f1f';
            appendLog('PID arrêté');
            showToast('PID arrêté', 'info');
            stopStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de l arrêt', 'error');
        }});
    }}

    // Réinitialiser le PID
    function resetPid() {{
        fetch('/pid/reset', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            appendLog('PID réinitialisé');
            showToast('PID réinitialisé', 'info');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la réinitialisation', 'error');
        }});
    }}

    // Polling du statut
    function startStatusPolling() {{
        if (statusInterval) return;
        statusInterval = setInterval(function() {{
            fetch('/pid/status')
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                if (data.error !== undefined) {{
                    document.getElementById('currentError').textContent = parseFloat(data.error).toFixed(1);
                }}
                if (data.correction !== undefined) {{
                    document.getElementById('currentCorrection').textContent = parseFloat(data.correction).toFixed(1);
                }}
                if (data.left_speed !== undefined) {{
                    document.getElementById('leftSpeed').textContent = data.left_speed;
                }}
                if (data.right_speed !== undefined) {{
                    document.getElementById('rightSpeed').textContent = data.right_speed;
                }}
            }})
            .catch(function(err) {{ console.error('Status polling error:', err); }});
        }}, 200);
    }}

    function stopStatusPolling() {{
        if (statusInterval) {{
            clearInterval(statusInterval);
            statusInterval = null;
        }}
    }}

    // ========== MODE STEP-BY-STEP ==========
    var stepModeRunning = false;
    var stepStatusInterval = null;

    function startStepMode() {{
        fetch('/pid/step_mode/start', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            stepModeRunning = true;
            document.getElementById('stepModeStatus').textContent = 'Actif';
            document.getElementById('stepModeStatus').style.color = '#2d6a4f';
            document.getElementById('approveStepBtn').disabled = false;
            appendLog('Mode Step-by-Step démarré');
            showToast('Mode Step activé!', 'success');
            refreshVideoFeed();
            startStepStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors du démarrage', 'error');
        }});
    }}

    function stopStepMode() {{
        fetch('/pid/step_mode/stop', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            stepModeRunning = false;
            document.getElementById('stepModeStatus').textContent = 'Arrêté';
            document.getElementById('stepModeStatus').style.color = '#888';
            document.getElementById('approveStepBtn').disabled = true;
            document.getElementById('stepWaitingIndicator').style.display = 'none';
            appendLog('Mode Step-by-Step arrêté');
            showToast('Mode Step arrêté', 'info');
            stopStepStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de l arrêt', 'error');
        }});
    }}

    function approveNextStep() {{
        fetch('/pid/step_mode/approve', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            appendLog('✓ Prochaine étape autorisée');
            showToast('Étape autorisée!', 'success');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de l approbation', 'error');
        }});
    }}

    function startStepStatusPolling() {{
        if (stepStatusInterval) return;
        stepStatusInterval = setInterval(function() {{
            fetch('/pid/step_mode/status')
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                // Mettre à jour l'état de la machine
                var state = data.state || 'IDLE';
                document.getElementById('stepMachineState').textContent = state;
                
                // Mettre à jour le compteur d'étapes
                document.getElementById('stepCount').textContent = data.step_count || 0;
                
                // Afficher l'indicateur d'attente si nécessaire
                if (data.waiting_approval) {{
                    document.getElementById('stepWaitingIndicator').style.display = 'block';
                    document.getElementById('approveStepBtn').style.animation = 'pulse 1.5s infinite';
                }} else {{
                    document.getElementById('stepWaitingIndicator').style.display = 'none';
                    document.getElementById('approveStepBtn').style.animation = 'none';
                }}
                
                // Mettre à jour les valeurs de debug
                if (data.line_offset !== undefined) {{
                    document.getElementById('currentError').textContent = parseFloat(data.line_offset).toFixed(1);
                }}
                if (data.left_speed !== undefined) {{
                    document.getElementById('leftSpeed').textContent = data.left_speed;
                }}
                if (data.right_speed !== undefined) {{
                    document.getElementById('rightSpeed').textContent = data.right_speed;
                }}
            }})
            .catch(function(err) {{ console.error('Step status polling error:', err); }});
        }}, 200);
    }}

    function stopStepStatusPolling() {{
        if (stepStatusInterval) {{
            clearInterval(stepStatusInterval);
            stepStatusInterval = null;
        }}
    }}

    // Contrôle manuel de rotation
    function manualTurn(angle) {{
        appendLog('Rotation manuelle: ' + angle + '° demandée...');
        
        fetch('/zumi/turn', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ angle: angle }})
        }})
        .then(function(r) {{ 
            if (!r.ok) throw new Error('Erreur ' + r.status); 
            return r.json(); 
        }})
        .then(function(data) {{
            var msg = data.message || 'Rotation complétée';
            appendLog('✓ ' + msg);
            showToast(msg, 'success');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la rotation', 'error');
        }});
    }}

    function quickTurn(angle) {{
        manualTurn(angle);
    }}

    function turnLeft() {{
        var angle = parseFloat(document.getElementById('manualAngleInput').value) || 90;
        manualTurn(Math.abs(angle));  // Positif = gauche
    }}

    function turnRight() {{
        var angle = parseFloat(document.getElementById('manualAngleInput').value) || 90;
        manualTurn(-Math.abs(angle));  // Négatif = droite
    }}

    // Navigation avec fermeture propre du PID et caméra
    function navigateTo(path) {{
        try {{
            stopStatusPolling();
            stopStepStatusPolling();
            
            var promises = [];
            
            // Arrêter le PID s'il est actif
            if (pidRunning) {{
                promises.push(fetch('/pid/stop', {{ method: 'POST' }}));
            }}
            
            // Arrêter le mode step s'il est actif
            if (stepModeRunning) {{
                promises.push(fetch('/pid/step_mode/stop', {{ method: 'POST' }}));
            }}
            
            // Fermer la caméra
            promises.push(fetch('/close_camera', {{ method: 'POST' }}));
            
            // Attendre la fin de tous les arrêts avant de naviguer
            if (promises.length > 0) {{
                Promise.all(promises)
                    .then(function() {{ location.href = path; }})
                    .catch(function(err) {{ 
                        console.error('Erreur lors de la fermeture:', err);
                        location.href = path; 
                    }});
            }} else {{
                location.href = path;
            }}
        }} catch (e) {{
            console.error('Erreur navigateTo:', e);
            location.href = path;
        }}
    }}

    // Active l'état du bouton d'onglet selon l'URL courante
    (function() {{
        var norm = function(p) {{ return (p || '').replace(/\\/+$/,'') || '/'; }};
        var here = norm(location.pathname);
        var btns = document.querySelectorAll('.tab-nav .primary-btn');
        Array.prototype.forEach.call(btns, function(btn) {{
            var p = norm(btn.getAttribute('data-path'));
            if (p === here) btn.classList.add('active');
        }});
    }})();

    // Event listeners
    window.addEventListener('DOMContentLoaded', function() {{
        // Boutons de contrôle
        document.getElementById('updateParamsBtn').addEventListener('click', updateParams);
        document.getElementById('startPidBtn').addEventListener('click', startPid);
        document.getElementById('stopPidBtn').addEventListener('click', stopPid);
        document.getElementById('resetPidBtn').addEventListener('click', resetPid);
        
        // Boutons de mode
        document.getElementById('rotationModeBtn').addEventListener('click', setRotationMode);
        document.getElementById('driveModeBtn').addEventListener('click', setDriveMode);
        
        // Bouton détecteur de ligne
        document.getElementById('updateLineDetectorBtn').addEventListener('click', updateLineDetectorParams);

        // Boutons de rotation manuelle
        document.getElementById('turnLeftBtn').addEventListener('click', turnLeft);
        document.getElementById('turnRightBtn').addEventListener('click', turnRight);

        // Boutons du mode step-by-step
        document.getElementById('startStepModeBtn').addEventListener('click', startStepMode);
        document.getElementById('stopStepModeBtn').addEventListener('click', stopStepMode);
        document.getElementById('approveStepBtn').addEventListener('click', approveNextStep);

        // Charger les paramètres initiaux
        fetch('/pid/get_params')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            document.getElementById('kpInput').value = data.kp || 0.1;
            document.getElementById('kiInput').value = data.ki || 0.0;
            document.getElementById('kdInput').value = data.kd || 0.05;
            document.getElementById('baseSpeedInput').value = data.base_speed || 20;
            document.getElementById('maxCorrectionInput').value = data.max_correction || 30;
            
            // Charger les paramètres d'angle
            document.getElementById('angleScaleInput').value = data.angle_scale || 0.3;
            document.getElementById('maxAngleInput').value = data.max_angle || 45;
            document.getElementById('minAngleThresholdInput').value = data.min_angle_threshold || 2;
            
            rotationMode = data.rotation_mode !== undefined ? data.rotation_mode : true;
            if (rotationMode) {{
                document.getElementById('rotationModeBtn').style.background = '#A8E6CF';
                document.getElementById('driveModeBtn').style.background = '#ccc';
            }} else {{
                document.getElementById('rotationModeBtn').style.background = '#ccc';
                document.getElementById('driveModeBtn').style.background = '#A8E6CF';
            }}
            appendLog('Paramètres chargés depuis le serveur');
        }})
        .catch(function(err) {{
            appendLog('Impossible de charger les paramètres: ' + err.message);
        }});
        
        // Charger les paramètres du détecteur
        fetch('/line_detector/get_params')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            document.getElementById('whiteThresholdInput').value = data.white_threshold || 200;
            document.getElementById('minAreaInput').value = data.min_area || 300;
            document.getElementById('offsetRatioInput').value = data.offset_ratio || 0.6;
            appendLog('Paramètres du détecteur chargés');
        }})
        .catch(function(err) {{
            appendLog('Impossible de charger les paramètres du détecteur: ' + err.message);
        }});

        // Vérifier si la caméra tourne déjà
        fetch('/status')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            if (data.camera_running) {{
                refreshVideoFeed();
                appendLog('Caméra déjà active');
            }}
        }})
        .catch(function(err) {{ /* ignore */ }});
    }});

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {{
        stopStatusPolling();
        stopStepStatusPolling();
        if (pidRunning) {{
            fetch('/pid/stop', {{ method: 'POST' }});
        }}
        if (stepModeRunning) {{
            fetch('/pid/step_mode/stop', {{ method: 'POST' }});
        }}
        if (document.getElementById('videoFeed').src) {{
            fetch('/close_camera', {{ method: 'POST' }});
        }}
    }});
    </script>
    </body></html>
    """.format(title=title)

    return html
