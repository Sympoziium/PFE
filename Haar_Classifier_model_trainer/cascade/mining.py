# cascade/mining.py
# ------------------
# Hard Negative Mining : extraire les fausses détections du modèle courant
# et les stocker dans data/hard_negatives/ pour le prochain cycle de ré-entraînement.

import os
import re
import random
import cv2
import xml.etree.ElementTree as ET

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it


def _extract_window_size_from_cascade(cascade_path):
    """
    Extract the window size (width, height) from a cascade XML file.
    
    :param cascade_path: Path to the cascade.xml file
    :return: Tuple (width, height) or (None, None) if extraction fails
    """
    try:
        tree = ET.parse(cascade_path)
        root = tree.getroot()
        # OpenCV cascade XML: <opencv_storage><cascade><width>/<height>
        cascade_node = root.find('cascade')
        if cascade_node is None:
            cascade_node = root
        width = cascade_node.findtext('width')
        height = cascade_node.findtext('height')
        if width and height:
            return int(width), int(height)
    except Exception as e:
        print(f"  Warning: Could not extract window size from cascade: {e}")
    return None, None


def _apply_hn_decay(hn_dir, current_round, decay=0.5):
    """
    Applique une décroissance exponentielle aux HN des rounds précédents.
    
    À chaque round, on conserve `decay` fraction des HN de chaque round antérieur.
    L'effet cumulé donne : round N-1 garde 50%, N-2 garde 25%, N-3 garde 12.5%, etc.
    Cela assure que les rounds récents ont plus d'influence.
    
    :param hn_dir: Dossier des hard negatives
    :param current_round: Numéro du round actuel (on ne touche pas aux HN de ce round)
    :param decay: Fraction à conserver par round (défaut 0.5)
    :return: Nombre total de HN supprimées
    """
    if not os.path.isdir(hn_dir):
        return 0
    
    # Grouper les fichiers par round
    files_by_round = {}
    for f in os.listdir(hn_dir):
        if not os.path.isfile(os.path.join(hn_dir, f)):
            continue
        m = re.match(r'hn_r(\d+)_', f)
        if m:
            r = int(m.group(1))
            if r < current_round:
                files_by_round.setdefault(r, []).append(f)
        elif f.startswith('hn_'):
            # Ancien format sans tag de round → traiter comme round 0
            files_by_round.setdefault(0, []).append(f)
    
    total_deleted = 0
    for r in sorted(files_by_round.keys()):
        files = files_by_round[r]
        n_keep = max(1, int(len(files) * decay))
        n_delete = len(files) - n_keep
        if n_delete > 0:
            to_delete = random.sample(files, n_delete)
            for f in to_delete:
                os.remove(os.path.join(hn_dir, f))
            total_deleted += n_delete
            print(f"    Round {r} : {len(files)} → {n_keep} HN "
                  f"(conservé {decay:.0%}, -{n_delete})")
    
    return total_deleted


