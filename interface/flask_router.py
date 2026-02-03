#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flask_router.py

def register_routes(ctrl):
    app = ctrl.app

    # Pages Web
    app.add_url_rule('/', 'home', lambda: ctrl.home())
    app.add_url_rule('/vision', 'vision', lambda: ctrl.vision())
    app.add_url_rule('/onglet_template', 'onglet_template', lambda: ctrl.onglet_template())

    # Système
    app.add_url_rule('/exit', 'exit_server', lambda: ctrl.exit_server(), methods=['POST'])

    # Caméra & Vision
    app.add_url_rule('/download_image/<filename>', 'download_image', lambda filename: ctrl.download_image(filename))
    app.add_url_rule('/capture_image', 'capture_image', lambda: ctrl.capture_image(), methods=['POST'])
    app.add_url_rule('/status', 'status', lambda: ctrl.status())
    app.add_url_rule('/video', 'video_feed', lambda: ctrl.video_feed())
    app.add_url_rule('/close_camera', 'close_camera', lambda: ctrl.close_camera(), methods=['POST'])
    app.add_url_rule('/start_camera', 'start_camera', lambda: ctrl.start_camera(), methods=['POST'])

    # Zumi Moteurs
    app.add_url_rule('/zumi/forward', 'forward', lambda: ctrl.forward())
    app.add_url_rule('/zumi/reverse', 'reverse', lambda: ctrl.reverse())
    app.add_url_rule('/zumi/left', 'left', lambda: ctrl.left())
    app.add_url_rule('/zumi/right', 'right', lambda: ctrl.right())
    app.add_url_rule('/zumi/stop', 'stop', lambda: ctrl.stop())

    # --- PONT (Nouveaux liens) ---
    app.add_url_rule('/bridge/open', 'bridge_open', lambda: ctrl.bridge_open(), methods=['POST'])
    app.add_url_rule('/bridge/close', 'bridge_close', lambda: ctrl.bridge_close(), methods=['POST'])
    app.add_url_rule('/bridge/green', 'bridge_green', lambda: ctrl.bridge_green(), methods=['POST'])
    app.add_url_rule('/bridge/red', 'bridge_red', lambda: ctrl.bridge_red(), methods=['POST'])

    return app