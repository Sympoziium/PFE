from server_controller import controller
from flask_router import register_routes
from mock_zumi import MockZumi

if __name__ == "__main__":
    # 1. Créer un faux robot
    zumi = MockZumi()

    # 2. Créer le contrôleur
    ctrl = controller(zumi)

    # 3. Enregistrer les routes Flask
    app = register_routes(ctrl)

    # 4. Lancer le serveur
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
