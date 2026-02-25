# cascade/analysis/charts.py
# ----------------------------
# Génération des courbes PR / ROC et des graphiques per-stage.

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it

from .utils import _load_images_grayscale


def generate_pr_roc_data(model_path, test_pos_dir, test_neg_dir,
                         scaleFactor=1.1, max_img_dim=320):
    """
    Génère les données pour les courbes PR (Precision-Recall) et ROC
    en faisant varier le seuil minNeighbors.
    
    Pour un cascade classifier, minNeighbors agit comme un seuil de confiance :
    - minNeighbors=1 → très sensible (haut recall, basse précision)
    - minNeighbors élevé → très strict (bas recall, haute précision)
    
    :param model_path: Chemin du fichier cascade.xml
    :param test_pos_dir: Dossier des images positives de test
    :param test_neg_dir: Dossier des images négatives de test
    :param scaleFactor: Facteur d'échelle fixe
    :param max_img_dim: Dimension maximale (côté long) des images
    :return: dict avec recall, precision, fpr, tpr, f1, mn_values
    """
    print("\n  Génération des données PR / ROC...")
    
    cascade = cv2.CascadeClassifier(model_path)
    if cascade.empty():
        print("    ERREUR : Impossible de charger le modèle")
        return None
    
    mn_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
    
    print(f"    Chargement des images de test (max {max_img_dim}px)...")
    pos_images = _load_images_grayscale(test_pos_dir, max_img_dim)
    neg_images = _load_images_grayscale(test_neg_dir, max_img_dim)
    print(f"    {len(pos_images)} positives + {len(neg_images)} négatives chargées")
    print(f"    {len(mn_values)} seuils minNeighbors à tester (SF={scaleFactor} fixe)")
    
    data = {
        'mn': [], 'recall': [], 'precision': [], 'f1': [],
        'fpr': [], 'tpr': [], 'specificity': [],
        'tp': [], 'fn': [], 'fp': [], 'tn': []
    }
    
    results = []
    
    for mn in tqdm(mn_values, unit="mn", colour="magenta", ncols=80, desc="    PR/ROC"):
        tp, fn = 0, 0
        for img in pos_images:
            dets = cascade.detectMultiScale(img, scaleFactor=scaleFactor, minNeighbors=mn)
            if len(dets) > 0:
                tp += 1
            else:
                fn += 1
        
        fp, tn = 0, 0
        for img in neg_images:
            dets = cascade.detectMultiScale(img, scaleFactor=scaleFactor, minNeighbors=mn)
            if len(dets) > 0:
                fp += 1
            else:
                tn += 1
        
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        f1 = 2 * (precision / 100) * (recall / 100) / ((precision / 100) + (recall / 100)) \
            if (precision + recall) > 0 else 0
        specificity = tn / (tn + fp) * 100 if (tn + fp) > 0 else 0
        fpr = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0
        tpr = recall
        
        results.append({
            'mn': mn, 'recall': recall, 'precision': precision, 'f1': f1,
            'fpr': fpr, 'tpr': tpr, 'specificity': specificity,
            'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn
        })
        
        if recall == 0 and mn > 5:
            break
    
    # Tableau des résultats
    print(f"\n    {'MN':>4} │ {'Recall':>8} │ {'Précis.':>8} │ {'F1':>7} │ {'FPR':>7} │ {'Spécif.':>8}")
    print(f"    {'─'*4}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*7}─┼─{'─'*7}─┼─{'─'*8}")
    
    for r in results:
        print(f"    {r['mn']:>4} │ {r['recall']:>7.1f}% │ {r['precision']:>7.1f}% │ "
              f"{r['f1']:>7.3f} │ {r['fpr']:>6.1f}% │ {r['specificity']:>7.1f}%")
    
    print(f"    {'─'*4}─┴─{'─'*8}─┴─{'─'*8}─┴─{'─'*7}─┴─{'─'*7}─┴─{'─'*8}")
    
    for r in results:
        for key in data:
            data[key].append(r[key])
    
    data['scaleFactor'] = scaleFactor
    return data


