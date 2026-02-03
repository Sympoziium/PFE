#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_acceuil.py

def render_accueil_tab(title: str = "Accueil") -> str:
    html = """<!DOCTYPE html><html lang='fr'>
    <head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>{title}</title>
    <style>
    body { margin: 0; padding: 0; width: 100vw; height: 100vh; font-family: Arial; background: linear-gradient(135deg, #40E0D0, #00BFFF); color: #333; display: flex; flex-direction: column; }
    .container { display: flex; justify-content: center; padding: 20px; height: calc(100vh - 40px); }
    .tab-shell { background: rgba(255,255,255,0.95); border-radius: 16px; padding: 18px; width: min(980px, 100%); display:flex; flex-direction:column;}
    .tab-header { display: flex; align-items: center; margin-bottom: 15px; }
    .tab-nav { margin-left: auto; display: flex; gap: 5px; }
    .tab-content { display: flex; gap: 20px; flex: 1; min-height:0; }
    
    .left-panel, .right-panel { background: #f8f9fa; border-radius: 12px; padding: 15px; flex: 1; display:flex; flex-direction:column; align-items:center; border: 1px solid #ddd; overflow-y: auto;}
    
    /* Boutons */
    .primary-btn { background: #007acc; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
    .command-button { margin: 5px; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color:white; width: 120px; transition: all 0.3s ease;}
    .btn-green { background: #28a745; }
    .btn-red { background: #dc3545; }
    .btn-blue { background: #007bff; }
    
    /* --- CLASSE POUR DÉSACTIVER LES BOUTONS --- */
    .disabled { 
        background-color: #cccccc !important; 
        color: #666666 !important; 
        cursor: not-allowed; 
        pointer-events: none; 
        box-shadow: none;
    }
    
    /* D-PAD */
    .dpad-container { display: grid; grid-template-areas: ". up ." "left center right" ". down ."; gap: 5px; width: 150px; height: 150px; margin-top:20px; }
    .dpad-button { background: #ddd; border: none; border-radius: 10px; cursor: pointer; display:flex; justify-content:center; align-items:center; }
    .dpad-button:active { background: #bbb; }
    .dpad-up { grid-area: up; } .dpad-down { grid-area: down; }
    .dpad-left { grid-area: left; } .dpad-right { grid-area: right; }
    
    .live-feed img { width: 100%; border-radius: 8px; border: 2px solid #333; margin-top:10px; display:none;}

    /* SWITCH CSS */
    .switch { position: relative; display: inline-block; width: 50px; height: 24px; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 34px; }
    .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
    input:checked + .slider { background-color: #2196F3; }
    input:checked + .slider:before { transform: translateX(26px); }
    </style>
    </head>
    <body>
    <div class='container'>
        <div class='tab-shell'>
            <div class='tab-header'>
                <h2>{title}</h2>
                <div class='tab-nav'>
                    <button class='primary-btn' onclick="location.href='/'">Accueil</button>
                    <button class='primary-btn' onclick="location.href='/vision'">Vision</button>
                    <button class='primary-btn' style='background:#dc3545;' onclick="fetch('/exit', {method:'POST'})">EXIT</button>
                </div>
            </div>

            <div class='tab-content'>
                <div class='left-panel'>
                    <button class='primary-btn' id='camBtn' onclick='toggleCamera()'>▶️ Start Camera</button>
                    <div class='live-feed'><img id='videoStream'></div>

                    <hr style="width:100%; margin: 20px 0; border: 1px solid #ccc;">

                    <h3>🌉 Pont Levis</h3>
                    
                    <div style="margin-bottom:15px; display:flex; align-items:center; gap:10px;">
                        <span style="font-weight:bold;">Mode Auto:</span>
                        <label class="switch">
                          <input type="checkbox" id="autoCheck" onchange="toggleAuto(this.checked)" checked>
                          <span class="slider round"></span>
                        </label>
                    </div>

                    <div style="margin-bottom:10px;">
                        <button class='command-button btn-green' onclick="fetch('/bridge/green', {method:'POST'})">Feu Vert</button>
                        <button class='command-button btn-red' onclick="fetch('/bridge/red', {method:'POST'})">Feu Rouge</button>
                    </div>
                    <div>
                        <button id="btnOpen" class='command-button btn-blue disabled' onclick="fetch('/bridge/open', {method:'POST'})">Ouvrir ⬆️</button>
                        <button id="btnClose" class='command-button btn-blue disabled' onclick="fetch('/bridge/close', {method:'POST'})">Fermer ⬇️</button>
                    </div>
                </div>

                <div class='right-panel'>
                    <h3>🏎️ Contrôle Zumi</h3>
                    <div class="dpad-container">
                        <button class="dpad-button dpad-up" onmousedown="start('forward')" onmouseup="stop()" ontouchstart="start('forward')" ontouchend="stop()">⬆️</button>
                        <button class="dpad-button dpad-left" onmousedown="start('left')" onmouseup="stop()" ontouchstart="start('left')" ontouchend="stop()">⬅️</button>
                        <button class="dpad-button dpad-center" onclick="stop()">🛑</button>
                        <button class="dpad-button dpad-right" onmousedown="start('right')" onmouseup="stop()" ontouchstart="start('right')" ontouchend="stop()">➡️</button>
                        <button class="dpad-button dpad-down" onmousedown="start('reverse')" onmouseup="stop()" ontouchstart="start('reverse')" ontouchend="stop()">⬇️</button>
                    </div>
                </div>  
            </div>
        </div>
    </div>

    <script>
    // Caméra
    function toggleCamera() { 
        const img = document.getElementById('videoStream'); 
        const btn = document.getElementById('camBtn');
        if (img.style.display === 'block') {
            img.style.display = 'none'; btn.textContent = '▶️ Start Camera'; img.src = "";
            fetch('/close_camera', { method: 'POST' });
        } else {
            btn.textContent = '⛔ Stop Camera';
            fetch('/start_camera', { method: 'POST' }).then(() => {
                img.style.display = 'block'; img.src = '/video?' + Date.now();
            });
        }
    }

    // --- MODE AUTO ET GESTION UI ---
    function toggleAuto(isAuto) {
        // 1. Envoie la commande au serveur
        const val = isAuto ? '1' : '0';
        fetch('/bridge/mode_auto/' + val, { method: 'POST' })
            .then(res => console.log("Mode auto changé: " + val))
            .catch(err => console.error("Erreur:", err));

        // 2. Gestion de l'interface (Griser les boutons)
        const btnOpen = document.getElementById('btnOpen');
        const btnClose = document.getElementById('btnClose');

        if (isAuto) {
            btnOpen.classList.add('disabled');
            btnClose.classList.add('disabled');
        } else {
            btnOpen.classList.remove('disabled');
            btnClose.classList.remove('disabled');
        }
    }
    // ----------------------------------

    // Mouvements Zumi
    let moveInterval = null;
    function start(dir) {
        if (moveInterval) return;
        const send = () => fetch('/zumi/' + dir).catch(e => console.log(e));
        send();
        moveInterval = setInterval(send, 300);
    }
    function stop() {
        if (moveInterval) { clearInterval(moveInterval); moveInterval = null; }
        fetch('/zumi/stop');
    }
    </script>
    </body></html>
    """
    return html.replace("{title}", title)