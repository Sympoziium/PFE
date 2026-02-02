#!/usr/bin/env python
# -*- coding: utf-8 -*-

def render_accueil_tab(title: str = "Accueil") -> str:
    html = """<!DOCTYPE html><html lang='fr'>
    <head>
        <meta charset='UTF-8'>
        <title>{title}</title>
        <style>
            body {{ margin: 0; font-family: Arial, sans-serif; background: linear-gradient(135deg, #40E0D0, #00BFFF); display: flex; flex-direction: column; height: 100vh; }}
            .container {{ display: flex; justify-content: center; padding: 20px; }}
            .tab-shell {{ background: white; border-radius: 16px; padding: 20px; width: 900px; display: flex; flex-direction: column; }}
            .tab-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .tab-content {{ display: flex; gap: 20px; border: 2px dashed #bcdffb; padding: 20px; border-radius: 12px; }}
            .left-panel, .right-panel {{ flex: 1; padding: 10px; }}
            .primary-btn {{ background: #007acc; color: white; border: none; padding: 10px; border-radius: 8px; cursor: pointer; }}
            .dpad-container {{ display: grid; grid-template-areas: ". up ." "left center right" ". down ."; grid-gap: 10px; width: 150px; margin: 0 auto; }}
            .dpad-button {{ background: #eee; border: none; border-radius: 10px; height: 50px; cursor: pointer; }}
            .dpad-up {{ grid-area: up; }} .dpad-down {{ grid-area: down; }} .dpad-left {{ grid-area: left; }} .dpad-right {{ grid-area: right; }} .dpad-center {{ grid-area: center; background: white; border: 2px solid #ccc; }}
            .live-feed img {{ width: 100%; border-radius: 8px; border: 3px solid #00BFFF; }}
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
                        <button class='primary-btn' onclick="fetch('/exit', {{method:'POST'}})">EXIT</button>
                    </div>
                </div>
                <div class='tab-content'>
                    <div class='left-panel'>
                        <button class='primary-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>
                        <div id='liveFeed' style='display:none; margin-top:15px;'>
                            <img id='videoStream' src='' alt='Flux vidéo'>
                        </div>
                    </div>
                    <div class='right-panel'>
                        <button onclick="calibrateZumi()" style="width:100%; background:#f39c12; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer; margin-bottom:20px;">
                            🔧 Recalibrer les Capteurs
                        </button>
                        <div class="dpad-container">
                            <button class="dpad-button dpad-up" onmousedown="startMove('forward')" onmouseup="stopMove()">↑</button>
                            <button class="dpad-button dpad-left" onmousedown="startMove('left')" onmouseup="stopMove()">←</button>
                            <button class="dpad-button dpad-center" onclick="stopMove()">■</button>
                            <button class="dpad-button dpad-right" onmousedown="startMove('right')" onmouseup="stopMove()">→</button>
                            <button class="dpad-button dpad-down" onmousedown="startMove('reverse')" onmouseup="stopMove()">↓</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            function calibrateZumi() {{
                if(confirm("Zumi doit être immobile. Lancer la calibration ?")) {{
                    fetch('/zumi/calibrate').then(r => r.ok ? alert("Succès !") : alert("Erreur"));
                }}
            }}
            function toggleCamera() {{
                const feed = document.getElementById('liveFeed');
                const img = document.getElementById('videoStream');
                if(feed.style.display === 'none') {{
                    fetch('/start_camera', {{method:'POST'}}).then(() => {{
                        feed.style.display = 'block';
                        img.src = '/video?' + Date.now();
                    }});
                }} else {{
                    feed.style.display = 'none';
                    img.src = '';
                    fetch('/close_camera', {{method:'POST'}});
                }}
            }}
            function startMove(dir) {{ fetch('/zumi/'+dir); }}
            function stopMove() {{ fetch('/zumi/stop'); }}
        </script>
    </body></html>"""
    return html.replace("{title}", title)