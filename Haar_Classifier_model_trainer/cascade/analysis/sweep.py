# cascade/analysis/sweep.py
# ---------------------------
# Sweep complet scaleFactor × minNeighbors – heatmaps F1 / Recall / Précision.

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


def generate_full_parameter_sweep(model_path, test_pos_dir, test_neg_dir,
                                   output_dir, max_img_dim=320):
    """
    Sweep complet scaleFactor × minNeighbors pour trouver la combinaison optimale.
    
    Teste une grille de SF × MN et produit :
    - Un tableau des résultats (top 5)
    - Un heatmap F1 sauvegardé sur disque
    - La recommandation du meilleur combo
    
    :param model_path: Chemin du cascade.xml
    :param test_pos_dir: Dossier des images positives de test
    :param test_neg_dir: Dossier des images négatives de test
    :param output_dir: Dossier de sortie (data/analysis/)
    :param max_img_dim: Dimension max des images chargées
    :return: dict avec les résultats du sweep
    """
    print("\n  Sweep complet scaleFactor × minNeighbors...")
    
    cascade = cv2.CascadeClassifier(model_path)
    if cascade.empty():
        print("    ERREUR : Impossible de charger le modèle")
        return None
    
    sf_values = [1.03, 1.05, 1.08, 1.10, 1.15, 1.20, 1.30]
    mn_values = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12]
    
    print(f"    Chargement des images de test (max {max_img_dim}px)...")
    pos_images = _load_images_grayscale(test_pos_dir, max_img_dim)
    neg_images = _load_images_grayscale(test_neg_dir, max_img_dim)
    print(f"    {len(pos_images)} positives + {len(neg_images)} négatives chargées")
    print(f"    Grille : {len(sf_values)} SF × {len(mn_values)} MN = {len(sf_values) * len(mn_values)} combinaisons")
    
    results = []
    f1_matrix = np.zeros((len(mn_values), len(sf_values)))
    recall_matrix = np.zeros_like(f1_matrix)
    precision_matrix = np.zeros_like(f1_matrix)
    
    total = len(sf_values) * len(mn_values)
    pbar = tqdm(total=total, unit="combo", colour="magenta", ncols=80, desc="    Sweep")
    
    for j, sf in enumerate(sf_values):
        for i, mn in enumerate(mn_values):
            tp, fn = 0, 0
            for img in pos_images:
                dets = cascade.detectMultiScale(img, scaleFactor=sf, minNeighbors=mn)
                if len(dets) > 0:
                    tp += 1
                else:
                    fn += 1
            
            fp, tn = 0, 0
            for img in neg_images:
                dets = cascade.detectMultiScale(img, scaleFactor=sf, minNeighbors=mn)
                if len(dets) > 0:
                    fp += 1
                else:
                    tn += 1
            
            recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
            precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
            f1 = 2 * (precision / 100) * (recall / 100) / ((precision / 100) + (recall / 100)) \
                if (precision + recall) > 0 else 0
            specificity = tn / (tn + fp) * 100 if (tn + fp) > 0 else 0
            
            f1_matrix[i, j] = f1
            recall_matrix[i, j] = recall
            precision_matrix[i, j] = precision
            
            results.append({
                'sf': sf, 'mn': mn,
                'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
                'recall': recall, 'precision': precision,
                'f1': f1, 'specificity': specificity
            })
            pbar.update(1)
    
    pbar.close()
    
    best = max(results, key=lambda x: x['f1'])
    
    # Top 5 par F1
    sorted_results = sorted(results, key=lambda x: x['f1'], reverse=True)
    print(f"\n    Top 5 combinaisons par F1-Score :")
    print(f"    ┌──────┬──────┬──────────┬──────────┬─────────┬──────────┐")
    print(f"    │ {'SF':^4} │ {'MN':^4} │ {'Recall':^8} │ {'Précis.':^8} │ {'F1':^7} │ {'Spécif.':^8} │")
    print(f"    ├──────┼──────┼──────────┼──────────┼─────────┼──────────┤")
    for r in sorted_results[:5]:
        marker = '►' if r == best else ' '
        print(f"    │{marker}{r['sf']:>4} │ {r['mn']:>4} │ {r['recall']:>6.1f}%  │ {r['precision']:>6.1f}%  │ {r['f1']:>7.3f} │ {r['specificity']:>6.1f}%  │")
    print(f"    └──────┴──────┴──────────┴──────────┴─────────┴──────────┘")
    print(f"    ► = Meilleur F1 : SF={best['sf']}, MN={best['mn']}, F1={best['f1']:.3f}")
    
    # Heatmaps
    os.makedirs(output_dir, exist_ok=True)
    
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    
    for ax, matrix, title, cmap in [
        (axes[0], f1_matrix, 'F1-Score', 'RdYlGn'),
        (axes[1], recall_matrix, 'Recall (%)', 'Blues'),
        (axes[2], precision_matrix, 'Précision (%)', 'Oranges')
    ]:
        im = ax.imshow(matrix, aspect='auto', cmap=cmap, interpolation='nearest')
        ax.set_xticks(range(len(sf_values)))
        ax.set_xticklabels([str(s) for s in sf_values], fontsize=9)
        ax.set_yticks(range(len(mn_values)))
        ax.set_yticklabels([str(m) for m in mn_values], fontsize=9)
        ax.set_xlabel('scaleFactor', fontsize=11)
        ax.set_ylabel('minNeighbors', fontsize=11)
        ax.set_title(title, fontsize=13, fontweight='bold')
        
        for ii in range(len(mn_values)):
            for jj in range(len(sf_values)):
                val = matrix[ii, jj]
                color = 'white' if val > matrix.max() * 0.6 else 'black'
                fmt = f'{val:.3f}' if title == 'F1-Score' else f'{val:.0f}'
                ax.text(jj, ii, fmt, ha='center', va='center', fontsize=7, color=color)
        
        plt.colorbar(im, ax=ax, shrink=0.8)
    
    best_j = sf_values.index(best['sf'])
    best_i = mn_values.index(best['mn'])
    axes[0].add_patch(plt.Rectangle((best_j - 0.5, best_i - 0.5), 1, 1,
                                     fill=False, edgecolor='red', linewidth=3))
    
    fig.suptitle(f'Sweep SF × MN — Meilleur F1={best["f1"]:.3f} (SF={best["sf"]}, MN={best["mn"]})',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(output_dir, 'parameter_sweep_heatmap.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"    Heatmap sauvegardé : {path}")
    
    return {
        'results': results,
        'best': best,
        'sf_values': sf_values,
        'mn_values': mn_values,
        'f1_matrix': f1_matrix
    }
