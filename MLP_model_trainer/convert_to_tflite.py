#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Conversion du modèle PyTorch vers TensorFlow Lite.

Pipeline: PyTorch → TensorFlow SavedModel → TFLite

Usage:
    python convert_to_tflite.py                           # Utilise le meilleur modèle par défaut
    python convert_to_tflite.py --model checkpoints/best_model.pt
    python convert_to_tflite.py --quantize                # Quantization int8 pour Pi Zero
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

# Import du modèle local
from model import ZumiMLP


def load_pytorch_model(model_path: Path) -> tuple:
    """Charge le modèle PyTorch depuis un checkpoint.

    Returns:
        tuple: (model, checkpoint_data)
    """
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)

    model = ZumiMLP(
        input_dim=checkpoint['input_dim'],
        output_dim=checkpoint['output_dim'],
        hidden_dims=checkpoint['hidden_dims']
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    print(f"[Load] Modèle chargé: {model_path}")
    print(f"       Input: {checkpoint['input_dim']}, Output: {checkpoint['output_dim']}")
    print(f"       Hidden: {checkpoint['hidden_dims']}")
    print(f"       Val loss: {checkpoint['val_loss']:.6f}")

    return model, checkpoint


def export_to_savedmodel(model: torch.nn.Module, input_dim: int, output_path: Path):
    """Exporte le modèle PyTorch vers TensorFlow SavedModel.

    Cette approche contourne le besoin de onnx-tf (qui n'existe pas pour Python 3.13).
    On crée une fonction traçable PyTorch puis la convertit.
    """
    try:
        import tensorflow as tf
        from tensorflow.python.framework import conversion_util
    except ImportError:
        print("Erreur: tensorflow non installé. Installez avec:")
        print("  pip install tensorflow>=2.13.0")
        sys.exit(1)

    # 1. Créer une entrée factice
    dummy_input = torch.randn(1, input_dim).float()

    # 2. Tracer le modèle
    traced_model = torch.jit.trace(model, dummy_input)

    # 3. Convertir via le format intermédiaire numpy
    # On va créer un wrapper TensorFlow qui imite le modèle PyTorch
    class MLPWrapper(tf.Module):
        def __init__(self, torch_model, input_dim):
            super().__init__()
            self.torch_model = torch_model
            self.input_dim = input_dim

        @tf.function(input_signature=[
            tf.TensorSpec(shape=[None, input_dim], dtype=tf.float32, name='state')
        ])
        def __call__(self, x):
            # Convertir en PyTorch tensor
            x_torch = torch.from_numpy(x.numpy()).float()

            # Inférence PyTorch
            with torch.no_grad():
                y_torch = self.torch_model(x_torch)

            # Convertir en numpy puis TF tensor
            return tf.constant(y_torch.numpy(), dtype=tf.float32)

    # 4. Créer et exporter
    wrapper = MLPWrapper(traced_model, input_dim)
    tf.saved_model.save(wrapper, str(output_path), signatures=wrapper.__call__)

    print(f"[SavedModel] Créé: {output_path}")


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
    except ImportError:
        print("Erreur: tensorflow non installé. Installez avec:")
        print("  pip install tensorflow>=2.13.0")
        sys.exit(1)

    converter = tf.lite.TFLiteConverter.from_saved_model(str(savedmodel_path))

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

    # Chemins de sortie
    savedmodel_path = output_dir / "zumi_mlp_tf"
    tflite_name = "zumi_mlp_quant.tflite" if args.quantize else "zumi_mlp.tflite"
    tflite_path = output_dir / tflite_name

    print("=" * 60)
    print("Conversion PyTorch → TFLite")
    print("=" * 60)

    # 1. Charger le modèle PyTorch
    model, checkpoint = load_pytorch_model(model_path)
    input_dim = checkpoint['input_dim']

    # 2. Exporter vers TensorFlow SavedModel
    export_to_savedmodel(model, input_dim, savedmodel_path)

    # 3. Convertir TensorFlow → TFLite
    convert_savedmodel_to_tflite(savedmodel_path, tflite_path, quantize=args.quantize, input_dim=input_dim)

    # 4. Vérification
    if not args.skip_verification:
        verify_tflite_model(tflite_path, input_dim)

    print("\n" + "=" * 60)
    print("Conversion terminée!")
    print(f"Fichier TFLite: {tflite_path}")
    print("=" * 60)

    # Instructions de déploiement
    print("\nPour déployer sur le robot:")
    print(f"  scp {tflite_path} pi@<ip_robot>:~/robot/models/")


if __name__ == "__main__":
    main()

