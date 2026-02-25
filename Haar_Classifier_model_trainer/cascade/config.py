# cascade/config.py
# ---------------------
# Constantes et préconfigurations pour le module d'entraînement Haar/LBP.

# ══════════════════════════════════════════════════════════════════════
#  CONSTANTES — Préconfigurations de détection (scaleFactor, minNeighbors)
# ══════════════════════════════════════════════════════════════════════
# Ces préréglages sont utilisés UNIFORMÉMENT dans :
#   - L'évaluation post-entraînement
#   - L'analyse avancée
#   - La génération de la plaque du modèle
#   - Les recommandations d'utilisation
#
# scaleFactor : facteur de réduction de l'image à chaque échelle de la pyramide.
#   Plus proche de 1.0 = plus d'échelles scannées = meilleur recall mais plus lent.
#
# minNeighbors : nombre minimum de détections voisines pour confirmer un objet.
#   Plus élevé = plus discriminant = moins de faux positifs mais risque de FN.
#
DETECTION_PRESETS = {
    'sensible':  {'sf': 1.05, 'mn': 3, 'label': 'Sensible',  'desc': 'Max recall, plus de FP, plus lent'},
    'equilibre': {'sf': 1.10, 'mn': 5, 'label': 'Équilibré', 'desc': 'Compromis recall/précision'},
    'strict':    {'sf': 1.20, 'mn': 7, 'label': 'Strict',    'desc': 'Max précision, plus rapide, risque de FN'},
}

# Préréglages spécifiques au Hard Negative Mining (plus agressifs pour capturer un max de FP)
HNM_PRESETS = {
    'sensible':  {'sf': 1.05, 'mn': 1, 'label': 'Sensible',  'desc': 'Max de crops, peut être bruité'},
    'equilibre': {'sf': 1.10, 'mn': 3, 'label': 'Équilibré', 'desc': 'Recommandé'},
    'strict':    {'sf': 1.20, 'mn': 5, 'label': 'Strict',    'desc': 'Moins de crops, plus fiables'},
}

# Taille de la fenêtre de détection (doit être adaptée à la taille des objets dans les images positives)
WINDOW_SIZE = {
    'min': (12, 24),          # Taille minimale de la fenêtre de détection
    'recommended': (16, 30),  # Taille recommandée basée sur l'analyse des images positives
    'max': (24, 42),          # Taille maximale de la fenêtre de détection
}
