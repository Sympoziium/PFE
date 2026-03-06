# cascade/evaluation.py
# ---------------------
# Évaluation du modèle : test sur les ensembles pos/neg, rapport détaillé,
# diagnostic contextuel et génération de la plaque du modèle.

import os
import shutil
import xml.etree.ElementTree as ET
import cv2
from datetime import datetime

from .config import DETECTION_PRESETS


def test_model(model, test_image_dir, positive=True, scaleFactor=1.1, minNeighbors=5):
    """
    Test le modèle sur un ensemble d'images et retourne des statistiques détaillées.
    
    :param model: Objet CascadeClassifier chargé
    :param test_image_dir: Chemin du dossier contenant les images de test
    :param positive: True = images positives (détection attendue), False = négatives
    :param scaleFactor: Facteur d'échelle pour detectMultiScale
    :param minNeighbors: Nombre minimum de voisins pour detectMultiScale
    :return: dict avec tp, fn, fp, tn, total_detections, multi_detect_count, iou_sum, iou_count
    """
    test_images = [f for f in os.listdir(test_image_dir) if os.path.isfile(os.path.join(test_image_dir, f))]
    
    stats = {
        'tp': 0, 'fn': 0, 'fp': 0, 'tn': 0,
        'total_detections': 0,
        'multi_detect_count': 0,
        'iou_sum': 0.0,
        'iou_count': 0
    }

    for img_file in test_images:
        img_path = os.path.join(test_image_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            print(f"  ATTENTION : image illisible ignorée : {img_file}")
            continue
        
        detections = model.detectMultiScale(img, scaleFactor=scaleFactor, minNeighbors=minNeighbors)
        n_det = len(detections)
        stats['total_detections'] += n_det
        
        if positive:
            if n_det == 0:
                stats['fn'] += 1
            else:
                stats['tp'] += 1
                if n_det > 1:
                    stats['multi_detect_count'] += 1
                h_img, w_img = img.shape[:2]
                best_iou = 0.0
                for (x, y, w, h) in detections:
                    inter_x1, inter_y1 = max(0, x), max(0, y)
                    inter_x2 = min(w_img, x + w)
                    inter_y2 = min(h_img, y + h)
                    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
                    union_area = w_img * h_img + w * h - inter_area
                    iou = inter_area / union_area if union_area > 0 else 0
                    best_iou = max(best_iou, iou)
                stats['iou_sum'] += best_iou
                stats['iou_count'] += 1
        else:
            if n_det == 0:
                stats['tn'] += 1
            else:
                stats['fp'] += 1

    return stats


def evaluate_model(model_path, test_pos_dir, test_neg_dir):
    """
    Évalue les performances du modèle entraîné sur l'ensemble de test
    en utilisant les 3 préconfigurations DETECTION_PRESETS.
    
    :param model_path: Chemin du fichier cascade.xml
    :param test_pos_dir: Dossier contenant les images positives de test
    :param test_neg_dir: Dossier contenant les images négatives de test
    :return: (all_results, best_idx)
    """
    print("\n")
    print(f"Évaluation du modèle entraîné...")
    print("-----------------------------------")

    if model_path is None:
        print(f"  ERREUR : Aucun modèle à évaluer (chemin None).")
        print(f"  L'entraînement n'a probablement pas produit de cascade.xml.")
        print(f"  Utilisez l'option [4] du menu pour générer cascade.xml à partir des stages existants.")
        return [], 0

    if not os.path.exists(model_path):
        print(f"  ERREUR : Modèle non trouvé à {model_path}")
        return [], 0

    cascade = cv2.CascadeClassifier(model_path)
    if cascade.empty():
        print(f"  ERREUR : Impossible de charger le modèle à {model_path}")
        return [], 0

    presets = list(DETECTION_PRESETS.values())
    nb_test_pos = len([f for f in os.listdir(test_pos_dir) if os.path.isfile(os.path.join(test_pos_dir, f))])
    nb_test_neg = len([f for f in os.listdir(test_neg_dir) if os.path.isfile(os.path.join(test_neg_dir, f))])

    all_results = []
    best_f1 = -1
    best_idx = 0

    print(f"Évaluation avec {len(presets)} préconfigurations (Sensible / Équilibré / Strict)...")
    for i, preset in enumerate(presets):
        sf = preset['sf']
        mn = preset['mn']
        print(f"  [{i+1}/{len(presets)}] {preset['label']} : SF={sf}, MN={mn} — {preset['desc']}...")
        pos_stats = test_model(cascade, test_pos_dir, positive=True, scaleFactor=sf, minNeighbors=mn)
        neg_stats = test_model(cascade, test_neg_dir, positive=False, scaleFactor=sf, minNeighbors=mn)

        tp = pos_stats['tp']
        fn = pos_stats['fn']
        fp = neg_stats['fp']
        tn = neg_stats['tn']

        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        f1 = 2 * (precision / 100) * (recall / 100) / ((precision / 100) + (recall / 100)) if (precision + recall) > 0 else 0
        specificity = tn / (tn + fp) * 100 if (tn + fp) > 0 else 0
        fp_per_img = fp / nb_test_neg if nb_test_neg > 0 else 0
        miss_rate = 100 - recall
        avg_iou = pos_stats['iou_sum'] / pos_stats['iou_count'] if pos_stats['iou_count'] > 0 else 0
        multi_pct = pos_stats['multi_detect_count'] / tp * 100 if tp > 0 else 0
        avg_det_pos = pos_stats['total_detections'] / nb_test_pos if nb_test_pos > 0 else 0
        avg_det_neg = neg_stats['total_detections'] / nb_test_neg if nb_test_neg > 0 else 0

        result = {
            'sf': sf, 'mn': mn,
            'preset_label': preset['label'], 'preset_desc': preset['desc'],
            'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
            'recall': recall, 'precision': precision, 'f1': f1,
            'specificity': specificity, 'fp_per_img': fp_per_img,
            'miss_rate': miss_rate, 'avg_iou': avg_iou,
            'multi_pct': multi_pct, 'avg_det_pos': avg_det_pos,
            'avg_det_neg': avg_det_neg
        }
        all_results.append(result)

        if f1 > best_f1:
            best_f1 = f1
            best_idx = len(all_results) - 1

    best = all_results[best_idx]

    # Tableau comparatif
    print(f"\n  Comparaison des {len(presets)} préconfigurations :")
    print(f"  {'Profil':<12} {'SF':>5} {'MN':>4}  {'Recall':>8} {'Préc.':>8} {'F1':>7} {'Spéc.':>8} {'FP/img':>8} {'IoU':>6}")
    print(f"  {'─'*12} {'─'*5} {'─'*4}  {'─'*8} {'─'*8} {'─'*7} {'─'*8} {'─'*8} {'─'*6}")
    for i, r in enumerate(all_results):
        marker = "►" if i == best_idx else " "
        print(f"  {marker}{r['preset_label']:<11} {r['sf']:>5} {r['mn']:>4}  {r['recall']:>7.1f}% {r['precision']:>7.1f}% {r['f1']:>7.3f} {r['specificity']:>7.1f}% {r['fp_per_img']:>8.3f} {r['avg_iou']:>5.2f}")
    print(f"  {'─'*76}")
    print(f"  ► = Meilleure config par F1-Score")

    # Rapport détaillé pour la meilleure configuration
    r = best
    print(f"\n  Rapport détaillé ({r['preset_label']} : SF={r['sf']}, MN={r['mn']}) :")
    print(f"  ┌────────────────────────────────┬──────────────┐")
    print(f"  │ {'Métrique':<30} │ {'Valeur':>12} │")
    print(f"  ├────────────────────────────────┼──────────────┤")
    print(f"  │ {'Recall (Taux détection)':<30} │ {r['recall']:>11.1f}% │")
    print(f"  │ {'Précision':<30} │ {r['precision']:>11.1f}% │")
    print(f"  │ {'F1-Score':<30} │ {r['f1']:>12.3f} │")
    print(f"  │ {'Spécificité (TN rate)':<30} │ {r['specificity']:>11.1f}% │")
    print(f"  │ {'Miss rate':<30} │ {r['miss_rate']:>11.1f}% │")
    print(f"  │ {'FP / image négative':<30} │ {r['fp_per_img']:>12.3f} │")
    print(f"  │ {'IoU moyen':<30} │ {r['avg_iou']:>12.2f} │")
    print(f"  │ {'Multi-détections (% des TP)':<30} │ {r['multi_pct']:>11.1f}% │")
    print(f"  │ {'Détections moy. / positive':<30} │ {r['avg_det_pos']:>12.2f} │")
    print(f"  │ {'Détections moy. / négative':<30} │ {r['avg_det_neg']:>12.2f} │")
    print(f"  ├────────────────────────────────┴──────────────┤")
    counts_str = f"TP={r['tp']}  FN={r['fn']}  FP={r['fp']}  TN={r['tn']}"
    print(f"  │ {counts_str:<45} │")
    print(f"  └───────────────────────────────────────────────┘")

    # Diagnostic contextuel
    print(f"\n  Diagnostic :")
    diagnostics = []

    if r['recall'] < 55:
        diagnostics.append((
            f"⚠ Recall faible ({r['recall']:.1f}%) — ~{r['miss_rate']:.0f}% des objets manqués.",
            ["Augmenter le nombre d'images positives originales",
             "Diversifier les augmentations (angles, éclairages, distances)",
             "Réduire scaleFactor pour scanner plus d'échelles" + (f" (actuellement {r['sf']})" if r['sf'] > 1.1 else "")]
        ))

    if r['precision'] < 50:
        diagnostics.append((
            f"⚠ Précision faible ({r['precision']:.1f}%) — beaucoup de fausses détections.",
            ["Augmenter minNeighbors (filtre les détections isolées)",
             "Ajouter plus d'images négatives variées à l'entraînement",
             "Passer au profil HAAR pour de meilleures features (si LBP actuel)"]
        ))

    if 0 < r['avg_iou'] < 0.5:
        diagnostics.append((
            f"⚠ IoU faible ({r['avg_iou']:.2f}) — localisation imprécise.",
            ["Vérifier que le ratio w:h de la fenêtre correspond à la forme de l'objet",
             "Les images positives sont-elles bien cadrées (crop serré) sur l'objet ?"]
        ))

    if r['multi_pct'] > 30:
        diagnostics.append((
            f"ℹ Multi-détections fréquentes ({r['multi_pct']:.0f}% des TP) — normal pour Haar/LBP.",
            ["Réduire le FA a 0.45 aide beaucoup, mais le meilleur moyen ces de faire du hard negative mining option [8] du menu"]
        ))

    if r['avg_det_neg'] > 0.1:
        diagnostics.append((
            f"⚠ Détections parasites sur négatifs ({r['avg_det_neg']:.2f} détections/img).",
            ["Hard negative mining [8] : récolter les FP, les ajouter comme négatifs, ré-entraîner",
             "Augmenter le nombre de stages ou réduire le FA (False Alarm Rate) pour un entraînement plus strict"]
        ))

    if r['f1'] >= 0.7:
        diagnostics.append((f"✓ F1-Score bon ({r['f1']:.3f}) — modèle exploitable.", []))
    elif r['f1'] >= 0.5:
        diagnostics.append((f"~ F1-Score moyen ({r['f1']:.3f}) — améliorations recommandées avant déploiement.", []))
    else:
        diagnostics.append((
            f"✗ F1-Score faible ({r['f1']:.3f}) — le modèle nécessite des améliorations significatives.",
            ["Entraîner avec le profil Équilibré ou Précis (HAAR, plus de stages)",
             "Augmenter et diversifier le dataset positif"]
        ))

    for diag_title, suggestions in diagnostics:
        print(f"    {diag_title}")
        for s in suggestions:
            print(f"      → {s}")

    # Recommandation d'utilisation
    print(f"\n  Recommandation d'utilisation :")
    print(f"    Meilleur profil par F1 : {best['preset_label']} (SF={best['sf']}, MN={best['mn']})")
    print(f"    F1={best['f1']:.3f}, Recall={best['recall']:.1f}%, Précision={best['precision']:.1f}%")

    return all_results, best_idx


def generate_model_plaque(model_path, config, sample_width, sample_height,
                           eval_results, best_idx, data_dir, base_dir,
                           state_checker=None):
    """
    Génère un fichier récapitulatif (plaque) du modèle + copie du cascade.xml
    dans le dossier Incubator/.
    
    :param state_checker: fonction check_data_state (injectée depuis le menu)
    """
    print("\n")
    print("Génération de la plaque du modèle...")
    print("-----------------------------------")
    
    incubator_dir = os.path.join(base_dir, 'Incubator')
    os.makedirs(incubator_dir, exist_ok=True)
    
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    feature = config.get('feature', 'LBP')
    model_name = f"{feature}_{date_str}"
    
    # Copier cascade.xml dans Incubator/
    dest_xml = os.path.join(incubator_dir, f"{model_name}.xml")
    if os.path.exists(model_path):
        shutil.copy2(model_path, dest_xml)
        print(f"  cascade.xml copié → {dest_xml}")
    
    # Lire l'état des données pour le résumé
    state = state_checker(data_dir) if state_checker else {}
    
    # Lire les infos du cascade.xml
    cascade_info = ""
    if os.path.exists(model_path):
        try:
            tree = ET.parse(model_path)
            root = tree.getroot()
            cascade_el = root.find('cascade')
            actual_stages = int(cascade_el.find('stageNum').text)
            actual_feature = cascade_el.find('featureType').text
            actual_w = int(cascade_el.find('width').text)
            actual_h = int(cascade_el.find('height').text)
            
            stages_el = cascade_el.find('stages')
            total_features = 0
            for stage in stages_el.findall('_'):
                weak_count_el = stage.find('maxWeakCount')
                if weak_count_el is not None:
                    total_features += int(weak_count_el.text)
            
            cascade_info = (f"  - Stages réels : {actual_stages}\n"
                          f"  - Feature type : {actual_feature}\n"
                          f"  - Fenêtre : {actual_w}×{actual_h}\n"
                          f"  - Features totales : {total_features}")
        except Exception:
            cascade_info = "  (Impossible de lire les détails du cascade.xml)"
    
    # Construire le contenu de la plaque
    lines = []
    lines.append(f"# Plaque du modèle — {model_name}")
    lines.append(f"")
    lines.append(f"**Date** : {date_str} à {time_str}")
    lines.append(f"**Profil d'entraînement** : {config.get('name', 'N/A')}")
    lines.append(f"")
    lines.append(f"## Configuration d'entraînement")
    lines.append(f"")
    lines.append(f"| Paramètre | Valeur |")
    lines.append(f"|---|---|")
    lines.append(f"| Feature type | {feature} |")
    lines.append(f"| Stages demandés | {config.get('stages', 'N/A')} |")
    lines.append(f"| minHitRate | {config.get('min_hit_rate', 'N/A')} |")
    lines.append(f"| maxFalseAlarmRate | {config.get('max_false_alarm_rate', 'N/A')} |")
    lines.append(f"| Fenêtre | {sample_width}×{sample_height} |")
    lines.append(f"")
    
    if cascade_info:
        lines.append(f"### Modèle produit")
        lines.append(f"```")
        lines.append(cascade_info)
        lines.append(f"```")
        lines.append(f"")
    
    lines.append(f"## Dataset")
    lines.append(f"")
    lines.append(f"| Ensemble | Positives | Négatives |")
    lines.append(f"|---|---|---|")
    lines.append(f"| Originales | {state.get('n_orig_pos', '?')} | {state.get('n_orig_neg', '?')} |")
    lines.append(f"| Train | {state.get('n_train_pos', '?')} | {state.get('n_train_neg', '?')} |")
    lines.append(f"| Test | {state.get('n_test_pos', '?')} | {state.get('n_test_neg', '?')} |")
    if state.get('n_hard_negatives', 0) > 0:
        lines.append(f"| Hard negatives | — | {state['n_hard_negatives']} |")
    lines.append(f"")
    
    lines.append(f"## Performances d'évaluation")
    lines.append(f"")
    
    if eval_results:
        lines.append(f"| Profil | SF | MN | Recall | Précision | F1 | Spécificité | FP/img |")
        lines.append(f"|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(eval_results):
            marker = " **►**" if i == best_idx else ""
            lines.append(
                f"| {r.get('preset_label', '?')}{marker} | {r['sf']} | {r['mn']} | "
                f"{r['recall']:.1f}% | {r['precision']:.1f}% | {r['f1']:.3f} | "
                f"{r['specificity']:.1f}% | {r['fp_per_img']:.3f} |"
            )
        lines.append(f"")
        lines.append(f"**► = Meilleur F1-Score**")
        lines.append(f"")
        
        best = eval_results[best_idx]
        lines.append(f"### Détail du meilleur profil ({best.get('preset_label', '?')})")
        lines.append(f"")
        lines.append(f"| Métrique | Valeur |")
        lines.append(f"|---|---|")
        lines.append(f"| Recall | {best['recall']:.1f}% |")
        lines.append(f"| Précision | {best['precision']:.1f}% |")
        lines.append(f"| F1-Score | {best['f1']:.3f} |")
        lines.append(f"| Spécificité | {best['specificity']:.1f}% |")
        lines.append(f"| IoU moyen | {best['avg_iou']:.2f} |")
        lines.append(f"| TP={best['tp']} | FN={best['fn']} | FP={best['fp']} | TN={best['tn']} |")
        lines.append(f"")
    else:
        lines.append(f"*Aucun résultat d'évaluation disponible.*")
        lines.append(f"")
    
    lines.append(f"## Paramètres d'utilisation recommandés")
    lines.append(f"")
    if eval_results:
        best = eval_results[best_idx]
        lines.append(f"### Qualité maximale (PC)")
        lines.append(f"```python")
        lines.append(f"cascade.detectMultiScale(gray, scaleFactor={best['sf']}, minNeighbors={best['mn']})")
        lines.append(f"```")
        lines.append(f"")
        
        strict = eval_results[-1]
        lines.append(f"### Raspberry Pi / embarqué")
        lines.append(f"```python")
        lines.append(f"cascade.detectMultiScale(gray, scaleFactor={strict['sf']}, minNeighbors={strict['mn']})")
        lines.append(f"```")
        lines.append(f"Note : LBP est ~3-5× plus rapide que HAAR à l'exécution.")
    
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Généré automatiquement par train_cascade.py*")
    
    plaque_path = os.path.join(incubator_dir, f"{model_name}_plaque.md")
    with open(plaque_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print("  Plaque générée")
    print(f"  Modèle copié   → {dest_xml}")
    print(f"  Dossier : {incubator_dir}")
    print("-----------------------------------\n")
