# cascade/data_prep.py
# ---------------------
# Préparation des données : validation, split train/test, augmentation,
# annotations et fichier bg.txt.

import os
import shutil
import numpy as np
import cv2
from tqdm import tqdm

from cascade.config import WINDOW_SIZE


def prepare_data(positive_images_dir, negative_images_dir, data_dir, num_augmented=5, w = WINDOW_SIZE['recommended'][0], h = WINDOW_SIZE['recommended'][1]):
    """Préparation des données pour l'entraînement du modèle de cascade de classifieurs Haar.
    
    :param num_augmented: Nombre de variantes augmentées par image positive (défaut 5).
                          En mode HNM itératif, ce paramètre est augmenté dynamiquement
                          pour élever le plafond numPos → numNeg et compenser les HN.
    """

    print("\n")
    print("Préparation des données d'entraînement...")
    print("-----------------------------------")

    # Étape 1.0b : Nettoyage des anciens hard negatives dans data/negative/ (si présents)
    old_hn_in_neg = [f for f in os.listdir(negative_images_dir)
                     if f.startswith('hn_') and os.path.isfile(os.path.join(negative_images_dir, f))]
    if old_hn_in_neg:
        print(f"  Nettoyage : suppression de {len(old_hn_in_neg)} anciens hn_* dans data/negative/...")
        for f in old_hn_in_neg:
            os.remove(os.path.join(negative_images_dir, f))
        print(f"  → Les hard negatives sont maintenant gérés dans data/hard_negatives/")

    # Étape 1.0c : Assainir les noms de fichiers (espaces → underscores)
    #   opencv_createsamples et opencv_traincascade utilisent un format
    #   délimité par des espaces ; les noms contenant des espaces cassent le parsing.
    sanitize_filenames(positive_images_dir)
    sanitize_filenames(negative_images_dir)

    # Étape 1.1 : Validation des images positives et négatives
    validate_images(positive_images_dir)
    validate_images(negative_images_dir)

    # Étape 1.2 : Filtrer les images trop petites (< 2× fenêtre de détection)
    filtered_log = filter_small_images(positive_images_dir, data_dir, w_main=w, h_main=h)

    # Étape 1.3 : Séparation train / test AVANT l'augmentation (évite le data leakage)
    train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir = split_data(positive_images_dir, negative_images_dir, data_dir)

    # Étape 1.3b : Intégrer les hard negatives (s'ils existent) dans l'ensemble TRAIN
    hn_dir = os.path.join(data_dir, 'hard_negatives')
    nb_hn_added = 0
    if os.path.isdir(hn_dir):
        hn_files = [f for f in os.listdir(hn_dir) if os.path.isfile(os.path.join(hn_dir, f))]
        if hn_files:
            print(f"Intégration de {len(hn_files)} hard negatives dans le train set...")
            for f in tqdm(hn_files, unit="img", colour="yellow", ncols=80):
                shutil.copy2(os.path.join(hn_dir, f), os.path.join(train_neg_dir, f))
                nb_hn_added += 1
            print(f"  {nb_hn_added} hard negatives ajoutés au train set.")

    # Étape 1.4 : Augmentation des positives du TRAIN set uniquement
    augment_data(train_pos_dir, train_pos_dir, num_augmented=num_augmented)

    # Étape 1.2 : Génération des annotations
    #   Mode plein cadre : bbox = image entière pour chaque image positive
    annotations_file = os.path.join(data_dir, 'annotations.txt')
    nb_annotations = generate_annotations(train_pos_dir, annotations_file)

    # Étape 1.5 : Préparation du fichier bg.txt pour les négatifs
    print("Préparation du fichier bg.txt pour les négatifs...")
    bg_file = os.path.join(data_dir, 'bg.txt')
    nb_negatives = generate_bg_file(train_neg_dir, bg_file)

    # Résumé final après augmentation
    n_train_pos = len(os.listdir(train_pos_dir))
    n_train_neg = len(os.listdir(train_neg_dir))
    n_test_pos = len(os.listdir(test_pos_dir))
    n_test_neg = len(os.listdir(test_neg_dir))
    
    print(f"\nRésumé final des données :")
    print(f"  Train : {n_train_pos} positives (originales + augmentées), {n_train_neg} négatives" +
          (f" (dont {nb_hn_added} hard negatives)" if nb_hn_added > 0 else ""))
    print(f"  Test  : {n_test_pos} positives, {n_test_neg} négatives")
    print(f"  Annotations : {annotations_file} ({nb_annotations} entrées)")
    print(f"  Négatifs    : {bg_file} ({nb_negatives} entrées)")
    print("-----------------------------------\n")

    return train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, nb_annotations, nb_negatives, annotations_file, bg_file


