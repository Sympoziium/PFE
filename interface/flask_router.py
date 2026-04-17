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
    app.add_url_rule('/set_fsm_overlay', 'set_fsm_overlay', lambda: ctrl.set_fsm_overlay(), methods=['POST'])

    # Moteur
    app.add_url_rule('/zumi/forward', 'forward', lambda: ctrl.forward())
    app.add_url_rule('/zumi/reverse', 'reverse', lambda: ctrl.reverse())
    app.add_url_rule('/zumi/left', 'left', lambda: ctrl.left())
    app.add_url_rule('/zumi/right', 'right', lambda: ctrl.right())
    app.add_url_rule('/zumi/stop', 'stop', lambda: ctrl.stop())
    app.add_url_rule('/zumi/turn', 'manual_turn', lambda: ctrl.manual_turn(), methods=['POST'])
    app.add_url_rule('/zumi/move', 'move', lambda: ctrl.move(), methods=['POST'])

    # Routes pour l'onglet control
    app.add_url_rule('/start_sampling', 'start_sampling', lambda: ctrl.start_sampling(), methods=['POST'])
    app.add_url_rule('/stop_sampling', 'stop_sampling', lambda: ctrl.stop_sampling(), methods=['POST'])
    app.add_url_rule('/sampling/download', 'sampling_download', lambda: ctrl.download_sampling(), methods=['GET'])
    app.add_url_rule('/sampling/feature_kill', 'sampling_feature_kill', lambda: ctrl.sampling_feature_kill(), methods=['GET', 'POST'])
    app.add_url_rule('/manual/settings', 'manual_settings', lambda: ctrl.manual_settings(), methods=['GET', 'POST'])
    app.add_url_rule('/controller/start', 'controller_start', lambda: ctrl.start_controller(), methods=['POST'])
    app.add_url_rule('/controller/stop', 'controller_stop', lambda: ctrl.stop_controller(), methods=['POST'])
    app.add_url_rule('/controller/status', 'controller_status_route', lambda: ctrl.controller_status())
    app.add_url_rule('/controller/list', 'controller_list', lambda: ctrl.controller_list())
    app.add_url_rule('/controller/params', 'controller_params', lambda: ctrl.controller_params(), methods=['GET', 'POST'])
    app.add_url_rule('/controller/step', 'controller_step', lambda: ctrl.controller_step(), methods=['POST'])
    app.add_url_rule('/controller/debug/toggle', 'controller_debug_toggle', lambda: ctrl.toggle_ml_debug(), methods=['POST'])

    # Routes PID
    app.add_url_rule('/pid/update_params', 'pid_update_params', lambda: ctrl.pid_update_params(), methods=['POST'])
    app.add_url_rule('/pid/get_params', 'pid_get_params', lambda: ctrl.pid_get_params())
    app.add_url_rule('/pid/start', 'pid_start', lambda: ctrl.pid_start(), methods=['POST'])
    app.add_url_rule('/pid/stop', 'pid_stop', lambda: ctrl.pid_stop(), methods=['POST'])
    app.add_url_rule('/pid/reset', 'pid_reset', lambda: ctrl.pid_reset(), methods=['POST'])
    app.add_url_rule('/pid/status', 'pid_status', lambda: ctrl.pid_status())
    
    # Routes pour le mode step-by-step
    app.add_url_rule('/pid/step_mode/start', 'pid_step_start', lambda: ctrl.pid_step_start(), methods=['POST'])
    app.add_url_rule('/pid/step_mode/stop', 'pid_step_stop', lambda: ctrl.pid_step_stop(), methods=['POST'])
    app.add_url_rule('/pid/step_mode/approve', 'pid_step_approve', lambda: ctrl.pid_step_approve(), methods=['POST'])
    app.add_url_rule('/pid/step_mode/status', 'pid_step_status', lambda: ctrl.pid_step_status())
    
    # Routes pour le détecteur de ligne
    app.add_url_rule('/line_detector/update_params', 'line_detector_update_params', 
                    lambda: ctrl.line_detector_update_params(), methods=['POST'])
    app.add_url_rule('/line_detector/get_params', 'line_detector_get_params', 
                    lambda: ctrl.line_detector_get_params())

    # Reset capteurs / PID
    app.add_url_rule('/robot/calibrate', 'robot_calibrate', lambda: ctrl.robot_calibrate(), methods=['POST'])
    app.add_url_rule('/robot/reset_drive', 'robot_reset_drive', lambda: ctrl.robot_reset_drive(), methods=['POST'])
    app.add_url_rule('/robot/reset_gyro', 'robot_reset_gyro', lambda: ctrl.robot_reset_gyro(), methods=['POST'])
    app.add_url_rule('/robot/reset_pid', 'robot_reset_pid', lambda: ctrl.robot_reset_pid(), methods=['POST'])
    app.add_url_rule('/controller/calibrate_ir', 'calibrate_ir', lambda: ctrl.calibrate_ir(), methods=['POST'])

    # Sensor Profiler
    app.add_url_rule('/robot/sensor_profile/start', 'sp_start', lambda: ctrl.sensor_profile_start(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/status', 'sp_status', lambda: ctrl.sensor_profile_status(), methods=['GET'])
    app.add_url_rule('/robot/sensor_profile/record', 'sp_record', lambda: ctrl.sensor_profile_record(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/run', 'sp_run', lambda: ctrl.sensor_profile_run(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/run_status', 'sp_run_status', lambda: ctrl.sensor_profile_run_status(), methods=['GET'])
    app.add_url_rule('/robot/sensor_profile/next', 'sp_next', lambda: ctrl.sensor_profile_next(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/stop', 'sp_stop', lambda: ctrl.sensor_profile_stop(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/results', 'sp_results', lambda: ctrl.sensor_profile_results(), methods=['GET'])
    app.add_url_rule('/robot/sensor_profile/manual_start', 'sp_manual_start', lambda: ctrl.sensor_profile_manual_start(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/manual_stop', 'sp_manual_stop', lambda: ctrl.sensor_profile_manual_stop(), methods=['POST'])
    app.add_url_rule('/robot/sensor_profile/summary', 'sp_summary', lambda: ctrl.sensor_profile_summary(), methods=['GET'])
    app.add_url_rule('/robot/sensor_profile/download', 'sp_download', lambda: ctrl.sensor_profile_download(), methods=['GET'])

    # --- PONT (Nouveaux liens) ---
    app.add_url_rule('/bridge/open', 'bridge_open', lambda: ctrl.bridge_open(), methods=['POST'])
    app.add_url_rule('/bridge/close', 'bridge_close', lambda: ctrl.bridge_close(), methods=['POST'])
    app.add_url_rule('/bridge/green', 'bridge_green', lambda: ctrl.bridge_green(), methods=['POST'])
    app.add_url_rule('/bridge/red', 'bridge_red', lambda: ctrl.bridge_red(), methods=['POST'])
    app.add_url_rule('/bridge/mode_auto/<etat>', 'bridge_mode_auto', lambda etat: ctrl.bridge_mode_auto(etat), methods=['POST'])
    return app