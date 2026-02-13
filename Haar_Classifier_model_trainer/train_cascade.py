# train_cascade.py
# ---------------------
# Script permettant de créer un modèle de cascade de classifieurs Haar pour la détection d'objets.
# Ce script utilise OpenCV pour entraîner le modèle à partir d'images positives et négatives.

import shutil 
import os
import platform
import subprocess
import re
import time
import numpy as np # retirer plus tard
import cv2 # retirer plus tard
from tqdm import tqdm # retirer plus tard

##########################################################################################
#                         Étape 0 : Validation de l'environnement
##########################################################################################

def validate_environment():
    
    print("\n")
    print("Validation de l'environnement...")
    print("-----------------------------------")
    
    # Vérification de la présence des outils CLI de OpenCV nécessaires pour l'entraînement
    if not shutil.which("opencv_traincascade") or not shutil.which("opencv_createsamples"):
        print("""
        L'outil opencv_traincascade n'est pas installé ou n'est pas dans le PATH.

        Comment obtenir les outils CLI (Windows)
        ============================================
        Télécharge le fichier pré-compilé OpenCV 3.4.3 pour Windows :
        https://sourceforge.net/projects/opencvlibrary/files/opencv-win/3.4.3/opencv-3.4.3-vc14_vc15.exe/download

        C'est un auto-extracteur de 182 MB. Voici les étapes :

        1. Télécharge et exécute opencv-3.4.3-vc14_vc15.exe — il va extraire un dossier 
        (choisis par exemple C:\\opencv-3.4.3\\)

        2. Les exécutables seront dans :
        - C:\\opencv-3.4.3\\opencv\\build\\x64\\vc15\\bin\\opencv_createsamples.exe
        - C:\\opencv-3.4.3\\opencv\\build\\x64\\vc15\\bin\\opencv_traincascade.exe

        3. Vérifie avec :
        - "C:\\opencv-3.4.3\\opencv\\build\\x64\\vc15\\bin\\opencv_createsamples"
        - "C:\\opencv-3.4.3\\opencv\\build\\x64\\vc15\\bin\\opencv_traincascade"

        4. (Optionnel) Pour pouvoir les appeler de n'importe où, ajoute le dossier bin au PATH :
        $env:PATH += ";C:\\opencv-3.4.3\\opencv\\build\\x64\\vc15\\bin"
        """)
        exit(1)

    # Si les outils sont trouvés
    print("Outils CLI de OpenCV trouvés.")

    # vérification de la version de Python (Pour la compatibilité des lib)
    python_vers = platform.python_version_tuple()
    major, minor = int(python_vers[0]), int(python_vers[1])
    if not (major == 3 and minor >= 6):
        print(f"Python version {platform.python_version()} détectée. Veuillez installer Python 3.6 ou une version ultérieure.")
        exit(1)

    # Si la version est correcte
    print(f"Python version {platform.python_version()} détectée.")

    # vérification de la version de OpenCV (Nécessaire pour le traitement d'images)
    try:
        import cv2
    except (ImportError, RuntimeError) as e:
        print(f"Impossible de charger OpenCV : {e}")
        print("Vérifiez qu'un seul package OpenCV est installé (pip install opencv-python).")
        print("Si vous avez opencv-contrib-python 3.4.x avec NumPy 2.x, désinstallez-le :")
        print("  pip uninstall opencv-contrib-python")
        print("  pip install opencv-python")
        exit(1)
    try:
        cv2_major = cv2.getVersionMajor()
        cv2_minor = cv2.getVersionMinor()
        cv2_version = (cv2_major, cv2_minor)
        cv2_version_str = f"{cv2_major}.{cv2_minor}"
    except AttributeError:
        # Fallback pour les anciennes versions
        cv2_version_str = cv2.__version__ if hasattr(cv2, '__version__') else "unknown"
        cv2_version = (3, 4)  # Assume minimum version
    
    if cv2_version < (3, 4):
        print(f"OpenCV version {cv2_version_str} détectée. Version 3.4+ requise.")
        exit(1)

    # Si la version est correcte (3.4+ ou 4.x — les deux supportent CascadeClassifier)
    print(f"OpenCV version {cv2_version_str} détectée.")

    # vérification du package numpy (Pour les transformations d'augmentation d'images)
    try:
        import numpy as np
    except ImportError:
        print("Le package numpy n'est pas installé. Veuillez l'installer avec 'pip install numpy'.")
        exit(1)

    # Si la version est correcte
    print(f"Numpy version {np.__version__} détectée.")

    # vérification du package tqdm (Pour les barres de progressions **purement esthétiques** pour retirer ctrl+f "tqdm")
    try:
        import tqdm
    except ImportError:
        print("Le package tqdm n'est pas installé. Veuillez l'installer avec 'pip install tqdm'.")
        exit(1)

    # Si la version est correcte
    print(f"tqdm version {tqdm.__version__} détectée.")

    # vérification de la présence des dossiers d'images
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'data\\positive\\')):
        print("Le dossier 'positive' est manquant. Veuillez le créer et y ajouter les images positives.")
        exit(1)
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'data\\negative\\')):
        print("Le dossier 'negative' est manquant. Veuillez le créer et y ajouter les images negatives.")
        exit(1)
    
    print("-----------------------------------")
    print("Environnement validé avec succès.")
    print("\n")

    return 0

