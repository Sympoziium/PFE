#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_vision.py
# ------------------
# ce module défini un onglet de l'interface web dédié au fonctionnalitées du module de vision
# ------------------

def render_vision_tab(title: str = "Vision du Zumi") -> str:
	"""Retourne une page HTML complète avec les widgets pour l'onglet de vision."""

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
		font-family: Arial, sans-serif;
		background: linear-gradient(135deg, #40E0D0, #00BFFF);
		color: #333; display: flex; flex-direction: column;
	}

	.container {
		display: flex; justify-content: center; align-items: flex-start;
		padding: 20px; height: calc(100vh - 40px);
	}

	.tab-shell {
		background: rgba(255,255,255,0.92);
		border-radius: 16px;
		padding: 18px;
		box-shadow: 0 0 15px rgba(0,0,0,0.12);
		width: min(980px, 100%);
	}

	.tab-header {
		display: flex; align-items: center;
		margin-bottom: 12px;
	}

	.tab-nav {
		display: flex; align-items: center;
		gap: 4px;
		margin-left: auto; /* pousse la nav à droite */
	}

	.tab-btn-group {
		display: flex; flex-direction: column; align-items: stretch; justify-content: flex-start;
		gap: 8px;
		border: 2px solid #000000;
		background: #e0e0e0;
		padding: 8px;
	}

	.tab-row {
		display: flex; align-items: flex-start; gap: 12px;
	}

	.tab-content {
		border: 2px solid #bcdffb;
		border-radius: 12px;
		padding: 16px;
		min-height: 200px;
		background: #f7fbff;
	}

	/* --- Styles pour les différents types de texte --- */
	
	/* Boite de texte format titre */
	.tab-title {
		font-size: 22px; font-weight: bold; margin: 0;
	}

	/* Boite de texte format sous-titre */
	.tab-subtitle {
		font-size: 18px; font-weight: bold; margin: 0;
	}

	/* Boite de texte format texte normal */
	.tab-text {
		font-size: 16px; font-weight: normal; margin: 0;
	}

	/* --- Déclarations des différents styles de widgets --- */

	/* style bouton cliquable principal */
	.primary-btn {
		background: #007acc; color: white; border: none;
		padding: 10px 18px; border-radius: 10px;
		cursor: pointer; font-size: 15px;
	}

	.primary-btn:hover { background: #005fa3; }

	/* état actif pour le bouton d'onglet courant */
	.primary-btn.active {
		background: #00528a;
		box-shadow: 0 0 0 2px rgba(0,0,0,0.06) inset;
	}

	/* style bouton toggle */
	.toggle-btn {
        background: #007acc; 
        color: white; 
        border: none; 
        padding: 10px 18px; 
        border-radius: 10px; 
        cursor: pointer; 
        margin-top: 15px; 
        font-size: 15px;
	}

	.toggle-btn:hover { background: #005fa3; } 

	/* --- Styles pour le live feed vidéo --- */

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

	/* Exemple de style additionnel pour les boutons et zones de résultats */
	/* container : conteneur principal de l'onglet
	   tab-shell : "coquille" de l'onglet avec le fond blanc et les arrondis
	   tab-header : entête de l'onglet avec le titre et les actions globales
	   tab-title : titre de l'onglet
	   tab-content : zone principale de contenu de l'onglet
	   L'ordre des classes CSS suit l'ordre d'apparition dans le HTML.
	   Sections délimitées par <div class='XXX'> ... </div> */

	/* Ajout styles pour select */
	.select-detector {
		padding: 8px; border-radius: 8px; border: 1px solid #aaa; background: #fff; font-size: 14px;
	}

	/* --- Stop Detection UI panel --- */
	.stop-detect-panel {
		display: none; /* visible seulement pour le détecteur stop */
		flex: 1;
		border: 2px solid #00b894;
		border-radius: 12px;
		padding: 12px;
		background: #f7fbff;
	}

	.stop-detect-layout {
		display: flex; gap: 12px; align-items: flex-start;
	}

	.captured-box {
		position: relative;
		flex: 2;
		background: #f0f8ff;
		border-radius: 12px;
		padding: 10px;
		text-align: center;
	}

	.captured-box img {
		max-width: 100%; height: auto; border-radius: 8px; border: 4px solid #00BFFF;
	}

	#bboxOverlay {
		position: absolute;
		border: 4px solid #00FF00;
		border-radius: 4px;
		display: none;
		box-shadow: 0 0 8px rgba(0, 255, 0, 0.6);
		pointer-events: none;
	}

	.indicator-and-terminal {
		flex: 1; display: flex; flex-direction: column; gap: 10px; align-items: stretch;
	}

	.detect-indicator {
		border-radius: 10px; padding: 10px; text-align: center; font-weight: bold; color: #fff;
		background: #bdc3c7; /* défaut: gris */
	}

	.detect-indicator.on { background: #2ecc71; }
	.detect-indicator.off { background: #e74c3c; }

	.log-terminal {
		background: #000; color: #fff; font-family: Consolas, monospace; font-size: 13px;
		border-radius: 10px; padding: 10px; min-height: 120px; max-height: 220px; overflow: auto;
		white-space: pre-wrap;
	}

	</style>
	</head>
	<body>
	<div class='container'>
		<div class='tab-shell'>
			<div class='tab-header'>
				<h2 class='tab-title'>{title}</h2>
				<!-- Boutons de navigation entre onglets -->
				<div class='tab-nav'>
					<button class='primary-btn' data-path="/" onclick="location.href='/'">Accueil</button>
					<button class='primary-btn' data-path="/vision" onclick="location.href='/vision'">Vision</button>
					<button class='primary-btn' data-path="/onglet_template" onclick="location.href='/onglet_template'">Template</button>
				</div>
			</div>

			<div class='tab-content'>
				<div class='tab-header'>
					<h3 class='tab-subtitle'>Capture image</h3>
				</div>
				<!-- AJOUT DES FONCTIONS DE CAPTURE -->
				<button class='toggle-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>
				<button class='primary-btn' onclick='captureImage()'>📸 Capture Image</button> 
				
				<div id='zone-resultats'></div>
				<!-- Conteneur du flux vidéo en direct -->
				<div class='live-feed' id='liveFeed' style = 'display:none;'>
					<img id='videoStream' alt='Flux vidéo en direct'>
				</div>
			</div>

			<div class='tab-content'>
				<div class='tab-header'>
					<h3 class='tab-subtitle'>Image Detection</h3>
				</div>
				<!-- AJOUT DES FONCTIONS DE DÉTECTION -->
				<div class='tab-row'>
					<div class='tab-btn-group'>
						<label for='detectorSelect' class='tab-text'>Choix du détecteur</label>
						<select id='detectorSelect' class='select-detector' onchange='onDetectorChange()'>
							<!-- options remplies dynamiquement -->
						</select>
						<button class='primary-btn' onclick="runDetection()">Lancer Détection</button>
						<button class='primary-btn' onclick="toggleResults()">Afficher/masquer Résultats</button>
					</div>
					<!-- Stop detection diagnostic panel -->
					<div class='stop-detect-panel' id='stopDetectPanel'>
						<div class='tab-subtitle'>Diagnostic Stop</div>
						<div class='stop-detect-layout'>
							<div class='captured-box'>
								<div style='position:relative; display:inline-block;'>
									<img id='lastCapturedImage' alt='Dernière image capturée'>
									<div id='bboxOverlay'></div>
								</div>
								<div style='margin-top:8px; text-align:right;'>
									<button class='primary-btn' onclick='runStopDiagnostics()'>Diagnostiquer Stop</button>
								</div>
							</div>
							<div class='indicator-and-terminal'>
								<div id='stopDetectIndicator' class='detect-indicator'>Aucune détection</div>
								<div id='stopDetectTerminal' class='log-terminal'>Terminal vide</div>
							</div>
						</div>
					</div>
					<!-- ajouter la dernière image capturée -->
				</div>
				
				<div id='zone-resultats-detection' style='display:none;'></div>
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
		console.log('toggleCamera() appelee');
		var liveFeed = document.getElementById('liveFeed'); 
		var btn = document.getElementById('cameraToggleBtn'); 
		var img = liveFeed.querySelector('img'); 
		var isActive = liveFeed.style.display === 'block';
		if (!isActive) {
			btn.textContent = '⛔ Stop Camera';
			fetch('/start_camera', { method: 'POST' })
				.then(function() {
					liveFeed.style.display = 'block';
					img.src = '/video?' + new Date().getTime();
				});
		} else {
            // 1. Cache le conteneur et change le bouton 
            liveFeed.style.display = 'none'; 
            btn.textContent = '▶️ Start Camera'; 
            
            // 2. Vide la source de l'image (arrete le flux gele) 
            img.src = "";  
            
            // 3. Envoie la commande d'arret au serveur 
			fetch('/close_camera', { method: 'POST' }); 
		}
	}
	
	function captureImage() {
		console.log('captureImage() appelee'); // pour debug

		fetch('/capture_image', { method: 'POST' })
			.then(function(response) { return response.json(); })
			.then(function(data) {
				var file_url = data.file_url;
				var download_url = data.download_url;
				var filename = data.filename;
				var error = data.error;
				if (error) {
					alert('Erreur lors de la capture image : ' + error);
					return;
				}
				alert('Image capturee et enregistree sur le serveur : ' + download_url);
				// enregistrement de l'image sur le PC
				var link = document.createElement('a');
				link.href = download_url;
				link.download = filename;
				imageCapturedCallback(file_url); // mise a jour de la dernière image capturée
				document.body.appendChild(link);
				link.click();
				link.remove();
			})
			.catch(function(err) {
				alert('Erreur lors de la communication avec le serveur : ' + err);
				console.log('Erreur lors de la communication avec le serveur : ' + err); // pour debug
			});
	}
	
	function imageCapturedCallback(imageUrl) {
		console.log("imageCapturedCallback mise a jour de l'image : " + imageUrl); // pour debug
		const panel = document.getElementById('stopDetectPanel');
		const img = document.getElementById('lastCapturedImage');
		panel.style.display = panel.style.display === 'none' ? 'none' : 'block';
		img.src = imageUrl;
		clearOverlayBox();
	}
	
	// --- Détecteurs: chargement, sélection et exécution ---
	var DETECTORS_MAP = {}; // index -> name
	var SELECTED_DETECTOR_NAME = null;

	function loadDetectors() {
		fetch('/detectors')
			.then(function(r) { return r.json(); })
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
				}
				if (selected != null && selected >= 0) {
					sel.value = String(selected);
					SELECTED_DETECTOR_NAME = DETECTORS_MAP[selected] || null;
					updateStopUIPanelVisibility();
				}
			})
			.catch(function() {});
	}

	function onDetectorChange() {
		var sel = document.getElementById('detectorSelect');
		var idx = parseInt(sel.value, 10);
		if (isNaN(idx) || idx < 0) return;
		fetch('/detector', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ index: idx })
		}).catch(function() {});
		SELECTED_DETECTOR_NAME = DETECTORS_MAP[idx] || null;
		updateStopUIPanelVisibility();
	}

	function runDetection() {
		fetch('/run_detection', { method: 'POST' })
			.then(function(r) { return r.json(); })
			.then(function(res) {
				var zone = document.getElementById('zone-resultats-detection');
				zone.style.display = 'block';
				zone.textContent = JSON.stringify(res, null, 2);
				if (res && res.annotated_file_url) {
					imageCapturedCallback(res.annotated_file_url);
				} else if (res && res.source_file_url) {
					imageCapturedCallback(res.source_file_url);
				}
			})
			.catch(function(err) {
				var zone2 = document.getElementById('zone-resultats-detection');
				zone2.style.display = 'block';
				zone2.textContent = 'Erreur: ' + err;
			});
	}

	function updateStopUIPanelVisibility() {
		var panel = document.getElementById('stopDetectPanel');
		if (!SELECTED_DETECTOR_NAME) { panel.style.display = 'none'; return; }
		panel.style.display = (SELECTED_DETECTOR_NAME.indexOf('StopDetectorZumi') !== -1) ? 'block' : 'none';
	}

	function clearOverlayBox() {
		var box = document.getElementById('bboxOverlay');
		if (!box) return;
		box.style.display = 'none';
		box.style.left = '0px'; box.style.top = '0px'; box.style.width = '0px'; box.style.height = '0px';
	}

	function updateOverlayBox(bbox) {
		var img = document.getElementById('lastCapturedImage');
		var box = document.getElementById('bboxOverlay');
		if (!img || !box || !bbox) { clearOverlayBox(); return; }
		var rect = img.getBoundingClientRect();
		var naturalW = img.naturalWidth || rect.width;
		var naturalH = img.naturalHeight || rect.height;
		var scaleX = rect.width / naturalW;
		var scaleY = rect.height / naturalH;
		var x = bbox[0] * scaleX;
		var y = bbox[1] * scaleY;
		var w = bbox[2] * scaleX;
		var h = bbox[3] * scaleY;
		box.style.left = Math.round(x) + 'px';
		box.style.top = Math.round(y) + 'px';
		box.style.width = Math.round(w) + 'px';
		box.style.height = Math.round(h) + 'px';
		box.style.display = 'block';
	}

	function runStopDiagnostics() {
		var indicator = document.getElementById('stopDetectIndicator');
		var terminal = document.getElementById('stopDetectTerminal');
		indicator.classList.remove('on', 'off');
		indicator.textContent = 'Diagnostic en cours...';
		terminal.textContent = 'Execution du balayage des parametres..."\n"';
		fetch('/diagnose_stop', { method: 'POST' })
			.then(function(r) { return r.json(); })
			.then(function(payload) {
				if (payload.logs && Array.isArray(payload.logs)) {
					terminal.textContent = payload.logs.join('"\n"');
				} else {
					terminal.textContent = JSON.stringify(payload, null, 2);
				}
				var best = payload.best || {};
				var imgUrl = best.file_url || payload.source_file_url;
				if (imgUrl) { imageCapturedCallback(imgUrl); }
				if (best.bbox) {
					updateOverlayBox(best.bbox);
					indicator.classList.add('on');
					indicator.textContent = 'STOP detecte';
				} else {
					clearOverlayBox();
					indicator.classList.add('off');
					indicator.textContent = 'Aucune detection';
				}
			})
			.catch(function(err) {
				terminal.textContent = 'Erreur: ' + err;
				indicator.classList.remove('on');
				indicator.classList.add('off');
				indicator.textContent = 'Erreur';
			});
	}

	function toggleResults() {
		const zone = document.getElementById('zone-resultats-detection');
		zone.style.display = (zone.style.display === 'none' || zone.style.display === '') ? 'block' : 'none';
	}

	// Charger la liste des détecteurs au chargement de la page
	window.addEventListener('DOMContentLoaded', loadDetectors);
	</script>
	</body></html>
	"""

	# Remplacer uniquement le titre sans interpréter les autres accolades
	return html.replace("{title}", title)