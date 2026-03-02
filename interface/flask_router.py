#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flask_server.py
# ------------------
"""Définit les routes Flask et les lie aux méthodes du contrôleur backend.
    On déclare ici une route pour chaque bouton ou action du serveur vers
    une méthode du contrôleur.
"""

def register_routes(ctrl):
    app = ctrl.app

    # Pages
    app.add_url_rule('/', 'home', lambda: ctrl.home())
    app.add_url_rule('/vision', 'vision', lambda: ctrl.vision())
    app.add_url_rule('/onglet_template', 'onglet_template', lambda: ctrl.onglet_template())

    # MISC actions
    app.add_url_rule('/exit', 'exit_server', lambda: ctrl.exit_server(), methods=['POST'])
    app.add_url_rule('/resource_usage', 'resource_usage', lambda: ctrl.get_resource_usage())

    # Vision actions
    app.add_url_rule('/download_image/<filename>', 'download_image', lambda filename: ctrl.download_image(filename))
    app.add_url_rule('/capture_image', 'capture_image', lambda: ctrl.capture_image(), methods=['POST'])
    app.add_url_rule('/status', 'status', lambda: ctrl.status())
    app.add_url_rule('/video', 'video_feed', lambda: ctrl.video_feed())
    app.add_url_rule('/close_camera', 'close_camera', lambda: ctrl.close_camera(), methods=['POST'])
    app.add_url_rule('/start_camera', 'start_camera', lambda: ctrl.start_camera(), methods=['POST'])
    app.add_url_rule('/set_resolution', 'set_resolution', lambda: ctrl.set_resolution(), methods=['POST'])
    app.add_url_rule('/start_passive_detection', 'start_passive_detection', lambda: ctrl.start_passive_detection(), methods=['POST'])
    app.add_url_rule('/stop_passive_detection', 'stop_passive_detection', lambda: ctrl.stop_passive_detection(), methods=['POST'])
    app.add_url_rule('/pause_passive_detection', 'pause_passive_detection', lambda: ctrl.pause_passive_detection(), methods=['POST'])
    app.add_url_rule('/resume_passive_detection', 'resume_passive_detection', lambda: ctrl.resume_passive_detection(), methods=['POST'])
    app.add_url_rule('/get_passive_detection', 'get_passive_detection', lambda: ctrl.get_passive_detection(), methods=['GET'])
    # Hard positive mining
    app.add_url_rule('/toggle_mining', 'toggle_mining', lambda: ctrl.toggle_mining(), methods=['POST'])
    app.add_url_rule('/mining_stats', 'mining_stats', lambda: ctrl.mining_stats(), methods=['GET'])
    app.add_url_rule('/download_mining_crops', 'download_mining_crops', lambda: ctrl.download_mining_crops(), methods=['GET'])
    # Détecteurs: liste/selection et exécution
    app.add_url_rule('/detectors', 'detectors', lambda: ctrl.detectors())  # GET
    app.add_url_rule('/detector', 'set_detector', lambda: ctrl.set_detector(), methods=['POST'])
    app.add_url_rule('/run_detection', 'run_detection', lambda: ctrl.run_detection(), methods=['POST'])
    app.add_url_rule('/diagnose_detector', 'diagnose_detector', lambda: ctrl.diagnose_detector(), methods=['POST'])  # Route générique de diagnostic

    # Moteur
    app.add_url_rule('/zumi/forward', 'forward', lambda: ctrl.forward())
    app.add_url_rule('/zumi/reverse', 'reverse', lambda: ctrl.reverse())
    app.add_url_rule('/zumi/left', 'left', lambda: ctrl.left())
    app.add_url_rule('/zumi/right', 'right', lambda: ctrl.right())
    app.add_url_rule('/zumi/stop', 'stop', lambda: ctrl.stop())

    return app
