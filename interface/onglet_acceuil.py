#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_acceuil.py
# ------------------
# ce module défini un onglet de l'interface web dédié à l'accueil
# on y trouve notamment des boutons pour naviguer vers les autres onglets,
# un livefeed de la caméra, les boutons de contrôle du Zumi, les boutons de
# choix de scénarios et les boutons de contrôle du pont levis.

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
    
    /* SWITCH CSS */
    .switch { position: relative; display: inline-block; width: 50px; height: 24px; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 34px; }
    .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
    input:checked + .slider { background-color: #2196F3; }
    input:checked + .slider:before { transform: translateX(26px); }
    
    /* --- CLASSE POUR DÉSACTIVER LES BOUTONS --- */
    .disabled { 
        background-color: #cccccc !important; 
        color: #666666 !important; 
        cursor: not-allowed; 
        pointer-events: none; 
        box-shadow: none;
    }

    .left-panel {
        margin-right: 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .right-panel { overflow-y: auto; }

    /* Boite d'entête */
    .tab-header {
		display: flex; align-items: center;
		margin-bottom: 12px;
	}

    /* Boite de boutons de navigation entre onglets */
    .tab-nav {
		display: flex; align-items: center;
		gap: 4px;
		margin-left: auto; /* pousse la nav à droite */
	}

    /* Boite de contenu, contour pointillé */
    .tab-content {
		border: 2px dashed #bcdffb;
		border-radius: 12px;
		padding: 16px;
		min-height: 200px;
		background: #f7fbff;
	}

    /* Ligne horizontale pour agencer des éléments */
    .tab-row {
		display: flex; align-items: flex-start; gap: 12px;
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

	/* --- definition des elements de controle du robot --- */
	.command-button {
        margin: 5px;
        padding: 10px 15px;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        cursor: pointer;
    }

        .driving-mode {
            background-color: #e0f7fa;
            padding: 15px;
            border-radius: 15px;
            text-align: center;
            margin-top: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            align-items: center; /* Centre le D-pad */
        }

        .driving-mode h3 {
            margin-bottom: 10px;
        }

        /* Conteneur principal pour le D-pad */
        .dpad-container {
            display: grid;
            /* Définit la disposition en 3x3 */
            grid-template-areas:
                ".     up     ."
                "left  center right"
                ".     down   .";
            grid-gap: 8px; /* Espace entre les boutons */
            width: 180px;  /* Taille réduite pour s'adapter */
            height: 180px; /* Taille réduite pour s'adapter */
        }

        .dpad-button {
            background-color: #e0e0e0; /* Gris clair */
            border: none;
            border-radius: 20px; /* Coins arrondis */
            cursor: pointer;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: all 0.15s ease-out;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 
                        inset 0 1px 1px rgba(255, 255, 255, 0.7);
            user-select: none; /* Empêche la sélection de texte/icône */
        }

        .dpad-button:hover {
            background-color: #d0d0d0;
        }

        /* Effet d'enfoncement au clic/toucher */
        .dpad-button:active {
            background-color: #c0c0c0;
            transform: scale(0.95);
            box-shadow: 0 2px 3px rgba(0, 0, 0, 0.1);
        }

        /* Icônes SVG pour les flèches (couleur #555) */
        .dpad-button svg {
            width: 50%;
            height: 50%;
            stroke: #555;
            stroke-width: 12;
            stroke-linecap: round;
            stroke-linejoin: round;
            fill: none;
        }

        /* Assignation aux zones de la grille */
        .dpad-up { grid-area: up; }
        .dpad-down { grid-area: down; }
        .dpad-left { grid-area: left; }
        .dpad-right { grid-area: right; }

        .dpad-center {
            grid-area: center;
            background-color: #ffffff; /* Centre blanc */
            border: 3px solid #e0e0e0;
        }
        .dpad-center:hover { background-color: #f0f0f0; }
        .dpad-center:active { background-color: #e0e0e0; }


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

	
	/* --- Arrangements des éléments de l'interface --- */
	
	</style>
	</head>
	<body>
	<div class='container'>
		<div class='tab-shell'>
			<div class='tab-header'>
				<h2 class='tab-title'>{title}</h2>
				<div class='tab-nav'>
				<!-- Boutons de navigation entre onglets -->
				<button class='primary-btn' data-path="/">Accueil</button>
				<button class='primary-btn' data-path="/vision">Vision</button>
				<button class='primary-btn' data-path="/onglet_template">Template</button>
                <button class='primary-btn' onclick="fetch('/exit', {method:'POST'})">EXIT</button>
				</div>
			</div>

			<div class='tab-content'>
				<!-- AJOUTER VOS BOUTONS ICI -->
				<div class='left-panel'>
					<button class='toggle-btn' id='cameraToggleBtn'>▶️ Start Camera</button>
					<div id='zone-resultats'>
						<!-- Conteneur du flux vidéo en direct -->
						<div class='live-feed' id='liveFeed' style = 'display:none;'>
							<img id='videoStream' alt='Flux vidéo en direct'>
              <hr style="width:100%; margin: 20px 0; border: 1px solid #ccc;">

                <h3>🌉 Pont Levis</h3>

                <div style="margin-bottom:15px; display:flex; align-items:center; gap:10px;">
                    <span style="font-weight:bold;">Mode Auto:</span>
                    <label class="switch">
                      <input type="checkbox" id="autoCheck" checked>
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
					</div>
				</div>

				<div class='right-panel'>
					<div class='driving-mode'>
						<h3>Contrôle du Zumi</h3>
						<div class="dpad-container">
							<!-- HAUT -->
							<button class="dpad-button dpad-up" data-direction="forward">
								<svg viewBox="0 0 100 100"><path d="M50 20 L50 80 M20 50 L50 20 L80 50"></path></svg>
							</button>
							<!-- GAUCHE -->
							<button class="dpad-button dpad-left" data-direction="left">
								<svg viewBox="0 0 100 100"><path d="M80 50 L20 50 M50 20 L20 50 L50 80"></path></svg>
							</button>
							<!-- CENTRE (Stop) -->
							<button class="dpad-button dpad-center" id="dpadCenterBtn"></button>
							<!-- DROITE -->
							<button class="dpad-button dpad-right" data-direction="right">
								<svg viewBox="0 0 100 100"><path d="M20 50 L80 50 M50 20 L80 50 L50 80"></path></svg>
							</button>
							<!-- BAS -->
							<button class="dpad-button dpad-down" data-direction="reverse">
								<svg viewBox="0 0 100 100"><path d="M50 80 L50 20 M20 50 L50 80 L80 50"></path></svg>
							</button>
        				</div>
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

	// --- Unified error logging (console) ---
	function nowTS() { return new Date().toISOString(); }
	function logError(context, error, extra) {
		var msg = (error && error.message) ? error.message : String(error);
		console.error('[UI][' + nowTS() + '] ' + context + ': ' + msg, extra || '');
	}

	// Global error hooks for visibility
	window.addEventListener('error', function(e) {
		logError('window.onerror', e.error || e.message);
	});
	window.addEventListener('unhandledrejection', function(e) {
		logError('window.unhandledrejection', e.reason);
	});

	// État global : état caméra
	var CAMERA_ACTIVE = false;

	// Navigation helper: close camera feed if active before redirecting
	function navigateTo(path) {
		try {
			var liveFeed = document.getElementById('liveFeed');
			var isActive = CAMERA_ACTIVE && liveFeed && liveFeed.style.display === 'block';
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
		var liveFeed = document.getElementById('liveFeed');
		var img = document.getElementById('videoStream');
		var btn = document.getElementById('cameraToggleBtn');
		var isActive = CAMERA_ACTIVE && liveFeed.style.display === 'block';

		if (!isActive) {
			// Démarrer la caméra
			btn.textContent = '⛔ Stop Camera';
			fetch('/start_camera', { method: 'POST' })
				.then(function(response) {
					if (!response.ok) throw new Error('start_camera failed: ' + response.status + ' ' + response.statusText);
					liveFeed.style.display = 'block';
					img.src = '/video?' + new Date().getTime();
					CAMERA_ACTIVE = true;
				})
				.catch(function(err) {
					logError('toggleCamera: /start_camera', err);
					btn.textContent = '▶️ Start Camera';
					CAMERA_ACTIVE = false;
				});
		} else {
			// Arrêter la caméra
			liveFeed.style.display = 'none';
			btn.textContent = '▶️ Start Camera';
			img.src = '';
			CAMERA_ACTIVE = false;
			fetch('/close_camera', { method: 'POST' }).catch(function(err) { logError('toggleCamera: /close_camera', err); });
		}
	}

	// --- MODE AUTO ET GESTION UI ---
	function toggleAuto(isAuto) {
		var val = isAuto ? '1' : '0';
		fetch('/bridge/mode_auto/' + val, { method: 'POST' })
			.then(function() { console.log('Mode auto changé: ' + val); })
			.catch(function(err) { logError('toggleAuto', err, { val: val }); });

		var btnOpen = document.getElementById('btnOpen');
		var btnClose = document.getElementById('btnClose');
		if (isAuto) {
			btnOpen.classList.add('disabled');
			btnClose.classList.add('disabled');
		} else {
			btnOpen.classList.remove('disabled');
			btnClose.classList.remove('disabled');
		}
	}

	// --- FONCTIONS DE MOUVEMENT ---
	var isMoving = false;
	var moveInterval = null;

	function startMove(direction) {
		if (isMoving) return;
		isMoving = true;

		var sendMoveCommand = function() {
			fetch('/zumi/' + direction)
				.then(function(response) {
					if (!response.ok) logError('startMove', new Error('move failed'), { direction: direction });
				})
				.catch(function(error) { logError('startMove: fetch', error, { direction: direction }); });
		};

		sendMoveCommand();
		moveInterval = setInterval(sendMoveCommand, 250);
	}

	function stopMove() {
		if (!isMoving) return;
		isMoving = false;
		if (moveInterval) {
			clearInterval(moveInterval);
			moveInterval = null;
		}
	}

	// --- Charger les événements au DOMContentLoaded ---
	window.addEventListener('DOMContentLoaded', function() {
		// Navigation buttons (utilise data-path pour déterminer la destination)
		var navBtns = document.querySelectorAll('.tab-nav .primary-btn');
		Array.prototype.forEach.call(navBtns, function(btn) {
			var path = btn.getAttribute('data-path');
			if (path) {
				btn.addEventListener('click', function() { navigateTo(path); });
			}
		});

		// Camera toggle
		var camBtn = document.getElementById('cameraToggleBtn');
		if (camBtn) camBtn.addEventListener('click', toggleCamera);

		// Auto check (pont levis)
		var autoCheck = document.getElementById('autoCheck');
		if (autoCheck) autoCheck.addEventListener('change', function() { toggleAuto(this.checked); });

		// D-pad: register mouse + passive touch events
		var dpadButtons = document.querySelectorAll('.dpad-button[data-direction]');
		Array.prototype.forEach.call(dpadButtons, function(btn) {
			var dir = btn.getAttribute('data-direction');
			btn.addEventListener('mousedown', function() { startMove(dir); });
			btn.addEventListener('mouseup', stopMove);
			btn.addEventListener('mouseleave', stopMove);
			btn.addEventListener('touchstart', function() { startMove(dir); }, { passive: true });
			btn.addEventListener('touchend', stopMove, { passive: true });
		});

		// D-pad center button (stop)
		var centerBtn = document.getElementById('dpadCenterBtn');
		if (centerBtn) centerBtn.addEventListener('click', stopMove);
	});

	// Exposer les fonctions au scope global (pour les onclick inline restants)
	window.navigateTo = navigateTo;
	window.toggleCamera = toggleCamera;
	window.toggleAuto = toggleAuto;
	window.startMove = startMove;
	window.stopMove = stopMove;

	</script>
    </body></html>
    """
    return html.replace("{title}", title)