def sanitize_filenames(images_dir):
    """Renomme les fichiers dont le nom contient des espaces ou caractères spéciaux.
    
    opencv_createsamples et opencv_traincascade utilisent un format d'annotations
    délimité par des espaces. Un nom de fichier contenant des espaces (ex. 
    'stop 15 cm.jpg') casse le parsing et provoque 'Unable to open image'.
    
    Remplacement : espaces → underscores, parenthèses supprimées.
    Gère les conflits de noms via un suffixe numérique.
    
    :param images_dir: Dossier contenant les images à assainir
    """
    import re as _re

    image_files = [f for f in os.listdir(images_dir)
                   if os.path.isfile(os.path.join(images_dir, f))]
    
    renamed = 0
    for filename in image_files:
        # Remplacer caractères problématiques pour le format d'annotations OpenCV
        new_name = filename.replace(' ', '_')
        new_name = _re.sub(r'[()]+', '', new_name)       # supprimer parenthèses
        new_name = _re.sub(r'_+', '_', new_name)         # fusionner underscores multiples
        new_name = new_name.strip('_')                     # pas d'underscore en début/fin
        
        if new_name == filename:
            continue
        
        # Gérer les conflits de noms
        dst = os.path.join(images_dir, new_name)
        if os.path.exists(dst):
            base, ext = os.path.splitext(new_name)
            counter = 1
            while os.path.exists(dst):
                dst = os.path.join(images_dir, f"{base}_{counter}{ext}")
                counter += 1
            new_name = os.path.basename(dst)
        
        os.rename(os.path.join(images_dir, filename), dst)
        renamed += 1
    
    if renamed > 0:
        print(f"  Assainissement : {renamed} fichier(s) renommé(s) dans {os.path.basename(images_dir)}/ "
              f"(espaces → underscores)")


