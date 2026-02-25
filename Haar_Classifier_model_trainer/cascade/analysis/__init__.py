# cascade/analysis/__init__.py
# -----------------------------
# Analyse avancée du modèle — orchestrateur et exports publics.

import os
import numpy as np

from ..config import DETECTION_PRESETS
from .sweep import generate_full_parameter_sweep
from .stages import visualize_fn_tp_montage, evaluate_per_stage
from .charts import generate_pr_roc_data, generate_analysis_charts
from .data_quality import analyze_input_data_quality, analyze_optimal_window_size

__all__ = [
    'advanced_model_analysis',
    'generate_full_parameter_sweep',
    'visualize_fn_tp_montage',
    'evaluate_per_stage',
    'generate_pr_roc_data',
    'generate_analysis_charts',
    'analyze_input_data_quality',
    'analyze_optimal_window_size',
]


def advanced_model_analysis(model_path, cascade_dir, data_dir,
                            test_pos_dir, test_neg_dir):
    """
    Analyse avancée complète du modèle entraîné.
    
    Pipeline cohérent en 7 phases — le sweep tourne en premier et ses
    résultats (meilleur SF, MN) sont propagés à TOUTES les phases suivantes.
    
    Phases :
    1. Sweep complet SF × MN → détermine les meilleurs paramètres
    2. Mosaïque FN / TP (avec les meilleurs params)
    3. Évaluation per-stage (avec les meilleurs params)
    4. Courbes PR et ROC (avec le meilleur SF du sweep)
    5. Analyse qualité des données d'entrée (avec les meilleurs params)
    6. Graphiques per-stage + PR/ROC
    7. Analyse de la taille optimale de la fenêtre de détection
    
    Tous les résultats sont sauvegardés dans data/analysis/
    
    :param model_path: Chemin du fichier cascade.xml
    :param cascade_dir: Dossier cascade/ contenant les stageN.xml
    :param data_dir: Dossier data/ racine
    :param test_pos_dir: Dossier des images positives de test
    :param test_neg_dir: Dossier des images négatives de test
    """
    print("\n")
    print("=" * 60)
    print("  ANALYSE AVANCÉE DU MODÈLE")
    print("=" * 60)
    
    analysis_dir = os.path.join(data_dir, 'analysis')
    os.makedirs(analysis_dir, exist_ok=True)
    
    # Vérifications préalables
    if model_path is None or not os.path.exists(model_path):
        print(f"\n  ERREUR : Modèle non trouvé à {model_path}")
        print(f"  → Générez cascade.xml d'abord (option [4])")
        return
    
    if not os.path.isdir(test_pos_dir) or not os.path.isdir(test_neg_dir):
        print(f"\n  ERREUR : Dossiers de test manquants.")
        print(f"  → Préparez les données d'abord (option [2])")
        return
    
    # ──────────────────────────────────────────────────────────
    #  Phase 1 : Sweep complet SF × MN
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 1/7 — Sweep complet scaleFactor × minNeighbors")
    print(f"{'─' * 60}")
    
    sweep_data = generate_full_parameter_sweep(
        model_path, test_pos_dir, test_neg_dir, analysis_dir
    )
    
    if sweep_data and sweep_data.get('best'):
        best = sweep_data['best']
        sf = best['sf']
        mn = best['mn']
        print(f"\n  ► Meilleurs paramètres identifiés : SF={sf}, MN={mn}")
        print(f"    F1={best['f1']:.3f}, Recall={best['recall']:.1f}%, Précision={best['precision']:.1f}%")
        print(f"    → Ces paramètres seront utilisés pour TOUTES les phases suivantes.")
    else:
        sf = DETECTION_PRESETS['equilibre']['sf']
        mn = DETECTION_PRESETS['equilibre']['mn']
        print(f"\n  ⚠ Sweep échoué — fallback sur preset Équilibré : SF={sf}, MN={mn}")
    
    # ──────────────────────────────────────────────────────────
    #  Phase 2 : Mosaïque FN / TP
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 2/7 — Mosaïque Faux Négatifs vs Vrais Positifs (SF={sf}, MN={mn})")
    print(f"{'─' * 60}")
    
    fn_files, tp_files = visualize_fn_tp_montage(
        model_path, test_pos_dir, analysis_dir,
        scaleFactor=sf, minNeighbors=mn
    )
    
    # ──────────────────────────────────────────────────────────
    #  Phase 3 : Évaluation per-stage
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 3/7 — Métriques par stage (SF={sf}, MN={mn})")
    print(f"{'─' * 60}")
    
    stage_metrics = evaluate_per_stage(
        model_path, test_pos_dir, test_neg_dir,
        scaleFactor=sf, minNeighbors=mn
    )
    
    # ──────────────────────────────────────────────────────────
    #  Phase 4 : Courbes PR et ROC
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 4/7 — Courbes PR et ROC (SF={sf} fixe, sweep MN)")
    print(f"{'─' * 60}")
    
    pr_roc_data = generate_pr_roc_data(
        model_path, test_pos_dir, test_neg_dir,
        scaleFactor=sf
    )
    
    # ──────────────────────────────────────────────────────────
    #  Phase 5 : Analyse qualité des données d'entrée
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 5/7 — Analyse qualité des données d'entrée (SF={sf}, MN={mn})")
    print(f"{'─' * 60}")
    
    analyze_input_data_quality(
        model_path, data_dir, test_pos_dir, test_neg_dir,
        analysis_dir, sf=sf, mn=mn
    )
    
    # ──────────────────────────────────────────────────────────
    #  Phase 6 : Graphiques per-stage + PR/ROC
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 6/7 — Génération des graphiques per-stage et PR/ROC")
    print(f"{'─' * 60}")
    
    generate_analysis_charts(stage_metrics, pr_roc_data, analysis_dir)
    
    # ──────────────────────────────────────────────────────────
    #  Phase 7 : Analyse de la taille optimale de la fenêtre
    # ──────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  Phase 7/7 — Analyse de la taille de fenêtre (sample_width × sample_height)")
    print(f"{'─' * 60}")
    
    window_recommendation = analyze_optimal_window_size(
        model_path, data_dir, analysis_dir
    )
    
    # ──────────────────────────────────────────────────────────
    #  Résumé unifié
    # ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  RÉSUMÉ DE L'ANALYSE")
    print(f"{'=' * 60}")
    
    nb_test_pos = len([f for f in os.listdir(test_pos_dir)
                       if os.path.isfile(os.path.join(test_pos_dir, f))])
    nb_test_neg = len([f for f in os.listdir(test_neg_dir)
                       if os.path.isfile(os.path.join(test_neg_dir, f))])
    
    print(f"\n  Paramètres de référence (issus du sweep) : SF={sf}, MN={mn}")
    print(f"  Dataset de test : {nb_test_pos} positives, {nb_test_neg} négatives")
    if (len(fn_files) + len(tp_files)) > 0:
        print(f"  Mosaïque : {len(fn_files)} FN + {len(tp_files)} TP "
              f"(Recall = {len(tp_files)/(len(fn_files)+len(tp_files))*100:.1f}%)")
    
    if sweep_data and sweep_data.get('best'):
        b = sweep_data['best']
        print(f"\n  Meilleur combo (sweep SF×MN) :")
        print(f"    SF={b['sf']}, MN={b['mn']} → F1={b['f1']:.3f} "
              f"(Recall={b['recall']:.1f}%, Précision={b['precision']:.1f}%)")
    
    if stage_metrics and stage_metrics['stage']:
        best_f1_idx = stage_metrics['f1'].index(max(stage_metrics['f1']))
        best_stage = stage_metrics['stage'][best_f1_idx]
        best_f1 = stage_metrics['f1'][best_f1_idx]
        final_f1 = stage_metrics['f1'][-1]
        final_recall = stage_metrics['recall'][-1]
        final_precision = stage_metrics['precision'][-1]
        total_stages = stage_metrics['stage'][-1]
        
        print(f"\n  Analyse per-stage ({total_stages} stages, SF={sf}, MN={mn}) :")
        print(f"    Meilleur F1 : {best_f1:.3f} au stage {best_stage}")
        print(f"    F1 final (stage {total_stages}) : {final_f1:.3f} "
              f"(Recall={final_recall:.1f}%, Précision={final_precision:.1f}%)")
        
        recalls = stage_metrics['recall']
        if len(recalls) >= 4:
            mid = len(recalls) // 2
            early_recall = np.mean(recalls[mid:mid+2])
            late_recall = np.mean(recalls[-2:])
            if abs(late_recall - early_recall) < 3:
                print(f"    ⚠ Recall stagne (~{late_recall:.1f}%) dès le stage ~{stage_metrics['stage'][mid]}")
                print(f"      → Le problème est dans les données, pas les paramètres")
        
        if len(stage_metrics['f1']) >= 3 and best_stage < total_stages and best_f1 - final_f1 > 0.02:
            print(f"    ⚠ F1 diminue après le stage {best_stage} → possible surapprentissage")
            print(f"      → Considérer un modèle avec {best_stage} stages (option [7])")
    
    if pr_roc_data and pr_roc_data['mn']:
        best_f1_idx = pr_roc_data['f1'].index(max(pr_roc_data['f1']))
        best_mn_pr = pr_roc_data['mn'][best_f1_idx]
        best_f1_pr = pr_roc_data['f1'][best_f1_idx]
        print(f"\n  Courbe PR/ROC (SF={sf} fixe, sweep MN) :")
        print(f"    Meilleur F1 par MN : {best_f1_pr:.3f} à MN={best_mn_pr}")
        if best_mn_pr != mn:
            print(f"    ℹ Note : le MN optimal PR ({best_mn_pr}) diffère du sweep global ({mn})")
            print(f"      → Normal : le sweep global explore aussi d'autres SF adjacents")
    
    if window_recommendation:
        print(f"\n  Taille de fenêtre (Phase 7) :")
        print(f"    Recommandation : {window_recommendation['w']}×{window_recommendation['h']} px")
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(model_path)
            root = tree.getroot()
            cur_w_el = root.find('.//width')
            cur_h_el = root.find('.//height')
            if cur_w_el is not None and cur_h_el is not None:
                cur_w = int(cur_w_el.text)
                cur_h = int(cur_h_el.text)
                if cur_w != window_recommendation['w'] or cur_h != window_recommendation['h']:
                    print(f"    Actuel          : {cur_w}×{cur_h} px")
                    print(f"    → Un changement nécessite un ré-entraînement complet")
                else:
                    print(f"    ✓ La fenêtre actuelle ({cur_w}×{cur_h}) est déjà optimale")
        except Exception:
            pass
    
    print(f"\n  Fichiers générés dans : {analysis_dir}")
    generated = [f for f in os.listdir(analysis_dir)
                 if os.path.isfile(os.path.join(analysis_dir, f))]
    for f in sorted(generated):
        size = os.path.getsize(os.path.join(analysis_dir, f)) / 1024
        print(f"    • {f} ({size:.1f} KB)")
    
    print(f"\n{'=' * 60}\n")
