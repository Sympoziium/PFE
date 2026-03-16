#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flask_router.py
# ------------------
"""Définit les routes Flask et les lie aux méthodes du contrôleur backend.
    On déclare ici une route pour chaque bouton ou action du serveur vers
    une méthode du contrôleur.
"""

def register_routes(ctrl):
    app = ctrl.app

    # Pages Web
    app.add_url_rule('/', 'home', lambda: ctrl.home())
    app.add_url_rule('/vision', 'vision', lambda: ctrl.vision())
    app.add_url_rule('/onglet_template', 'onglet_template', lambda: ctrl.onglet_template())
    app.add_url_rule('/pid', 'pid_page', lambda: ctrl.pid_page())
    app.add_url_rule('/onglet_control', 'onglet_control', lambda: ctrl.onglet_control())
    # Système
    app.add_url_rule('/exit', 'exit_server', lambda: ctrl.exit_server(), methods=['POST'])
    app.add_url_rule('/resource_usage', 'resource_usage', lambda: ctrl.get_resource_usage())

    # Caméra & Vision
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
    app.add_url_rule('/set_livefeed_fps', 'set_livefeed_fps', lambda: ctrl.set_livefeed_fps(), methods=['POST'])
    app.add_url_rule('/set_passive_detection_rate', 'set_passive_detection_rate', lambda: ctrl.set_passive_detection_rate(), methods=['POST'])

    # Moteur
    app.add_url_rule('/zumi/forward', 'forward', lambda: ctrl.forward())
    app.add_url_rule('/zumi/reverse', 'reverse', lambda: ctrl.reverse())
    app.add_url_rule('/zumi/left', 'left', lambda: ctrl.left())
    app.add_url_rule('/zumi/right', 'right', lambda: ctrl.right())
    app.add_url_rule('/zumi/stop', 'stop', lambda: ctrl.stop())
    app.add_url_rule('/zumi/turn', 'manual_turn', lambda: ctrl.manual_turn(), methods=['POST'])

    # Routes pour l'onglet control
    app.add_url_rule('/start_sampling', 'start_sampling', lambda: ctrl.start_sampling(), methods=['POST'])
    app.add_url_rule('/stop_sampling', 'stop_sampling', lambda: ctrl.stop_sampling(), methods=['POST'])
    app.add_url_rule('/sampling/download', 'sampling_download', lambda: ctrl.download_sampling(), methods=['GET'])
    app.add_url_rule('/controller/start', 'controller_start', lambda: ctrl.start_controller(), methods=['POST'])
    app.add_url_rule('/controller/stop', 'controller_stop', lambda: ctrl.stop_controller(), methods=['POST'])
    app.add_url_rule('/controller/status', 'controller_status_route', lambda: ctrl.controller_status())
    app.add_url_rule('/controller/list', 'controller_list', lambda: ctrl.controller_list())

    # Routes PID
    # app.add_url_rule('/pid/update_params', 'pid_update_params', lambda: ctrl.pid_update_params(), methods=['POST'])
    # app.add_url_rule('/pid/get_params', 'pid_get_params', lambda: ctrl.pid_get_params())
    # app.add_url_rule('/pid/start', 'pid_start', lambda: ctrl.pid_start(), methods=['POST'])
    # app.add_url_rule('/pid/stop', 'pid_stop', lambda: ctrl.pid_stop(), methods=['POST'])
    # app.add_url_rule('/pid/reset', 'pid_reset', lambda: ctrl.pid_reset(), methods=['POST'])
    # app.add_url_rule('/pid/status', 'pid_status', lambda: ctrl.pid_status())
    
    # # Routes pour le mode step-by-step
    # app.add_url_rule('/pid/step_mode/start', 'pid_step_start', lambda: ctrl.pid_step_start(), methods=['POST'])
    # app.add_url_rule('/pid/step_mode/stop', 'pid_step_stop', lambda: ctrl.pid_step_stop(), methods=['POST'])
    # app.add_url_rule('/pid/step_mode/approve', 'pid_step_approve', lambda: ctrl.pid_step_approve(), methods=['POST'])
    # app.add_url_rule('/pid/step_mode/status', 'pid_step_status', lambda: ctrl.pid_step_status())
    
    # # Routes pour le détecteur de ligne
    # app.add_url_rule('/line_detector/update_params', 'line_detector_update_params', 
    #                 lambda: ctrl.line_detector_update_params(), methods=['POST'])
    # app.add_url_rule('/line_detector/get_params', 'line_detector_get_params', 
    #                 lambda: ctrl.line_detector_get_params())
    
    # app.add_url_rule('/state_machine/start', 'state_machine_start', lambda: ctrl.state_machine_start(), methods=['POST'])
    # app.add_url_rule('/state_machine/stop', 'state_machine_stop', lambda: ctrl.state_machine_stop(), methods=['POST'])
    # app.add_url_rule('/state_machine/status', 'state_machine_status', lambda: ctrl.state_machine_status())

    # --- PONT (Nouveaux liens) ---
    app.add_url_rule('/bridge/open', 'bridge_open', lambda: ctrl.bridge_open(), methods=['POST'])
    app.add_url_rule('/bridge/close', 'bridge_close', lambda: ctrl.bridge_close(), methods=['POST'])
    app.add_url_rule('/bridge/green', 'bridge_green', lambda: ctrl.bridge_green(), methods=['POST'])
    app.add_url_rule('/bridge/red', 'bridge_red', lambda: ctrl.bridge_red(), methods=['POST'])
    app.add_url_rule('/bridge/mode_auto/<etat>', 'bridge_mode_auto', lambda etat: ctrl.bridge_mode_auto(etat), methods=['POST'])
    return app