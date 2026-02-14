#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_pid.py
# ------------------
"""Page web pour le contrôle PID du suivi de ligne."""

def render_pid_tab(title: str = "Asservissement PID") -> str:
    """Retourne une page HTML complète pour le contrôle PID."""

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

    </style>
    </head>
    <body>
    <div class='container'>
        <div class='tab-shell'>
            <div class='tab-header'>
                <h2 class='tab-title'>{title}</h2>
                <div class='tab-nav'>
                    <button class='primary-btn' data-path="/">Accueil</button>
                    <button class='primary-btn' data-path="/vision">Vision</button>
                    <button class='primary-btn' data-path="/pid">PID</button>
                    <button class='primary-btn' data-path="/onglet_template">Template</button>
                </div>
            </div>

            <!-- Paramètres PID -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Paramètres PID</h3>
                <div class='param-grid'>
                    <div class='param-item'>
                        <label class='param-label'>Kp (Proportionnel)</label>
                        <input type='number' step='0.01' class='param-input' id='kpInput' value='0.1'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Ki (Intégral)</label>
                        <input type='number' step='0.001' class='param-input' id='kiInput' value='0.0'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Kd (Dérivé)</label>
                        <input type='number' step='0.01' class='param-input' id='kdInput' value='0.05'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Vitesse de base</label>
                        <input type='number' step='1' class='param-input' id='baseSpeedInput' value='20'>
                    </div>
                    <div class='param-item'>
                        <label class='param-label'>Correction max</label>
                        <input type='number' step='1' class='param-input' id='maxCorrectionInput' value='30'>
                    </div>
                </div>
                <button class='primary-btn' id='updateParamsBtn'>📝 Mettre à jour les paramètres</button>
            </div>

            <!-- Contrôles -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Contrôle</h3>
                <div style='text-align: center;'>
                    <button class='control-btn' id='startPidBtn'>▶️ Démarrer PID</button>
                    <button class='control-btn stop' id='stopPidBtn'>⛔ Arrêter PID</button>
                    <button class='primary-btn' id='resetPidBtn'>🔄 Réinitialiser PID</button>
                </div>
            </div>

            <!-- Statut temps réel -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Statut temps réel</h3>
                <div class='status-panel'>
                    <div class='status-grid'>
                        <div class='status-item'>
                            <div class='status-label'>État</div>
                            <div class='status-value' id='pidStatus'>Arrêté</div>
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

            <!-- Flux vidéo -->
            <div class='tab-content'>
                <h3 class='tab-subtitle'>Flux vidéo</h3>
                <div class='live-feed'>
                    <img id='videoFeed' src='/video' alt='Flux vidéo'>
                </div>
            </div>
        </div>
    </div>

    <div class='toast-container' id='toastContainer'></div>

    <script>
    // Variables globales
    var pidRunning = false;
    var statusInterval = null;

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

    // Mettre à jour les paramètres PID
    function updateParams() {{
        var params = {{
            kp: parseFloat(document.getElementById('kpInput').value),
            ki: parseFloat(document.getElementById('kiInput').value),
            kd: parseFloat(document.getElementById('kdInput').value),
            base_speed: parseInt(document.getElementById('baseSpeedInput').value),
            max_correction: parseInt(document.getElementById('maxCorrectionInput').value)
        }};

        fetch('/pid/update_params', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(params)
        }})
        .then(function(r) {{ if (!r.ok) throw new Error('Erreur ' + r.status); return r.json(); }})
        .then(function(data) {{
            appendLog('Paramètres mis à jour: Kp=' + params.kp + ', Ki=' + params.ki + ', Kd=' + params.kd);
            showToast('Paramètres PID mis à jour!', 'success');
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
            document.getElementById('pidStatus').style.color = '#28a745';
            appendLog('PID démarré');
            showToast('PID démarré!', 'success');
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
            document.getElementById('pidStatus').style.color = '#dc3545';
            appendLog('PID arrêté');
            showToast('PID arrêté', 'info');
            stopStatusPolling();
        }})
        .catch(function(err) {{
            appendLog('ERREUR: ' + err.message);
            showToast('Erreur lors de l\'arrêt', 'error');
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
                if (data.error) {{
                    document.getElementById('currentError').textContent = parseFloat(data.error).toFixed(1);
                }}
                if (data.correction) {{
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
        }}, 200);  // Mise à jour toutes les 200ms
    }}

    function stopStatusPolling() {{
        if (statusInterval) {{
            clearInterval(statusInterval);
            statusInterval = null;
        }}
    }}

    // Navigation
    function navigateTo(path) {{
        stopStatusPolling();
        if (pidRunning) {{
            fetch('/pid/stop', {{ method: 'POST' }})
                .then(function() {{ location.href = path; }})
                .catch(function() {{ location.href = path; }});
        }} else {{
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
        // Boutons de navigation
        var navBtns = document.querySelectorAll('.tab-nav .primary-btn');
        Array.prototype.forEach.call(navBtns, function(btn) {{
            btn.addEventListener('click', function() {{
                navigateTo(btn.getAttribute('data-path'));
            }});
        }});

        // Boutons de contrôle
        document.getElementById('updateParamsBtn').addEventListener('click', updateParams);
        document.getElementById('startPidBtn').addEventListener('click', startPid);
        document.getElementById('stopPidBtn').addEventListener('click', stopPid);
        document.getElementById('resetPidBtn').addEventListener('click', resetPid);

        // Charger les paramètres initiaux
        fetch('/pid/get_params')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            document.getElementById('kpInput').value = data.kp || 0.1;
            document.getElementById('kiInput').value = data.ki || 0.0;
            document.getElementById('kdInput').value = data.kd || 0.05;
            document.getElementById('baseSpeedInput').value = data.base_speed || 20;
            document.getElementById('maxCorrectionInput').value = data.max_correction || 30;
            appendLog('Paramètres chargés depuis le serveur');
        }})
        .catch(function(err) {{
            appendLog('Impossible de charger les paramètres: ' + err.message);
        }});
    }});

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {{
        stopStatusPolling();
        if (pidRunning) {{
            fetch('/pid/stop', {{ method: 'POST' }});
        }}
    }});
    </script>
    </body></html>
    """

    return html.format(title=title)