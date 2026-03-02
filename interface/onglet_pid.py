#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_pid.py
# ------------------
"""Page web pour le contrÃ´le PID du suivi de ligne."""

def render_pid_tab(title="Asservissement PID"):
    """Retourne une page HTML complÃ¨te pour le contrÃ´le PID."""

    html = """<!DOCTYPE html><html lang='fr'>
    <head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>{title}</title>
    <link rel='icon' href='data:,'>
    <style>
    body {{
        margin: 0; padding: 0;
        width: 100vw; height: 100vh;
        font-family: Arial, sans-serif;
        background: linear-gradient(135deg, #40E0D0, #00BFFF);
        color: #333; display: flex; flex-direction: column;
    }}

    .container {{
        display: flex; justify-content: center; align-items: flex-start;
        padding: 20px; height: calc(100vh - 40px);
        overflow-y: auto;
    }}

    .tab-shell {{
        background: rgba(255,255,255,0.92);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 0 15px rgba(0,0,0,0.12);
        width: min(1200px, 100%);
    }}

    .tab-header {{
        display: flex; align-items: center;
        margin-bottom: 12px;
    }}

    .tab-nav {{
        display: flex; align-items: center;
        gap: 4px;
        margin-left: auto;
    }}

    .tab-content {{
        border: 2px solid #bcdffb;
        border-radius: 12px;
        padding: 16px;
        min-height: 200px;
        background: #f7fbff;
        margin-bottom: 12px;
    }}

    .tab-title {{
        font-size: 22px; font-weight: bold; margin: 0;
    }}

    .tab-subtitle {{
        font-size: 18px; font-weight: bold; margin: 0 0 12px 0;
    }}

    .tab-text {{
        font-size: 16px; font-weight: normal; margin: 0;
    }}

    .primary-btn {{
        background: #007acc; color: white; border: none;
        padding: 10px 18px; border-radius: 10px;
        cursor: pointer; font-size: 15px;
    }}

    .primary-btn:hover {{ background: #005fa3; }}

    .primary-btn.active {{
        background: #00528a;
        box-shadow: 0 0 0 2px rgba(0,0,0,0.06) inset;
    }}

    .control-btn {{
        background: #28a745; color: white; border: none;
        padding: 12px 24px; border-radius: 10px;
        cursor: pointer; font-size: 16px;
        margin: 5px;
    }}

    .control-btn:hover {{ background: #218838; }}

    .control-btn.stop {{
        background: #dc3545;
    }}

    .control-btn.stop:hover {{ background: #bd2130; }}

    .control-btn:disabled {{
        background: #6c757d;
        cursor: not-allowed;
    }}

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
        font-size: 14px;
    }}

    .param-input {{
        padding: 8px;
        border: 2px solid #007acc;
        border-radius: 8px;
        font-size: 14px;
    }}

    .param-input:focus {{
        outline: none;
        border-color: #005fa3;
        box-shadow: 0 0 5px rgba(0,122,204,0.3);
    }}

    .status-panel {{
        background: #e9ecef;
        border-radius: 10px;
        padding: 15px;
        margin: 15px 0;
    }}

    .status-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
    }}

    .status-item {{
        background: white;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }}

    .status-label {{
        font-size: 12px;
        color: #666;
    }}

    .status-value {{
        font-size: 18px;
        font-weight: bold;
        color: #007acc;
    }}

    .log-terminal {{
        background: #000;
        color: #0f0;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        border-radius: 10px;
        padding: 10px;
        height: 200px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}

    .live-feed {{
        width: 100%;
        margin-top: 15px;
        text-align: center;
    }}

    .live-feed img {{
        width: 70%;
        max-width: 640px;
        height: auto;
        border-radius: 8px;
        border: 4px solid #00BFFF;
    }}

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
        border-radius: 8px;
        color: #fff;
        font-size: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        opacity: 0;
        transform: translateX(80px);
        transition: opacity 0.3s, transform 0.3s;
    }}

    .toast.show {{ opacity: 1; transform: translateX(0); }}
    .toast.warning {{ background: #e67e22; }}
    .toast.error {{ background: #e74c3c; }}
    .toast.info {{ background: #3498db; }}
    .toast.success {{ background: #27ae60; }}

    @keyframes pulse {{
        0% {{ transform: scale(1); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
        50% {{ transform: scale(1.05); box-shadow: 0 6px 20px rgba(40, 167, 69, 0.5); }}
        100% {{ transform: scale(1); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
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
                    <button class='primary-btn' data-path="/pid" onclick="navigateTo('/pid')">PID</button>
                    <button class='primary-btn' data-path="/onglet_template" onclick="navigateTo('/onglet_template')">Template</button>
                </div>
            </div>

            <!-- ParamÃ¨tres PID -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>ParamÃ¨tres PID</h3>
                
                <!-- Mode de contrÃ´le -->
                <div style='margin-bottom: 20px; padding: 15px; background: #e3f2fd; border-radius: 10px;'>
                    <label style='font-weight: bold; font-size: 16px; display: block; margin-bottom: 10px;'>
                        Mode de contrÃ´le
                    </label>
                    <div style='display: flex; gap: 10px;'>
                        <button class='control-btn' id='rotationModeBtn' style='flex: 1;'>
                            ðŸ”„ Mode Rotation (Tuning)
                        </button>
                        <button class='control-btn' id='driveModeBtn' style='flex: 1; background: #6c757d;'>
                            âž¡ï¸ Mode Avance (Suivi)
                        </button>
                    </div>
                    <p style='margin-top: 10px; font-size: 13px; color: #666;'>
                        <strong>Mode Rotation:</strong> Le Zumi tourne sur place pour centrer la ligne (idÃ©al pour rÃ©gler Kp, Ki, Kd).<br>
                        <strong>Mode Avance:</strong> Le Zumi avance en suivant la ligne.
                    </p>
                </div>
                
                <div class='param-grid'>
                    <div class='param-item'>
                        <label class='param-label'>Kp (Proportionnel)</label>
                        <input type='number' step='0.01' class='param-input' id='kpInput' value='0.1'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Ki (IntÃ©gral)</label>
                        <input type='number' step='0.001' class='param-input' id='kiInput' value='0.0'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Kd (DÃ©rivÃ©)</label>
                        <input type='number' step='0.01' class='param-input' id='kdInput' value='0.05'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Vitesse de base</label>
                        <input type='number' step='1' class='param-input' id='baseSpeedInput' value='20'>
                        <small style='color: #666;'>(utilisÃ© uniquement en mode avance)</small>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Correction max</label>
                        <input type='number' step='1' class='param-input' id='maxCorrectionInput' value='30'>
                    </div>
                </div>
                
                <!-- ParamÃ¨tres de calcul d'angle pour le mode rotation -->
                <div style='margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 10px; border: 2px solid #ffc107;'>
                    <h4 style='margin: 0 0 10px 0; color: #856404;'>âš™ï¸ ParamÃ¨tres de rotation (Mode Rotation uniquement)</h4>
                    <p style='font-size: 13px; color: #856404; margin-bottom: 15px;'>
                        Ces paramÃ¨tres contrÃ´lent le calcul de l'angle lorsque le mode rotation est activÃ©.
                    </p>
                    <div class='param-grid'>
                        <div class='param-item'>
                            <label class='param-label'>Ã‰chelle d'angle (angle_scale)</label>
                            <input type='number' step='0.01' class='param-input' id='angleScaleInput' value='0.3'>
                            <small style='color: #666;'>Conversion erreur â†’ angle (0.3 = 100px â†’ 30Â°)</small>
                        </div>
                        <div class='param-item'>
                            <label class='param-label'>Angle maximal (degrÃ©s)</label>
                            <input type='number' step='1' class='param-input' id='maxAngleInput' value='45'>
                            <small style='color: #666;'>Limite les rotations brusques</small>
                        </div>
                        <div class='param-item'>
                            <label class='param-label'>Seuil minimal (degrÃ©s)</label>
                            <input type='number' step='0.5' class='param-input' id='minAngleThresholdInput' value='2'>
                            <small style='color: #666;'>Angle minimum pour dÃ©clencher une rotation</small>
                        </div>
                    </div>
                </div>
                
                <button class='primary-btn' id='updateParamsBtn'>ðŸ“ Mettre Ã  jour les paramÃ¨tres</button>
            </div>

            <!-- ParamÃ¨tres du dÃ©tecteur de ligne -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>ParamÃ¨tres du dÃ©tecteur de ligne</h3>
                <div class='param-grid'>
                    <div class='param-item'>
                        <label class='param-label'>Seuil blanc (0-255)</label>
                        <input type='number' min='0' max='255' step='5' class='param-input' id='whiteThresholdInput' value='200'>
                        <small style='color: #666;'>Plus Ã©levÃ© = dÃ©tecte seulement le blanc pur</small>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Aire minimale (pixels)</label>
                        <input type='number' min='100' max='1000' step='50' class='param-input' id='minAreaInput' value='300'>
                        <small style='color: #666;'>Ignore les petits objets blancs</small>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Zone de dÃ©tection (0.0-1.0)</label>
                        <input type='number' min='0' max='1' step='0.05' class='param-input' id='offsetRatioInput' value='0.6'>
                        <small style='color: #666;'>0.6 = cherche dans les 40% infÃ©rieurs</small>
                    </div>
                </div>
                <button class='primary-btn' id='updateLineDetectorBtn'>ðŸ“ Mettre Ã  jour le dÃ©tecteur</button>
            </div>

            <!-- ContrÃ´le Manuel de Rotation -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>ðŸŽ® ContrÃ´le Manuel de Rotation</h3>
                <p class='tab-text' style='margin-bottom: 15px; color: #666;'>
                    Utilisez la fonction turn() du Zumi pour effectuer des rotations prÃ©cises avec le gyroscope.
                </p>
                
                <div style='background: #e8f4f8; padding: 15px; border-radius: 10px; margin-bottom: 15px;'>
                    <div style='display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;'>
                        <div style='flex: 1; min-width: 200px;'>
                            <label class='param-label'>Angle de rotation (degrÃ©s)</label>
                            <input type='number' step='1' class='param-input' id='manualAngleInput' value='90' 
                                   style='font-size: 18px; font-weight: bold;'>
                            <small style='color: #666;'>Positif = gauche, NÃ©gatif = droite</small>
                        </div>
                        <div style='display: flex; gap: 10px;'>
                            <button class='control-btn' id='turnLeftBtn' style='background: #17a2b8;'>
                                â†º Tourner Ã  gauche
                            </button>
                            <button class='control-btn' id='turnRightBtn' style='background: #17a2b8;'>
                                â†» Tourner Ã  droite
                            </button>
                        </div>
                    </div>
                </div>
                
                <div style='margin-top: 15px;'>
                    <p class='param-label' style='margin-bottom: 8px;'>Rotations rapides :</p>
                    <div style='display: flex; gap: 8px; flex-wrap: wrap;'>
                        <button class='primary-btn' onclick='quickTurn(45)'>â†º 45Â° G</button>
                        <button class='primary-btn' onclick='quickTurn(90)'>â†º 90Â° G</button>
                        <button class='primary-btn' onclick='quickTurn(180)'>â†º 180Â°</button>
                        <button class='primary-btn' onclick='quickTurn(-90)'>â†» 90Â° D</button>
                        <button class='primary-btn' onclick='quickTurn(-45)'>â†» 45Â° D</button>
                    </div>
                </div>
            </div>

            <!-- ContrÃ´les -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>ContrÃ´le</h3>
                <div style='text-align: center;'>
                    <button class='control-btn' id='startPidBtn'>â–¶ï¸ DÃ©marrer PID</button>
                    <button class='control-btn stop' id='stopPidBtn'>â›” ArrÃªter PID</button>
                    <button class='primary-btn' id='resetPidBtn'>ðŸ”„ RÃ©initialiser PID</button>
                </div>
            </div>

            <!-- Mode Step-by-Step (AvancÃ©) -->
            <div class='tab-content' style='border: 3px solid #ffc107; background: #fffbf0;'>
                <h3 class='tab-subtitle' style='color: #856404;'>ðŸš¶ Mode AvancÃ©: Step-by-Step</h3>
                <p class='tab-text' style='margin-bottom: 15px; color: #856404;'>
                    <strong>Mode pas Ã  pas :</strong> Le robot avance par Ã©tapes, s'arrÃªte pour que l'image soit nette, 
                    puis attend votre autorisation pour continuer. Si la ligne est perdue, il la cherche automatiquement.
                </p>
                
                <div style='background: #fff; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 2px solid #ffc107;'>
                    <div style='display: flex; gap: 15px; align-items: center; margin-bottom: 15px;'>
                        <div style='flex: 1;'>
                            <div class='status-label'>Ã‰tat du mode Step</div>
                            <div class='status-value' id='stepModeStatus' style='color: #6c757d;'>ArrÃªtÃ©</div>
                        </div>
                        <div style='flex: 1;'>
                            <div class='status-label'>Ã‰tat de la machine</div>
                            <div class='status-value' id='stepMachineState' style='font-size: 14px;'>IDLE</div>
                        </div>
                        <div style='flex: 1;'>
                            <div class='status-label'>Ã‰tapes complÃ©tÃ©es</div>
                            <div class='status-value' id='stepCount'>0</div>
                        </div>
                    </div>
                    
                    <div style='display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;'>
                        <button class='control-btn' id='startStepModeBtn' style='background: #ffc107; color: #000;'>
                            â–¶ï¸ DÃ©marrer Mode Step
                        </button>
                        <button class='control-btn stop' id='stopStepModeBtn'>
                            â›” ArrÃªter Mode Step
                        </button>
                    </div>
                </div>
                
                <!-- Bouton d'autorisation d'Ã©tape (gros et visible) -->
                <div style='background: #28a745; padding: 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.2);'>
                    <button class='control-btn' id='approveStepBtn' 
                            style='background: #fff; color: #28a745; font-size: 20px; font-weight: bold; 
                                   padding: 20px 40px; border: 4px solid #28a745; cursor: pointer;'
                            disabled>
                        âœ… AUTORISER LA PROCHAINE Ã‰TAPE
                    </button>
                    <p style='margin-top: 10px; color: #fff; font-size: 14px;'>
                        Cliquez pour permettre au robot d'avancer Ã  la prochaine position
                    </p>
                    <div id='stepWaitingIndicator' style='margin-top: 10px; color: #fff; font-weight: bold; display: none;'>
                        â¸ï¸ En attente de votre autorisation...
                    </div>
                </div>
            </div>

            <!-- Statut temps rÃ©el -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Statut temps rÃ©el</h3>
                <div class='status-panel'>
                    <div class='status-grid'>
                        <div class='status-item'>
                            <div class='status-label'>Ã‰tat</div>
                            <div class='status-value' id='pidStatus'>ArrÃªtÃ©</div>
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

            <!-- Flux vidÃ©o -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Flux vidÃ©o</h3>
                <div class='live-feed'>
                    <img id='videoFeed' src='/video' alt='Flux vidÃ©o'>
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
        document.getElementById('rotationModeBtn').style.background = '#28a745';
        document.getElementById('driveModeBtn').style.background = '#6c757d';
        updateParams();
        appendLog('Mode ROTATION activÃ© - Le Zumi tourne sur place');
        showToast('Mode Rotation activÃ©', 'info');
    }}

    // Basculer en mode avance
    function setDriveMode() {{
        rotationMode = false;
        document.getElementById('rotationModeBtn').style.background = '#6c757d';
        document.getElementById('driveModeBtn').style.background = '#28a745';
        updateParams();
        appendLog('Mode AVANCE activÃ© - Le Zumi suit la ligne');
        showToast('Mode Avance activÃ©', 'info');
    }}

    // Mettre Ã  jour les paramÃ¨tres PID
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
            appendLog('ParamÃ¨tres mis Ã  jour: Kp=' + params.kp + ', Ki=' + params.ki + ', Kd=' + params.kd + ', Mode=' + mode);
            if (rotationMode) {{
                appendLog('  Angle: scale=' + params.angle_scale + ', max=' + params.max_angle + 'Â°, min=' + params.min_angle_threshold + 'Â°');
            }}
            showToast('ParamÃ¨tres PID mis Ã  jour!', 'success');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la mise Ã  jour', 'error');
        }});
    }}

    // Mettre Ã  jour les paramÃ¨tres du dÃ©tecteur de ligne
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
            appendLog('DÃ©tecteur de ligne mis Ã  jour: Seuil=' + params.white_threshold + ', Aire=' + params.min_area);
            showToast('ParamÃ¨tres du dÃ©tecteur mis Ã  jour!', 'success');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la mise Ã  jour', 'error');
        }});
    }}

    // DÃ©marrer le PID
    function startPid() {{
        fetch('/pid/start', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            pidRunning = true;
            document.getElementById('pidStatus').textContent = 'Actif';
            document.getElementById('pidStatus').style.color = '#28a745';
            appendLog('PID dÃ©marrÃ©');
            showToast('PID dÃ©marrÃ©!', 'success');
            startStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors du dÃ©marrage', 'error');
        }});
    }}

    // ArrÃªter le PID
    function stopPid() {{
        fetch('/pid/stop', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            pidRunning = false;
            document.getElementById('pidStatus').textContent = 'ArrÃªtÃ©';
            document.getElementById('pidStatus').style.color = '#dc3545';
            appendLog('PID arrÃªtÃ©');
            showToast('PID arrÃªtÃ©', 'info');
            stopStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de l arrÃªt', 'error');
        }});
    }}

    // RÃ©initialiser le PID
    function resetPid() {{
        fetch('/pid/reset', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            appendLog('PID rÃ©initialisÃ©');
            showToast('PID rÃ©initialisÃ©', 'info');
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de la rÃ©initialisation', 'error');
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
            document.getElementById('stepModeStatus').style.color = '#28a745';
            document.getElementById('approveStepBtn').disabled = false;
            appendLog('Mode Step-by-Step dÃ©marrÃ©');
            showToast('Mode Step activÃ©!', 'success');
            startStepStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors du dÃ©marrage', 'error');
        }});
    }}

    function stopStepMode() {{
        fetch('/pid/step_mode/stop', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            stepModeRunning = false;
            document.getElementById('stepModeStatus').textContent = 'ArrÃªtÃ©';
            document.getElementById('stepModeStatus').style.color = '#6c757d';
            document.getElementById('approveStepBtn').disabled = true;
            document.getElementById('stepWaitingIndicator').style.display = 'none';
            appendLog('Mode Step-by-Step arrÃªtÃ©');
            showToast('Mode Step arrÃªtÃ©', 'info');
            stopStepStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de l arrÃªt', 'error');
        }});
    }}

    function approveNextStep() {{
        fetch('/pid/step_mode/approve', {{ method: 'POST' }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            appendLog('âœ“ Prochaine Ã©tape autorisÃ©e');
            showToast('Ã‰tape autorisÃ©e!', 'success');
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
                // Mettre Ã  jour l'Ã©tat de la machine
                var state = data.state || 'IDLE';
                document.getElementById('stepMachineState').textContent = state;
                
                // Mettre Ã  jour le compteur d'Ã©tapes
                document.getElementById('stepCount').textContent = data.step_count || 0;
                
                // Afficher l'indicateur d'attente si nÃ©cessaire
                if (data.waiting_approval) {{
                    document.getElementById('stepWaitingIndicator').style.display = 'block';
                    document.getElementById('approveStepBtn').style.animation = 'pulse 1.5s infinite';
                }} else {{
                    document.getElementById('stepWaitingIndicator').style.display = 'none';
                    document.getElementById('approveStepBtn').style.animation = 'none';
                }}
                
                // Mettre Ã  jour les valeurs de debug
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

    // ContrÃ´le manuel de rotation
    function manualTurn(angle) {{
        appendLog('Rotation manuelle: ' + angle + 'Â° demandÃ©e...');
        
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
            var msg = data.message || 'Rotation complÃ©tÃ©e';
            appendLog('âœ“ ' + msg);
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
        manualTurn(-Math.abs(angle));  // NÃ©gatif = droite
    }}

    // Navigation
    function navigateTo(path) {{
        stopStatusPolling();
        stopStepStatusPolling();
        
        var promises = [];
        if (pidRunning) {{
            promises.push(fetch('/pid/stop', {{ method: 'POST' }}));
        }}
        if (stepModeRunning) {{
            promises.push(fetch('/pid/step_mode/stop', {{ method: 'POST' }}));
        }}
        
        if (promises.length > 0) {{
            Promise.all(promises)
                .then(function() {{ location.href = path; }})
                .catch(function() {{ location.href = path; }});
        }} else {{
            location.href = path;
        }}
    }}

    // Active l'Ã©tat du bouton d'onglet selon l'URL courante
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
        // Boutons de contrÃ´le
        document.getElementById('updateParamsBtn').addEventListener('click', updateParams);
        document.getElementById('startPidBtn').addEventListener('click', startPid);
        document.getElementById('stopPidBtn').addEventListener('click', stopPid);
        document.getElementById('resetPidBtn').addEventListener('click', resetPid);
        
        // Boutons de mode
        document.getElementById('rotationModeBtn').addEventListener('click', setRotationMode);
        document.getElementById('driveModeBtn').addEventListener('click', setDriveMode);
        
        // Bouton dÃ©tecteur de ligne
        document.getElementById('updateLineDetectorBtn').addEventListener('click', updateLineDetectorParams);

        // Boutons de rotation manuelle
        document.getElementById('turnLeftBtn').addEventListener('click', turnLeft);
        document.getElementById('turnRightBtn').addEventListener('click', turnRight);

        // Boutons du mode step-by-step
        document.getElementById('startStepModeBtn').addEventListener('click', startStepMode);
        document.getElementById('stopStepModeBtn').addEventListener('click', stopStepMode);
        document.getElementById('approveStepBtn').addEventListener('click', approveNextStep);

        // Charger les paramÃ¨tres initiaux
        fetch('/pid/get_params')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            document.getElementById('kpInput').value = data.kp || 0.1;
            document.getElementById('kiInput').value = data.ki || 0.0;
            document.getElementById('kdInput').value = data.kd || 0.05;
            document.getElementById('baseSpeedInput').value = data.base_speed || 20;
            document.getElementById('maxCorrectionInput').value = data.max_correction || 30;
            
            // Charger les paramÃ¨tres d'angle
            document.getElementById('angleScaleInput').value = data.angle_scale || 0.3;
            document.getElementById('maxAngleInput').value = data.max_angle || 45;
            document.getElementById('minAngleThresholdInput').value = data.min_angle_threshold || 2;
            
            rotationMode = data.rotation_mode !== undefined ? data.rotation_mode : true;
            if (rotationMode) {{
                document.getElementById('rotationModeBtn').style.background = '#28a745';
                document.getElementById('driveModeBtn').style.background = '#6c757d';
            }} else {{
                document.getElementById('rotationModeBtn').style.background = '#6c757d';
                document.getElementById('driveModeBtn').style.background = '#28a745';
            }}
            
            appendLog('ParamÃ¨tres chargÃ©s depuis le serveur');
        }})
        .catch(function(err) {{
            appendLog('Impossible de charger les paramÃ¨tres: ' + err.message);
        }});
        
        // Charger les paramÃ¨tres du dÃ©tecteur
        fetch('/line_detector/get_params')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            document.getElementById('whiteThresholdInput').value = data.white_threshold || 200;
            document.getElementById('minAreaInput').value = data.min_area || 300;
            document.getElementById('offsetRatioInput').value = data.offset_ratio || 0.6;
            appendLog('ParamÃ¨tres du dÃ©tecteur chargÃ©s');
        }})
        .catch(function(err) {{
            appendLog('Impossible de charger les paramÃ¨tres du dÃ©tecteur: ' + err.message);
        }});
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
    }});
    </script>
    </body></html>
    """.format(title=title)

    return html
