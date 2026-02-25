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
