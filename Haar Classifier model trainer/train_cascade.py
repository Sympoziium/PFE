# train_cascade.py
# ---------------------
# Script permettant de créer un modèle de cascade de classifieurs Haar pour la détection d'objets.
# Ce script utilise OpenCV pour entraîner le modèle à partir d'images positives et négatives.

import shutil
import os
import platform
import numpy as np
import cv2


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

    # vérification de la version de Python
    python_vers = platform.python_version_tuple()
    major, minor = int(python_vers[0]), int(python_vers[1])
    if not (major == 3 and minor >= 6):
        print(f"Python version {platform.python_version()} détectée. Veuillez installer Python 3.6 ou une version ultérieure.")
        exit(1)

    # Si la version est correcte
    print(f"Python version {platform.python_version()} détectée.")

    # vérification de la version de OpenCV
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

    # vérification du package numpy
    try:
        import numpy as np
    except ImportError:
        print("Le package numpy n'est pas installé. Veuillez l'installer avec 'pip install numpy'.")
        exit(1)

    # Si la version est correcte
    print(f"Numpy version {np.__version__} détectée.")

    # vérification du package tqdm
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
    
    # étape 2: vérifier que chaque image est lisible par OpenCV
    for img_file in image_files:
        img_path = os.path.join(images_dir, img_file)
        img = cv2.imread(img_path)
        if img is None:
            print(f"Image illisible : {img_file}. Veuillez vérifier le fichier.")
            exit(1)
    
    print(f"Toutes les images dans le dossier sont lisibles par OpenCV.")

    # étape 3: Calculer les dimensions min/max/moyenne
    dimensions = []
    for img_file in image_files:
        img_path = os.path.join(images_dir, img_file)
        img = cv2.imread(img_path)
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

    print(f"Augmentation des données dans '{source_dir}'...")

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
        for f in old_augmented:
            os.remove(os.path.join(output_dir, f))
        print(f"{len(old_augmented)} anciennes images augmentées supprimées.")

    # Augmenter les images
    nb_generated = 0
    for img_file in image_files:
        img_path = os.path.join(source_dir, img_file)
        img = cv2.imread(img_path)

        for i in range(num_augmented):
            augmented_img = apply_random_transformations(img)
            
            # Sauvegarder l'image augmentée
            augmented_img_path = os.path.join(output_dir, f"aug_{i}_{img_file}")
            cv2.imwrite(augmented_img_path, augmented_img)
            nb_generated += 1

    print(f"Augmentation terminée. {nb_generated} images augmentées sauvegardées dans '{output_dir}'.")
    print(f"Total d'images dans le dossier : {len(os.listdir(output_dir))}")

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

    # Créer la structure de dossiers train/test
    train_pos_dir = os.path.join(data_dir, 'train', 'positive')
    train_neg_dir = os.path.join(data_dir, 'train', 'negative')
    test_pos_dir = os.path.join(data_dir, 'test', 'positive')
    test_neg_dir = os.path.join(data_dir, 'test', 'negative')

    for d in [train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)  # Nettoyer les anciens fichiers
        os.makedirs(d)

    # 1. Split des images positives originales
    pos_files = [f for f in os.listdir(positive_dir) if os.path.isfile(os.path.join(positive_dir, f))]
    np.random.shuffle(pos_files)
    split_idx = max(1, int(len(pos_files) * train_ratio))  # Au moins 1 image en train
    
    for f in pos_files[:split_idx]:
        shutil.copy2(os.path.join(positive_dir, f), os.path.join(train_pos_dir, f))
    for f in pos_files[split_idx:]:
        shutil.copy2(os.path.join(positive_dir, f), os.path.join(test_pos_dir, f))

    # 2. Split des images négatives
    neg_files = [f for f in os.listdir(negative_dir) if os.path.isfile(os.path.join(negative_dir, f))]
    np.random.shuffle(neg_files)
    split_idx = max(1, int(len(neg_files) * train_ratio))  # Au moins 1 image en train
    
    for f in neg_files[:split_idx]:
        shutil.copy2(os.path.join(negative_dir, f), os.path.join(train_neg_dir, f))
    for f in neg_files[split_idx:]:
        shutil.copy2(os.path.join(negative_dir, f), os.path.join(test_neg_dir, f))

    # Résumé détaillé
    n_train_pos = len(os.listdir(train_pos_dir))
    n_train_neg = len(os.listdir(train_neg_dir))
    n_test_pos = len(os.listdir(test_pos_dir))
    n_test_neg = len(os.listdir(test_neg_dir))

    print(f"Split train/test terminé (ratio {train_ratio:.0%} / {1-train_ratio:.0%}) :")
    print(f"  Train : {n_train_pos} positives, {n_train_neg} négatives")
    print(f"  Test  : {n_test_pos} positives, {n_test_neg} négatives")
    print(f"  Dossiers créés : data/train/ et data/test/")

    return train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir




def prepare_data(positive_images_dir, negative_images_dir, data_dir):
    """Préparation des données pour l'entraînement du modèle de cascade de classifieurs Haar"""

    print("Préparation des données d'entraînement...")
    print("-----------------------------------")

    # Étape 1.1 : Validation des images positives et négatives
    validate_images(positive_images_dir)
    validate_images(negative_images_dir)

    # Étape 1.2 : Annotation des images positives
    # Si on fournit des images déja cadrées, on peut sauter cette étape.
    # Sinon, il faudrait utiliser opencv_annotation pour créer un fichier annotations.txt

    # Étape 1.3 : Séparation train / test AVANT l'augmentation (évite le data leakage)
    print("\nSéparation des données en train/test...")
    train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir = split_data(
        positive_images_dir, negative_images_dir, data_dir
    )

    # Étape 1.4 : Augmentation des positives du TRAIN set uniquement
    #   Les images augmentées sont sauvegardées directement dans train/positive/
    #   pour simplifier le pipeline en aval.
    print("\nAugmentation des positives du train set...")
    augment_data(train_pos_dir, train_pos_dir)

    # Résumé final après augmentation
    n_train_pos = len(os.listdir(train_pos_dir))
    n_train_neg = len(os.listdir(train_neg_dir))
    n_test_pos = len(os.listdir(test_pos_dir))
    n_test_neg = len(os.listdir(test_neg_dir))
    print(f"\nRésumé final des données :")
    print(f"  Train : {n_train_pos} positives (originales + augmentées), {n_train_neg} négatives")
    print(f"  Test  : {n_test_pos} positives, {n_test_neg} négatives")
    print("-----------------------------------\n")

    return train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir




if __name__ == "__main__":
    # Chemins vers les fichiers et dossiers nécessaires    
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, 'data')                                           # Dossier racine des données
    positive_images_dir = os.path.join(data_dir, 'positive')                             # Dossier contenant les images positives
    negative_images_dir = os.path.join(data_dir, 'negative')                             # Dossier contenant les images négatives
    output_dir = os.path.join(data_dir, 'cascade')                                      # Dossier où le modèle entraîné sera sauvegardé

    # Étape 0: Vérification de l'environnement
    validate_environment()

    # Étape 1: Préparation des données
    train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir = prepare_data(
        positive_images_dir, negative_images_dir, data_dir
    )

    # Commande pour entraîner le modèle de cascade de classifieurs Haar
    # command = f"opencv_traincascade -data {output_dir} -vec positives.vec -bg negatives.txt -numPos 1000 -numNeg 500 -numStages 20"
    
    # # Exécution de la commande d'entraînement
    # os.system(command)