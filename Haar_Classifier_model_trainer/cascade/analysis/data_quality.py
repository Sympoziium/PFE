# cascade/analysis/data_quality.py
# ----------------------------------
# Analyse de la qualité des données d'entrée et de la taille optimale
# de la fenêtre de détection.

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it


def analyze_input_data_quality(model_path, data_dir, test_pos_dir, test_neg_dir,
                                output_dir, sf=1.10, mn=5, max_img_dim=320):
    """
    Analyse la qualité et la composition des données d'entrée.
    
    Produit :
    1. Recensement des tailles des images positives + détection par taille
    2. Analyse de la complexité du fond (simple vs complexe)
    3. Évaluation de la diversité des augmentations
    4. Groupement des négatives par similarité + taux de FP par groupe
    
    :param model_path: Chemin du cascade.xml
    :param data_dir: Dossier data/ racine
    :param test_pos_dir: Dossier des images positives de test
    :param test_neg_dir: Dossier des images négatives de test
    :param output_dir: Dossier de sortie (data/analysis/)
    :param sf: scaleFactor pour la détection
    :param mn: minNeighbors pour la détection
    :param max_img_dim: Dimension max pour le chargement
    """
    print("\n  Analyse de la qualité des données d'entrée...")
    os.makedirs(output_dir, exist_ok=True)
    
    cascade = cv2.CascadeClassifier(model_path)
    if cascade.empty():
        print("    ERREUR : Impossible de charger le modèle")
        return
    
    # Extraire les dimensions de la fenêtre de détection depuis le cascade.xml
    sample_w, sample_h = 24, 42  # valeurs par défaut
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(model_path)
        root = tree.getroot()
        h_el = root.find('.//height')
        w_el = root.find('.//width')
        if h_el is not None and w_el is not None:
            sample_h = int(h_el.text)
            sample_w = int(w_el.text)
            print(f"    Fenêtre de détection (du modèle) : {sample_w}×{sample_h} px")
    except Exception:
        print(f"    ⚠ Lecture fenêtre impossible — défaut {sample_w}×{sample_h} px")
    
    # ══════════════════════════════════════════════════════════
    #  5a. Recensement des tailles d'images positives
    # ══════════════════════════════════════════════════════════
    print("\n    5a. Recensement des tailles (positives de test)...")
    
    pos_files = sorted([f for f in os.listdir(test_pos_dir) if os.path.isfile(os.path.join(test_pos_dir, f))])
    
    size_data = []
    for f in tqdm(pos_files, desc="    Tailles", unit="img", colour="cyan", ncols=80):
        img_path = os.path.join(test_pos_dir, f)
        img = cv2.imread(img_path)
        if img is None:
            continue
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        dets = cascade.detectMultiScale(gray, scaleFactor=sf, minNeighbors=mn)
        detected = len(dets) > 0
        size_data.append({'file': f, 'w': w, 'h': h, 'area': w * h, 'detected': detected})
    
    if size_data:
        fn_data = [d for d in size_data if not d['detected']]
        tp_data = [d for d in size_data if d['detected']]
        all_h = [d['h'] for d in size_data]
        all_w = [d['w'] for d in size_data]
        all_ratios = [d['w'] / d['h'] for d in size_data if d['h'] > 0]
        
        def _print_dim_table(bins, dim_key, dim_label, win_size):
            """Affiche un tableau de catégories dimensionnelles."""
            print(f"\n    Répartition par {dim_label} (fenêtre {dim_label} = {win_size} px) :")
            print(f"    ┌──────────────────────────┬───────┬──────┬──────┬──────────┬────────────────────────────────┐")
            print(f"    │ {'Catégorie':^24} │ {'Total':^5} │ {'TP':^4} │ {'FN':^4} │ {'Recall':^8} │ {'Note':^30} │")
            print(f"    ├──────────────────────────┼───────┼──────┼──────┼──────────┼────────────────────────────────┤")
            for lo, hi, label, note in bins:
                group = [d for d in size_data if lo <= d[dim_key] < hi]
                if not group:
                    continue
                n = len(group)
                n_tp = sum(1 for d in group if d['detected'])
                n_fn = n - n_tp
                recall = n_tp / n * 100 if n > 0 else 0
                print(f"    │ {label:<24} │ {n:>5} │ {n_tp:>4} │ {n_fn:>4} │ {recall:>6.1f}%  │ {note:<30} │")
            print(f"    └──────────────────────────┴───────┴──────┴──────┴──────────┴────────────────────────────────┘")
        
        # Tableau par HAUTEUR
        height_bins = [
            (0,              sample_h,     f'Micro (<{sample_h}px)',                'Sous fenêtre — indétectable'),
            (sample_h,       sample_h*2,   f'Très petit ({sample_h}-{sample_h*2})', '1-2× — fragile'),
            (sample_h*2,     sample_h*4,   f'Petit ({sample_h*2}-{sample_h*4})',    '2-4× — partielle'),
            (sample_h*4,     sample_h*10,  f'Moyen ({sample_h*4}-{sample_h*10})',   '4-10× — bonne'),
            (sample_h*10,    float('inf'), f'Grand (>{sample_h*10})',               '10×+ — robuste'),
        ]
        _print_dim_table(height_bins, 'h', 'hauteur', sample_h)
        
        # Tableau par LARGEUR
        width_bins = [
            (0,              sample_w,     f'Micro (<{sample_w}px)',                'Sous fenêtre — indétectable'),
            (sample_w,       sample_w*2,   f'Très petit ({sample_w}-{sample_w*2})', '1-2× — fragile'),
            (sample_w*2,     sample_w*4,   f'Petit ({sample_w*2}-{sample_w*4})',    '2-4× — partielle'),
            (sample_w*4,     sample_w*10,  f'Moyen ({sample_w*4}-{sample_w*10})',   '4-10× — bonne'),
            (sample_w*10,    float('inf'), f'Grand (>{sample_w*10})',               '10×+ — robuste'),
        ]
        _print_dim_table(width_bins, 'w', 'largeur', sample_w)
        
        # Stats complémentaires
        print(f"\n    Dimensions globales ({len(size_data)} images) :")
        print(f"      Hauteur  : min={min(all_h)} px, max={max(all_h)} px, médiane={int(np.median(all_h))} px")
        print(f"      Largeur  : min={min(all_w)} px, max={max(all_w)} px, médiane={int(np.median(all_w))} px")
        if all_ratios:
            print(f"      Ratio W/H: min={min(all_ratios):.2f}, max={max(all_ratios):.2f}, médiane={np.median(all_ratios):.2f}")
        if fn_data:
            fn_h = [d['h'] for d in fn_data]
            fn_w = [d['w'] for d in fn_data]
            print(f"    FN seulement ({len(fn_data)} images) :")
            print(f"      Hauteur  : min={min(fn_h)} px, max={max(fn_h)} px, médiane={int(np.median(fn_h))} px")
            print(f"      Largeur  : min={min(fn_w)} px, max={max(fn_w)} px, médiane={int(np.median(fn_w))} px")
            pct_small_h = sum(1 for d in fn_data if d['h'] < sample_h * 2) / len(fn_data) * 100
            pct_small_w = sum(1 for d in fn_data if d['w'] < sample_w * 2) / len(fn_data) * 100
            print(f"      {pct_small_h:.0f}% des FN ont une hauteur < {sample_h*2} px (2× fenêtre)")
            print(f"      {pct_small_w:.0f}% des FN ont une largeur < {sample_w*2} px (2× fenêtre)")
        
        # Graphique : Analyse dimensionnelle complète (3×2)
        fig, axes = plt.subplots(3, 2, figsize=(16, 20))
        
        det_w = [d['w'] for d in tp_data]
        det_h = [d['h'] for d in tp_data]
        miss_w = [d['w'] for d in fn_data]
        miss_h = [d['h'] for d in fn_data]
        
        # (a) Scatter W×H
        ax = axes[0, 0]
        if det_w:
            ax.scatter(det_w, det_h, c='green', alpha=0.6, label='Détecté (TP)', s=30)
        if miss_w:
            ax.scatter(miss_w, miss_h, c='red', alpha=0.8, label='Manqué (FN)', s=50, marker='x')
        ax.axhline(y=sample_h, color='orange', linestyle='--', alpha=0.6, linewidth=1.5, label=f'H fenêtre ({sample_h}px)')
        ax.axhline(y=sample_h*2, color='blue', linestyle=':', alpha=0.4, linewidth=1, label=f'2× H ({sample_h*2}px)')
        ax.axvline(x=sample_w, color='darkorange', linestyle='--', alpha=0.6, linewidth=1.5, label=f'W fenêtre ({sample_w}px)')
        ax.axvline(x=sample_w*2, color='navy', linestyle=':', alpha=0.4, linewidth=1, label=f'2× W ({sample_w*2}px)')
        ax.set_xlabel('Largeur (px)', fontsize=11)
        ax.set_ylabel('Hauteur (px)', fontsize=11)
        ax.set_title('Dimensions — Toutes les images', fontsize=13, fontweight='bold')
        ax.legend(fontsize=7, loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # (b) Histogramme des hauteurs
        ax = axes[0, 1]
        h_bins_hist = np.arange(0, max(all_h) + 20, 20)
        ax.hist([det_h, miss_h], bins=h_bins_hist, label=['TP', 'FN'],
                color=['green', 'red'], alpha=0.7, stacked=True)
        ax.axvline(x=sample_h, color='orange', linestyle='--', linewidth=1.5, label=f'Fenêtre ({sample_h}px)')
        ax.axvline(x=sample_h*2, color='blue', linestyle=':', linewidth=1, label=f'2× ({sample_h*2}px)')
        ax.set_xlabel('Hauteur (px)', fontsize=11)
        ax.set_ylabel("Nombre d'images", fontsize=11)
        ax.set_title('Distribution des hauteurs', fontsize=13, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # (c) Histogramme des largeurs
        ax = axes[1, 0]
        w_bins_hist = np.arange(0, max(all_w) + 20, 20)
        ax.hist([det_w, miss_w], bins=w_bins_hist, label=['TP', 'FN'],
                color=['green', 'red'], alpha=0.7, stacked=True)
        ax.axvline(x=sample_w, color='darkorange', linestyle='--', linewidth=1.5, label=f'Fenêtre ({sample_w}px)')
        ax.axvline(x=sample_w*2, color='navy', linestyle=':', linewidth=1, label=f'2× ({sample_w*2}px)')
        ax.set_xlabel('Largeur (px)', fontsize=11)
        ax.set_ylabel("Nombre d'images", fontsize=11)
        ax.set_title('Distribution des largeurs', fontsize=13, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # (d) Zoom petites images
        ax = axes[1, 1]
        small_tp = [d for d in tp_data if d['h'] < 200 or d['w'] < 200]
        small_fn = [d for d in fn_data if d['h'] < 200 or d['w'] < 200]
        if small_tp:
            ax.scatter([d['w'] for d in small_tp], [d['h'] for d in small_tp],
                      c='green', alpha=0.6, label=f'TP ({len(small_tp)})', s=40)
        if small_fn:
            ax.scatter([d['w'] for d in small_fn], [d['h'] for d in small_fn],
                      c='red', alpha=0.8, label=f'FN ({len(small_fn)})', s=60, marker='x')
        ax.axhline(y=sample_h, color='orange', linestyle='--', alpha=0.6, linewidth=1.5, label=f'H ({sample_h}px)')
        ax.axhline(y=sample_h*2, color='blue', linestyle=':', alpha=0.4, linewidth=1)
        ax.axvline(x=sample_w, color='darkorange', linestyle='--', alpha=0.6, linewidth=1.5, label=f'W ({sample_w}px)')
        ax.axvline(x=sample_w*2, color='navy', linestyle=':', alpha=0.4, linewidth=1)
        ax.set_xlabel('Largeur (px)', fontsize=11)
        ax.set_ylabel('Hauteur (px)', fontsize=11)
        ax.set_title('Zoom — Petites images (<200px)', fontsize=13, fontweight='bold')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        zoom_data = [d for d in size_data if d['h'] < 200 or d['w'] < 200]
        if zoom_data:
            ax.set_ylim(0, min(max(d['h'] for d in zoom_data) + 20, 210))
            ax.set_xlim(0, min(max(d['w'] for d in zoom_data) + 20, 210))
        
        # (e) FN seulement
        ax = axes[2, 0]
        if miss_w:
            scatter = ax.scatter(miss_w, miss_h, c=[d['area'] for d in fn_data],
                                cmap='Reds', alpha=0.8, s=60, marker='x', edgecolors='darkred')
            plt.colorbar(scatter, ax=ax, label='Aire (px²)', shrink=0.8)
            large_fn = sorted(fn_data, key=lambda d: d['h'], reverse=True)[:5]
            for d in large_fn:
                if d['h'] > sample_h * 2:
                    ax.annotate(f"{d['w']}×{d['h']}", xy=(d['w'], d['h']),
                               fontsize=7, color='darkred', alpha=0.7,
                               xytext=(5, 5), textcoords='offset points')
        ax.axhline(y=sample_h, color='orange', linestyle='--', alpha=0.6, linewidth=1.5)
        ax.axhline(y=sample_h*2, color='blue', linestyle=':', alpha=0.4, linewidth=1)
        ax.axvline(x=sample_w, color='darkorange', linestyle='--', alpha=0.6, linewidth=1.5)
        ax.axvline(x=sample_w*2, color='navy', linestyle=':', alpha=0.4, linewidth=1)
        ax.set_xlabel('Largeur (px)', fontsize=11)
        ax.set_ylabel('Hauteur (px)', fontsize=11)
        ax.set_title(f'FN seulement ({len(fn_data)} images)', fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # (f) Distribution du ratio W/H
        ax = axes[2, 1]
        tp_ratios = [d['w'] / d['h'] for d in tp_data if d['h'] > 0]
        fn_ratios = [d['w'] / d['h'] for d in fn_data if d['h'] > 0]
        max_ratio = max(all_ratios) if all_ratios else 2.0
        ratio_bins = np.arange(0, max_ratio + 0.1, 0.1)
        ax.hist([tp_ratios, fn_ratios], bins=ratio_bins, label=['TP', 'FN'],
                color=['green', 'red'], alpha=0.7, stacked=True)
        window_ratio = sample_w / sample_h if sample_h > 0 else 0.57
        ax.axvline(x=window_ratio, color='purple', linestyle='--', linewidth=1.5,
                   label=f'Ratio fenêtre ({window_ratio:.2f})')
        ax.set_xlabel('Ratio W/H', fontsize=11)
        ax.set_ylabel("Nombre d'images", fontsize=11)
        ax.set_title("Distribution du ratio d'aspect", fontsize=13, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        fig.suptitle(f'Analyse dimensionnelle des positives — SF={sf}, MN={mn}\n'
                     f'Fenêtre de détection : {sample_w}×{sample_h} px',
                     fontsize=15, fontweight='bold', y=1.01)
        plt.tight_layout()
        path = os.path.join(output_dir, 'size_distribution_positive.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"    Graphique sauvegardé : {path}")
    
    # ══════════════════════════════════════════════════════════
    #  5b. Analyse de la complexité du fond
    # ══════════════════════════════════════════════════════════
    print("\n    5b. Complexité du fond (positives de test)...")
    
    complexity_data = []
    for f in tqdm(pos_files, desc="    Fond", unit="img", colour="cyan", ncols=80):
        img_path = os.path.join(test_pos_dir, f)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        
        std_dev = np.std(img)
        edges = cv2.Canny(img, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        variance_lap = laplacian.var()
        
        dets = cascade.detectMultiScale(img, scaleFactor=sf, minNeighbors=mn)
        detected = len(dets) > 0
        
        complexity_data.append({
            'file': f, 'std': std_dev, 'edge_density': edge_density,
            'lap_var': variance_lap, 'detected': detected
        })
    
    if complexity_data:
        median_std = np.median([d['std'] for d in complexity_data])
        median_edge = np.median([d['edge_density'] for d in complexity_data])
        
        simple = [d for d in complexity_data if d['std'] <= median_std and d['edge_density'] <= median_edge]
        complex_bg = [d for d in complexity_data if d['std'] > median_std or d['edge_density'] > median_edge]
        
        simple_recall = sum(1 for d in simple if d['detected']) / len(simple) * 100 if simple else 0
        complex_recall = sum(1 for d in complex_bg if d['detected']) / len(complex_bg) * 100 if complex_bg else 0
        
        print(f"\n    Fond simple  : {len(simple):>4} images, Recall = {simple_recall:.1f}%")
        print(f"    Fond complexe: {len(complex_bg):>4} images, Recall = {complex_recall:.1f}%")
        
        if abs(simple_recall - complex_recall) > 15:
            if simple_recall > complex_recall:
                print(f"    ⚠ Le modèle performe mieux sur fond simple ({simple_recall:.0f}% vs {complex_recall:.0f}%)")
                print(f"      → Ajouter plus d'images d'entraînement avec des fonds variés")
            else:
                print(f"    ℹ Le modèle performe mieux sur fond complexe ({complex_recall:.0f}% vs {simple_recall:.0f}%)")
                print(f"      → Les images simples pourraient manquer de texture distinctive")
        
        # Graphique
        fig, ax = plt.subplots(figsize=(10, 7))
        det_std = [d['std'] for d in complexity_data if d['detected']]
        det_edge = [d['edge_density'] for d in complexity_data if d['detected']]
        miss_std = [d['std'] for d in complexity_data if not d['detected']]
        miss_edge = [d['edge_density'] for d in complexity_data if not d['detected']]
        
        if det_std:
            ax.scatter(det_std, det_edge, c='green', alpha=0.6, label='Détecté (TP)', s=40)
        if miss_std:
            ax.scatter(miss_std, miss_edge, c='red', alpha=0.8, label='Manqué (FN)', s=60, marker='x')
        
        ax.axvline(x=median_std, color='gray', linestyle='--', alpha=0.4, label=f'Médiane std={median_std:.1f}')
        ax.axhline(y=median_edge, color='gray', linestyle=':', alpha=0.4, label=f'Médiane edges={median_edge:.3f}')
        
        ax.set_xlabel('Écart-type des pixels', fontsize=11)
        ax.set_ylabel('Densité d\'arêtes (Canny)', fontsize=11)
        ax.set_title('Complexité du fond vs Détection', fontsize=13, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        path = os.path.join(output_dir, 'background_complexity.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"    Graphique sauvegardé : {path}")
    
    # ══════════════════════════════════════════════════════════
    #  5c. Diversité des images augmentées
    # ══════════════════════════════════════════════════════════
    print("\n    5c. Diversité des images augmentées...")
    
    train_pos_dir = os.path.join(data_dir, 'train', 'positive')
    if os.path.isdir(train_pos_dir):
        train_files = sorted(os.listdir(train_pos_dir))
        originals = [f for f in train_files if not f.startswith('aug_') and os.path.isfile(os.path.join(train_pos_dir, f))]
        augmented = [f for f in train_files if f.startswith('aug_') and os.path.isfile(os.path.join(train_pos_dir, f))]
        
        print(f"    {len(originals)} originales, {len(augmented)} augmentées dans train/positive/")
        
        if originals and augmented:
            similarities = []
            n_checked = 0
            
            for aug_file in tqdm(augmented[:min(len(augmented), 200)],
                                  desc="    Similarité", unit="img", colour="cyan", ncols=80):
                parts = aug_file.split('_', 2)
                if len(parts) < 3:
                    continue
                source_name = parts[2]
                source_path = os.path.join(train_pos_dir, source_name)
                aug_path = os.path.join(train_pos_dir, aug_file)
                
                if not os.path.isfile(source_path):
                    continue
                
                src_img = cv2.imread(source_path, cv2.IMREAD_GRAYSCALE)
                aug_img = cv2.imread(aug_path, cv2.IMREAD_GRAYSCALE)
                if src_img is None or aug_img is None:
                    continue
                
                target_size = (64, 64)
                src_resized = cv2.resize(src_img, target_size)
                aug_resized = cv2.resize(aug_img, target_size)
                
                src_hist = cv2.calcHist([src_resized], [0], None, [64], [0, 256])
                aug_hist = cv2.calcHist([aug_resized], [0], None, [64], [0, 256])
                cv2.normalize(src_hist, src_hist)
                cv2.normalize(aug_hist, aug_hist)
                
                similarity = cv2.compareHist(src_hist, aug_hist, cv2.HISTCMP_CORREL)
                similarities.append(similarity)
                n_checked += 1
            
            if similarities:
                avg_sim = np.mean(similarities)
                std_sim = np.std(similarities)
                very_similar = sum(1 for s in similarities if s > 0.98)
                
                print(f"\n    Similarité augmentées ↔ originales ({n_checked} paires) :")
                print(f"      Corrélation moyenne : {avg_sim:.3f} (std={std_sim:.3f})")
                print(f"      Très similaires (>0.98) : {very_similar}/{n_checked} ({very_similar/n_checked*100:.0f}%)")
                
                if avg_sim > 0.95:
                    print(f"    ⚠ Les augmentations sont très proches des originales — diversité insuffisante")
                    print(f"      → Augmenter l'amplitude des transformations (contraste, gamma)")
                    print(f"      → Ajouter des transformations supplémentaires (flou, bruit)")
                elif avg_sim < 0.7:
                    print(f"    ⚠ Les augmentations sont très différentes — risque de distorsion")
                    print(f"      → Vérifier que les augmentations ne déforment pas l'objet")
                else:
                    print(f"    ✓ Diversité des augmentations adéquate")
                
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.hist(similarities, bins=30, color='steelblue', alpha=0.8, edgecolor='white')
                ax.axvline(x=avg_sim, color='red', linestyle='--', linewidth=2,
                          label=f'Moyenne = {avg_sim:.3f}')
                ax.axvline(x=0.98, color='orange', linestyle=':', linewidth=1.5,
                          label='Seuil très similaire (0.98)')
                ax.set_xlabel('Corrélation d\'histogramme', fontsize=11)
                ax.set_ylabel('Nombre de paires', fontsize=11)
                ax.set_title('Diversité des augmentations — Similarité avec l\'original',
                            fontsize=13, fontweight='bold')
                ax.legend(fontsize=10)
                ax.grid(True, alpha=0.3)
                
                plt.tight_layout()
                path = os.path.join(output_dir, 'augmentation_diversity.png')
                plt.savefig(path, dpi=150, bbox_inches='tight')
                plt.close()
                print(f"    Graphique sauvegardé : {path}")
    else:
        print("    Dossier train/positive/ non trouvé — analyse des augmentations ignorée")
    
    # ══════════════════════════════════════════════════════════
    #  5d. Groupement des négatives par similarité + taux de FP
    # ══════════════════════════════════════════════════════════
    print("\n    5d. Analyse des négatives par groupe de similarité...")
    
    neg_files = sorted([f for f in os.listdir(test_neg_dir) if os.path.isfile(os.path.join(test_neg_dir, f))])
    
    if not neg_files:
        print("    Aucune image négative de test trouvée.")
        return
    
    neg_features = []
    neg_results = []
    
    for f in tqdm(neg_files[:min(len(neg_files), 300)],
                  desc="    Négatifs", unit="img", colour="cyan", ncols=80):
        img_path = os.path.join(test_neg_dir, f)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        
        resized = cv2.resize(img, (64, 64))
        
        hist = cv2.calcHist([resized], [0], None, [32], [0, 256]).flatten()
        hist = hist / (hist.sum() + 1e-8)
        
        std = np.std(resized)
        mean = np.mean(resized)
        edges = cv2.Canny(resized, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        feature_vec = np.concatenate([hist, [std / 255, mean / 255, edge_density]])
        neg_features.append(feature_vec)
        
        dets = cascade.detectMultiScale(img, scaleFactor=sf, minNeighbors=mn)
        is_fp = len(dets) > 0
        neg_results.append({'file': f, 'fp': is_fp})
    
    if len(neg_features) >= 4:
        try:
            from sklearn.cluster import KMeans
        except ImportError:
            print("    sklearn non installé — clustering des négatives ignoré")
            print("    → pip install scikit-learn pour activer cette analyse")
            print("\n    ✓ Analyse de la qualité des données terminée.")
            return
        
        features_array = np.array(neg_features)
        n_clusters = min(6, len(neg_features) // 3)
        n_clusters = max(2, n_clusters)
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(features_array)
        
        print(f"\n    {n_clusters} groupes identifiés parmi {len(neg_files)} négatives :")
        print(f"    ┌─────────┬───────┬──────┬───────────┐")
        print(f"    │ {'Groupe':^7} │ {'Nb':^5} │ {'FP':^4} │ {'Taux FP':^9} │")
        print(f"    ├─────────┼───────┼──────┼───────────┤")
        
        group_stats = []
        for c in range(n_clusters):
            group_indices = [i for i, l in enumerate(labels) if l == c]
            n = len(group_indices)
            n_fp = sum(1 for i in group_indices if neg_results[i]['fp'])
            fp_rate = n_fp / n * 100 if n > 0 else 0
            group_stats.append({'cluster': c, 'n': n, 'fp': n_fp, 'fp_rate': fp_rate})
            print(f"    │ {c+1:^7} │ {n:>5} │ {n_fp:>4} │ {fp_rate:>7.1f}%  │")
        
        print(f"    └─────────┴───────┴──────┴───────────┘")
        
        worst_group = max(group_stats, key=lambda x: x['fp_rate'])
        if worst_group['fp_rate'] > 20:
            print(f"\n    ⚠ Groupe {worst_group['cluster']+1} a un taux de FP élevé ({worst_group['fp_rate']:.0f}%)")
            print(f"      → Ces images négatives ressemblent peut-être trop aux positives")
            print(f"      → Ajouter plus de négatives similaires en entraînement (HNM)")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        groups = [f"G{g['cluster']+1}\n(n={g['n']})" for g in group_stats]
        fp_rates = [g['fp_rate'] for g in group_stats]
        colors = ['#e74c3c' if r > 20 else '#f39c12' if r > 5 else '#2ecc71' for r in fp_rates]
        
        bars = ax.bar(groups, fp_rates, color=colors, alpha=0.8, edgecolor='white', linewidth=1.5)
        
        for bar, rate in zip(bars, fp_rates):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                   f'{rate:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        ax.set_xlabel('Groupe de similarité', fontsize=11)
        ax.set_ylabel('Taux de faux positifs (%)', fontsize=11)
        ax.set_title('Taux de FP par groupe de négatives similaires', fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim(0, max(fp_rates) * 1.3 if fp_rates else 10)
        
        plt.tight_layout()
        path = os.path.join(output_dir, 'negative_similarity_groups.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"    Graphique sauvegardé : {path}")
    else:
        print("    Pas assez d'images pour le clustering.")
    
    print("\n    ✓ Analyse de la qualité des données terminée.")


def analyze_optimal_window_size(model_path, data_dir, analysis_dir):
    """
    Analyse les dimensions des images positives pour recommander
    la taille optimale de la fenêtre de détection (sample_width × sample_height).
    
    :param model_path: Chemin du cascade.xml (ou None)
    :param data_dir: Dossier data/ racine (contient positive/)
    :param analysis_dir: Dossier de sortie pour les graphiques
    :return: dict avec la recommandation {'w': int, 'h': int} ou None
    """
    print("\n")
    print("─" * 60)
    print("  Analyse de la taille optimale de la fenêtre de détection")
    print("─" * 60)
    
    pos_dir = os.path.join(data_dir, 'positive')
    if not os.path.isdir(pos_dir):
        print(f"\n  ERREUR : Dossier {pos_dir} introuvable.")
        print(f"  → Il faut des images positives pré-découpées (bounding boxes)")
        return None
    
    pos_files = [f for f in os.listdir(pos_dir)
                 if os.path.isfile(os.path.join(pos_dir, f))]
    if not pos_files:
        print("\n  ERREUR : Aucune image positive trouvée.")
        return None
    
    widths, heights = [], []
    for f in tqdm(pos_files, desc="  Dimensions", unit="img", colour="cyan", ncols=80):
        img = cv2.imread(os.path.join(pos_dir, f))
        if img is None:
            continue
        h, w = img.shape[:2]
        widths.append(w)
        heights.append(h)
    
    if not widths:
        print("\n  ERREUR : Aucune image lisible.")
        return None
    
    widths = np.array(widths)
    heights = np.array(heights)
    ratios = widths / heights
    
    # Fenêtre actuelle du modèle
    current_sw, current_sh = None, None
    if model_path and os.path.exists(model_path):
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(model_path)
            root = tree.getroot()
            w_el = root.find('.//width')
            h_el = root.find('.//height')
            if w_el is not None and h_el is not None:
                current_sw = int(w_el.text)
                current_sh = int(h_el.text)
        except Exception:
            pass
    
    # Statistiques
    print(f"\n  ── Statistiques des images positives ({len(widths)} images) ──")
    p10_w, p25_w, p50_w = int(np.percentile(widths, 10)), int(np.percentile(widths, 25)), int(np.percentile(widths, 50))
    p10_h, p25_h, p50_h = int(np.percentile(heights, 10)), int(np.percentile(heights, 25)), int(np.percentile(heights, 50))
    print(f"  Largeur  : min={widths.min()}, max={widths.max()}, p10={p10_w}, p25={p25_w}, médiane={p50_w}")
    print(f"  Hauteur  : min={heights.min()}, max={heights.max()}, p10={p10_h}, p25={p25_h}, médiane={p50_h}")
    print(f"  Ratio W/H: min={ratios.min():.2f}, max={ratios.max():.2f}, médiane={np.median(ratios):.2f}")
    
    if current_sw and current_sh:
        print(f"\n  Fenêtre actuelle du modèle : {current_sw}×{current_sh} (ratio={current_sw/current_sh:.2f})")
    
    # Fenêtres candidates
    median_ratio = np.median(ratios)
    candidates = []
    
    for p, label in [(10, 'P10'), (15, 'P15'), (20, 'P20'), (25, 'P25')]:
        w_p = int(np.percentile(widths, p))
        h_p = int(np.percentile(heights, p))
        w_p = max(12, w_p - (w_p % 2))
        h_p = max(12, h_p - (h_p % 2))
        candidates.append((w_p, h_p, f'Percentile {label}'))
    
    for base_h in [20, 24, 30, 36, 42, 48, 56, 64]:
        base_w = int(base_h * median_ratio)
        base_w = max(12, base_w - (base_w % 2))
        candidates.append((base_w, base_h, f'Ratio médian'))
    
    if current_sw and current_sh:
        candidates.append((current_sw, current_sh, 'Actuel'))
    
    seen = set()
    unique_candidates = []
    for w_c, h_c, label in candidates:
        key = (w_c, h_c)
        if key not in seen:
            seen.add(key)
            unique_candidates.append((w_c, h_c, label))
    candidates = sorted(unique_candidates, key=lambda x: x[0] * x[1])
    
    # Évaluation
    print(f"\n  ── Évaluation des fenêtres candidates ──")
    print(f"  ┌──────────────┬───────────┬───────────┬───────────┬───────────┬─────────────────────┐")
    print(f"  │ {'Fenêtre':^12} │ {'Ratio':^9} │ {'< Fenêtre':^9} │ {'1-2× Fen.':^9} │ {'≥ 2× Fen.':^9} │ {'Source':^19} │")
    print(f"  ├──────────────┼───────────┼───────────┼───────────┼───────────┼─────────────────────┤")
    
    best_score = -float('inf')
    best_candidate = None
    eval_results = []
    
    for w_c, h_c, source in candidates:
        below = np.sum((widths < w_c) | (heights < h_c))
        borderline = np.sum(
            (widths >= w_c) & (heights >= h_c) &
            ((widths < w_c * 2) | (heights < h_c * 2))
        )
        good = np.sum((widths >= w_c * 2) & (heights >= h_c * 2))
        n = len(widths)
        
        pct_below = below / n * 100
        pct_border = borderline / n * 100
        pct_good = good / n * 100
        
        ratio_c = w_c / h_c if h_c > 0 else 0
        
        ratio_penalty = abs(ratio_c - median_ratio) * 10
        score = pct_good * 2 + pct_border - pct_below * 3 - ratio_penalty
        
        marker = ''
        is_current = (current_sw == w_c and current_sh == h_c)
        if is_current:
            marker = ' ◄'
        
        if score > best_score and not is_current:
            best_score = score
            best_candidate = (w_c, h_c, source)
        
        label = f'{w_c}×{h_c}'
        print(f"  │ {label:^12} │ {ratio_c:^9.2f} │ {pct_below:>7.1f}%  │ {pct_border:>7.1f}%  │ {pct_good:>7.1f}%  │ {source:<17}{marker:>2} │")
        eval_results.append({
            'w': w_c, 'h': h_c, 'source': source,
            'pct_below': pct_below, 'pct_border': pct_border,
            'pct_good': pct_good, 'score': score, 'is_current': is_current
        })
    
    print(f"  └──────────────┴───────────┴───────────┴───────────┴───────────┴─────────────────────┘")
    print(f"  Légende : < Fenêtre = W ou H sous le minimum → indétectable")
    print(f"            1-2× Fen. = détection fragile mais possible")
    print(f"            ≥ 2× Fen. = bonne détection attendue")
    
    # Recommandation
    if best_candidate:
        w_best, h_best, src_best = best_candidate
        print(f"\n  ► Recommandation : {w_best}×{h_best} ({src_best})")
        print(f"    Ratio d'aspect : {w_best/h_best:.2f} (médiane images : {median_ratio:.2f})")
        
        if current_sw and current_sh:
            print(f"    Actuel         : {current_sw}×{current_sh}")
            if w_best != current_sw or h_best != current_sh:
                print(f"    → Un changement de fenêtre nécessite un ré-entraînement complet")
                print(f"      (opencv_createsamples + opencv_traincascade)")
    
    # Graphique
    os.makedirs(analysis_dir, exist_ok=True)
    fig, axes_plot = plt.subplots(2, 2, figsize=(16, 14))
    
    # (a) Scatter des dimensions
    ax = axes_plot[0, 0]
    ax.scatter(widths, heights, c='steelblue', alpha=0.4, s=20, label=f'Images ({len(widths)})')
    if current_sw and current_sh:
        from matplotlib.patches import Rectangle
        rect = Rectangle((0, 0), current_sw, current_sh, linewidth=2,
                         edgecolor='red', facecolor='red', alpha=0.15, label=f'Fenêtre actuelle ({current_sw}×{current_sh})')
        ax.add_patch(rect)
    if best_candidate:
        from matplotlib.patches import Rectangle as Rect2
        rect2 = Rect2((0, 0), w_best, h_best, linewidth=2,
                      edgecolor='green', facecolor='green', alpha=0.15, label=f'Recommandée ({w_best}×{h_best})')
        ax.add_patch(rect2)
    ax.set_xlabel('Largeur (px)', fontsize=11)
    ax.set_ylabel('Hauteur (px)', fontsize=11)
    ax.set_title('Dimensions des images positives', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    
    # (b) Histogramme des hauteurs
    ax = axes_plot[0, 1]
    ax.hist(heights, bins=30, color='steelblue', alpha=0.7, edgecolor='white')
    ax.axvline(x=p10_h, color='red', linestyle='--', linewidth=1.5, label=f'P10 ({p10_h}px)')
    ax.axvline(x=p25_h, color='orange', linestyle='--', linewidth=1.5, label=f'P25 ({p25_h}px)')
    ax.axvline(x=p50_h, color='green', linestyle='--', linewidth=1.5, label=f'P50 ({p50_h}px)')
    if current_sh:
        ax.axvline(x=current_sh, color='purple', linestyle=':', linewidth=2, label=f'Actuel ({current_sh}px)')
    ax.set_xlabel('Hauteur (px)', fontsize=11)
    ax.set_ylabel("Nombre d'images", fontsize=11)
    ax.set_title('Distribution des hauteurs', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    
    # (c) Histogramme des largeurs
    ax = axes_plot[1, 0]
    ax.hist(widths, bins=30, color='steelblue', alpha=0.7, edgecolor='white')
    ax.axvline(x=p10_w, color='red', linestyle='--', linewidth=1.5, label=f'P10 ({p10_w}px)')
    ax.axvline(x=p25_w, color='orange', linestyle='--', linewidth=1.5, label=f'P25 ({p25_w}px)')
    ax.axvline(x=p50_w, color='green', linestyle='--', linewidth=1.5, label=f'P50 ({p50_w}px)')
    if current_sw:
        ax.axvline(x=current_sw, color='purple', linestyle=':', linewidth=2, label=f'Actuel ({current_sw}px)')
    ax.set_xlabel('Largeur (px)', fontsize=11)
    ax.set_ylabel("Nombre d'images", fontsize=11)
    ax.set_title('Distribution des largeurs', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    
    # (d) Barplot couverture
    ax = axes_plot[1, 1]
    labels_plot = [f"{r['w']}×{r['h']}" for r in eval_results]
    below_vals = [r['pct_below'] for r in eval_results]
    border_vals = [r['pct_border'] for r in eval_results]
    good_vals = [r['pct_good'] for r in eval_results]
    
    x_pos = np.arange(len(labels_plot))
    bar_width = 0.6
    ax.bar(x_pos, good_vals, bar_width, label='≥ 2× (bon)', color='green', alpha=0.7)
    ax.bar(x_pos, border_vals, bar_width, bottom=good_vals, label='1-2× (fragile)', color='orange', alpha=0.7)
    ax.bar(x_pos, below_vals, bar_width,
           bottom=[g + b for g, b in zip(good_vals, border_vals)],
           label='< Fenêtre', color='red', alpha=0.7)
    
    for i, r in enumerate(eval_results):
        if r['is_current']:
            ax.annotate('actuel', xy=(i, 5), fontsize=8, ha='center',
                       color='purple', fontweight='bold')
    if best_candidate:
        best_idx = next((i for i, r in enumerate(eval_results)
                        if r['w'] == w_best and r['h'] == h_best), None)
        if best_idx is not None:
            ax.annotate('★ reco', xy=(best_idx, 5), fontsize=8, ha='center',
                       color='darkgreen', fontweight='bold')
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels_plot, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('% des images', fontsize=11)
    ax.set_title('Couverture par taille de fenêtre', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    
    fig.suptitle("Analyse de la taille optimale de fenêtre (sample_width × sample_height)\n"
                 f"Basée sur {len(widths)} images positives d'entraînement",
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    path = os.path.join(analysis_dir, 'window_size_analysis.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  Graphique sauvegardé : {path}")
    
    result = {'w': w_best, 'h': h_best} if best_candidate else None
    return result