def validate_images(images_dir):
    """"Validation et collecte de stats des images du dossier spécifié"""
    
    print(f"Validation des images dans '{images_dir}'...")

    # étape 0: Vérifier si le dossier est vide 
    image_files = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    if not image_files:
        print(f"Le dossier '{images_dir}' est vide. Veuillez y ajouter des images.")
        exit(1)
    else:
        nb_images = len(image_files)
        print(f"Nombre d'images : {nb_images}")

    # étape 1: lister les images et vérifier les extensions
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    image_ext = {os.path.splitext(f)[1].lower() for f in image_files}
    if not image_ext.issubset(valid_extensions):
        print(f"Extensions non valides dans '{images_dir}': {image_ext - valid_extensions}")
        exit(1)
    else:
        print(f"Extensions des images validées")
    
    # étape 2: vérifier que chaque image est lisible par OpenCV + collecter dimensions
    print("Vérification et analyse des images...")
    dimensions = []
    for img_file in tqdm(image_files, unit="img", colour="green", ncols=80):
        img_path = os.path.join(images_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            print(f"Image illisible : {img_file}. Veuillez vérifier le fichier.")
            exit(1)
        dimensions.append((img.shape[1], img.shape[0]))  # (width, height)

    # calcul des stats
    widths, heights = zip(*dimensions)
    min_width, max_width = min(widths), max(widths)
    min_height, max_height = min(heights), max(heights)
    avg_width = sum(widths) / len(widths)
    avg_height = sum(heights) / len(heights)

    # étape 4: Afficher un résumé
    print(f"Dimensions des images :")
    print(f"  Largeur : min={min_width}, max={max_width}, moyenne={avg_width:.2f}")
    print(f"  Hauteur : min={min_height}, max={max_height}, moyenne={avg_height:.2f}")
    print(f"Images validées.\n")


def filter_small_images(positive_dir, data_dir, min_factor=2.0, w_main=None, h_main=None):
    """
    Filtre les images positives trop petites pour être apprenables par le cascade.
    
    Critère : l'image doit faire au moins min_factor × la fenêtre de détection
    en largeur ET en hauteur. Les images sous ce seuil sont déplacées dans un
    dossier data/filtered_too_small/ et indexées dans un log.
    
    :param positive_dir: Dossier des images positives originales
    :param data_dir: Dossier data/ racine
    :param min_factor: Facteur minimum (default 2.0 → image ≥ 2× la fenêtre)
    :param w: Largeur de la fenêtre de détection
    :param h: Hauteur de la fenêtre de détection
    :return: Chemin vers le fichier log des images filtrées (ou None si aucune)
    """
    win_w, win_h = w_main, h_main
    min_w = int(win_w * min_factor)
    min_h = int(win_h * min_factor)
    
    print(f"Filtrage des images trop petites (seuil : {min_w}×{min_h} px = "
          f"{min_factor:.0f}× fenêtre {win_w}×{win_h})...")
    
    image_files = [f for f in os.listdir(positive_dir)
                   if os.path.isfile(os.path.join(positive_dir, f))]
    
    filtered_dir = os.path.join(data_dir, 'filtered_too_small')
    log_entries = []
    
    for img_file in image_files:
        img_path = os.path.join(positive_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            continue
        h, w = img.shape[:2]
        if w < min_w or h < min_h:
            log_entries.append({
                'file': img_file,
                'width': w,
                'height': h,
                'reason': f'{w}×{h} < seuil {min_w}×{min_h}'
            })
    
    if not log_entries:
        print(f"  ✓ Aucune image trop petite détectée.")
        return None
    
    # Créer le dossier de quarantaine
    os.makedirs(filtered_dir, exist_ok=True)
    
    # Déplacer les images etLogger
    log_path = os.path.join(data_dir, 'filtered_small_images.log')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"# Images positives filtrées (trop petites)\n")
        f.write(f"# Seuil minimum : {min_w}×{min_h} px ({min_factor:.0f}× fenêtre {win_w}×{win_h})\n")
        f.write(f"# Date : {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Total filtré : {len(log_entries)}\n")
        f.write(f"#\n")
        f.write(f"# {'Fichier':<50} {'Dimensions':<15} {'Raison'}\n")
        f.write(f"# {'='*80}\n")
        
        for entry in log_entries:
            src = os.path.join(positive_dir, entry['file'])
            dst = os.path.join(filtered_dir, entry['file'])
            shutil.move(src, dst)
            f.write(f"  {entry['file']:<50} {entry['width']}×{entry['height']:<10} {entry['reason']}\n")
    
    print(f"  ⚠ {len(log_entries)} images filtrées (trop petites pour l'entraînement)")
    print(f"    → Déplacées dans : {filtered_dir}")
    print(f"    → Index détaillé : {log_path}")
    print(f"    → Consultez le log pour retirer ces images de votre source si désiré.\n")
    
    return log_path


def split_data(positive_dir, negative_dir, data_dir, train_ratio=0.85):
    """
    Sépare les données originales en ensembles d'entraînement et de test.
    Crée les dossiers data/train/ et data/test/ avec sous-dossiers positive/ et negative/.
    Les fichiers sont COPIÉS (les originaux restent intacts).
    
    :param positive_dir: Dossier contenant les images positives originales
    :param negative_dir: Dossier contenant les images négatives originales
    :param data_dir: Dossier racine data/ (pour créer train/ et test/)
    :param train_ratio: Ratio de données d'entraînement (default 0.85)
    :return: (train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir)
    """
    print("Séparation des données en train/test...")
    train_pos_dir = os.path.join(data_dir, 'train', 'positive')
    train_neg_dir = os.path.join(data_dir, 'train', 'negative')
    test_pos_dir = os.path.join(data_dir, 'test', 'positive')
    test_neg_dir = os.path.join(data_dir, 'test', 'negative')

    for d in [train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)

    # Split des images positives
    pos_files = [f for f in os.listdir(positive_dir) if os.path.isfile(os.path.join(positive_dir, f))]
    np.random.shuffle(pos_files)
    split_idx_pos = max(1, int(len(pos_files) * train_ratio))

    # Split des images négatives
    neg_files = [f for f in os.listdir(negative_dir) if os.path.isfile(os.path.join(negative_dir, f))]
    np.random.shuffle(neg_files)
    split_idx_neg = max(1, int(len(neg_files) * train_ratio))

    # Copie de toutes les images
    copy_tasks = []
    for f in pos_files[:split_idx_pos]:
        copy_tasks.append((os.path.join(positive_dir, f), os.path.join(train_pos_dir, f)))
    for f in pos_files[split_idx_pos:]:
        copy_tasks.append((os.path.join(positive_dir, f), os.path.join(test_pos_dir, f)))
    for f in neg_files[:split_idx_neg]:
        copy_tasks.append((os.path.join(negative_dir, f), os.path.join(train_neg_dir, f)))
    for f in neg_files[split_idx_neg:]:
        copy_tasks.append((os.path.join(negative_dir, f), os.path.join(test_neg_dir, f)))
    
    print("Copie des images...")
    for src, dst in tqdm(copy_tasks, unit="img", colour="green", ncols=80):
        shutil.copy2(src, dst)

    n_train_pos = len(os.listdir(train_pos_dir))
    n_train_neg = len(os.listdir(train_neg_dir))
    n_test_pos = len(os.listdir(test_pos_dir))
    n_test_neg = len(os.listdir(test_neg_dir))

    print(f"Split train/test terminé (ratio {train_ratio:.0%} / {1-train_ratio:.0%}) :")
    print(f"  Train : {n_train_pos} positives, {n_train_neg} négatives")
    print(f"  Test  : {n_test_pos} positives, {n_test_neg} négatives")
    print(f"  Dossiers créés : data/train/ et data/test/\n")

    return train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir


def augment_data(source_dir, output_dir, num_augmented=5):
    """
    Augmentation des données d'entraînement.
    
    Génère num_augmented variantes par image originale.
    Si source_dir == output_dir, les images augmentées sont ajoutées au même dossier
    (préfixe 'aug_' pour les distinguer).
    
    :param source_dir: Dossier contenant les images originales à augmenter
    :param output_dir: Dossier de sortie pour les images augmentées
    :param num_augmented: Nombre de variantes par image originale (default 3)
    """
    print("Augmentation des images positives du train set...")

    image_files = [
        f for f in os.listdir(source_dir)
        if os.path.isfile(os.path.join(source_dir, f)) and not f.startswith('aug_')
    ]
    
    if not image_files:
        print("Aucune image à augmenter.")
        return
    
    # Supprimer les anciennes images augmentées
    old_augmented = [f for f in os.listdir(output_dir) if f.startswith('aug_')]
    if old_augmented:
        print(f"Suppression de {len(old_augmented)} anciennes images augmentées...")
        for f in tqdm(old_augmented, unit="img", colour="green", ncols=80):
            os.remove(os.path.join(output_dir, f))

    print("Augmentation des images...")
    nb_generated = 0
    for img_file in tqdm(image_files, unit="img", colour="green", ncols=80):
        img_path = os.path.join(source_dir, img_file)
        img = cv2.imread(img_path)

        for i in range(num_augmented):
            augmented_img = apply_random_transformations(img)
            augmented_img_path = os.path.join(output_dir, f"aug_{i}_{img_file}")
            cv2.imwrite(augmented_img_path, augmented_img)
            nb_generated += 1

    print(f"Augmentation terminée. {nb_generated} images générées.")
    print(f"Total d'images dans le dossier : {len(os.listdir(output_dir))}\n")


def apply_random_transformations(image):
    """Applique des transformations aléatoires adaptées aux images CROPPÉES serrées.
    
    IMPORTANT : Aucune transformation géométrique (rotation, translation, perspective)
    car les images sont croppées plein cadre sur l'objet — toute bordure ajoutée
    serait du bruit non représentatif du contexte de détection.
    
    Transforms disponibles (sans modification des contours) :
    - Flip horizontal : double la variabilité
    - Brightness / contraste : simule éclairages variables
    - Correction gamma : simule réponse caméra robot
    - Flou gaussien : simule défocus / flou de mouvement (camera Zumi)
    - Bruit gaussien : simule bruit capteur (Pi camera)
    - CLAHE : égalisation adaptative pour conditions de lumière extrêmes
    - Sharpening : augmente les contours (contraste local)
    - Scale jitter : downscale + upscale → simule basse résolution / distance
    - Compression JPEG : simule artefacts de compression
    """
    # ── Flip horizontal aléatoire (50%) ──
    if np.random.rand() > 0.5:
        image = cv2.flip(image, 1)

    # ── Brightness + contraste (toujours, mais intensité variable) ──
    alpha = np.random.uniform(0.75, 1.25)
    beta = np.random.uniform(-20, 20)
    image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)

    # ── Correction gamma (40% de chance) ──
    if np.random.rand() < 0.4:
        gamma = np.random.uniform(0.6, 1.5)
        inv_gamma = 1.0 / gamma
        table = np.array([
            ((i / 255.0) ** inv_gamma) * 255
            for i in np.arange(0, 256)
        ]).astype('uint8')
        image = cv2.LUT(image, table)

    # ── Flou gaussien (35% de chance) — simule défocus / flou caméra ──
    if np.random.rand() < 0.35:
        ksize = np.random.choice([3, 5])
        image = cv2.GaussianBlur(image, (ksize, ksize), 0)

    # ── Bruit gaussien (30% de chance) — simule bruit capteur Pi camera ──
    if np.random.rand() < 0.30:
        sigma = np.random.uniform(5, 20)
        noise = np.random.normal(0, sigma, image.shape).astype(np.float32)
        image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # ── CLAHE — égalisation adaptative (20% de chance) ──
    if np.random.rand() < 0.20:
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=np.random.uniform(1.5, 4.0),
                                     tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=np.random.uniform(1.5, 4.0),
                                     tileGridSize=(8, 8))
            image = clahe.apply(image)

    # ── Sharpening (20% de chance) — renforce les arêtes ──
    if np.random.rand() < 0.20:
        strength = np.random.uniform(0.3, 0.8)
        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]], dtype=np.float32)
        kernel = (1 - strength) * np.eye(3, dtype=np.float32) + strength * kernel / 5
        # Utiliser un kernel simple sharpen
        sharpen_kernel = np.array([[ 0, -1,  0],
                                   [-1,  5, -1],
                                   [ 0, -1,  0]], dtype=np.float32)
        blended = cv2.filter2D(image, -1, sharpen_kernel)
        image = cv2.addWeighted(image, 1 - strength, blended, strength, 0)

    # ── Scale jitter (25% de chance) — downscale + upscale → perte de détails ──
    if np.random.rand() < 0.25:
        h, w = image.shape[:2]
        if h > 16 and w > 16:  # seulement si l'image est assez grande
            scale = np.random.uniform(0.4, 0.8)
            small = cv2.resize(image, (max(4, int(w * scale)), max(4, int(h * scale))),
                               interpolation=cv2.INTER_AREA)
            image = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

    # ── Compression JPEG (20% de chance) — simule artefacts ──
    if np.random.rand() < 0.20:
        quality = np.random.randint(30, 70)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, encoded = cv2.imencode('.jpg', image, encode_param)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR if len(image.shape) == 3
                             else cv2.IMREAD_GRAYSCALE)

    return image


