#!/usr/bin/env python
# -*- coding: utf-8 -*-
# onglet_template.py
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
        border-radius: 20px;
        padding: 2%;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        width: 92%; max-width: 1100px;
        min-height: fit-content; margin-bottom: 4vh;
        display: flex; flex-direction: column;
    }

    .tab-header {
        display: flex; align-items: center;
        margin-bottom: 2vh;
        padding-bottom: 1vh;
        border-bottom: 2px solid #e0f4ff;
    }

    .tab-nav {
        display: flex; align-items: center;
        gap: 8px;
        margin-left: auto;
    }

    .tab-content {
        border: 3px dashed #B5FFFC;
        border-radius: 15px;
        padding: 3%;
        background: #FFFDF0;
        margin-bottom: 16px;
    }

    .tab-row {
        display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap;
    }

    .tab-title {
        font-size: 1.8rem; font-weight: bold; color: #5A99C7; margin: 0;
    }

    .tab-subtitle {
        font-size: 1.3rem; font-weight: bold; color: #666; margin-bottom: 15px; margin-top: 0;
    }

    .tab-text {
        font-size: 1.1rem; color: #444;
    }

    .primary-btn {
        background: #87C7F1; color: white; border: none;
        padding: 12px 20px; border-radius: 12px;
        cursor: pointer; font-size: 1rem; font-weight: bold;
        transition: transform 0.2s, background 0.2s;
        box-shadow: 0 4px 0 #6BAED6;
    }

    .primary-btn:hover {
        background: #76B9E4;
        transform: translateY(-2px);
    }

    .primary-btn:active {
        transform: translateY(2px);
        box-shadow: 0 2px 0 #6BAED6;
    }

    .primary-btn.active {
        background: #5A99C7;
        box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
    }

    .toggle-btn {
        background: #FFB7D5; color: white; border: none;
        padding: 12px 24px; border-radius: 12px;
        cursor: pointer; font-weight: bold; font-size: 1rem;
        box-shadow: 0 4px 0 #E896B9;
        transition: transform 0.2s, background 0.2s;
    }

    .toggle-btn:hover { background: #FFA3C8; transform: translateY(-2px); }
    .toggle-btn:active { transform: translateY(2px); box-shadow: 0 2px 0 #E896B9; }

    </style>
    </head>
    <body>
    <div class='container'>
        <div class='tab-shell'>
            <div class='tab-header'>
                <h2 class='tab-title'>{title}</h2>
                <div class='tab-nav'>
                <button class='primary-btn' data-path="/" onclick="navigateTo('/')">Accueil</button>
                <button class='primary-btn' data-path="/vision" onclick="navigateTo('/vision')">Vision</button>
                <button class='primary-btn' data-path="/pid" onclick="navigateTo('/pid')">PID</button>
                                </div>
            </div>

            <div class='tab-content'>
                <!-- AJOUTER VOS BOUTONS ICI -->
            </div>
        </div>
    </div>

    <script>
    (function() {
        var norm = function(p) { return (p || '').replace(/\/+$/,'') || '/'; };
        var here = norm(location.pathname);
        var btns = document.querySelectorAll('.tab-nav .primary-btn');
        Array.prototype.forEach.call(btns, function(btn) {
            var p = norm(btn.getAttribute('data-path'));
            if (p === here) btn.classList.add('active');
        });
    })();

    function navigateTo(path) {
        location.href = path;
    }
    </script>
    </body></html>
    """

    # Remplacer uniquement le titre sans interpréter les autres accolades
    return html.replace("{title}", title)


# Rappel d'intégration rapide dans Flask (page simple) :
# dans flask_router.py :
# app.add_url_rule('/onglet_template', 'template', lambda: ctrl.onglet_template())
#
# dans controller.py :
# def onglet_template(self):
#     return render_template_tab("Mon onglet perso")


