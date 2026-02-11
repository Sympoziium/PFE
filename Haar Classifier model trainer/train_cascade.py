# train_cascade.py
# ---------------------
# Script permettant de créer un modèle de cascade de classifieurs Haar pour la détection d'objets.
# Ce script utilise OpenCV pour entraîner le modèle à partir d'images positives et négatives.

import shutil
import os
import platform

def validate_environment():
    
    print("Validation de l'environnement...")
    print("-----------------------------------")
    print("\n")
    
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
        import numpy
    except ImportError:
        print("Le package numpy n'est pas installé. Veuillez l'installer avec 'pip install numpy'.")
        exit(1)

    # Si la version est correcte
    print(f"Numpy version {numpy.__version__} détectée.")

    # vérification du package tqdm
    try:
        import tqdm
    except ImportError:
        print("Le package tqdm n'est pas installé. Veuillez l'installer avec 'pip install tqdm'.")
        exit(1)

    # Si la version est correcte
    print(f"tqdm version {tqdm.__version__} détectée.")

    # vérification de la présence des dossiers d'images
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'images positives')):
        print("Le dossier 'images positives' est manquant. Veuillez le créer et y ajouter les images positives.")
        exit(1)
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'images negatives')):
        print("Le dossier 'images negatives' est manquant. Veuillez le créer et y ajouter les images negatives.")
        exit(1)

    # Vérification que les dossiers ne sont pas vides et validation des extensions
    positive_dir = os.path.join(os.path.dirname(__file__), 'images positives')
    negative_dir = os.path.join(os.path.dirname(__file__), 'images negatives')
    
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    # Vérifier dossier images positives
    positive_files = [f for f in os.listdir(positive_dir) if os.path.isfile(os.path.join(positive_dir, f))]
    if not positive_files:
        print("Le dossier 'images positives' est vide. Veuillez y ajouter des images.")
        exit(1)
    
    positive_extensions = {os.path.splitext(f)[1].lower() for f in positive_files}
    if not positive_extensions.issubset(valid_extensions):
        print(f"Extensions non valides dans 'images positives': {positive_extensions - valid_extensions}")
        exit(1)
    
    print("Dossier 'images positives' validé.")

    # Vérifier dossier images négatives
    negative_files = [f for f in os.listdir(negative_dir) if os.path.isfile(os.path.join(negative_dir, f))]
    if not negative_files:
        print("Le dossier 'images negatives' est vide. Veuillez y ajouter des images.")
        exit(1)
    
    negative_extensions = {os.path.splitext(f)[1].lower() for f in negative_files}
    if not negative_extensions.issubset(valid_extensions):
        print(f"Extensions non valides dans 'images negatives': {negative_extensions - valid_extensions}")
        exit(1)

    print("Dossier 'images negatives' validé.")
    
    print("\n")
    print("-----------------------------------")
    print("Environnement validé avec succès.")
    
def validate_positive():
    """"Validation des images positives (exemples d'objets à détecter)"""
    

if __name__ == "__main__":
    # Chemins vers les fichiers et dossiers nécessaires    
    positive_images_dir = os.path.join(os.path.dirname(__file__), 'images positives')  # Dossier contenant les images positives
    negative_images_dir = os.path.join(os.path.dirname(__file__), 'images negatives')  # Dossier contenant les images négatives
    output_dir = os.path.join(os.path.dirname(__file__), 'modele output')              # Dossier où le modèle entraîné sera sauvegardé

    # Étape 0: Vérification de l'environnement
    validate_environment()

    # Étape 1: Préparation des données


    # Commande pour entraîner le modèle de cascade de classifieurs Haar
    # command = f"opencv_traincascade -data {output_dir} -vec positives.vec -bg negatives.txt -numPos 1000 -numNeg 500 -numStages 20"
    
    # # Exécution de la commande d'entraînement
    # os.system(command)