def generate_analysis_charts(stage_metrics, pr_roc_data, output_dir):
    """
    Génère tous les graphiques d'analyse et les sauvegarde sur disque.
    
    Fichiers produits :
    - stage_metrics_all.png      : Recall, Precision, F1×100, Specificity par stage
    - stage_metrics_f1.png       : Zoom F1-Score par stage
    - pr_curve.png               : Courbe Precision-Recall
    - roc_curve.png              : Courbe ROC (TPR vs FPR)
    
    :param stage_metrics: dict retourné par evaluate_per_stage() (peut être None)
    :param pr_roc_data: dict retourné par generate_pr_roc_data() (peut être None)
    :param output_dir: Dossier de sortie (data/analysis/)
    """
    os.makedirs(output_dir, exist_ok=True)
    generated = []
    
    # ══════════════════════════════════════════════════════════
    #  Graphiques per-stage
    # ══════════════════════════════════════════════════════════
    if stage_metrics and len(stage_metrics['stage']) > 1:
        stages = stage_metrics['stage']
        
        # Graphique 1 : Toutes les métriques par stage
        fig, ax = plt.subplots(figsize=(12, 7))
        
        ax.plot(stages, stage_metrics['recall'], 'b-o',
                label='Recall (%)', linewidth=2, markersize=6)
        ax.plot(stages, stage_metrics['precision'], 'g-s',
                label='Précision (%)', linewidth=2, markersize=6)
        ax.plot(stages, [f * 100 for f in stage_metrics['f1']], 'r-^',
                label='F1-Score (×100)', linewidth=2, markersize=6)
        ax.plot(stages, stage_metrics['specificity'], 'm-D',
                label='Spécificité (%)', linewidth=2, markersize=6)
        
        ax.set_xlabel('Nombre de stages', fontsize=12)
        ax.set_ylabel('Métrique (%)', fontsize=12)
        ax.set_title('Évolution des métriques par nombre de stages', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10, loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_xticks(stages)
        ax.set_ylim(0, 105)
        
        for key, color in [('recall', 'blue'), ('precision', 'green'), ('specificity', 'purple')]:
            vals = stage_metrics[key]
            if vals:
                ax.annotate(f'{vals[-1]:.1f}%', xy=(stages[-1], vals[-1]),
                           fontsize=8, color=color, fontweight='bold',
                           xytext=(5, 0), textcoords='offset points')
        f1_100 = [f * 100 for f in stage_metrics['f1']]
        if f1_100:
            ax.annotate(f'{f1_100[-1]:.1f}', xy=(stages[-1], f1_100[-1]),
                       fontsize=8, color='red', fontweight='bold',
                       xytext=(5, 0), textcoords='offset points')
        
        plt.tight_layout()
        path = os.path.join(output_dir, 'stage_metrics_all.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(path)
        
        # Graphique 2 : Zoom F1-Score par stage
        fig, ax = plt.subplots(figsize=(10, 6))
        
        f1_vals = stage_metrics['f1']
        ax.plot(stages, f1_vals, 'r-o', linewidth=2.5, markersize=8, label='F1-Score')
        ax.fill_between(stages, f1_vals, alpha=0.15, color='red')
        
        for s, f in zip(stages, f1_vals):
            ax.annotate(f'{f:.3f}', xy=(s, f), fontsize=9, fontweight='bold',
                       ha='center', va='bottom', xytext=(0, 8), textcoords='offset points')
        
        best_f1 = max(f1_vals)
        best_stage = stages[f1_vals.index(best_f1)]
        ax.axhline(y=best_f1, color='green', linestyle='--', alpha=0.5, linewidth=1)
        ax.annotate(f'Meilleur F1 = {best_f1:.3f} (stage {best_stage})',
                   xy=(stages[0], best_f1), fontsize=9, color='green',
                   xytext=(10, 5), textcoords='offset points')
        
        ax.set_xlabel('Nombre de stages', fontsize=12)
        ax.set_ylabel('F1-Score', fontsize=12)
        ax.set_title('Évolution du F1-Score par nombre de stages', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xticks(stages)
        ax.set_ylim(0, max(1.0, best_f1 + 0.05))
        
        plt.tight_layout()
        path = os.path.join(output_dir, 'stage_metrics_f1.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(path)
    
    # ══════════════════════════════════════════════════════════
    #  Courbes PR et ROC
    # ══════════════════════════════════════════════════════════
    if pr_roc_data and len(pr_roc_data['recall']) > 1:
        recalls = pr_roc_data['recall']
        precisions = pr_roc_data['precision']
        fprs = pr_roc_data['fpr']
        tprs = pr_roc_data['tpr']
        mns = pr_roc_data['mn']
        f1s = pr_roc_data['f1']
        
        # Courbe PR (Precision-Recall)
        fig, ax = plt.subplots(figsize=(10, 7))
        
        ax.plot(recalls, precisions, 'b-o', linewidth=2, markersize=7)
        
        best_f1_idx = f1s.index(max(f1s))
        for i, (rec, prec, mn) in enumerate(zip(recalls, precisions, mns)):
            color = 'red' if i == best_f1_idx else '#555555'
            weight = 'bold' if i == best_f1_idx else 'normal'
            ax.annotate(f'MN={mn}', xy=(rec, prec), fontsize=8,
                       fontweight=weight, color=color,
                       ha='left', va='bottom', xytext=(4, 4),
                       textcoords='offset points')
        
        ax.scatter([recalls[best_f1_idx]], [precisions[best_f1_idx]],
                  color='red', s=120, zorder=5, marker='*',
                  label=f'Meilleur F1={max(f1s):.3f} (MN={mns[best_f1_idx]})')
        
        pr_sf = pr_roc_data.get('scaleFactor', '?')
        ax.set_xlabel('Recall (%)', fontsize=12)
        ax.set_ylabel('Précision (%)', fontsize=12)
        ax.set_title(f'Courbe Precision-Recall (SF={pr_sf} fixe)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 105)
        ax.set_ylim(0, 105)
        
        plt.tight_layout()
        path = os.path.join(output_dir, 'pr_curve.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(path)
        
        # Courbe ROC (TPR vs FPR)
        fig, ax = plt.subplots(figsize=(10, 7))
        
        ax.plot(fprs, tprs, 'g-o', linewidth=2, markersize=7, label='ROC')
        ax.plot([0, 100], [0, 100], 'k--', alpha=0.3, label='Aléatoire')
        
        for i, (fpr, tpr, mn) in enumerate(zip(fprs, tprs, mns)):
            color = 'red' if i == best_f1_idx else '#555555'
            weight = 'bold' if i == best_f1_idx else 'normal'
            ax.annotate(f'MN={mn}', xy=(fpr, tpr), fontsize=8,
                       fontweight=weight, color=color,
                       ha='left', va='bottom', xytext=(4, 4),
                       textcoords='offset points')
        
        ax.scatter([fprs[best_f1_idx]], [tprs[best_f1_idx]],
                  color='red', s=120, zorder=5, marker='*',
                  label=f'Meilleur F1={max(f1s):.3f}')
        
        roc_sf = pr_roc_data.get('scaleFactor', '?')
        ax.set_xlabel('Taux de Faux Positifs — FPR (%)', fontsize=12)
        ax.set_ylabel('Taux de Vrais Positifs — TPR (%)', fontsize=12)
        ax.set_title(f'Courbe ROC (SF={roc_sf} fixe)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-2, 105)
        ax.set_ylim(0, 105)
        
        plt.tight_layout()
        path = os.path.join(output_dir, 'roc_curve.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(path)
    
    for p in generated:
        print(f"    Graphique sauvegardé : {p}")

    return generated
