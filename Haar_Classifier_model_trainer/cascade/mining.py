# cascade/mining.py
# ------------------
# Hard Negative Mining : extraire les fausses détections du modèle courant
# et les stocker dans data/hard_negatives/ pour le prochain cycle de ré-entraînement.

import os
import cv2

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it


def hard_negative_mining(model_path, negative_images_dir, output_dir, data_dir,
                         scaleFactor=1.1, minNeighbors=4, max_crops_per_image=5):
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
    
    # Supprimer les anciens hard negatives (on regénère à chaque cycle)
    old_hn = [f for f in os.listdir(hn_output) if os.path.isfile(os.path.join(hn_output, f))]
    if old_hn:
        print(f"  Suppression de {len(old_hn)} anciens hard negatives...")
        for f in old_hn:
            os.remove(os.path.join(hn_output, f))
    
    nb_crops = 0
    nb_images_with_fp = 0
    min_crop_size = 20
    
    print("  Analyse des images négatives...")
    for img_path in tqdm(unique_sources, unit="img", colour="yellow", ncols=80):
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        detections = cascade.detectMultiScale(
            gray,
            scaleFactor=scaleFactor,
            minNeighbors=minNeighbors,
            minSize=(min_crop_size, min_crop_size)
        )
        
        if len(detections) == 0:
            continue
        
        nb_images_with_fp += 1
        crops_this_image = 0
        
        for (x, y, w, h) in detections:
            if crops_this_image >= max_crops_per_image:
                break
            
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(img.shape[1], x + w)
            y2 = min(img.shape[0], y + h)
            
            crop_w = x2 - x1
            crop_h = y2 - y1
            
            if crop_w < min_crop_size or crop_h < min_crop_size:
                continue
            
            crop = img[y1:y2, x1:x2]
            
            src_name = os.path.splitext(os.path.basename(img_path))[0]
            crop_filename = f"hn_{src_name}_{x}_{y}_{w}_{h}.jpg"
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


def iterative_hnm(model_path, negative_images_dir, data_dir, output_dir,
                  num_rounds=3, scaleFactor=1.10, minNeighbors=3):
    """
    Hard Negative Mining itératif — Automatise le cycle :
      mine → retrain → mine → retrain → ...
    
    À chaque round :
      1. Mine les HN avec le modèle courant
      2. Intègre les HN au train set
      3. Re-prépare les données (annotations + bg.txt + .vec)
      4. Ré-entraîne le modèle
      5. Évalue le nouveau modèle
    
    :param model_path: Chemin du modèle cascade.xml initial
    :param negative_images_dir: Dossier des images négatives originales
    :param data_dir: Dossier data/ racine
    :param output_dir: Dossier cascade/ de sortie
    :param num_rounds: Nombre de rounds de mining (default 3)
    :param scaleFactor: SF pour la détection HNM
    :param minNeighbors: MN pour la détection HNM
    :return: Chemin du modèle final, ou None si échec
    """
    from cascade.config import WINDOW_SIZE
    from cascade.data_prep import prepare_data
    from cascade.training import check_cascade_resume, train_cascade, create_samples

    print(f"\n{'='*60}")
    print(f"  Hard Negative Mining Itératif — {num_rounds} rounds")
    print(f"{'='*60}")
    print(f"  Ce processus va automatiquement :")
    print(f"    1. Extraire les fausses détections (hard negatives)")
    print(f"    2. Les ajouter au jeu d'entraînement")
    print(f"    3. Ré-entraîner le modèle")
    print(f"    ... répété {num_rounds} fois\n")

    current_model = model_path
    sample_width, sample_height = WINDOW_SIZE['recommended']
    positive_images_dir = os.path.join(data_dir, 'positive')

    results = []

    for round_num in range(1, num_rounds + 1):
        print(f"\n  {'─'*50}")
        print(f"  Round {round_num}/{num_rounds}")
        print(f"  {'─'*50}")

        # Étape 1 : Mine les hard negatives
        nb_hn = hard_negative_mining(
            model_path=current_model,
            negative_images_dir=negative_images_dir,
            output_dir=negative_images_dir,
            data_dir=data_dir,
            scaleFactor=scaleFactor,
            minNeighbors=minNeighbors
        )

        if nb_hn == 0:
            print(f"\n  ℹ Round {round_num} : Aucun hard negative trouvé.")
            print(f"    → Le modèle actuel ne produit plus de FP avec ces paramètres.")
            print(f"    → Arrêt anticipé du HNM itératif.")
            break

        # Étape 2 : Re-préparer les données (split + intégrer HN + augment + annotations)
        print(f"\n  Re-préparation des données (round {round_num})...")
        train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, \
            nb_annotations, nb_negatives, annotations_file, bg_file = \
            prepare_data(positive_images_dir, negative_images_dir, data_dir)

        # Étape 3 : Recréer le .vec
        from cascade.training import create_samples
        create_samples(
            annotations_file=annotations_file,
            vec_file=os.path.join(data_dir, 'samples.vec'),
            num_samples=nb_annotations,
            width=sample_width, height=sample_height
        )

        # Étape 4 : Ré-entraîner
        print(f"\n  Ré-entraînement (round {round_num})...")
        # Nettoyer l'ancien cascade pour forcer un nouvel entraînement
        cascade_file = os.path.join(output_dir, 'cascade.xml')
        for f in os.listdir(output_dir):
            fpath = os.path.join(output_dir, f)
            if os.path.isfile(fpath):
                os.remove(fpath)

        config = {'name': f'HNM-Round-{round_num}', 'feature': 'LBP',
                  'stages': 14, 'min_hit_rate': 0.995}

        new_model = train_cascade(
            nb_annotations, nb_negatives,
            sample_width, sample_height,
            data_dir, output_dir, config=config
        )

        if new_model is None:
            print(f"\n  ✗ Round {round_num} : Entraînement échoué.")
            break

        # Étape 5 : Évaluer
        from cascade.evaluation import evaluate_model
        eval_results, best_idx = evaluate_model(
            new_model, test_pos_dir, test_neg_dir)

        best = eval_results[best_idx]
        results.append({
            'round': round_num,
            'hn_added': nb_hn,
            'recall': best['recall'],
            'precision': best['precision'],
            'f1': best['f1'],
            'model': new_model
        })

        current_model = new_model

        print(f"\n  Round {round_num} terminé : "
              f"F1={best['f1']:.3f}  Recall={best['recall']:.1%}  "
              f"Précision={best['precision']:.1%}  (+{nb_hn} HN)")

    # Résumé final
    print(f"\n{'='*60}")
    print(f"  Résumé HNM Itératif — {len(results)} rounds complétés")
    print(f"{'='*60}")

    if results:
        print(f"\n  {'Round':<8} {'HN ajoutés':<14} {'Recall':<10} {'Précision':<12} {'F1':<8}")
        print(f"  {'─'*52}")
        for r in results:
            print(f"  {r['round']:<8} +{r['hn_added']:<13} "
                  f"{r['recall']:<10.1%} {r['precision']:<12.1%} {r['f1']:<8.3f}")

        best_round = max(results, key=lambda r: r['f1'])
        print(f"\n  Meilleur round : #{best_round['round']} (F1={best_round['f1']:.3f})")
        print(f"  Modèle final   : {current_model}")
    else:
        print(f"\n  Aucun round complété. Modèle inchangé.")

    print(f"{'='*60}\n")
    return current_model
