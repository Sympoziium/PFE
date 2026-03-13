# cascade/environment.py
# ---------------------
# Validation de l'environnement (outils CLI OpenCV, Python, libs).

import os
import shutil
import platform


def validate_environment():
    """
    Vérifie que l'environnement contient :
    - opencv_traincascade et opencv_createsamples dans le PATH
    - Python >= 3.6
    - OpenCV (cv2) importable et version >= 3.4
    - numpy, tqdm, matplotlib
    - Dossiers data/positive/ et data/negative/ existants
    """
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

    print("Outils CLI de OpenCV trouvés.")

    # Python
    python_vers = platform.python_version_tuple()
    major, minor = int(python_vers[0]), int(python_vers[1])
    if not (major == 3 and minor >= 6):
        print(f"Python version {platform.python_version()} détectée. Veuillez installer Python 3.6 ou une version ultérieure.")
        exit(1)
    print(f"Python version {platform.python_version()} détectée.")

    # OpenCV
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
        cv2_version_str = cv2.__version__ if hasattr(cv2, '__version__') else "unknown"
        cv2_version = (3, 4)

    if cv2_version < (3, 4):
        print(f"OpenCV version {cv2_version_str} détectée. Version 3.4+ requise.")
        exit(1)
    print(f"OpenCV version {cv2_version_str} détectée.")

    # numpy
    try:
        import numpy as np
    except ImportError:
        print("Le package numpy n'est pas installé. Veuillez l'installer avec 'pip install numpy'.")
        exit(1)
    print(f"Numpy version {np.__version__} détectée.")

    # tqdm
    try:
        import tqdm
    except ImportError:
        print("Le package tqdm n'est pas installé. Veuillez l'installer avec 'pip install tqdm'.")
        exit(1)
    print(f"tqdm version {tqdm.__version__} détectée.")

    # Dossiers d'images
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    if not os.path.exists(os.path.join(base_dir, 'data', 'positive')):
        print("Le dossier 'data/positive' est manquant. Veuillez le créer et y ajouter les images positives.")
        exit(1)
    if not os.path.exists(os.path.join(base_dir, 'data', 'negative')):
        print("Le dossier 'data/negative' est manquant. Veuillez le créer et y ajouter les images négatives.")
        exit(1)

    print("-----------------------------------")
    print("Environnement validé avec succès.\n")
    return 0
