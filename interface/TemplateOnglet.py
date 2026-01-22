# TemplateOnglet.py
# ------------------
# Template de base (HTML/CSS/JS inline) pour un onglet vide prêt à être branché dans Flask.
# Procédure pour l'utiliser dans le serveur Flask :
# 1) Importer `render_template_tab` et appeler la fonction pour obtenir une string HTML complète (page autonome).
# 2) Coller/retourner cette string dans un endpoint (ex.: `return render_template_tab("Vision")`).
# 3) Remplacer la zone marquée "<!-- AJOUTER VOS BOUTONS ICI -->" par vos boutons/contrôles spécifiques.
# 4) Reprendre le style du serveur existant (fond dégradé, boutons bleus) déjà inclus ci-dessous.
# 5) Si vous voulez plusieurs onglets, vous pouvez dupliquer ce fichier avec d'autres noms ou composer plusieurs blocs dans un template parent.


def render_template_tab(title: str = "Onglet générique") -> str:
	"""Retourne une page HTML complète avec un onglet vide et le style existant.

	Le HTML est autonome : styles, structure et JS minimal pour cliquer sur des boutons si ajoutés.
	La page est volontairement vide de contrôles; insérez vos boutons à l'endroit indiqué.
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
	border: 2px dashed #bcdffb;
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
</style>
</head>
<body>
  <div class='container'>
	<div class='tab-shell'>
	  <div class='tab-header'>
		<h2 class='tab-title'>{title}</h2>
		<div class='tab-nav'>
		  <!-- Boutons de navigation entre onglets (exemples; à remplacer) -->
		  <button class='primary-btn' onclick="alert('Action onglet accueil (à remplacer)');">Accueil</button>
	  	  <button class='primary-btn' onclick="alert('Action onglet template (à remplacer)');">Template</button>
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

  <script>
  // Ajoutez ici vos callbacks JS pour câbler les boutons au backend Flask.
  // Exemple :
    async function startCamera() {{ await fetch('/start_camera', {{ method: 'POST' }}); }}
    async function capture() {{ const r = await fetch('/capture_image', {{ method: 'POST' }}); const j = await r.json(); console.log(j); }}
  </script>
</body></html>
"""


# Rappel d'intégration rapide dans Flask (page simple) :
# from interface.TemplateOnglet import render_template_tab
# @app.route('/mon_onglet')
# def mon_onglet():
#     html = render_template_tab("Mon onglet perso")
#     return html


