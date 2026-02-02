#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_acceuil.py
# ------------------
# ce module défini un onglet de l'interface web dédié à l'accueil
# on y trouve notamment des boutons pour naviguer vers les autres onglets,
# un livefeed de la caméra, les boutons de contrôle du Zumi, les boutons de
# choix de scénarios et les boutons de contrôle du pont levis.

def render_accueil_tab(title: str = "Accueil") -> str:
	"""Retourne la page HTML complète de l'onglet d'accueil.
	"""

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
	}}

	/* --- Déclarations des différents styles de conteneurs --- */

	/* Container principal des éléments de l'onglet */
    .container {
		display: flex; justify-content: center; align-items: flex-start;
		padding: 20px; height: calc(100vh - 40px);
	}}

    /* Shell de l'onglet avec fond blanc et ombre */
    .tab-shell {
		background: rgba(255,255,255,0.92);
		border-radius: 16px;
		padding: 18px;
		box-shadow: 0 0 15px rgba(0,0,0,0.12);
		width: min(980px, 100%);
	}}

	.left-panel, .right-panel {
        background: white;
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 0 15px rgba(0,0,0,0.2);
        flex: 1;
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
	}}

    /* Boite de boutons de navigation entre onglets */
    .tab-nav {
		display: flex; align-items: center;
		gap: 4px;
		margin-left: auto; /* pousse la nav à droite */
	}}

    /* Boite de contenu, contour pointillé */
    .tab-content {
		border: 2px dashed #bcdffb;
		border-radius: 12px;
		padding: 16px;
		min-height: 200px;
		background: #f7fbff;
	}}

    /* Ligne horizontale pour agencer des éléments */
    .tab-row {
		display: flex; align-items: flex-start; gap: 12px;
	}}

	/* --- Styles pour les différents types de texte --- */
	
    /* Boite de texte format titre */
    .tab-title {
		font-size: 22px; font-weight: bold; margin: 0;
	}}

    /* Boite de texte format sous-titre */
    .tab-subtitle {
		font-size: 18px; font-weight: bold; margin: 0;
	}}

    /* Boite de texte format texte normal */
    .tab-text {
		font-size: 16px; font-weight: normal; margin: 0;
	}}

	/* --- Déclarations des différents styles de widgets --- */

	/* style bouton cliquable principal */
    .primary-btn {
		background: #007acc; color: white; border: none;
		padding: 10px 18px; border-radius: 10px;
		cursor: pointer; font-size: 15px;
	}}

    .primary-btn:hover { background: #005fa3; }

	/* état actif pour le bouton d'onglet courant */
    .primary-btn.active {
		background: #00528a;
		box-shadow: 0 0 0 2px rgba(0,0,0,0.06) inset;
	}}

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
    }}

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
    }}

    .live-feed img {
        width: 50%; 
        max-width: 650px; 
        height: auto; 
        border-radius: 8px; 
        border: 4px solid #00BFFF; 
        margin-top: 10px; 
    }}

	
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
				<button class='primary-btn' data-path="/" onclick="location.href='/'">Accueil</button>
				<button class='primary-btn' data-path="/vision" onclick="location.href='/vision'">Vision</button>
				<button class='primary-btn' data-path="/onglet_template" onclick="location.href='/onglet_template'">Template</button>
                <button class='primary-btn' onclick="fetch('/exit', {method:'POST'})">EXIT</button>
				</div>
			</div>

			<div class='tab-content'>
				<!-- AJOUTER VOS BOUTONS ICI -->
				<div class='left-panel'>
					<button class='toggle-btn' id='cameraToggleBtn' onclick='toggleCamera()'>▶️ Start Camera</button>
					<div id='zone-resultats'>
						<!-- Conteneur du flux vidéo en direct -->
						<div class='live-feed' id='liveFeed' style = 'display:none;'>
							<img id='videoStream' alt='Flux vidéo en direct'>
						</div>
					</div>
				</div>

				<div class='right-panel'>
					<div class='driving-mode'>
						<h3>Contrôle du Zumi</h3>
						<div class="dpad-container">
                            <div style="margin-top: 20px; border-top: 1px solid #ccc; padding-top: 10px;">
                            <button onclick="calibrateZumi()" style="background-color: #f39c12; color: white; padding: 12px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%;">
                                🔧 Recalibrer les Capteurs
                            </button>
							<!-- HAUT -->
							<button 
								class="dpad-button dpad-up" 
								onmousedown="startMove('forward')" onmouseup="stopMove()" onmouseleave="stopMove()"
								ontouchstart="startMove('forward')" ontouchend="stopMove()">
								<svg viewBox="0 0 100 100"><path d="M50 20 L50 80 M20 50 L50 20 L80 50"></path></svg>
							</button>
							<!-- GAUCHE -->
							<button 
								class="dpad-button dpad-left"
								onmousedown="startMove('left')" onmouseup="stopMove()" onmouseleave="stopMove()"
								ontouchstart="startMove('left')" ontouchend="stopMove()">
								<svg viewBox="0 0 100 100"><path d="M80 50 L20 50 M50 20 L20 50 L50 80"></path></svg>
							</button>
							<!-- CENTRE (Stop) -->
							<button class="dpad-button dpad-center" onclick="stopMove()"></button>
							<!-- DROITE -->
							<button 
								class="dpad-button dpad-right"
								onmousedown="startMove('right')" onmouseup="stopMove()" onmouseleave="stopMove()"
								ontouchstart="startMove('right')" ontouchend="stopMove()">
								<svg viewBox="0 0 100 100"><path d="M20 50 L80 50 M50 20 L80 50 L50 80"></path></svg>
							</button>
							<!-- BAS -->
							<button 
								class="dpad-button dpad-down"
								onmousedown="startMove('reverse')" onmouseup="stopMove()" onmouseleave="stopMove()"
								ontouchstart="startMove('reverse')" ontouchend="stopMove()">
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
	// Active l'état du bouton d'onglet selon l'URL courante
    (function() {
		const norm = p => (p || '').replace(/\/+$/,'') || '/';
		const here = norm(location.pathname);
        document.querySelectorAll('.tab-nav .primary-btn').forEach(btn => {
			const p = norm(btn.dataset?.path || btn.getAttribute('data-path'));
			if (p === here) btn.classList.add('active');
        });
    })();

    function toggleCamera() { 
        console.log("toggleCamera() appelée"); // pour debug

        const liveFeed = document.getElementById('liveFeed'); 
        const btn = document.getElementById('cameraToggleBtn'); 
        const img = liveFeed.querySelector('img'); 

        const isActive = liveFeed.style.display === 'block';

        if (!isActive) {
            // 1. Affiche le conteneur et change le bouton (pour la réactivité)  
            btn.textContent = '⛔ Stop Camera'; 

            // 2. Envoie la commande de démarrage au serveur 
            fetch('/start_camera', { method: 'POST' }) 
                .then(() => {
                // 3. ATTEND que le serveur ait confirmé le démarrage avant de demander le flux vidéo. 
                liveFeed.style.display = 'block';
                img.src = '/video?' + new Date().getTime(); 
            }); 
        
        } else {
            // 1. Cache le conteneur et change le bouton 
            liveFeed.style.display = 'none'; 
            btn.textContent = '▶️ Start Camera'; 
            
            // 2. Vide la source de l'image (arrête le flux gelé) 
            img.src = "";  
            
            // 3. Envoie la commande d'arrêt au serveur 
            fetch('/close_camera', { method: 'POST' }); 
        }
    }

	// --- NOUVEAU : Modifications pour le Watchdog ---
    let isMoving = false;
    let moveInterval = null; // Variable pour stocker notre 'setInterval'

    function startMove(direction) {
        if (isMoving) return; // Évite les commandes multiples
        isMoving = true;
        
        // Fonction interne pour envoyer la commande
        const sendMoveCommand = () => {
            fetch('/zumi/' + direction)
                .then(response => {
                    if (!response.ok) console.error('Error starting move: ' + direction);
                })
                .catch(error => console.error('Fetch error:', error));
        };

        // 1. Envoyer la commande 1x immédiatement pour la réactivité
        sendMoveCommand(); 
        
        // 2. Démarrer un intervalle qui 'nourrit' le watchdog 4x par seconde (250ms)
        moveInterval = setInterval(sendMoveCommand, 250);
    }

    function stopMove() {
        if (!isMoving) return; // Évite les 'stop' inutiles
        isMoving = false;
        
        // 1. Arrêter l'envoi de commandes en continu
        if (moveInterval) {
            clearInterval(moveInterval);
            moveInterval = null;
        }
        
        // 2. Envoyer la commande d'arrêt explicite
        fetch('/zumi/stop')
            .then(response => {
                if (!response.ok) console.error('Error stopping move');
            })
            .catch(error => console.error('Fetch error:', error));
    }
    // --- FIN DES MODIFICATIONS WATCHDOG ---

    // Sécurité : si l'utilisateur relâche le clic n'importe où sur la page
    window.addEventListener('mouseup', stopMove);
    window.addEventListener('touchend', stopMove);

	</script>
	</body></html>
	"""

	# Remplacer uniquement le titre sans interpréter les autres accolades
	return html.replace("{title}", title)


