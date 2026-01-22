# onglet_vision.py
# ------------------
# ce module défini un onglet de l'interface web dédié au fonctionnalitées du module de vision
# ------------------

from interface.TemplateOnglet import render_template_tab





def render_vision_tab(title: str = "Vision du Zumi") -> str:
	"""Retourne une page HTML complète avec un onglet vide et le style existant.


	"""

	return f"""<!DOCTYPE html><html lang='fr'>
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
	width: min(980px, 100%);
}}

.tab-header {{
	display: flex; align-items: center;
	margin-bottom: 12px;
}}

.tab-title {{
	font-size: 22px; font-weight: bold; margin: 0;
}}

.tab-nav {{
	display: flex; align-items: center;
	/* Ajustez l'espacement entre boutons ici (2-5px) */
	gap: 4px;
	margin-left: auto; /* pousse la nav à droite */
}}

.tab-content {{
	border: 2px solid #bcdffb;
	border-radius: 12px;
	padding: 16px;
	min-height: 200px;
	background: #f7fbff;
}}

.primary-btn {{
	background: #007acc; color: white; border: none;
	padding: 10px 18px; border-radius: 10px;
	cursor: pointer; font-size: 15px;
}}
.primary-btn:hover {{ background: #005fa3; }}

/* Exemple de style additionnel pour les boutons et zones de résultats */
// container : ces le conteneur principal de l'onglet
// tab-shell : la "coquille" de l'onglet avec le fond blanc et les arrondis
// tab-header : l'entête de l'onglet avec le titre et les actions globales#
// tab-title : le titre de l'onglet
// tab-content : la zone principale de contenu de l'onglet
// l'ordre des classes CSS est déterminé par l'ordre d'apparition dans le HTML 
// on délimite les sections par <div class='XXX'> ... </div> 

</style>
</head>
<body>
  <div class='container'>
	<div class='tab-shell'>
	  <div class='tab-header'>
		<h2 class='tab-title'>{title}</h2>
		<!-- Boutons de navigation entre onglets -->
		<div class='tab-nav'>
		  <!-- Boutons de navigation entre onglets (exemples; à remplacer) -->
		  <button class='primary-btn' onclick="alert('Action onglet accueil (à remplacer)');">Accueil</button>
	  	  <button class='primary-btn' onclick="alert('Action onglet vision (à remplacer)');">Vision</button>
		  <button class='primary-btn' onclick="alert('Action onglet template (à remplacer)');">Template</button>
		</div>
      </div>

	  <div class='tab-content'>
        <div class='tab-header'>
		  <h3 class='tab-title'>{"Capture image"}</h3>
		</div>
		<!-- AJOUT DES FONCTIONS DE CAPTURE -->
		<button class='primary-btn' onclick="onclick="alert('Action activer caméra (à remplacer)')">Start Camera</button>
		<button class='primary-btn' onclick="onclick="alert('Action capture image (à remplacer)')">Capture</button>
		<div id='zone-resultats'></div>
		
	  </div>
	</div>
  </div>

  <script>
  // Ajoutez ici vos callbacks JS pour câbler les boutons au backend Flask.
  // Exemple :
  //  async function startCamera() {{ await fetch('/start_camera', {{ method: 'POST' }}); }}
  //  async function capture() {{ const r = await fetch('/capture_image', {{ method: 'POST' }}); const j = await r.json(); console.log(j); }}
  </script>
</body></html>
"""


#Pour permettre de naviguer entre les onglets
# ----------------------------------------------------------------------------
#                       Pages de l'interface web
# ----------------------------------------------------------------------------


# # Route pour la page d'accueil
# @app.route('/')
# def home():
#     return page_accueil()

# # Route pour l'onglet de vision
# @app.route('/onglet_vision')
# def onglet_vision():
#     html = render_vision_tab("Vision du Zumi")
#     return html

# @app.route('/onglet_template')
# def onglet_template():
#     html = render_template_tab("Mon onglet perso")
#     return html
	
