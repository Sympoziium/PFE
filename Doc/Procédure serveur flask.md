# Procédure de modification du serveur Flask (mise à jour)

Cette procédure reflète la nouvelle architecture: le backend est géré par la classe `controller` et les routes sont enregistrées via un module routeur (`flask_router.register_routes(ctrl)`). Les pages HTML sont construites dans les onglets (`interface/onglet_*.py`) avec CSS/JS inline.

## Architecture actuelle (résumé)
- Backend: `interface/server_controller.py` contient les méthodes de callback (ex.: `start_camera()`, `forward()`, `exit_server()`). Il expose `self.app` et `attach_pipeline_vision(...)`.
- Routeur: `interface/flask_router.py` fournit `register_routes(ctrl)` et ajoute les endpoints avec `app.add_url_rule(...)` en déléguant à `ctrl`.
- Entrypoint: `main.py` crée `ctrl`, enregistre les routes (`routes.register_routes(ctrl)`) puis lance `ctrl.app.run(...)`.
- Frontend: `interface/onglet_acceuil.py`, `interface/onglet_vision.py`, `interface/onglet_template.py` retournent une string HTML; le titre est injecté via `html.replace("{title}", title)` (ne pas utiliser `format()` sur le HTML).

## Ajout d'un bouton (nouveau flux)
1) Ajouter la méthode backend dans `server_controller.py`:
    ```python
    # interface/server_controller.py
    class controller:
        # ...
        def toggle_light(self):
            # Votre logique backend ici
            # Ex.: self.robot.set_leds(r=255, g=0, b=0)
            return ("", 204)  # ou return jsonify({"ok": True})
    ```

2) Enregistrer la route dans `flask_router.register_routes(ctrl)`:
    ```python
    # interface/flask_router.py
    def register_routes(ctrl):
        app = ctrl.app
        # ... autres routes ...
        app.add_url_rule('/toggle_light', 'toggle_light', lambda: ctrl.toggle_light(), methods=['POST'])
        return app
    ```

3) Ajouter le style CSS du bouton dans l'onglet concerné (ex.: accueil):
    ```css
    /* Ajout du nouveau bouton */
    .nouveau-btn {
        background-color: #4caf50;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        cursor: pointer;
        font-size: 16px;
    }
    .nouveau-btn:hover { background-color: #388e3c; }
    ```
    Notes:
    - Utiliser des **accolades simples** `{}` en CSS/JS.
    - Les commentaires CSS doivent être au format `/* ... */` (éviter `//`).

4) Ajouter la fonction JS qui appelle la route via `fetch`:
    ```javascript
    function onClickNouveauBtn() {
        console.log("onClickNouveauBtn() appelée");
        fetch('/toggle_light', { method: 'POST' })
            .then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); })
            .catch(err => {
                alert('Erreur lors de l\'appel de la fonction : ' + err);
                console.log('Erreur de communication avec le serveur :', err);
            });
    }
    ```

5) Ajouter le bouton dans le HTML de l'onglet et le lier à la fonction JS:
    ```html
    /* Dans interface/onglet_acceuil.py (ou un autre onglet) à l'endroit approprié*/
    "<button class='nouveau-btn' id='nouveaubouton' onclick='onClickNouveauBtn()'>Allumer LED</button>"
    ```

## Bonnes pratiques et pièges évités
- Ne pas utiliser `str.format()` sur les blocks HTML complets (CSS/JS contiennent des `{}` qui provoquent des KeyError). Préférer `html.replace("{title}", title)` pour n'injecter que le titre.
- Éviter `{{` et `}}` en CSS/JS (double accolades), toujours utiliser `{` et `}`.
- Côté routes, rester cohérent avec le routeur: **toutes** les routes passent par `register_routes(ctrl)` et délèguent à `ctrl.<méthode>()`.
- Les endpoints qui modifient l'état (ex.: moteur, caméra, EXIT) doivent être en `POST`.
- L’arrêt du serveur: utiliser `/EXIT` ou `/exit` avec `POST`, qui appelle `ctrl.exit_server()` et arrête proprement Flask + pipeline.

## Exemple complet minimal
Backend (`server_controller.py`):
```python
def set_red_led(self):
    try:
        if self.robot:
            self.robot.set_leds(255, 0, 0)
        return ("", 204)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

Route (`flask_router.py`):
```python
app.add_url_rule('/set_red_led', 'set_red_led', lambda: ctrl.set_red_led(), methods=['POST'])
```

HTML/JS (dans un onglet):
```html
<button class='primary-btn' onclick="setRedLed()">LED Rouge</button>
<script>
function setRedLed() {
  fetch('/set_red_led', { method: 'POST' })
    .then(res => { if (!res.ok) throw new Error(res.status); })
    .catch(err => alert('Erreur: ' + err));
}
</script>
```


