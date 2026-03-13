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
			border-radius: 20px; padding: 20px;
			box-shadow: 0 8px 20px rgba(0,0,0,0.08);
			width: 92%; max-width: 1100px;
			min-height: fit-content; margin-bottom: 4vh;
			display: flex; flex-direction: column;
		}

		.tab-header {
			display: flex; 
			align-items: center; /* Aligne titre et boutons sur la même ligne */
			margin-bottom: 2vh;
			padding-bottom: 1vh;
			border-bottom: 2px solid #e0f4ff;
		}

		.tab-title {
			font-size: 1.8rem; 
			font-weight: bold; 
			color: #5A99C7; 
			margin: 0;
		}

		.tab-nav { 
			display: flex; 
			align-items: center;
			gap: 8px;
			margin-left: auto;
		}

		/* --- Sections Pointillées --- */
		.tab-content, .detection-row {
			border: 3px dashed #B5FFFC; border-radius: 15px;
			padding: 15px; margin-bottom: 2vh;
			background: #FFFDF0; display: flex;
			gap: 20px; align-items: flex-start;
		}

		/* --- LA COLONNE MAGIQUE (Fixe la largeur) --- */
		.button-column {
			display: flex; flex-direction: column;
			gap: 10px; width: 220px; /* Largeur fixe pour les boutons */
			flex-shrink: 0; /* Empêche de rétrécir */
		}

		/* --- Titres resserrés --- */
		.tab-subtitle { 
			font-size: 1.1rem; font-weight: bold; color: #555; 
			margin: 0 0 5px 0; width: 100%; text-align: left;
		}

		/* 1. La base pour TOUS les boutons */
		.primary-btn, .toggle-btn, .remoteDL-toggle-btn, .detector-btn {
			width: 100%; padding: 10px; border-radius: 10px;
			border: none; cursor: pointer; font-weight: bold;
			font-size: 0.9rem; transition: transform 0.1s;
			text-align: center;
		}

		/* 2. Les couleurs spécifiques par défaut */
		.primary-btn { background: #87C7F1; color: white; box-shadow: 0 4px 0 #6BAED6; }
		.toggle-btn { background: #FFB7D5; color: white; box-shadow: 0 4px 0 #E896B9; }
		.detector-btn { background: #55efc4; color: #2d3436; box-shadow: 0 4px 0 #00b894; }

		/* 3. Les interactions (Survol et Clic) */
		.primary-btn:hover { background: #76B9E4; transform: translateY(-2px); }

		.primary-btn:active, .toggle-btn:active, .detector-btn:active { 
			transform: translateY(2px); 
			box-shadow: none; 
		}

		/* 4. L'ÉTAT ACTIF (Prioritaire) */
		.primary-btn.active {
			background: #5A99C7;
			box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
			transform: none;
		}

		/* 5. Les cas particuliers de téléchargement */
		.remoteDL-toggle-btn.on { background: #81ecec; box-shadow: 0 4px 0 #00cec9; color: #333; }
		.remoteDL-toggle-btn.off { background: #fab1a0; box-shadow: 0 4px 0 #e17055; color: white; }

		/* --- Viewer et Terminal --- */
		.image-viewer {
			background: white; border-radius: 20px; padding: 10px;
			flex-grow: 1; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
			text-align: center; border: 1px solid #eee; display: none;
		}

		.image-viewer img { max-width: 100%; border-radius: 10px; border: 4px solid #00BFFF; }

		.tab-btn-group {
			width: 220px; background: white; padding: 12px;
			border-radius: 15px; border: 2px solid #B5FFFC;
			display: flex; flex-direction: column; gap: 8px;
		}

		.log-terminal {
			background: #2d3436; color: #55efc4; border-radius: 10px;
			padding: 10px; flex-grow: 1; height: 120px; overflow-y: auto;
			font-family: monospace; font-size: 0.8rem;
		}
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
                    <button class='primary-btn' data-path="/onglet_template">Template</button>
                </div>
            </div>

            <!-- SECTION CAPTURE -->
            <div class='tab-content'>
                <div class="button-column">
                    <h3 class='tab-subtitle'>Capture image</h3>
                    <button class='toggle-btn' id='cameraToggleBtn'>🎥 Allumer la caméra !</button>
                    <button class='primary-btn' id='captureImageBtn'>📸 Capture Image</button>
                    <button class='remoteDL-toggle-btn off' id='toggleDownloadCapturedBtn'>💾 Off</button>
                </div>
                <div class='image-viewer' id='mainImageDisplay'>
                    <img id='mainImage' alt='Vue du robot'>
                </div>
            </div>

            <!-- SECTION DÉTECTION -->
            <div class='detection-row' style="display: flex; gap: 20px; align-items: flex-start;">
				<!-- Colonne GAUCHE : Toujours visible -->
				<div class="button-column">
					<h3 class='tab-subtitle'>Image Detection</h3>
					<div class='tab-btn-group'>
						<label for='detectorSelect' class='tab-text' style="font-size:0.85rem;">Choix du détecteur</label>
						<select id='detectorSelect' class='select-detector'></select>
						<button class='detector-btn' id='runDetectionBtn'>Lancer Détection</button>
						<button class='detector-btn' id='runDiagnosticsBtn'>Diagnostique Détecteur</button>
					</div>
				</div>

				<!-- Colonne DROITE : Cachée par défaut, apparaît avec le détecteur -->
				<div id='stopDetectPanel' style="display: none; flex-direction: column; flex-grow: 1; gap: 10px;">
					<h3 class='tab-subtitle'>Diagnostic Stop</h3>
					<div style="background: white; border-radius: 20px; border: 2px solid #55efc4; padding: 15px; display: flex; flex-direction: column; gap: 10px;">
						<div id='stopDetectIndicator' class='detect-indicator' style="padding:12px; border-radius:12px; text-align:center; font-weight:bold; color:white; background:#bdc3c7; width: 100%; box-sizing: border-box;">Aucune détection</div>
						<div id='stopDetectTerminal' class='log-terminal'>Terminal vide</div>
					</div>
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
			btn.textContent = '⏹️ Arrêter la caméra';
			fetch('/start_camera', { method: 'POST' })
				.then(function(response) {
					if (!response.ok) throw new Error('start_camera failed: ' + response.status + ' ' + response.statusText);
					mainDisplay.style.display = 'block';
					mainImage.src = '/video?' + new Date().getTime();
					DISPLAY_MODE = 'livefeed';
					CAMERA_ACTIVE = true;
					captureBtn.textContent = '📸 Capture Image';
					captureBtn.onclick = captureImage;
				})
				.catch(function(err) {
					logError('toggleCamera: /start_camera', err);
					btn.textContent = '🎥 Allumer la caméra !';
					CAMERA_ACTIVE = false;
				});
		} else {
			// Arrêter la caméra
			mainDisplay.style.display = 'none';
			btn.textContent = '🎥 Allumer la caméra !';
			mainImage.src = "";
			DISPLAY_MODE = 'livefeed';
			CAMERA_ACTIVE = false;
			captureBtn.textContent = '📸 Capture Image';
			captureBtn.onclick = captureImage;
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
					alert('Image capturee et enregistree sur le serveur : ' + download_url);
					var link = document.createElement('a');
					link.href = download_url;
					link.download = filename;
					document.body.appendChild(link);
					link.click();
					link.remove();
				}

				// Basculer vers l'image capturée dans l'affichage principal
				var mainImage = document.getElementById('mainImage');
				var mainDisplay = document.getElementById('mainImageDisplay');
				var captureBtn = document.getElementById('captureImageBtn');

				mainImage.src = file_url;
				mainDisplay.style.display = 'block';
				DISPLAY_MODE = 'captured';
				captureBtn.textContent = '↩️ Return to Livefeed';
				captureBtn.onclick = returnToLivefeed;

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
			captureBtn.onclick = captureImage;
		} else {
			// Caméra pas active, la redémarrer
			var btn = document.getElementById('cameraToggleBtn');
			btn.textContent = '⏹️ Arrêter la caméra';
			fetch('/start_camera', { method: 'POST' })
				.then(function(response) {
					if (!response.ok) throw new Error('start_camera failed: ' + response.status + ' ' + response.statusText);
					mainDisplay.style.display = 'block';
					mainImage.src = '/video?' + new Date().getTime();
					DISPLAY_MODE = 'livefeed';
					CAMERA_ACTIVE = true;
					captureBtn.textContent = '📸 Capture Image';
					captureBtn.onclick = captureImage;
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
					updateStopUIPanelVisibility();
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
		updateStopUIPanelVisibility();
	}

	function runDetection() {
		var terminal = document.getElementById('stopDetectTerminal');
		var indicator = document.getElementById('stopDetectIndicator');
		clearTerminal();
		fetch('/run_detection', { method: 'POST' })
			.then(function(r) { if (!r.ok) throw new Error('run_detection failed: ' + r.status + ' ' + r.statusText); return r.json(); })
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

				// Utiliser Object_detected au lieu de Stop_detected
				if (res.Object_detected) {
					indicator.classList.add('on');
					indicator.textContent = 'STOP detecte';
				} else {
					indicator.classList.add('off');
					indicator.textContent = 'Aucune detection';
				}
			})
			.catch(function(err) {
				logError('runDetection: /run_detection', err);
				var terminal = document.getElementById('stopDetectTerminal');
				terminal.style.display = 'block';
				appendTerminalLines('Erreur: ' + err);
			});
	}

	function updateStopUIPanelVisibility() {
		var panel = document.getElementById('stopDetectPanel');
		if (!SELECTED_DETECTOR_NAME) { panel.style.display = 'none'; return; }
		// Afficher pour tout détecteur de stop (Zumi ou CV)
		panel.style.display = (SELECTED_DETECTOR_NAME.indexOf('StopDetector') !== -1) ? 'block' : 'none';
	}

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
		console.log('[DEBUG runGenericDiagnostics] Function called, fetching /diagnose_detector');
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
				// Stop detecté - utiliser Object_detected
				if (payload.Object_detected) {
					indicator.classList.add('on');
					indicator.textContent = 'STOP detecte';
				} else {
					indicator.classList.add('off');
					indicator.textContent = 'Aucune detection';
				}

				// best bbox overlay - utiliser annotated_url
				var imgUrl = (payload.steps && payload.steps.length) ? payload.steps[payload.steps.length - 1].url : payload.source_file_url;
				if (imgUrl) { imageCapturedCallback(imgUrl); }
				// enleve le draw de la bbox on le fait directement dans le backend sur une copie de l'image qu'on affiche ensuite
				if (payload.detection_box) {
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
		console.log('[DEBUG runDiagnostics] SELECTED_DETECTOR_NAME:', detectorName);

		if (detectorName === 'StopDetectorZumi') {
			// Détecteur Zumi spécifique avec balayage de paramètres
			console.log('[DEBUG runDiagnostics] Matched "StopDetectorZumi", calling runStopDiagnostics');
			runStopDiagnostics();
		} else if (detectorName.indexOf('StopDetector') !== -1) {
			// Tous les autres détecteurs de stop (CV, Matt, etc.) utilisent la route générique
			console.log('[DEBUG runDiagnostics] Matched detector containing "StopDetector", calling runGenericDiagnostics');
			runGenericDiagnostics();
		} else {
			console.log('[DEBUG runDiagnostics] No match, showing alert');
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
	window.returnToLivefeed = returnToLivefeed;
	window.runDetection = runDetection;
	window.runDiagnostics = runDiagnostics;
	window.onDetectorChange = onDetectorChange;
	</script>
	</body></html>
	"""

	# Remplacer uniquement le titre sans interpréter les autres accolades
	return html.replace("{title}", title)