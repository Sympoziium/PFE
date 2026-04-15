#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

"""
Conversion du modèle PyTorch vers TensorFlow Lite.

Pipeline: PyTorch → TensorFlow SavedModel → TFLite

Usage:
    python convert_to_tflite.py                           # Utilise le meilleur modèle par défaut
    python convert_to_tflite.py --model checkpoints/best_model.pt
    python convert_to_tflite.py --quantize                # Quantization int8 pour Pi Zero
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import torch

# Import du modèle local
from model import ZumiMLP


def load_pytorch_model(model_path: Path) -> tuple:
    """Charge le modèle PyTorch depuis un checkpoint.

    Si le modèle utilise BatchNorm, les couches BN sont automatiquement
    fusionnées dans les couches Linear pour l'export TFLite.

    Returns:
        tuple: (model, checkpoint_data)
    """
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)

    use_batchnorm = checkpoint.get('use_batchnorm', False)

    model = ZumiMLP(
        input_dim=checkpoint['input_dim'],
        output_dim=checkpoint['output_dim'],
        hidden_dims=checkpoint['hidden_dims'],
        use_batchnorm=use_batchnorm
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    # Fusionner BatchNorm pour export (le modele TF ne contient que Dense+GELU)
    if use_batchnorm:
        print(f"[Load] BatchNorm detecte, fusion dans les couches Linear...")
        model = model.fuse_batchnorm()

    print(f"[Load] Modèle chargé: {model_path}")
    print(f"       Input: {checkpoint['input_dim']}, Output: {checkpoint['output_dim']}")
    print(f"       Hidden: {checkpoint['hidden_dims']}")
    print(f"       BatchNorm: {use_batchnorm} (fusionne pour export)")
    print(f"       Val loss: {checkpoint['val_loss']:.6f}")

    return model, checkpoint


def export_to_savedmodel(model: torch.nn.Module, input_dim: int, output_path: Path, hidden_dims: list, output_dim: int):
    """Exporte le modèle PyTorch vers TensorFlow SavedModel.

    Approche: Crée un modèle TensorFlow équivalent avec les mêmes weights et architecture.
    TFLite ne peut pas utiliser tf.py_function, donc on crée un vrai modèle TensorFlow.

    Args:
        model: Modèle PyTorch à convertir
        input_dim: Dimension d'entrée
        output_path: Chemin de sortie pour le SavedModel
        hidden_dims: Liste des dimensions des couches cachées (ex: [128, 64, 32])
        output_dim: Dimension de sortie (ex: 2)
    """
    try:
        import tensorflow as tf
    except ImportError as e:
        print("Erreur: tensorflow non installé. Installez avec:")
        print("  pip install tensorflow>=2.13.0")
        print(f"  Détails: {e}")
        sys.exit(1)

    # Nettoyer si le répertoire existe déjà
    if output_path.exists():
        shutil.rmtree(output_path)

    # Créer un modèle TensorFlow équivalent dynamiquement
    # Architecture: Input → [Dense(hidden, GELU)] × N → Dense(output, Tanh)
    tf_model = tf.keras.Sequential()
    tf_model.add(tf.keras.layers.Input(shape=(input_dim,)))

    for hidden_dim in hidden_dims:
        tf_model.add(tf.keras.layers.Dense(hidden_dim, activation='gelu'))

    tf_model.add(tf.keras.layers.Dense(output_dim, activation='tanh'))

    print(f"[TF Model] Architecture: {input_dim} → {' → '.join(map(str, hidden_dims))} → {output_dim}")

    # Copier les poids du modèle PyTorch
    # Itérer sur les couches PyTorch
    torch_params = list(model.parameters())
    param_idx = 0

    for layer in tf_model.layers:
        if isinstance(layer, tf.keras.layers.Dense):
            # Dense a weight et bias
            # PyTorch: Linear(in, out) → weight shape (out, in), bias shape (out,)
            # TensorFlow: Dense(out, in) → kernel shape (in, out), bias shape (out,)

            if param_idx < len(torch_params):
                weight_torch = torch_params[param_idx].cpu().detach().numpy()
                param_idx += 1

                # Transpose car PyTorch utilise (out, in) et TensorFlow (in, out)
                weight_tf = weight_torch.T.astype(np.float32)
                layer.kernel.assign(weight_tf)

            if param_idx < len(torch_params):
                bias_torch = torch_params[param_idx].cpu().detach().numpy().astype(np.float32)
                param_idx += 1
                layer.bias.assign(bias_torch)

    # Sauvegarder le modèle
    try:
        # Utiliser export() pour créer un SavedModel compatible avec TFLite
        tf_model.export(str(output_path))
        print(f"[SavedModel] Créé: {output_path}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde SavedModel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def convert_savedmodel_to_tflite(
    savedmodel_path: Path,
    tflite_path: Path,
    quantize: bool = False,
    input_dim: int = 21
):
    """Convertit TensorFlow SavedModel vers TFLite.

    Args:
        savedmodel_path: Chemin vers le SavedModel
        tflite_path: Chemin de sortie .tflite
        quantize: Appliquer la quantization int8
        input_dim: Dimension d'entrée pour la calibration
    """
    try:
        import tensorflow as tf
    except ImportError as e:
        print("Erreur: tensorflow non installé. Installez avec:")
        print("  pip install tensorflow>=2.13.0")
        print(f"  Détails: {e}")
        sys.exit(1)

    converter = tf.lite.TFLiteConverter.from_saved_model(str(savedmodel_path))

    # La quantization int8 permet de réduire drastiquement la taille du modèle en convertissant les paramètres
    # du modèle qui lors de l'entrainement sont en float32 en int8. Cela est particulièrement bénéfique pour 
    # les microcontrôleurs ou les processeurs à ressources limitées comme le Raspberry Pi Zero.
    if quantize:
        # Quantization dynamique (pas besoin de données de calibration)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]

        # Pour une quantization full int8, fournir des données représentatives
        def representative_dataset():
            for _ in range(100):
                data = np.random.uniform(-1, 1, (1, input_dim)).astype(np.float32)
                yield [data]

        converter.representative_dataset = representative_dataset
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.float32  # Garder float en entrée/sortie
        converter.inference_output_type = tf.float32

        print("[TFLite] Quantization INT8 activée")

    tflite_model = converter.convert()

    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)

    size_kb = tflite_path.stat().st_size / 1024
    print(f"[TFLite] Modèle créé: {tflite_path} ({size_kb:.1f} KB)")


def verify_tflite_model(tflite_path: Path, input_dim: int):
    """Vérifie que le modèle TFLite fonctionne correctement."""
    try:
        import tensorflow as tf
    except ImportError:
        print("Vérification ignorée: tensorflow non installé")
        return

    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"\n[Verification] Modèle TFLite:")
    print(f"  Input: {input_details[0]['shape']} ({input_details[0]['dtype']})")
    print(f"  Output: {output_details[0]['shape']} ({output_details[0]['dtype']})")

    # Test avec des données aléatoires
    test_input = np.random.uniform(-1, 1, (1, input_dim)).astype(np.float32)
    interpreter.set_tensor(input_details[0]['index'], test_input)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])

    print(f"  Test input: {test_input.flatten()[:4]}...")
    print(f"  Test output: {output.flatten()}")
    print(f"  Output range: [{output.min():.3f}, {output.max():.3f}]")


def export_normalization_stats(checkpoint: dict, output_dir: Path) -> bool:
    """Exporte les statistiques de normalisation z-score depuis le checkpoint.

    Crée normalization_stats.json à côté du .tflite pour que ml_controller
    puisse appliquer la même normalisation à l'inférence.

    Args:
        checkpoint: Données du checkpoint PyTorch
        output_dir: Répertoire de sortie (même que le .tflite)

    Returns:
        bool: True si les stats ont été exportées
    """
    if 'feature_mean' not in checkpoint or 'feature_std' not in checkpoint:
        print("[NormStats] Pas de stats de normalisation dans le checkpoint (ancien modèle?).")
        return False

    stats = {
        "feature_mean": checkpoint['feature_mean'],
        "feature_std": checkpoint['feature_std'],
        "input_dim": checkpoint['input_dim'],
        "feature_mask": checkpoint.get('feature_mask'),
        "motor_speed_max": checkpoint.get('motor_speed_max', 50.0),
        # Constantes de feature engineering (pour ml_controller.py)
        "ir_offset_bottom": checkpoint.get('ir_offset_bottom', -17.0),
        "gap_threshold": checkpoint.get('gap_threshold', 195.0),
        "off_road_threshold": checkpoint.get('off_road_threshold', 120.0),
        "grass_threshold": checkpoint.get('grass_threshold', 140.0),
        "feature_version": checkpoint.get('feature_version', 1),
        # Metadonnees fenetre glissante
        "mode": checkpoint.get('mode', 'sliding_window'),
        "window_size": checkpoint.get('window_size', 25),
        "window_feature_dim": checkpoint.get('window_feature_dim', 26),
        "temporal_decay": checkpoint.get('temporal_decay', 0.95),
        # Exclusion detection
        "exclude_detection": checkpoint.get('exclude_detection', False),
        "detection_indices": checkpoint.get('detection_indices', list(range(8, 16))),
    }

    stats_path = output_dir / "normalization_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"[NormStats] Exporté: {stats_path}")
    print(f"[NormStats] input_dim={stats['input_dim']}, "
          f"{len(stats['feature_mean'])} features")

    return True


def deploy_to_models_dir(export_dir: Path, script_dir: Path):
    """Copie les fichiers exportes vers core/control/controlers/models/.

    Remplace les fichiers existants pour que le modele soit pret a
    etre stage et push via git pour deploiement sur le robot.
    """
    models_dir = script_dir.parent / "core" / "control" / "controlers" / "models"
    if not models_dir.exists():
        print(f"[Deploy] Repertoire non trouve: {models_dir}")
        return False

    files_to_deploy = [
        ("zumi_mlp.tflite", "zumi_mlp.tflite"),
        ("normalization_stats.json", "normalization_stats.json"),
    ]

    deployed = 0
    for src_name, dst_name in files_to_deploy:
        src = export_dir / src_name
        dst = models_dir / dst_name

        if not src.exists():
            print(f"[Deploy] Source non trouvee: {src}")
            continue

        # Supprimer l'ancien fichier s'il existe
        if dst.exists():
            dst.unlink()

        shutil.copy2(src, dst)
        deployed += 1
        print(f"[Deploy] {src_name} -> {dst}")

    print(f"[Deploy] {deployed} fichier(s) deploye(s) dans {models_dir}")
    return deployed > 0


def main():
    parser = argparse.ArgumentParser(description="Conversion PyTorch → TFLite")
    parser.add_argument("--model", type=str, default="checkpoints/best_model.pt",
                        help="Chemin vers le modèle PyTorch")
    parser.add_argument("--output-dir", type=str, default="export",
                        help="Répertoire de sortie")
    parser.add_argument("--quantize", action="store_true",
                        help="Appliquer la quantization int8")
    parser.add_argument("--skip-verification", action="store_true",
                        help="Sauter la vérification finale")

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    model_path = script_dir / args.model
    output_dir = script_dir / args.output_dir

    if not model_path.exists():
        print(f"Erreur: modèle non trouvé: {model_path}")
        print("Lancez d'abord l'entraînement avec: python train.py")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Chemins de sortie (toujours zumi_mlp.tflite, meme avec quantization)
    savedmodel_path = output_dir / "zumi_mlp_tf"
    tflite_name = "zumi_mlp.tflite"
    tflite_path = output_dir / tflite_name

    print("=" * 60)
    print("Conversion PyTorch → TFLite")
    print("=" * 60)

    # 1. Charger le modèle PyTorch
    model, checkpoint = load_pytorch_model(model_path)
    input_dim = checkpoint['input_dim']
    output_dim = checkpoint['output_dim']
    hidden_dims = checkpoint['hidden_dims']

    # 2. Exporter vers TensorFlow SavedModel
    export_to_savedmodel(model, input_dim, savedmodel_path, hidden_dims, output_dim)

    # 3. Convertir TensorFlow → TFLite
    convert_savedmodel_to_tflite(savedmodel_path, tflite_path, quantize=args.quantize, input_dim=input_dim)

    # 4. Exporter les stats de normalisation z-score
    export_normalization_stats(checkpoint, output_dir)

    # 5. Vérification
    if not args.skip_verification:
        verify_tflite_model(tflite_path, input_dim)

    # 6. Deployer vers core/control/controlers/models/
    print()
    deploy_to_models_dir(output_dir, script_dir)

    print("\n" + "=" * 60)
    print("Conversion terminée!")
    print(f"Fichier TFLite: {tflite_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