def generate_annotations(images_dir, output_file):
    """
    Génère le fichier annotations.txt au format attendu par opencv_createsamples.
    
    Mode plein cadre : chaque image positive est déjà cadrée sur l'objet d'intérêt,
    donc l'annotation est automatique (1 objet par image, bbox = image entière).
    
    Format de sortie :
        chemin/image.jpg  1  0 0 <width> <height>
    
    :param images_dir: Dossier contenant les images positives (train/positive/)
    :param output_file: Chemin du fichier annotations.txt à générer
    :return: Nombre d'annotations générées
    """
    print(f"Génération des annotations (mode plein cadre)...")
    
    image_files = sorted([
        f for f in os.listdir(images_dir)
        if os.path.isfile(os.path.join(images_dir, f))
    ])
    
    if not image_files:
        print("Aucune image positive trouvée pour l'annotation.")
        exit(1)
    
    annotations_dir = os.path.dirname(os.path.abspath(output_file))

    annotations = []
    for img_file in tqdm(image_files, unit="img", colour="green", ncols=80):
        img_path = os.path.join(images_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            print(f"  ATTENTION : image illisible ignorée : {img_file}")
            continue
        h, w = img.shape[:2]
        rel_path = os.path.relpath(os.path.abspath(img_path), annotations_dir).replace('\\', '/')
        annotations.append(f"{rel_path}  1  0 0 {w} {h}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(annotations) + '\n')
    
    print(f"  {len(annotations)} annotations générées → {output_file}\n")
    return len(annotations)


def generate_bg_file(negative_dir, output_file):
    """
    Génère le fichier bg.txt listant les chemins des images négatives.
    
    Ce fichier est requis par opencv_traincascade pour le paramètre -bg.
    Les hard negatives (préfixe 'hn_') sont intercalés uniformément parmi
    les négatifs originaux pour une distribution équilibrée.
    
    :param negative_dir: Dossier contenant les images négatives (train/negative/)
    :param output_file: Chemin du fichier bg.txt à générer
    :return: Nombre de négatifs listés
    """
    print("Préparation du fichier bg.txt pour les négatifs...")
    
    all_files = [
        f for f in os.listdir(negative_dir)
        if os.path.isfile(os.path.join(negative_dir, f))
    ]
    
    if not all_files:
        print("Aucune image négative trouvée.")
        exit(1)
    
    # Séparer HN et négatifs normaux, puis intercaler uniformément
    hn_files = sorted([f for f in all_files if f.startswith('hn_')])
    normal_files = sorted([f for f in all_files if not f.startswith('hn_')])
    
    # Intercalage uniforme (Bresenham) : les originaux dominent, les HN
    # sont répartis régulièrement pour ne pas noyer les originaux
    if hn_files and normal_files:
        ordered_files = []
        total = len(normal_files) + len(hn_files)
        normal_idx = 0
        hn_idx = 0
        for i in range(total):
            target_normals = (i + 1) * len(normal_files) / total
            if normal_idx < target_normals and normal_idx < len(normal_files):
                ordered_files.append(normal_files[normal_idx])
                normal_idx += 1
            elif hn_idx < len(hn_files):
                ordered_files.append(hn_files[hn_idx])
                hn_idx += 1
            else:
                ordered_files.append(normal_files[normal_idx])
                normal_idx += 1
        print(f"  Ordre bg.txt : {len(normal_files)} négatifs originaux avec "
              f"{len(hn_files)} HN intercalés uniformément")
    else:
        ordered_files = normal_files + hn_files
    
    paths = []
    for f in tqdm(ordered_files, unit="img", colour="green", ncols=80):
        abs_path = os.path.abspath(os.path.join(negative_dir, f)).replace('\\', '/')
        paths.append(abs_path)
    
    with open(output_file, 'w', encoding='utf-8') as fout:
        fout.write('\n'.join(paths) + '\n')
    
    print(f"  {len(paths)} images négatives listées → {output_file}\n")
    return len(paths)
