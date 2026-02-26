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
		border-radius: 10px; padding: 10px;
		min-height: 200px; max-height: 50vh; min-width: 100px;
		overflow-y: auto; overflow-x: auto;
		white-space: pre-wrap; word-wrap: break-word;
	}

	/* --- Toast notifications --- */
	.toast-container {
		position: fixed; top: 20px; right: 20px; z-index: 9999;
		display: flex; flex-direction: column; gap: 8px;
	}
	.toast {
		padding: 12px 20px; border-radius: 8px;
		color: #fff; font-size: 14px; font-family: Arial, sans-serif;
		box-shadow: 0 4px 12px rgba(0,0,0,0.3);
		opacity: 0; transform: translateX(80px);
		transition: opacity 0.3s, transform 0.3s;
		max-width: 380px; word-wrap: break-word;
	}
	.toast.show { opacity: 1; transform: translateX(0); }
	.toast.warning { background: #e67e22; }
	.toast.error { background: #e74c3c; }
	.toast.info { background: #3498db; }
	.toast.success { background: #27ae60; }

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
				<button class='remoteDL-toggle-btn off' id='toggleHighResCapturedBtn' aria-pressed='false'> Low Res</button>
				<button class='remoteDL-toggle-btn off' id='togglePassiveDetectionBtn' aria-pressed='false'> Start Passive Detection</button>
				<div id='zone-resultats'></div>
				<!-- Conteneur unifié pour livefeed et image capturée -->
				<div class='live-feed' id='mainImageDisplay' style='display:none;'>
					<img id='mainImage' alt='Image principale'>
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
						<div class='indicator-and-terminal'>
							<div id='stopDetectIndicator' class='detect-indicator'>Aucune détection</div>
							<div id='stopDetectTerminal' class='log-terminal'>Terminal vide</div>
						</div>
					</div>
					<!-- ajouter la dernière image capturée -->
				</div>
			</div>
		</div>
	</div>

	<!-- Toast container -->
	<div class='toast-container' id='toastContainer'></div>

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

	function toggleHighResCaptured() {
		console.log('toggleHighResCaptured() appelee'); // pour debug
		var btn = document.getElementById('toggleHighResCapturedBtn');
		var isActive = btn.getAttribute('aria-pressed') === 'true';
		var nextActive = !isActive;
		btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
		btn.classList.toggle('on', nextActive);
		btn.classList.toggle('off', !nextActive);
		btn.textContent = nextActive ? 'High Res' : 'Low Res';
	}

	function togglePassiveDetection() {
		console.log('togglePassiveDetection() appelee'); // pour debug
		var btn = document.getElementById('togglePassiveDetectionBtn');
		var isActive = btn.getAttribute('aria-pressed') === 'true';
		var nextActive = !isActive;
		btn.setAttribute('aria-pressed', nextActive ? 'true' : 'false');
		btn.classList.toggle('on', nextActive);
		btn.classList.toggle('off', !nextActive);
		btn.textContent = nextActive ? 'Stop Passive Detection' : 'Start Passive Detection';
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
		var highResEnabled = document.getElementById('toggleHighResCapturedBtn').getAttribute('aria-pressed') === 'true';

		fetch(highResEnabled ? '/capture_image_hires' : '/capture_image', { method: 'POST' })
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
		// Toggle high res
		var hrBtn = document.getElementById('toggleHighResCapturedBtn');
		if (hrBtn) hrBtn.addEventListener('click', toggleHighResCaptured);
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
	});

	// --- Exposer les fonctions au scope global pour les onclick inline ---
	window.navigateTo = navigateTo;
	window.toggleCamera = toggleCamera;
	window.toggleDownloadCaptured = toggleDownloadCaptured;
	window.toggleHighResCaptured = toggleHighResCaptured;
	window.togglePassiveDetection = togglePassiveDetection;
	window.captureImage = captureImage;
	window.returnToLivefeed = returnToLivefeed;
	window.runDetection = runDetection;
	window.runDiagnostics = runDiagnostics;
	window.onDetectorChange = onDetectorChange;
	</script>
	</body></html>
	"""

	# Remplacer uniquement le titre sans interpréter les autres accolades
	return html.replace("{title}", title)