def hard_negative_mining(model_path, negative_images_dir, output_dir, data_dir,
                         scaleFactor=1.1, minNeighbors=4, max_crops_per_image=5,
                         keep_existing=False, min_crop_w=None, min_crop_h=None,
                         max_total_hn=None, round_num=None):
    """
    Hard Negative Mining — extrait les zones de fausses détections du modèle actuel
    et les ajoute comme images négatives supplémentaires.
    
    Processus :
    1. Charger le modèle cascade.xml existant
    2. Passer TOUTES les images négatives dans detectMultiScale
    3. Chaque fausse détection (bounding box) est croppée et sauvegardée
    4. Ces crops sont ajoutés au dossier hard_negatives/
    5. → Au prochain entraînement, le modèle apprendra à rejeter ces zones
    
    :param model_path: Chemin du fichier cascade.xml
    :param negative_images_dir: Dossier des images négatives ORIGINALES (data/negative/)
    :param output_dir: Dossier de sortie (non utilisé directement, hn vont dans data/hard_negatives/)
    :param data_dir: Dossier data/ racine
    :param scaleFactor: Facteur d'échelle pour detectMultiScale (1.1 = sensible)
    :param minNeighbors: Voisins minimum (3 = sensible, capte plus de FP)
    :param max_crops_per_image: Maximum de crops par image négative
    :param keep_existing: Si True, conserve les hard negatives existants (mode itératif).
                          Si False (défaut), supprime les anciens avant de miner.
    :param min_crop_w: Largeur minimale des crops (si None, utilise 2× fenêtre ou 40).
    :param min_crop_h: Hauteur minimale des crops (si None, utilise 2× fenêtre ou 40).
    :param max_total_hn: Nombre maximum total de HN dans le dossier (cap).
                         Si atteint, on arrête le mining. None = pas de cap.
    :return: Nombre de hard negatives générés
    """
    print("\n")
    print("Hard Negative Mining...")
    print("-----------------------------------")
    
    print("""
    Processus :
      1. Le modèle actuel analyse chaque image négative
      2. Chaque zone où le modèle détecte un objet (= fausse détection) est croppée
      3. Ces crops sont ajoutés comme nouvelles images négatives
      4. Au prochain entraînement, le modèle apprend à rejeter ces zones
    
    Paramètres utilisés :
      - scaleFactor={sf} (plus bas = plus de détections = plus de hard negatives)
      - minNeighbors={mn} (plus bas = plus sensible = capte plus de FP)
      - max_crops_per_image={mc} (limite les crops par image pour éviter le déséquilibre)
    """.format(sf=scaleFactor, mn=minNeighbors, mc=max_crops_per_image))
    
    # Étape 1 : Charger le modèle
    if model_path is None or not os.path.exists(model_path):
        print(f"  ERREUR : Modèle non trouvé à {model_path}")
        print(f"  → Générer d'abord cascade.xml (option [3] du menu)")
        return 0
    
    cascade = cv2.CascadeClassifier(model_path)
    if cascade.empty():
        print(f"  ERREUR : Impossible de charger le modèle")
        return 0
    
    # Étape 2 : Choisir les sources d'images négatives
    sources = []
    
    # Source 1 : dossier négatif original
    if os.path.isdir(negative_images_dir):
        orig_neg = [
            os.path.join(negative_images_dir, f)
            for f in os.listdir(negative_images_dir)
            if os.path.isfile(os.path.join(negative_images_dir, f))
            and not f.startswith('hn_')
        ]
        sources.extend(orig_neg)
    
    # Source 2 : négatifs de train (inclut les originaux copiés)
    train_neg_dir = os.path.join(data_dir, 'train', 'negative')
    if os.path.isdir(train_neg_dir):
        train_neg = [
            os.path.join(train_neg_dir, f)
            for f in os.listdir(train_neg_dir)
            if os.path.isfile(os.path.join(train_neg_dir, f))
            and not f.startswith('hn_')
        ]
        sources.extend(train_neg)
    
    # Dédupliquer par nom de fichier
    seen_names = set()
    unique_sources = []
    for path in sources:
        name = os.path.basename(path)
        if name not in seen_names:
            seen_names.add(name)
            unique_sources.append(path)
    
    if not unique_sources:
        print("  ERREUR : Aucune image négative trouvée")
        return 0
    
    print(f"  {len(unique_sources)} images négatives à analyser")
    
    # Étape 3 : Détecter les fausses détections et cropper
    hn_output = os.path.join(data_dir, 'hard_negatives')
    os.makedirs(hn_output, exist_ok=True)
    
    # Gestion des anciens hard negatives
    old_hn = [f for f in os.listdir(hn_output) if os.path.isfile(os.path.join(hn_output, f))]
    if old_hn and not keep_existing:
        print(f"  Suppression de {len(old_hn)} anciens hard negatives (mode non-itératif)...")
        for f in old_hn:
            os.remove(os.path.join(hn_output, f))
    elif old_hn and keep_existing:
        print(f"  Conservation de {len(old_hn)} hard negatives existants (mode itératif).")
    
    nb_crops = 0
    nb_images_with_fp = 0
    nb_too_small = 0
    nb_cap_reached = False

    # Taille minimale des crops : 2× la fenêtre de détection pour que
    # opencv_traincascade puisse extraire au moins un sliding window.
    _min_w = min_crop_w if min_crop_w else 40
    _min_h = min_crop_h if min_crop_h else 40
    print(f"  Taille minimale des crops : {_min_w}×{_min_h} px")
    if max_total_hn:
        n_existing = len([f for f in os.listdir(hn_output)
                         if os.path.isfile(os.path.join(hn_output, f))])
        budget = max(0, max_total_hn - n_existing)
        print(f"  Budget HN ce round : {budget} (cap total={max_total_hn}, existants={n_existing})")
    else:
        budget = float('inf')
    
    print("  Analyse des images négatives...")
    for img_path in tqdm(unique_sources, unit="img", colour="yellow", ncols=80):
        if nb_crops >= budget:
            nb_cap_reached = True
            break

        img = cv2.imread(img_path)
        if img is None:
            continue
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        detections = cascade.detectMultiScale(
            gray,
            scaleFactor=scaleFactor,
            minNeighbors=minNeighbors,
            minSize=(_min_w, _min_h)
        )
        
        if len(detections) == 0:
            continue
        
        nb_images_with_fp += 1
        crops_this_image = 0
        
        for (x, y, w, h) in detections:
            if crops_this_image >= max_crops_per_image:
                break
            if nb_crops >= budget:
                break
            
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(img.shape[1], x + w)
            y2 = min(img.shape[0], y + h)
            
            crop_w = x2 - x1
            crop_h = y2 - y1
            
            if crop_w < _min_w or crop_h < _min_h:
                nb_too_small += 1
                continue
            
            crop = img[y1:y2, x1:x2]
            
            src_name = os.path.splitext(os.path.basename(img_path))[0]
            _round_tag = f"r{round_num}_" if round_num else ""
            crop_filename = f"hn_{_round_tag}{src_name}_{x}_{y}_{w}_{h}.jpg"
            crop_path = os.path.join(hn_output, crop_filename)
            cv2.imwrite(crop_path, crop)
            
            nb_crops += 1
            crops_this_image += 1
    
    # --- Rapport ---
    n_total_hn = len([f for f in os.listdir(hn_output) if os.path.isfile(os.path.join(hn_output, f))])
    
    print(f"\n  Résumé du Hard Negative Mining :")
    print(f"    Images analysées         : {len(unique_sources)}")
    print(f"    Images avec faux positifs: {nb_images_with_fp} ({nb_images_with_fp/len(unique_sources)*100:.1f}%)")
    print(f"    Hard negatives générés   : {nb_crops}")
    if nb_too_small > 0:
        print(f"    Crops trop petits rejetés: {nb_too_small} (< {_min_w}×{_min_h})")
    if nb_cap_reached:
        print(f"    ⚠ Cap atteint             : {max_total_hn} HN max (arrêt anticipé du mining)")
    print(f"    Total hard negatives     : {n_total_hn}")
    print(f"    Dossier de sortie        : {hn_output}")
    
    if nb_crops == 0:
        print(f"\n  ℹ Aucune fausse détection trouvée avec ces paramètres.")
        print(f"    → Essayer avec scaleFactor plus bas (ex: 1.05) ou minNeighbors=1")
    else:
        print(f"\n  ✓ {nb_crops} hard negatives sauvegardés dans data/hard_negatives/")
        print(f"    → Relancez le pipeline complet (option [1]) pour ré-entraîner")
        print(f"    → Ils seront ajoutés au train set automatiquement (pas au test)")
        print(f"    → Le dossier négatif original n'est PAS modifié")
    
    print("-----------------------------------")
    print("\n")
    return nb_crops


