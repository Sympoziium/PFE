# cascade/analysis/stages.py
# ---------------------------
# Visualisation FN/TP et évaluation par stage (cascade tronquée).

import os
import tempfile
import cv2
import numpy as np
import matplotlib.pyplot as plt

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it

from .utils import _load_images_grayscale, _build_truncated_cascade_xml


def visualize_fn_tp_montage(model_path, test_pos_dir, output_dir,
                             scaleFactor=1.1, minNeighbors=5):
    """
    Crée une mosaïque visuelle montrant les Faux Négatifs ET les Vrais Positifs
    côte à côte, séparés par une barre visuelle.
    
    Layout de la mosaïque :
    ┌─────────────────────────────────────────┐
    │  FAUX NÉGATIFS (images non détectées)   │
    │  [img] [img] [img] [img] [img] [img]   │
    │  ─────────── SÉPARATION ──────────────  │
    │  VRAIS POSITIFS (images détectées)      │
    │  [img] [img] [img] [img] [img] [img]   │
    └─────────────────────────────────────────┘
    
    Aucune image individuelle n'est sauvegardée sur disque.
    Seul le montage final (fn_tp_montage.png) est conservé.
    
    :param model_path: Chemin du fichier cascade.xml
    :param test_pos_dir: Dossier des images positives de test
    :param output_dir: Dossier de sortie (data/analysis/)
    :param scaleFactor: Facteur d'échelle pour detectMultiScale
    :param minNeighbors: Nombre minimum de voisins
    :return: (liste noms FN, liste noms TP)
    """
    print("\n  Identification des FN et TP...")
    
    if model_path is None or not os.path.exists(model_path):
        print(f"    ERREUR : Modèle non trouvé à {model_path}")
        return [], []
    
    cascade = cv2.CascadeClassifier(model_path)
    if cascade.empty():
        print(f"    ERREUR : Impossible de charger le modèle")
        return [], []
    
    test_images = sorted([
        f for f in os.listdir(test_pos_dir)
        if os.path.isfile(os.path.join(test_pos_dir, f))
    ])
    
    fn_images, fn_names = [], []
    tp_images, tp_names = [], []
    
    for img_file in tqdm(test_images, desc="    Scan", unit="img", colour="cyan", ncols=80):
        img_path = os.path.join(test_pos_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        detections = cascade.detectMultiScale(
            gray, scaleFactor=scaleFactor, minNeighbors=minNeighbors
        )
        
        if len(detections) == 0:
            fn_images.append(img)
            fn_names.append(img_file)
        else:
            tp_images.append(img)
            tp_names.append(img_file)
    
    total = len(fn_names) + len(tp_names)
    if total == 0:
        print("    Aucune image lisible trouvée.")
        return [], []
    
    recall = len(tp_names) / total * 100
    print(f"    Résultat : {len(fn_names)} FN + {len(tp_names)} TP / {total} images "
          f"(Recall = {recall:.1f}%)")
    
    # ── Générer la mosaïque FN + séparateur + TP ──
    os.makedirs(output_dir, exist_ok=True)
    
    cols = min(8, max(len(fn_images), len(tp_images), 1))
    fn_rows = max(1, (len(fn_images) + cols - 1) // cols) if fn_images else 0
    tp_rows = max(1, (len(tp_images) + cols - 1) // cols) if tp_images else 0
    total_rows = fn_rows + 1 + tp_rows
    
    cell_h = 2.2
    fig, axes = plt.subplots(total_rows, cols,
                              figsize=(cols * 2.5, total_rows * cell_h))
    if total_rows == 1:
        axes = np.array([axes])
    if cols == 1:
        axes = axes.reshape(-1, 1)
    
    # Remplir la section FN
    for i in range(fn_rows):
        for j in range(cols):
            ax = axes[i, j]
            idx = i * cols + j
            if idx < len(fn_images):
                img_rgb = cv2.cvtColor(fn_images[idx], cv2.COLOR_BGR2RGB)
                ax.imshow(img_rgb)
                name = fn_names[idx]
                short = name if len(name) <= 20 else name[:17] + '...'
                ax.set_title(short, fontsize=6, color='red')
            ax.axis('off')
    
    # Ligne séparatrice
    sep_row = fn_rows
    for j in range(cols):
        ax = axes[sep_row, j]
        ax.axis('off')
    mid_ax = axes[sep_row, cols // 2]
    mid_ax.text(0.5, 0.5,
                f'▲ FN ({len(fn_names)})  ────────  TP ({len(tp_names)}) ▼',
                ha='center', va='center', fontsize=11, fontweight='bold',
                color='#333333', transform=mid_ax.transAxes)
    
    # Remplir la section TP
    for i in range(tp_rows):
        for j in range(cols):
            ax = axes[sep_row + 1 + i, j]
            idx = i * cols + j
            if idx < len(tp_images):
                img_rgb = cv2.cvtColor(tp_images[idx], cv2.COLOR_BGR2RGB)
                ax.imshow(img_rgb)
                name = tp_names[idx]
                short = name if len(name) <= 20 else name[:17] + '...'
                ax.set_title(short, fontsize=6, color='green')
            ax.axis('off')
    
    fig.suptitle(
        f'FN vs TP — SF={scaleFactor}, MN={minNeighbors} — '
        f'Recall={recall:.1f}% ({len(tp_names)}/{total})',
        fontsize=13, fontweight='bold'
    )
    plt.tight_layout()
    montage_path = os.path.join(output_dir, 'fn_tp_montage.png')
    plt.savefig(montage_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"    Mosaïque sauvegardée : {montage_path}")
    
    return fn_names, tp_names


def evaluate_per_stage(cascade_xml_path, test_pos_dir, test_neg_dir,
                       scaleFactor=1.1, minNeighbors=5, max_img_dim=320):
    """
    Évalue le modèle à chaque nombre de stages (1 → N) en construisant
    des cascade.xml tronqués par manipulation XML directe.
    
    OPTIMISATIONS DE VITESSE :
    - Images pré-chargées en mémoire une seule fois (grayscale, redimensionnées)
    - Pas d'appel à test_model() (évite le rechargement + tqdm imbriqué)
    - Redimensionnement à max_img_dim px de côté long
    
    :param cascade_xml_path: Chemin du cascade.xml complet
    :param test_pos_dir: Dossier des images positives de test
    :param test_neg_dir: Dossier des images négatives de test
    :param scaleFactor: Facteur d'échelle pour detectMultiScale
    :param minNeighbors: Nombre minimum de voisins
    :param max_img_dim: Dimension maximale (côté long) des images chargées
    :return: dict avec listes de métriques indexées par stage
    """
    print("\n  Analyse per-stage en cours...")
    
    if not os.path.isfile(cascade_xml_path):
        print(f"    ERREUR : cascade.xml non trouvé : {cascade_xml_path}")
        return None
    
    import xml.etree.ElementTree as ET
    tree = ET.parse(cascade_xml_path)
    root = tree.getroot()
    cascade_el = root.find('cascade')
    total_stages = int(cascade_el.find('stageNum').text)
    feature_type = cascade_el.find('featureType').text
    w = int(cascade_el.find('width').text)
    h = int(cascade_el.find('height').text)
    
    print(f"    Paramètres : {feature_type}, fenêtre={w}×{h}")
    print(f"    {total_stages} stages à analyser")
    print(f"    detectMultiScale : SF={scaleFactor}, MN={minNeighbors}")
    
    # Pré-chargement des images
    print(f"    Chargement des images de test (max {max_img_dim}px)...")
    pos_images = _load_images_grayscale(test_pos_dir, max_img_dim)
    neg_images = _load_images_grayscale(test_neg_dir, max_img_dim)
    print(f"    {len(pos_images)} positives + {len(neg_images)} négatives chargées")
    
    if not pos_images and not neg_images:
        print("    ERREUR : Aucune image de test chargée.")
        return None
    
    metrics = {
        'stage': [], 'recall': [], 'precision': [], 'f1': [],
        'specificity': [], 'tp': [], 'fn': [], 'fp': [], 'tn': []
    }
    
    # Déterminer le stage de départ
    if total_stages <= 3:
        start_stage = 1
    elif total_stages <= 8:
        start_stage = 2
    else:
        start_stage = min(5, total_stages)
    
    skipped = start_stage - 1
    if skipped > 0:
        print(f"    Stages 1-{skipped} ignorés (trop permissifs), départ au stage {start_stage}/{total_stages}")
    else:
        print(f"    Évaluation complète : stages 1 à {total_stages}")
    
    for n in tqdm(range(start_stage, total_stages + 1), unit="stage", colour="cyan",
                  ncols=80, desc="    Évaluation"):
        tmp_path = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(
                suffix='.xml', prefix=f'cascade_s{n}_', delete=False
            )
            tmp_path = tmp_file.name
            tmp_file.close()
            
            _build_truncated_cascade_xml(cascade_xml_path, n, tmp_path)
            
            cascade = cv2.CascadeClassifier(tmp_path)
            if cascade.empty():
                continue
            
            tp, fn = 0, 0
            for img in pos_images:
                dets = cascade.detectMultiScale(
                    img, scaleFactor=scaleFactor, minNeighbors=minNeighbors
                )
                if len(dets) > 0:
                    tp += 1
                else:
                    fn += 1
            
            fp, tn = 0, 0
            for img in neg_images:
                dets = cascade.detectMultiScale(
                    img, scaleFactor=scaleFactor, minNeighbors=minNeighbors
                )
                if len(dets) > 0:
                    fp += 1
                else:
                    tn += 1
            
            recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
            precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
            f1 = 2 * (precision / 100) * (recall / 100) / ((precision / 100) + (recall / 100)) \
                if (precision + recall) > 0 else 0
            specificity = tn / (tn + fp) * 100 if (tn + fp) > 0 else 0
            
            metrics['stage'].append(n)
            metrics['recall'].append(recall)
            metrics['precision'].append(precision)
            metrics['f1'].append(f1)
            metrics['specificity'].append(specificity)
            metrics['tp'].append(tp)
            metrics['fn'].append(fn)
            metrics['fp'].append(fp)
            metrics['tn'].append(tn)
        
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    # Tableau des résultats
    if metrics['stage']:
        print(f"\n    ┌──────────┬──────────┬──────────┬─────────┬──────────┬──────┬──────┬──────┬──────┐")
        print(f"    │ {'Stage':^8} │ {'Recall':^8} │ {'Précis.':^8} │ {'F1':^7} │ {'Spécif.':^8} │ {'TP':^4} │ {'FN':^4} │ {'FP':^4} │ {'TN':^4} │")
        print(f"    ├──────────┼──────────┼──────────┼─────────┼──────────┼──────┼──────┼──────┼──────┤")
        
        for i in range(len(metrics['stage'])):
            s = metrics['stage'][i]
            rec = metrics['recall'][i]
            prec = metrics['precision'][i]
            f1 = metrics['f1'][i]
            spec = metrics['specificity'][i]
            tp = metrics['tp'][i]
            fn = metrics['fn'][i]
            fp = metrics['fp'][i]
            tn = metrics['tn'][i]
            print(f"    │ {s:^8} │ {rec:>6.1f}%  │ {prec:>6.1f}%  │ {f1:>7.3f} │ {spec:>6.1f}%  │ {tp:>4} │ {fn:>4} │ {fp:>4} │ {tn:>4} │")
        
        print(f"    └──────────┴──────────┴──────────┴─────────┴──────────┴──────┴──────┴──────┴──────┘")
    else:
        print("    Aucun stage n'a pu être évalué.")
        return None
    
    return metrics
