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

    # Vision actions
    app.add_url_rule('/download_image/<filename>', 'download_image', lambda filename: ctrl.download_image(filename))
    app.add_url_rule('/capture_image', 'capture_image', lambda: ctrl.capture_image(), methods=['POST'])
    app.add_url_rule('/status', 'status', lambda: ctrl.status())
    app.add_url_rule('/video', 'video_feed', lambda: ctrl.video_feed())
    app.add_url_rule('/close_camera', 'close_camera', lambda: ctrl.close_camera(), methods=['POST'])
    app.add_url_rule('/start_camera', 'start_camera', lambda: ctrl.start_camera(), methods=['POST'])

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

    # Page PID
    app.add_url_rule('/pid', 'pid_page', lambda: ctrl.pid_page())

    # Routes PID
    app.add_url_rule('/pid/update_params', 'pid_update_params', lambda: ctrl.pid_update_params(), methods=['POST'])
    app.add_url_rule('/pid/get_params', 'pid_get_params', lambda: ctrl.pid_get_params())
    app.add_url_rule('/pid/start', 'pid_start', lambda: ctrl.pid_start(), methods=['POST'])
    app.add_url_rule('/pid/stop', 'pid_stop', lambda: ctrl.pid_stop(), methods=['POST'])
    app.add_url_rule('/pid/reset', 'pid_reset', lambda: ctrl.pid_reset(), methods=['POST'])
    app.add_url_rule('/pid/status', 'pid_status', lambda: ctrl.pid_status())
    # Routes pour le détecteur de ligne
    app.add_url_rule('/line_detector/update_params', 'line_detector_update_params', 
                    lambda: ctrl.line_detector_update_params(), methods=['POST'])
    app.add_url_rule('/line_detector/get_params', 'line_detector_get_params', 
                    lambda: ctrl.line_detector_get_params())

    return app