def iterative_hnm(model_path, negative_images_dir, data_dir, output_dir, sample_width, sample_height,
                  num_rounds=3, scaleFactor=1.10, minNeighbors=3, config=None):
    """
    Hard Negative Mining itératif — Automatise le cycle :
      mine → retrain → mine → retrain → ...
    
    Stratégie de gestion des HN :
      - Départ propre : suppression de toutes les anciennes HN.
      - HN tagués par round (hn_r1_..., hn_r2_...) pour traçabilité.
      - Décroissance exponentielle (50% par round) : les rounds récents
        ont plus d'influence que les anciens.
      - Augmentation adaptative des positives pour exploiter plus de négatifs.
      - Taille minimale des crops : 2× la fenêtre de détection.
      - HN intercalés uniformément dans bg.txt (pas en premier).
    
    Arrêt anticipé si F1 régresse sur 3 rounds consécutifs.
    
    :param model_path: Chemin du modèle cascade.xml initial
    :param negative_images_dir: Dossier des images négatives originales
    :param data_dir: Dossier data/ racine
    :param output_dir: Dossier cascade/ de sortie
    :param num_rounds: Nombre de rounds de mining (default 3)
    :param scaleFactor: SF pour la détection HNM
    :param minNeighbors: MN pour la détection HNM
    :param config: dict de configuration d'entraînement (feature, stages, min_hit_rate).
                   Si None, utilise LBP/14 stages par défaut.
    :return: Chemin du modèle final, ou None si échec
    """
    from cascade.config import WINDOW_SIZE
    from cascade.data_prep import prepare_data
    from cascade.training import check_cascade_resume, train_cascade, create_samples

    print(f"\n{'='*60}")
    print(f"  Hard Negative Mining Itératif — {num_rounds} rounds")
    print(f"{'='*60}")
    print(f"  Ce processus va automatiquement :")
    print(f"    1. Supprimer les anciennes HN (départ propre)")
    print(f"    2. Extraire les fausses détections (hard negatives)")
    print(f"    3. Décroissance des HN anciennes (50% par round)")
    print(f"    4. Adapter l'augmentation pour numPos↑ → numNeg↑")
    print(f"    5. Ré-entraîner avec HN intercalés dans bg.txt")
    print(f"    6. Arrêt anticipé si le F1 régresse")
    print(f"    ... répété jusqu'à {num_rounds} fois\n")

    current_model = model_path
    # Utiliser les dimensions de fenêtre passées en paramètre (config utilisateur)
    # plutôt que celles du modèle XML existant (qui peut avoir une taille différente)
    print(f"  Fenêtre d'entraînement : {sample_width}×{sample_height} (depuis config)")

    positive_images_dir = os.path.join(data_dir, 'positive')

    # ── Nettoyage des anciennes HN (départ propre) ──
    hn_dir = os.path.join(data_dir, 'hard_negatives')
    if os.path.isdir(hn_dir):
        old_hn = [f for f in os.listdir(hn_dir)
                  if os.path.isfile(os.path.join(hn_dir, f))]
        if old_hn:
            print(f"  Suppression de {len(old_hn)} anciennes HN (départ propre)...")
            for f in old_hn:
                os.remove(os.path.join(hn_dir, f))
    os.makedirs(hn_dir, exist_ok=True)

    if config is None:
        config = {'name': 'HNM-Itératif', 'feature': 'LBP',
                  'stages': 14, 'min_hit_rate': 0.995}

    print(f"  Config entraînement : {config.get('feature', 'LBP')}, "
          f"{config.get('stages', 14)} stages, "
          f"minHitRate={config.get('min_hit_rate', 0.995)}")

    # ── Comptage des images originales (AVANT tout HN) ──
    n_orig_pos = len([f for f in os.listdir(positive_images_dir)
                      if os.path.isfile(os.path.join(positive_images_dir, f))])
    n_orig_neg = len([f for f in os.listdir(negative_images_dir)
                      if os.path.isfile(os.path.join(negative_images_dir, f))
                      and not f.startswith('hn_')])
    n_orig_neg_train = int(n_orig_neg * 0.85)  # approx du split ratio
    n_orig_pos_train = int(n_orig_pos * 0.85)

    # Cap HN : maximum 50% du pool négatif final.
    # Si pool_final = orig_neg_train + HN, on veut HN ≤ pool_final * 0.50
    # → HN ≤ orig_neg_train  (car 50% de (orig + HN) = HN → HN = orig)
    max_hn_total = n_orig_neg_train
    print(f"\n  Données originales : {n_orig_pos} pos, {n_orig_neg} neg")
    print(f"  Cap HN total : {max_hn_total} (≤ négatifs originaux train pour garder ratio 50%)")

    # Taille minimale des crops : 2× la fenêtre pour sliding window viable
    min_crop_w = sample_width * 2
    min_crop_h = sample_height * 2
    print(f"  Taille min crops HN : {min_crop_w}×{min_crop_h} (2× fenêtre {sample_width}×{sample_height})")

    results = []
    total_hn_accumulated = 0
    BASE_AUGMENT = 5  # augmentation de base

    for round_num in range(1, num_rounds + 1):
        print(f"\n  {'─'*50}")
        print(f"  Round {round_num}/{num_rounds}")
        print(f"  {'─'*50}")

        # ── Étape 0 : Décroissance des HN des rounds précédents ──
        if round_num > 1:
            n_decayed = _apply_hn_decay(hn_dir, round_num, decay=0.5)
            if n_decayed > 0:
                print(f"  Décroissance appliquée : -{n_decayed} HN anciennes éliminées")

        # ── Étape 1 : Mine les hard negatives ──
        nb_hn = hard_negative_mining(
            model_path=current_model,
            negative_images_dir=negative_images_dir,
            output_dir=negative_images_dir,
            data_dir=data_dir,
            scaleFactor=scaleFactor,
            minNeighbors=minNeighbors,
            keep_existing=True,
            min_crop_w=min_crop_w,
            min_crop_h=min_crop_h,
            max_total_hn=max_hn_total,
            round_num=round_num
        )
        total_hn_accumulated += nb_hn

        if nb_hn == 0:
            print(f"\n  ℹ Round {round_num} : Aucun NOUVEAU hard negative trouvé.")
            print(f"    → Le modèle actuel ne produit plus de FP avec ces paramètres.")
            print(f"    → Arrêt anticipé du HNM itératif.")
            break

        # Compter le total accumulé dans le dossier
        hn_dir = os.path.join(data_dir, 'hard_negatives')
        total_in_dir = len([f for f in os.listdir(hn_dir)
                            if os.path.isfile(os.path.join(hn_dir, f))]) if os.path.isdir(hn_dir) else 0

        # ── Étape 1b : Calcul de l'augmentation adaptative ──
        # Objectif : élever numPos (et donc numNeg) pour exploiter les HN.
        #
        # Formule :
        #   total_neg_attendu = n_orig_neg_train + total_in_dir
        #   numNeg_voulu = total_neg_attendu × 0.80  (utiliser 80% du pool)
        #   numPos_voulu = numNeg_voulu / 3
        #   annotations_voulues = numPos_voulu / 0.80
        #   num_augmented = (annotations_voulues / n_orig_pos_train) - 1
        #
        # Cap à 12× pour limiter l'overfitting (5× base, max 12×).
        total_neg_expected = n_orig_neg_train + total_in_dir
        numNeg_target = int(total_neg_expected * 0.80)
        numPos_target = numNeg_target // 3
        annotations_target = int(numPos_target / 0.80)
        if n_orig_pos_train > 0:
            adaptive_augment = max(BASE_AUGMENT,
                                   min(12, (annotations_target // n_orig_pos_train)))
        else:
            adaptive_augment = BASE_AUGMENT

        actual_annotations = n_orig_pos_train * (1 + adaptive_augment)
        actual_numPos = int(actual_annotations * 0.80)
        actual_numNeg = min(total_neg_expected, actual_numPos * 3)
        neg_usage_pct = actual_numNeg / total_neg_expected * 100 if total_neg_expected > 0 else 0

        print(f"\n  HN ce round : +{nb_hn} | Total HN accumulé : {total_in_dir}")
        print(f"  Augmentation adaptative : {adaptive_augment}× (base={BASE_AUGMENT}×)")
        print(f"    → {n_orig_pos_train} orig pos × (1+{adaptive_augment}) = ~{actual_annotations} annotations")
        print(f"    → numPos≈{actual_numPos}, numNeg≈{actual_numNeg}/{total_neg_expected} ({neg_usage_pct:.0f}% du pool)")
        print(f"    → Ratio HN/pool : {total_in_dir}/{total_neg_expected} = {total_in_dir/total_neg_expected*100:.0f}%")

        # ── Étape 2 : Re-préparer les données avec augmentation adaptative ──
        print(f"\n  Re-préparation des données (round {round_num})...")
        train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, \
            nb_annotations, nb_negatives, annotations_file, bg_file = \
            prepare_data(positive_images_dir, negative_images_dir, data_dir,
                         num_augmented=adaptive_augment)

        # ── Étape 3 : Recréer le .vec ──
        from cascade.training import create_samples
        create_samples(
            annotations_file=annotations_file,
            vec_file=os.path.join(data_dir, 'samples.vec'),
            num_samples=nb_annotations,
            width=sample_width, height=sample_height
        )

        # ── Étape 4 : Ré-entraîner ──
        print(f"\n  Ré-entraînement (round {round_num})...")
        cascade_file = os.path.join(output_dir, 'cascade.xml')
        for f in os.listdir(output_dir):
            fpath = os.path.join(output_dir, f)
            if os.path.isfile(fpath):
                os.remove(fpath)

        round_config = dict(config)
        round_config['name'] = f"HNM-Round-{round_num} ({config.get('feature', 'LBP')})"

        new_model = train_cascade(
            nb_annotations, nb_negatives,
            sample_width, sample_height,
            data_dir, output_dir, config=round_config
        )

        if new_model is None:
            print(f"\n  ✗ Round {round_num} : Entraînement échoué.")
            break

        # ── Étape 5 : Évaluer ──
        from cascade.evaluation import evaluate_model
        eval_results, best_idx = evaluate_model(
            new_model, test_pos_dir, test_neg_dir)

        best = eval_results[best_idx]
        results.append({
            'round': round_num,
            'hn_added': nb_hn,
            'hn_total': total_in_dir,
            'augment': adaptive_augment,
            'recall': best['recall'],
            'precision': best['precision'],
            'f1': best['f1'],
            'model': new_model
        })

        current_model = new_model

        print(f"\n  Round {round_num} terminé : "
              f"F1={best['f1']:.3f}  Recall={best['recall']:.1f}%  "
              f"Précision={best['precision']:.1f}%  "
              f"(+{nb_hn} HN, {total_in_dir} total, aug={adaptive_augment}×)")

        # ── Arrêt anticipé si F1 régresse sur 3 rounds consécutifs ──
        if len(results) >= 3:
            last3 = [r['f1'] for r in results[-3:]]
            if last3[2] < last3[1] < last3[0]:
                print(f"\n  ⚠ F1 en régression sur 3 rounds : "
                      f"{last3[0]:.3f} → {last3[1]:.3f} → {last3[2]:.3f}")
                print(f"    → Arrêt anticipé pour éviter la dégradation.")
                print(f"    → Le meilleur modèle est probablement celui du round "
                      f"{results[-3]['round']} (F1={last3[0]:.3f}).")
                break
        elif len(results) >= 2:
            if results[-1]['f1'] < results[-2]['f1'] * 0.90:
                print(f"\n  ⚠ F1 en chute significative : "
                      f"{results[-2]['f1']:.3f} → {results[-1]['f1']:.3f} "
                      f"(-{(1 - results[-1]['f1']/results[-2]['f1'])*100:.1f}%)")
                print(f"    → Attention : le prochain round sera le dernier si F1 continue de baisser.")

    # ══════════════════════════════════════════════════════════
    # Résumé final
    # ══════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"  Résumé HNM Itératif — {len(results)} rounds complétés")
    print(f"{'='*60}")

    if results:
        print(f"\n  {'Round':<7} {'HN +':<8} {'HN tot':<8} {'Aug':<5} {'Recall':<9} {'Préc.':<9} {'F1':<8}")
        print(f"  {'─'*56}")
        for r in results:
            print(f"  {r['round']:<7} +{r['hn_added']:<7} "
                  f"{r['hn_total']:<8} {r['augment']}×{'':<3} "
                  f"{r['recall']:<8.1f}% {r['precision']:<8.1f}% {r['f1']:<8.3f}")

        best_round = max(results, key=lambda r: r['f1'])
        print(f"\n  Meilleur round : #{best_round['round']} (F1={best_round['f1']:.3f})")
        if best_round['model'] != current_model:
            print(f"  ⚠ Le modèle final n'est PAS le meilleur. Considérez utiliser")
            print(f"    l'option [7] pour regénérer cascade.xml au bon stage.")
        print(f"  Modèle final   : {current_model}")
    else:
        print(f"\n  Aucun round complété. Modèle inchangé.")

    print(f"{'='*60}\n")
    return current_model