##########################################################################################
#                   Étape 1 : Préparation des données d'entraînement
##########################################################################################

def prepare_data(positive_images_dir, negative_images_dir, data_dir):
    """Préparation des données pour l'entraînement du modèle de cascade de classifieurs Haar"""

    print("\n")
    print("Préparation des données d'entraînement...")
    print("-----------------------------------")

    # Étape 1.1 : Validation des images positives et négatives
    validate_images(positive_images_dir)
    validate_images(negative_images_dir)

    # Étape 1.3 : Séparation train / test AVANT l'augmentation (évite le data leakage)
    train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir = split_data(positive_images_dir, negative_images_dir, data_dir)

    # Étape 1.4 : Augmentation des positives du TRAIN set uniquement
    augment_data(train_pos_dir, train_pos_dir)

    # Étape 1.2 : Génération des annotations (APRÈS augmentation pour inclure les augmentées)
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
    print(f"  Train : {n_train_pos} positives (originales + augmentées), {n_train_neg} négatives")
    print(f"  Test  : {n_test_pos} positives, {n_test_neg} négatives")
    print(f"  Annotations : {annotations_file} ({nb_annotations} entrées)")
    print(f"  Négatifs    : {bg_file} ({nb_negatives} entrées)")
    print("-----------------------------------")
    print("\n")

    return train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, nb_annotations, nb_negatives, annotations_file, bg_file

def validate_images(images_dir):
    """"Validation et collecte de stats des images du dossier spécifié"""
    
    print(f"Validation des images dans '{images_dir}'...")

    # étape 0: Vérifier si le dossier est vide 
    image_files = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    if not image_files:
        print(f"Le dossier '{images_dir}' est vide. Veuillez y ajouter des images.")
        print("forreal")
        exit(1)
    else:
        nb_images = len(image_files)  # Compte le nombre d'images
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

    # étape 4: Afficher un résumé : nb total, dimensions, format
    print(f"Dimensions des images :")
    print(f"  Largeur : min={min_width}, max={max_width}, moyenne={avg_width:.2f}")
    print(f"  Hauteur : min={min_height}, max={max_height}, moyenne={avg_height:.2f}")
    print(f"Images validées.")
    print("\n")

def split_data(positive_dir, negative_dir, data_dir, train_ratio=0.85):
    """
    Sépare les données originales en ensembles d'entraînement et de test.
    Crée les dossiers data/train/ et data/test/ avec sous-dossiers positive/ et negative/.
    Les fichiers sont COPIÉS (les originaux restent intacts).
    
    Structure créée :
        data/train/positive/   — positives pour l'entraînement
        data/train/negative/   — négatives pour l'entraînement
        data/test/positive/    — positives pour l'évaluation
        data/test/negative/    — négatives pour l'évaluation
    
    :param positive_dir: Dossier contenant les images positives originales
    :param negative_dir: Dossier contenant les images négatives originales
    :param data_dir: Dossier racine data/ (pour créer train/ et test/)
    :param train_ratio: Ratio de données d'entraînement (default 0.85)
    :return: (train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir)
    """
    print("Séparation des données en train/test...")
    # Créer la structure de dossiers train/test
    train_pos_dir = os.path.join(data_dir, 'train', 'positive')
    train_neg_dir = os.path.join(data_dir, 'train', 'negative')
    test_pos_dir = os.path.join(data_dir, 'test', 'positive')
    test_neg_dir = os.path.join(data_dir, 'test', 'negative')

    # Nettoyer les anciens dossiers s'ils existent et recréer la structure
    for d in [train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)  # delete les anciens dossiers
        os.makedirs(d)

    # 1. Split des images positives originales
    pos_files = [f for f in os.listdir(positive_dir) if os.path.isfile(os.path.join(positive_dir, f))]
    np.random.shuffle(pos_files)
    split_idx_pos = max(1, int(len(pos_files) * train_ratio))  # Au moins 1 image en train

    # 2. Split des images négatives
    neg_files = [f for f in os.listdir(negative_dir) if os.path.isfile(os.path.join(negative_dir, f))]
    np.random.shuffle(neg_files)
    split_idx_neg = max(1, int(len(neg_files) * train_ratio))  # Au moins 1 image en train

    # Copie de toutes les images en une seule barre de progression
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

    # Résumé détaillé
    n_train_pos = len(os.listdir(train_pos_dir))
    n_train_neg = len(os.listdir(train_neg_dir))
    n_test_pos = len(os.listdir(test_pos_dir))
    n_test_neg = len(os.listdir(test_neg_dir))

    print(f"Split train/test terminé (ratio {train_ratio:.0%} / {1-train_ratio:.0%}) :")
    print(f"  Train : {n_train_pos} positives, {n_train_neg} négatives")
    print(f"  Test  : {n_test_pos} positives, {n_test_neg} négatives")
    print(f"  Dossiers créés : data/train/ et data/test/")
    print("\n")

    return train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir

