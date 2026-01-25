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

	return """<!DOCTYPE html><html lang='fr'>
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

	/* --- Déclarations des différents styles de conteneurs --- */

	/* Container principal des éléments de l'onglet */
	.container {{
		display: flex; justify-content: center; align-items: flex-start;
		padding: 20px; height: calc(100vh - 40px);
	}}

	// Shell de l'onglet avec fond blanc et ombre
	.tab-shell {{
		background: rgba(255,255,255,0.92);
		border-radius: 16px;
		padding: 18px;
		box-shadow: 0 0 15px rgba(0,0,0,0.12);
		width: min(980px, 100%);
	}}

	// Boite d'entête
	.tab-header {{
		display: flex; align-items: center;
		margin-bottom: 12px;
	}}

	// Boite de boutons de navigation entre onglets
	.tab-nav {{
		display: flex; align-items: center;
		gap: 4px;
		margin-left: auto; /* pousse la nav à droite */
	}}

	// Boite de contenu, contour pointillé
	.tab-content {{
		border: 2px dashed #bcdffb;
		border-radius: 12px;
		padding: 16px;
		min-height: 200px;
		background: #f7fbff;
	}}

	// Ligne horizontale pour agencer des éléments
	.tab-row {{
		display: flex; align-items: flex-start; gap: 12px;
	}}

	/* --- Styles pour les différents types de texte --- */
	
	// Boite de texte format titre
	.tab-title {{
		font-size: 22px; font-weight: bold; margin: 0;
	}}

	// Boite de texte format sous-titre
	.tab-subtitle {{
		font-size: 18px; font-weight: bold; margin: 0;
	}}

	// Boite de texte format texte normal
	.tab-text {{
		font-size: 16px; font-weight: normal; margin: 0;
	}}

	/* --- Déclarations des différents styles de widgets --- */

	/* style bouton cliquable principal */
	.primary-btn {{
		background: #007acc; color: white; border: none;
		padding: 10px 18px; border-radius: 10px;
		cursor: pointer; font-size: 15px;
	}}

	.primary-btn:hover {{ background: #005fa3; }}

	/* état actif pour le bouton d'onglet courant */
	.primary-btn.active {{
		background: #00528a;
		box-shadow: 0 0 0 2px rgba(0,0,0,0.06) inset;
	}}

	/* style bouton toggle */
	.toggle-btn {{
        background: #007acc; 
        color: white; 
        border: none; 
        padding: 10px 18px; 
        border-radius: 10px; 
        cursor: pointer; 
        margin-top: 15px; 
        font-size: 15px;
    }}

    .toggle-btn:hover {{ background: #005fa3; }} 

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
				</div>
			</div>

			<div class='tab-content'>
				<!-- AJOUTER VOS BOUTONS ICI -->
				<!-- Exemple :
				<button class='primary-btn' onclick="fetch('/start_camera', {{method:'POST'}})">Start Camera</button>
				<button class='primary-btn' onclick="fetch('/capture_image', {{method:'POST'}})">Capture</button>
				<div id='zone-resultats'></div>
				-->
			</div>
		</div>
	</div>

	<!-- --- Scripts JavaScript pour les interactions --- -->

	<script>
	// Active l'état du bouton d'onglet selon l'URL courante
	(function() {{
		const norm = p => (p || '').replace(/\/+$/,'') || '/';
		const here = norm(location.pathname);
		document.querySelectorAll('.tab-nav .primary-btn').forEach(btn => {{
			const p = norm(btn.dataset?.path || btn.getAttribute('data-path'));
			if (p === here) btn.classList.add('active');
		}});
	}})();

	// Ajoutez ici vos callbacks JS pour câbler les boutons au backend Flask.
	// Exemple :
		async function startCamera() {{ await fetch('/start_camera', {{ method: 'POST' }}); }}
		async function capture() {{ const r = await fetch('/capture_image', {{ method: 'POST' }}); const j = await r.json(); console.log(j); }}
	</script>
	</body></html>
	""".format(title=title)


