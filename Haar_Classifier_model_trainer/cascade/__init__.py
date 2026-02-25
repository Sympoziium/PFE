# cascade/__init__.py
# --------------------
# Package cascade — entraînement et analyse de classificateurs Haar/LBP.
#
# Architecture :
#   cascade/
#   ├── config.py          — constantes et préconfigurations
#   ├── environment.py     — validation de l'environnement (CLI, libs, dossiers)
#   ├── data_prep.py       — préparation des données (split, augment, annotations)
#   ├── training.py        — pipeline d'entraînement (samples, cascade, XML)
#   ├── evaluation.py      — évaluation du modèle (test, plaque, rapport)
#   ├── mining.py          — hard negative mining
#   └── analysis/          — analyse avancée du modèle
#       ├── __init__.py    — orchestrateur (advanced_model_analysis)
#       ├── utils.py       — utilitaires internes
#       ├── stages.py      — évaluation per-stage, mosaïque FN/TP
#       ├── charts.py      — courbes PR/ROC, graphiques per-stage
#       ├── sweep.py       — sweep complet SF × MN
#       └── data_quality.py— qualité des données, fenêtre optimale

from .config import DETECTION_PRESETS, HNM_PRESETS, WINDOW_SIZE
from .environment import validate_environment
from .data_prep import (
    prepare_data, validate_images, split_data,
    augment_data, generate_annotations, generate_bg_file
)
from .training import create_samples, train_cascade, generate_cascade_xml
from .evaluation import evaluate_model, test_model, generate_model_plaque
from .mining import hard_negative_mining
from .analysis import advanced_model_analysis

__all__ = [
    # Config
    'DETECTION_PRESETS', 'HNM_PRESETS', 'WINDOW_SIZE',
    # Environment
    'validate_environment',
    # Data preparation
    'prepare_data', 'validate_images', 'split_data',
    'augment_data', 'generate_annotations', 'generate_bg_file',
    # Training
    'create_samples', 'train_cascade', 'generate_cascade_xml',
    # Evaluation
    'evaluate_model', 'test_model', 'generate_model_plaque',
    # Mining
    'hard_negative_mining',
    # Analysis
    'advanced_model_analysis',
]
