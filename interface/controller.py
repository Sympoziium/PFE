# definir les fonctions utiliser par les routes ex : activer lumiere rouge, demarrer detection, etc pour les appeler par les routes.


from flask import request
from interface.flask_server import app

def exit_server():
    global vision_pipeline
    try:
        if vision_pipeline and vision_pipeline.is_running():
            vision_pipeline.stop()
    except Exception:
        pass

    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        return jsonify({"error": "shutdown unavailable"}), 500
    app.logger.info("Arrêt du serveur Flask demandé via /EXIT")
    func()  # Le serveur s'arrêtera après cette requête
    return ('', 204)