def augment_data(source_dir, output_dir, num_augmented=5):
    """
    Augmentation des données d'entraînement pour améliorer la robustesse du modèle.
    
    Génère num_augmented variantes par image originale.
    Si source_dir == output_dir, les images augmentées sont ajoutées au même dossier
    (préfixe 'aug_' pour les distinguer).
    
    :param source_dir: Dossier contenant les images originales à augmenter
    :param output_dir: Dossier de sortie pour les images augmentées
    :param num_augmented: Nombre de variantes par image originale (default 5)
    """
    print("Augmentation des positives du train set...")

    # Lister les images originales (exclure les images déjà augmentées)
    image_files = [
        f for f in os.listdir(source_dir)
        if os.path.isfile(os.path.join(source_dir, f)) and not f.startswith('aug_')
    ]
    
    if not image_files:
        print("Aucune image à augmenter.")
        return
    
    # Créer le dossier de sortie s'il n'existe pas
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Supprimer les anciennes images augmentées (celles avec le préfixe aug_)
    old_augmented = [f for f in os.listdir(output_dir) if f.startswith('aug_')]
    if old_augmented:
        print(f"Suppression de {len(old_augmented)} anciennes images augmentées...")
        for f in tqdm(old_augmented, unit="img", colour="green", ncols=80):
            os.remove(os.path.join(output_dir, f))

    # Augmenter les images
    print("Augmentation des images...")
    nb_generated = 0
    for img_file in tqdm(image_files, unit="img", colour="green", ncols=80):
        img_path = os.path.join(source_dir, img_file)
        img = cv2.imread(img_path)

        for i in range(num_augmented):
            augmented_img = apply_random_transformations(img)
            
            # Sauvegarder l'image augmentée
            augmented_img_path = os.path.join(output_dir, f"aug_{i}_{img_file}")
            cv2.imwrite(augmented_img_path, augmented_img)
            nb_generated += 1

    print(f"Augmentation terminée. {nb_generated} images générées.")
    print(f"Total d'images dans le dossier : {len(os.listdir(output_dir))}")
    print("\n")

