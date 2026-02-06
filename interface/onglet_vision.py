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

	.detector-btn {
		background: #28a745; color: white; border: none; /* vert */
		padding: 10px 18px; border-radius: 10px;
		cursor: pointer; font-size: 15px;
		active_detector: none;
	}

	.detector-btn:hover { background: #218838; } /* vert foncé au survol */



	/* style bouton toggle */
	.remoteDL-toggle-btn {
		color: white; 
		border: none; 
		padding: 10px 18px; 
		border-radius: 10px; 
		cursor: pointer; 
		margin-top: 15px; 
		font-size: 15px;
	}

	/* Etats explicites pour plus de robustesse */
	.remoteDL-toggle-btn.off { background: #dc3545; }
	.remoteDL-toggle-btn.off:hover { background: #bd2130; }
	.remoteDL-toggle-btn.on { background: #28a745; }
	.remoteDL-toggle-btn.on:hover { background: #218838; }

	/* style bouton toggle */
	.toggle-btn {
        background: #007acc; /* bleu par défaut */
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

	/*
	#bboxOverlay {
		position: absolute;
		border: 4px solid #00FF00;
		border-radius: 4px;
		display: none;
		box-shadow: 0 0 8px rgba(0, 255, 0, 0.6);
		pointer-events: none;
	}
	*/

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
		border-radius: 10px; padding: 10px; min-height: 200px; min-width: 100px; overflow: auto;
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
					<button class='primary-btn' data-path="/">Accueil</button>
					<button class='primary-btn' data-path="/vision">Vision</button>
					<button class='primary-btn' data-path="/onglet_template">Template</button>
				</div>
			</div>

			<div class='tab-content'>
				<div class='tab-header'>
					<h3 class='tab-subtitle'>Capture image</h3>
				</div>
				<!-- AJOUT DES FONCTIONS DE CAPTURE -->
				<button class='toggle-btn' id='cameraToggleBtn'>▶️ Start Camera</button>
				<button class='primary-btn' id='captureImageBtn'>📸 Capture Image</button> 
				<button class='remoteDL-toggle-btn off' id='toggleDownloadCapturedBtn' aria-pressed='false'> 💾 Off</button>
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
						<select id='detectorSelect' class='select-detector'>
							<!-- options remplies dynamiquement -->
						</select>
						<button class='detector-btn' id='runDetectionBtn'>Lancer Détection</button>
						<button class='detector-btn' id='runDiagnosticsBtn'>Diagnostique Détecteur</button>
					</div>
					<!-- Stop detection diagnostic panel -->
					<div class='stop-detect-panel' id='stopDetectPanel'>
						<div class='tab-subtitle'>Diagnostic Stop</div>
						<div class='stop-detect-layout'>
							<div class='captured-box'>
								<div style='position:relative; display:inline-block;'>
									<img id='lastCapturedImage' alt='Dernière image capturée'>
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
			var liveFeed = document.getElementById('liveFeed');
			var isActive = liveFeed && liveFeed.style.display === 'block';
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

	function toggleCamera() { 
		console.log('toggleCamera() appelee');
		var liveFeed = document.getElementById('liveFeed'); 
		var btn = document.getElementById('cameraToggleBtn'); 
		var img = liveFeed.querySelector('img'); 
		var isActive = liveFeed.style.display === 'block';
		if (!isActive) {
			btn.textContent = '⛔ Stop Camera';
			fetch('/start_camera', { method: 'POST' })
				.then(function(response) {
					if (!response.ok) throw new Error('start_camera failed: ' + response.status + ' ' + response.statusText);
					liveFeed.style.display = 'block';
					img.src = '/video?' + new Date().getTime();
				})
				.catch(function(err) {
					logError('toggleCamera: /start_camera', err);
					btn.textContent = '▶️ Start Camera';
				});
		} else {
            // 1. Cache le conteneur et change le bouton 
            liveFeed.style.display = 'none'; 
            btn.textContent = '▶️ Start Camera'; 
            
            // 2. Vide la source de l'image (arrete le flux gele) 
            img.src = "";  
            
            // 3. Envoie la commande d'arret au serveur 
			fetch('/close_camera', { method: 'POST' }).catch(function(err) { logError('toggleCamera: /close_camera', err); }); 
		}
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
		console.log('captureImage() appelee'); // pour debug
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
					alert('Image capturee et enregistree sur le serveur : ' + download_url);
					var link = document.createElement('a');
					link.href = download_url;
					link.download = filename;
					document.body.appendChild(link);
					link.click();
					link.remove();
				}

				imageCapturedCallback(file_url); // mise a jour de la dernière image capturée
			})
			.catch(function(err) {
				logError('captureImage: /capture_image', err);
				alert('Erreur lors de la communication avec le serveur : ' + err);
			});
	}
	
	function imageCapturedCallback(imageUrl) {
		console.log("imageCapturedCallback mise a jour de l'image : " + imageUrl); // pour debug
		const panel = document.getElementById('stopDetectPanel');
		const img = document.getElementById('lastCapturedImage');
		panel.style.display = panel.style.display === 'none' ? 'none' : 'block';
		img.src = imageUrl;
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
				}
				if (selected != null && selected >= 0) {
					sel.value = String(selected);
					SELECTED_DETECTOR_NAME = DETECTORS_MAP[selected] || null;
					updateStopUIPanelVisibility();
				}
			})
			.catch(function(err) { logError('loadDetectors: /detectors', err); });
	}

	function onDetectorChange() {
		var sel = document.getElementById('detectorSelect');
		var idx = parseInt(sel.value, 10);
		if (isNaN(idx) || idx < 0) return;
		fetch('/detector', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ index: idx })
		}).catch(function(err) { logError('onDetectorChange: /detector', err, { index: idx }); });
		SELECTED_DETECTOR_NAME = DETECTORS_MAP[idx] || null;
		updateStopUIPanelVisibility();
	}

	function runDetection() {
		fetch('/run_detection', { method: 'POST' })
			.then(function(r) { if (!r.ok) throw new Error('run_detection failed: ' + r.status + ' ' + r.statusText); return r.json(); })
			.then(function(res) {
				var terminal = document.getElementById('stopDetectTerminal');
				terminal.style.display = 'block';
				terminal.textContent = JSON.stringify(res, null, 2);
				if (res && res.annotated_file_url) {
					imageCapturedCallback(res.annotated_file_url);
				} else if (res && res.source_file_url) {
					imageCapturedCallback(res.source_file_url);
				}
			})
			.catch(function(err) {
				logError('runDetection: /run_detection', err);
				var terminal = document.getElementById('stopDetectTerminal');
				terminal.style.display = 'block';
				terminal.textContent = 'Erreur: ' + err;
			});
	}

	function updateStopUIPanelVisibility() {
		var panel = document.getElementById('stopDetectPanel');
		if (!SELECTED_DETECTOR_NAME) { panel.style.display = 'none'; return; }
		// Afficher pour tout détecteur de stop (Zumi ou CV)
		panel.style.display = (SELECTED_DETECTOR_NAME.indexOf('StopDetector') !== -1) ? 'block' : 'none';
	}

	/*
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
	*/

	function runStopDiagnostics() {
		var indicator = document.getElementById('stopDetectIndicator');
		var terminal = document.getElementById('stopDetectTerminal');
		indicator.classList.remove('on', 'off');
		indicator.textContent = 'Diagnostic en cours...';
		appendTerminalLines('Execution du balayage des parametres...');
		fetch('/diagnose_stop', { method: 'POST' })
			.then(function(r) { if (!r.ok) throw new Error('diagnose_stop failed: ' + r.status + ' ' + r.statusText); return r.json(); })
			.then(function(payload) {
				if (payload.logs && Array.isArray(payload.logs)) {
					appendTerminalLines(payload.logs);
				} else {
					appendTerminalLines(JSON.stringify(payload, null, 2));
				}
				var best = payload.best || {};
				var imgUrl = best.file_url || payload.source_file_url;
				if (imgUrl) { imageCapturedCallback(imgUrl); }
				if (best.bbox) {
					indicator.classList.add('on');
					indicator.textContent = 'STOP detecte';
				} else {
					indicator.classList.add('off');
					indicator.textContent = 'Aucune detection';
				}
			})
			.catch(function(err) {
				logError('runStopDiagnostics: /diagnose_stop', err);
				indicator.classList.remove('on');
				indicator.classList.add('off');
				indicator.textContent = 'Erreur';
			});
	}

	function runGenericDiagnostics() {
		var indicator = document.getElementById('stopDetectIndicator');
		var terminal = document.getElementById('stopDetectTerminal');
		indicator.classList.remove('on', 'off');
		indicator.textContent = 'Diagnostic en cours...';
		appendTerminalLines('Exécution du diagnostic...');
		fetch('/diagnose_detector', { method: 'POST' })
			.then(function(r) { if (!r.ok) throw new Error('diagnose_detector failed: ' + r.status + ' ' + r.statusText); return r.json(); })
			.then(function(payload) {
				// logs
				if (payload.logs && Array.isArray(payload.logs)) {
					appendTerminalLines(payload.logs);
				} else { appendTerminalLines(JSON.stringify(payload, null, 2)); }
				// Stop detecté
				if (payload.Stop_detected) {
					indicator.classList.add('on');
					indicator.textContent = 'STOP detecte';
				} else {
					indicator.classList.add('off');
					indicator.textContent = 'Aucune detection';
				}

				// best bbox overlay
				var best = payload.best || {};
				var imgUrl = (payload.steps && payload.steps.length) ? payload.steps[payload.steps.length - 1].url : payload.source_file_url;
				if (imgUrl) { imageCapturedCallback(imgUrl); }
				// enleve le draw de la bbox on le fait directement dans le backend sur une copie de l'image qu'on affiche ensuite
				if (best.bbox) {
					indicator.classList.add('on');
					indicator.textContent = 'STOP detecte';
				} else {
					indicator.classList.add('off');
					indicator.textContent = 'Aucune detection';
				}
				// open gallery in new tab
				if (payload.steps && payload.steps.length) {
					var w = window.open('', '_blank');
					if (w) {
						var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Diagnostic Gallery</title></head><body style="font-family:Arial; padding:12px;">';
						html += '<h3>Etapes du diagnostic</h3>';
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
				logError('runGenericDiagnostics: /diagnose_detector', err);
				indicator.classList.remove('on');
				indicator.classList.add('off');
				indicator.textContent = 'Erreur';
			});
	}

	function runDiagnostics() {
		var detectorName = SELECTED_DETECTOR_NAME || 'Inconnu';

		if (detectorName === 'StopDetector') {
			// Détecteur Zumi spécifique avec balayage de paramètres
			runStopDiagnostics();
		} else if (detectorName.indexOf('StopDetector') !== -1) {
			// Tous les autres détecteurs de stop (CV, Matt, etc.) utilisent la route générique
			runGenericDiagnostics();
		} else {
			alert('Aucun diagnostique disponible pour le détecteur sélectionné : ' + detectorName);
		}
	}

	// Charger la liste des détecteurs au chargement de la page et lier les événements
	window.addEventListener('DOMContentLoaded', function() {
		loadDetectors();
		// Navigation buttons
		var navBtns = document.querySelectorAll('.tab-nav .primary-btn');
		Array.prototype.forEach.call(navBtns, function(btn) {
			btn.addEventListener('click', function() {
				var path = btn.getAttribute('data-path');
				navigateTo(path);
			});
		});
		// Camera toggle
		var camBtn = document.getElementById('cameraToggleBtn');
		if (camBtn) camBtn.addEventListener('click', toggleCamera);
		// Capture image
		var capBtn = document.getElementById('captureImageBtn');
		if (capBtn) capBtn.addEventListener('click', captureImage);
		// Toggle download
		var dlBtn = document.getElementById('toggleDownloadCapturedBtn');
		if (dlBtn) dlBtn.addEventListener('click', toggleDownloadCaptured);
		// Run detection
		var runDetBtn = document.getElementById('runDetectionBtn');
		if (runDetBtn) runDetBtn.addEventListener('click', runDetection);
		// Run diagnostics
		var runDiagBtn = document.getElementById('runDiagnosticsBtn');
		if (runDiagBtn) runDiagBtn.addEventListener('click', runDiagnostics);
		// Detector select change
		var sel = document.getElementById('detectorSelect');
		if (sel) sel.addEventListener('change', onDetectorChange);
	});

	// --- Exposer les fonctions au scope global pour les onclick inline ---
	window.navigateTo = navigateTo;
	window.toggleCamera = toggleCamera;
	window.toggleDownloadCaptured = toggleDownloadCaptured;
	window.captureImage = captureImage;
	window.runDetection = runDetection;
	window.runDiagnostics = runDiagnostics;
	window.onDetectorChange = onDetectorChange;
	</script>
	</body></html>
	"""

	# Remplacer uniquement le titre sans interpréter les autres accolades
	return html.replace("{title}", title)