def apply_random_transformations(image):
    """Applique des transformations aléatoires à une image pour l'augmentation des données"""

    # Exemple de transformations : rotation, translation, zoom, etc.
    rows, cols = image.shape[:2]

    # Rotation aléatoire
    angle = np.random.uniform(-15, 15)
    M_rot = cv2.getRotationMatrix2D((cols / 2, rows / 2), angle, 1)

    # Flip horizontal aléatoire
    if np.random.rand() > 0.5:
        image = cv2.flip(image, 1)

    # Léger flou gaussien
    image = cv2.GaussianBlur(image, (5, 5), 0)

    # Ajout de bruit sel et poivre léger
    noise = np.random.choice([0, 255], (rows, cols), p=[0.98, 0.02])
    noisy_image = image.copy()
    noisy_image[noise == 255] = 255  # Sel
    noisy_image[noise == 0] = 0  # Poivre

    # Mélange de l'image originale et de l'image bruitée
    image = cv2.addWeighted(image, 0.9, noisy_image, 0.1, 0)

    # Variation de luminosité aléatoire
    brightness_factor = np.random.uniform(0.7, 1.2)
    image = cv2.convertScaleAbs(image, alpha=brightness_factor, beta=0)

    # Translation aléatoire
    tx = np.random.uniform(-0.1 * cols, 0.1 * cols)
    ty = np.random.uniform(-0.1 * rows, 0.1 * rows)
    M_trans = np.float32([[1, 0, tx], [0, 1, ty]])

    transformed_img = cv2.warpAffine(image, M_rot, (cols, rows))
    transformed_img = cv2.warpAffine(transformed_img, M_trans, (cols, rows))

    return transformed_img

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
    
    # Calculer le dossier parent du fichier annotations pour des chemins relatifs
    annotations_dir = os.path.dirname(os.path.abspath(output_file))

    annotations = []
    for img_file in tqdm(image_files, unit="img", colour="green", ncols=80):
        img_path = os.path.join(images_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            print(f"  ATTENTION : image illisible ignorée : {img_file}")
            continue
        h, w = img.shape[:2]
        # Chemin RELATIF au dossier du fichier annotations.txt
        # opencv_createsamples préfixe automatiquement le dossier du fichier -info
        rel_path = os.path.relpath(os.path.abspath(img_path), annotations_dir).replace('\\', '/')
        annotations.append(f"{rel_path}  1  0 0 {w} {h}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(annotations) + '\n')
    
    print(f"  {len(annotations)} annotations générées → {output_file}")
    print("\n")
    return len(annotations)

def generate_bg_file(negative_dir, output_file):
    """
    Génère le fichier bg.txt listant les chemins des images négatives.
    
    Ce fichier est requis par opencv_traincascade pour le paramètre -bg.
    
    Format de sortie (un chemin relatif par ligne, relatif au dossier du fichier bg.txt) :
        train/negative/img001.jpg
        train/negative/img002.jpg
    
    :param negative_dir: Dossier contenant les images négatives (train/negative/)
    :param output_file: Chemin du fichier bg.txt à générer
    :return: Nombre de négatifs listés
    """
    print("Préparation du fichier bg.txt pour les négatifs...")
    
    neg_files = sorted([
        f for f in os.listdir(negative_dir)
        if os.path.isfile(os.path.join(negative_dir, f))
    ])
    
    if not neg_files:
        print("Aucune image négative trouvée.")
        exit(1)
    
    # opencv_traincascade résout les chemins de bg.txt par rapport au CWD (pas au fichier bg.txt)
    # On utilise des chemins absolus pour éviter toute ambiguïté
    paths = []
    for f in tqdm(neg_files, unit="img", colour="green", ncols=80):
        abs_path = os.path.abspath(os.path.join(negative_dir, f)).replace('\\', '/')
        paths.append(abs_path)
    
    with open(output_file, 'w', encoding='utf-8') as fout:
        fout.write('\n'.join(paths) + '\n')
    
    print(f"  {len(paths)} images négatives listées → {output_file}")
    print("\n")
    return len(paths)

##########################################################################################
#                   Étape 2 : Création des échantillons
##########################################################################################

def create_samples(annotations_file, vec_file, num_samples, width=24, height=24):
    """
    Crée le fichier .vec à partir des annotations pour l'entraînement du cascade de classifieurs Haar.
    
    Utilise l'outil opencv_createsamples en mode "fichier d'annotations".
    
    :param annotations_file: Chemin du fichier annotations.txt généré précédemment
    :param vec_file: Chemin du fichier .vec à créer
    :param num_samples: Nombre d'échantillons à générer (doit être <= nombre d'annotations)
    :param width: Largeur des échantillons (default 24)
    :param height: Hauteur des échantillons (default 24)
    """
    print("\n")
    print(f"Création du fichier .vec avec opencv_createsamples...")
    print("-----------------------------------")
    
    command = f"opencv_createsamples -info {annotations_file} -vec {vec_file} -num {num_samples} -w {width} -h {height}"
    
    start_time = time.time()
    print("Création des échantillons...")
    pbar = tqdm(total=num_samples, unit="sample", colour="green", ncols=80)
    created_count = 0
    
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    
    for line in process.stdout:
        line = line.strip()
        
        # Ligne finale : "Done. Created 2166 samples"
        done_match = re.search(r'Done\.\s*Created\s+(\d+)\s+samples', line)
        if done_match:
            final_count = int(done_match.group(1))
            pbar.update(final_count - created_count)  # Compléter la barre
            created_count = final_count
        
        # Ligne d'erreur "Unable to open image"
        elif 'Unable to open image' in line or 'Error' in line:
            pbar.write(f"  ERREUR : {line}")
    
    process.wait()
    pbar.close()
    
    elapsed = time.time() - start_time
    
    if process.returncode != 0:
        print(f"  opencv_createsamples a échoué (code retour {process.returncode})")
        exit(1)
    
    print(f"  {created_count} échantillons créés en {elapsed:.1f}s → {vec_file}")
    print("-----------------------------------\n")
    print("\n")

##########################################################################################
#                   Étape 3 : Entraînement de la cascade
##########################################################################################

def check_cascade_resume(output_dir):
    """
    Vérifie si le dossier cascade contient des fichiers d'un entraînement précédent.
    Demande à l'utilisateur s'il veut reprendre ou recommencer à zéro.
    
    :param output_dir: Dossier de sortie cascade/
    :return: 'resume' si reprise, 'restart' si on recommence
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        return 'restart'
    
    # Chercher les fichiers de stages existants (stage0.xml, stage1.xml, ...)
    stage_files = sorted([f for f in os.listdir(output_dir) if re.match(r'stage\d+\.xml', f)])
    cascade_file = os.path.join(output_dir, 'cascade.xml')
    has_cascade = os.path.exists(cascade_file)
    
    if not stage_files and not has_cascade:
        return 'restart'
    
    # Afficher l'état actuel
    print(f"\n  Fichiers d'entraînement détectés dans {output_dir} :")
    if stage_files:
        print(f"    Stages complétés : {len(stage_files)} ({stage_files[0]} → {stage_files[-1]})")
    if has_cascade:
        size_kb = os.path.getsize(cascade_file) / 1024
        print(f"    Modèle final     : cascade.xml ({size_kb:.1f} KB)")
    
    # Demander à l'utilisateur
    print(f"\n  Options :")
    print(f"    [R] Reprendre l'entraînement à partir du stage {len(stage_files)}")
    print(f"    [N] Nouvel entraînement (supprimer les fichiers existants)")
    print(f"    [Q] Quitter")
    
    while True:
        choice = input("\n  Choix (R/N/Q) : ").strip().upper()
        if choice == 'R':
            print(f"  → Reprise de l'entraînement au stage {len(stage_files)}...")
            return 'resume'
        elif choice == 'N':
            # Supprimer tous les fichiers dans le dossier cascade
            for f in os.listdir(output_dir):
                file_path = os.path.join(output_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            print(f"  → Dossier cascade nettoyé. Nouvel entraînement...")
            return 'restart'
        elif choice == 'Q':
            print("  → Entraînement annulé.")
            exit(0)
        else:
            print("  Choix invalide. Entrer R, N ou Q.")

def train_cascade(nb_annotations, nb_negatives, sample_width, sample_height, data_dir, output_dir, PROTOTYPE= "Rapide"):
    """
    Entraîne le modèle de cascade de classifieurs Haar avec opencv_traincascade.
    
    Les paramètres d'entraînement sont configurés pour un bon compromis entre précision et temps d'entraînement.

    ** Penser à mettre PROTOTYPE à False pour un entraînement complet ! **
    """
    print("\n")
    print(f"Entraînement en cascade du classifieur...")
    print("-----------------------------------")

    # numPos doit être ~90% du .vec pour laisser une marge interne à OpenCV
    # numNeg recommandé : 2x numPos
    num_pos = int(nb_annotations * 0.9)
    num_neg = min(nb_negatives, num_pos * 2)
    dedicated_RAM_MB = 8192  # RAM dédiée pour l'entraînement (en MB) ** À ajuster selon votre machine (ex: 4096 pour 4GB, 8192 pour 8GB, etc.)
    
    # Configuration des paramètres d'entraînement selon le mode PROTOTYPE
    if PROTOTYPE == "Rapide":
        print("Mode PROTOTYPE : utilisation de valeurs réduites pour un test rapide.")
        num_stages = 15
        feature = "LBP"
    elif PROTOTYPE == "Equilibre":
        print("Mode ÉQUILIBRE : compromis entre rapidité et précision.")
        num_stages = 16
        feature = "HAAR"
    elif PROTOTYPE == "Précision":
        print("Mode PRÉCISION : utilisation des paramètres standards pour un entraînement complet.")
        num_stages = 20
        feature = "HAAR"

    # Lancement de la commande d'entraînement
    command = (
        f"opencv_traincascade"
        f" -data {output_dir}"
        f" -vec {os.path.join(data_dir, 'samples.vec')}"
        f" -bg {os.path.join(data_dir, 'bg.txt')}"
        f" -numPos {num_pos}"
        f" -numNeg {num_neg}"
        f" -numStages {num_stages}"
        f" -featureType {feature}"
        f" -minHitRate 0.995"
        f" -maxFalseAlarmRate 0.5"
        f" -w {sample_width} -h {sample_height}"
        f" -precalcValBufSize {dedicated_RAM_MB}"
        f" -precalcIdxBufSize {dedicated_RAM_MB}"
        f" -mode ALL"
        f" -maxDepth 1"
        f" -weightTrimRate 0.95"
    )

    print(f"  Paramètres : {num_stages} stages, {feature}, numPos={num_pos}, numNeg={num_neg}, {sample_width}x{sample_height}")
    print(f"  Détection globale théorique : ~{0.995**num_stages:.1%}  |  Faux positifs théoriques : ~{0.5**num_stages:.6%}")
    print()
    
    start_time = time.time()
    
    # Barre de progression globale (par stage)
    pbar = tqdm(
        total=num_stages,
        unit="stage", colour="green", ncols=80,
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} stages [{elapsed}<{remaining}]'
    )
    
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    
    # Variables pour le parsing de la sortie
    current_stage = -1
    stage_hr = None         # Dernier HR du stage courant
    stage_fa = None         # Dernier FA du stage courant
    stage_features = 0      # Nombre de features (weak classifiers) du stage
    stage_start_time = time.time()
    acceptance_ratio = None # Ratio d'acceptation des négatifs
    stages_summary = []     # Résumé de chaque stage pour le rapport final
    
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        
        # --- Détection du début d'un nouveau stage ---
        # Format : "===== TRAINING 0-stage ====="
        stage_match = re.search(r'TRAINING\s+(\d+)-stage', line)
        if stage_match:
            new_stage = int(stage_match.group(1))
            
            # Afficher le résumé du stage précédent (sauf le premier)
            if current_stage >= 0 and stage_hr is not None:
                stage_duration = time.time() - stage_start_time
                summary = f"Stage {current_stage:2d}/{num_stages} : HR={stage_hr:.4f}  FA={stage_fa:.4f}  [{stage_features} features]  ({stage_duration:.0f}s)"
                stages_summary.append({
                    'stage': current_stage, 'hr': stage_hr, 'fa': stage_fa,
                    'features': stage_features, 'duration': stage_duration,
                    'acceptance_ratio': acceptance_ratio
                })
                pbar.update(1)
                pbar.write(f"  ✓ {summary}")
            
            current_stage = new_stage
            stage_hr = None
            stage_fa = None
            stage_features = 0
            stage_start_time = time.time()
            continue
        
        # --- Parsing du nombre de positifs consommés ---
        # Format: "POS count : consumed   1949 : 1969"
        pos_match = re.search(r'POS count\s*:\s*consumed\s+(\d+)\s*:\s*(\d+)', line)
        if pos_match:
            pos_used = int(pos_match.group(1))
            pos_consumed = int(pos_match.group(2))
            if pos_consumed > pos_used:
                pbar.write(f"    Positifs : {pos_used} utilisés, {pos_consumed} consommés du .vec ({pos_consumed - pos_used} rejetés)")
            continue
        
        # --- Parsing du ratio d'acceptation des négatifs ---
        # Format: "NEG count : acceptanceRatio    3898 : 0.216"
        neg_match = re.search(r'NEG count\s*:\s*acceptanceRatio\s+(\d+)\s*:\s*([\d.e+-]+)', line)
        if neg_match:
            neg_count = int(neg_match.group(1))
            acceptance_ratio = float(neg_match.group(2))
            # L'acceptance ratio indique quel % des négatifs "passent" encore à travers
            # tous les stages précédents. Plus c'est bas, mieux le cascade rejette.
            pbar.write(f"    Négatifs : {neg_count} utilisés, acceptance ratio = {acceptance_ratio:.4f} ({acceptance_ratio:.2%} passent encore)")
            continue
        
        # --- Parsing des lignes HR/FA du tableau ---
        # Format: "|   5| 0.996921| 0.407132|"
        hr_fa_match = re.search(r'\|\s*(\d+)\|\s*([\d.]+)\|\s*([\d.]+)\|', line)
        if hr_fa_match:
            stage_features = int(hr_fa_match.group(1))
            stage_hr = float(hr_fa_match.group(2))
            stage_fa = float(hr_fa_match.group(3))
            continue
        
        # --- Détection d'erreurs critiques ---
        if 'Can not get new positive sample' in line:
            pbar.write(f"\n  ERREUR : {line}")
            pbar.write(f"  → numPos est trop élevé. Réduire à ~85% du .vec.")
        elif 'Train dataset for temp stage can not be filled' in line:
            pbar.write(f"\n  ERREUR : {line}")
            pbar.write(f"  → Pas assez d'images négatives. Ajouter plus de négatifs.")
        elif 'Required leaf false alarm rate achieved' in line:
            pbar.write(f"\n  INFO : Taux de faux positifs cible atteint avant le dernier stage.")
            pbar.write(f"  → L'entraînement s'est terminé plus tôt — c'est un BON signe.")
    
    process.wait()
    
    # Afficher le résumé du dernier stage
    if current_stage >= 0 and stage_hr is not None:
        stage_duration = time.time() - stage_start_time
        summary = f"Stage {current_stage:2d}/{num_stages} : HR={stage_hr:.4f}  FA={stage_fa:.4f}  [{stage_features} features]  ({stage_duration:.0f}s)"
        stages_summary.append({
            'stage': current_stage, 'hr': stage_hr, 'fa': stage_fa,
            'features': stage_features, 'duration': stage_duration,
            'acceptance_ratio': acceptance_ratio
        })
        pbar.update(1)
        pbar.write(f"  ✓ {summary}")
    
    pbar.close()
    
    total_elapsed = time.time() - start_time
    hours, remainder = divmod(int(total_elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # --- Rapport final ---
    print(f"\n{'='*60}")
    print(f"  ENTRAÎNEMENT TERMINÉ en {hours}h{minutes:02d}m{seconds:02d}s")
    print(f"{'='*60}")
    
    if stages_summary:
        total_features = sum(s['features'] for s in stages_summary)
        overall_hr = 1.0
        for s in stages_summary:
            overall_hr *= s['hr']
        final_ar = stages_summary[-1].get('acceptance_ratio', None)
        
        print(f"\n  Résumé :")
        print(f"    Stages complétés    : {len(stages_summary)} / {num_stages}")
        print(f"    Features totales    : {total_features}")
        print(f"    Détection globale   : {overall_hr:.2%}  (produit des HR de chaque stage)")
        if final_ar is not None:
            print(f"    Faux positifs       : {final_ar:.4%} des négatifs passent encore")
        print(f"    Durée totale        : {hours}h{minutes:02d}m{seconds:02d}s")
    
    cascade_file = os.path.join(output_dir, 'cascade.xml')
    if os.path.exists(cascade_file):
        size_kb = os.path.getsize(cascade_file) / 1024
        print(f"\n  Modèle sauvegardé : {cascade_file} ({size_kb:.1f} KB)")
    else:
        print(f"\n  ATTENTION : cascade.xml non trouvé dans {output_dir}")
        print(f"  L'entraînement a peut-être échoué. Vérifier les erreurs ci-dessus.")
    
    print(f"{'='*60}\n")
    print("-----------------------------------")
    print("\n")
    return cascade_file if os.path.exists(cascade_file) else None

##########################################################################################
#                   Étape 4 : Test du modèle entraîné
##########################################################################################

def evaluate_model(model_path, test_pos_dir, test_neg_dir):
    """
    Évalue les performances du modèle entraîné sur l'ensemble de test.
    
    :param model_path: Chemin du fichier cascade.xml du modèle entraîné
    :param test_pos_dir: Dossier contenant les images positives de test
    :param test_neg_dir: Dossier contenant les images négatives de test
    """
    print("\n")
    print(f"Évaluation du modèle entraîné...")
    print("-----------------------------------")

    # **Procédure** :
    # 1. Charger le `cascade.xml` avec `cv2.CascadeClassifier`
    # 2. Pour chaque image positive du test set :
    # - Exécuter `detectMultiScale` avec les paramètres par défaut
    # - Comparer la détection avec le ground truth (bounding box)
    # - Calculer IoU, compter TP/FN
    # 3. Pour chaque image négative :
    # - Exécuter `detectMultiScale`
    # - Compter les faux positifs
    # 4. Agréger les métriques et afficher un rapport

    # Étape 1 : Charger le modèle
    if not os.path.exists(model_path):
        print(f"  ERREUR : Modèle non trouvé à {model_path}")
        exit(1)
    
    cascade = cv2.CascadeClassifier(model_path)

    if cascade.empty():
        print(f"  ERREUR : Impossible de charger le modèle à {model_path}")
        exit(1)

    # Étape 2 : Évaluer sur les positives
    print("Évaluation sur les positives...")
    tp, fn = test_model(cascade, test_pos_dir, positive=True)

    # Étape 3 : Évaluer sur les négatives
    print("Évaluation sur les négatives...")
    fp = test_model(cascade, test_neg_dir, positive=False)

    # Étape 4 : Afficher le rapport d'évaluation
    nb_test_pos = len(os.listdir(test_pos_dir))
    nb_test_neg = len(os.listdir(test_neg_dir))
    detection_rate = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    false_positives_per_img = fp / nb_test_neg if nb_test_neg > 0 else 0
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0

    print("┌──────────────────────┬──────────┐")
    print("│ Métrique             │ Valeur   │")
    print("├──────────────────────┼──────────┤")
    print(f"│ Taux de détection    │ {detection_rate:.1f}%    │")
    print(f"│ Faux positifs / img  │ {false_positives_per_img:.3f}   │")
    print(f"│ Précision            │ {precision:.1f}%    │")
    print("└──────────────────────┴──────────┘")

    # Paramètres detectMultiScale recommandés :
    #     scaleFactor=1.1, minNeighbors=5

def test_model(model, test_image_dir, positive = True):
    """
    Test rapide du modèle sur une image de test.
    
    :param model: Objet CascadeClassifier chargé
    :param test_image_dir: Chemin du dossier contenant les images de test (positive ou négative)
    :param positive: Indique si les images de test sont positives (True) ou négatives (False) pour le calcul des métriques
    :return: (tp, fn) si positive=True, sinon fp
    """
    test_images = [f for f in os.listdir(test_image_dir) if os.path.isfile(os.path.join(test_image_dir, f))]
    tp = 0 # true positives
    fn = 0 # false negatives
    fp = 0 # false positives

    for img_file in tqdm(test_images, unit="img", colour="green", ncols=80):
        img_path = os.path.join(test_image_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            print(f"  ATTENTION : image illisible ignorée : {img_file}")
            continue
        
        # Détection
        detections = model.detectMultiScale(img, scaleFactor=1.1, minNeighbors=3)
        
        # En mode plein cadre, on considère que la bbox GT est l'image entière
        # gt_bbox = (0, 0, img.shape[1], img.shape[0])
        
        if positive:
            # Vérifier les détections contre le GT
            if len(detections) == 0:
                fn += 1
            else:
                tp += 1
        else:
            if len(detections) == 0:
                pass  # Pas de comptage ici car on ne veut pas compter les TN
            else:
                fp += 1

    if positive:            
        return tp, fn
    else:
        return fp

if __name__ == "__main__":
    # Chemins vers les fichiers et dossiers nécessaires    
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, 'data')                          # Dossier racine des données
    positive_images_dir = os.path.join(data_dir, 'positive')           # Dossier contenant les images positives
    negative_images_dir = os.path.join(data_dir, 'negative')           # Dossier contenant les images négatives
    output_dir = os.path.join(data_dir, 'cascade')                     # Dossier où le modèle entraîné sera sauvegardé
    MODEL_TRAINING_CONFIG = "Rapide"                                   # Choix du mode d'entraînement : "Rapide", "Équilibre", "Précision"



    # Étape 0: Vérification de l'environnement
    validate_environment()

    # Étape 1: Préparation des données
    train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, nb_annotations, nb_negatives, annotations_file, bg_file = prepare_data(positive_images_dir, negative_images_dir, data_dir)

    # --- Configuration de la taille de fenêtre (Important) ---
    # Le ratio doit correspondre à la forme de l'objet détecté.
    # Minifigures LEGO : ratio ~1:1.8 (rectangulaire vertical)
    # Panneaux stop : 24x24 (carré)
    sample_width = 24
    sample_height = 42

    # Étape 2: Création du fichier .vec avec opencv_createsamples
    create_samples(
        annotations_file=annotations_file,
        vec_file=os.path.join(data_dir, 'samples.vec'),
        num_samples=nb_annotations,
        width=sample_width,
        height=sample_height
    )

    # Étape 3: Entraînement de la cascade
    # Vérifier si un entraînement précédent existe dans le dossier cascade
    check_cascade_resume(output_dir)
    model_path = train_cascade(nb_annotations, nb_negatives, sample_width, sample_height, data_dir, output_dir, PROTOTYPE=MODEL_TRAINING_CONFIG)
    
    # Étape 4: Évaluation du modèle (TODO)
    # Utiliser l'ensemble de test pour évaluer les performances du modèle entraîné (précision, rappel, F1-score, etc.)
    # Afficher les résultats et les métriques d'évaluation pour analyser la qualité du modèle et identifier les éventuels points d'amélioration.
    # enregistrer sous formes de graphiques les courbes de précision/rappel, la matrice de confusion, etc. pour une analyse visuelle des performances du modèle.
    evaluate_model(model_path, test_pos_dir, test_neg_dir)