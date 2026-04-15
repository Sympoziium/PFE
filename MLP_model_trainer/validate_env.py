#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de validation d'environnement pour le pipeline MLP.

Détecte les capacités matérielles et logicielles, génère une configuration
optimale pour l'entraînement (PC) ou l'inférence (Raspberry Pi).

Usage:
    python validate_env.py                  # Détection automatique + configuration
    python validate_env.py --verbose        # Mode verbeux avec diagnostics
    python validate_env.py --apply          # Appliquer les configs au runtime
"""

import json
import os
import sys
import platform
from pathlib import Path


def get_system_info() -> dict:
    """Collecte les informations système de base."""
    try:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
    except Exception:
        cpu_count = 1

    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024**3)
    except Exception:
        ram_gb = 0.5  # Fallback pour Pi

    system_info = {
        "platform": sys.platform,
        "architecture": platform.machine(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "cpu_count": cpu_count,
        "ram_gb": round(ram_gb, 2),
        "os_name": platform.system(),
    }

    return system_info


def detect_pytorch() -> dict:
    """Détecte les capacités PyTorch disponibles."""
    pytorch_info = {
        "available": False,
        "version": None,
        "cuda_available": False,
        "cuda_version": None,
        "device": "cpu",
        "num_threads": 1,
    }

    try:
        import torch
        pytorch_info["available"] = True
        pytorch_info["version"] = torch.__version__

        # CUDA
        if torch.cuda.is_available():
            pytorch_info["cuda_available"] = True
            pytorch_info["cuda_version"] = torch.version.cuda
            pytorch_info["device"] = f"cuda:{torch.cuda.current_device()}"
            pytorch_info["gpu_name"] = torch.cuda.get_device_name(0)
            pytorch_info["gpu_memory_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / (1024**3), 2
            )

        # Threads CPU
        try:
            pytorch_info["num_threads"] = torch.get_num_threads()
        except Exception:
            pytorch_info["num_threads"] = 4

    except ImportError:
        pass

    return pytorch_info


def detect_tensorflow() -> dict:
    """Détecte les capacités TensorFlow disponibles."""
    tf_info = {
        "available": False,
        "version": None,
        "gpu_available": False,
        "gpus": [],
        "num_threads": 1,
    }

    try:
        import tensorflow as tf
        tf_info["available"] = True
        tf_info["version"] = tf.__version__

        # GPU
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            tf_info["gpu_available"] = True
            tf_info["gpus"] = [gpu.name for gpu in gpus]

        # Threads (limiter pour ne pas bloquer le système)
        try:
            tf_info["num_threads"] = min(4, os.cpu_count() or 4)
        except Exception:
            tf_info["num_threads"] = 4

    except ImportError:
        pass

    return tf_info


def detect_tflite() -> dict:
    """Détecte les capacités TFLite (notamment sur Pi)."""
    tflite_info = {
        "available": False,
        "version": None,
        "delegates": ["cpu"],  # CPU toujours disponible
        "num_threads_recommended": 1,
    }

    try:
        import tflite_runtime as tf
        tflite_info["available"] = True
        tflite_info["version"] = tf.__version__

        # Tester XNNPACK (optimisé sur ARM)
        try:
            # XNNPACK est généralement disponible dans TFLite
            tflite_info["delegates"].append("xnnpack")
        except Exception:
            pass

        # NNAPI (Android/certains systèmes)
        try:
            if sys.platform != "win32":
                tflite_info["delegates"].append("nnapi")
        except Exception:
            pass

        # Recommandation nombre de threads
        cpu_count = os.cpu_count() or 4
        # Sur Pi Zero 2 (4 cœurs), utiliser 2-3 threads pour ne pas bloquer
        tflite_info["num_threads_recommended"] = min(max(1, cpu_count - 1), 4)

    except ImportError:
        pass

    return tflite_info


def is_raspberry_pi() -> bool:
    """Détecte si on est sur un Raspberry Pi."""
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().lower()
            return "raspberry pi" in model
    except Exception:
        return False


def detect_pi_model() -> str:
    """Détecte le modèle spécifique du Pi."""
    try:
        with open("/proc/device-tree/model", "r") as f:
            return f.read().strip()
    except Exception:
        return "Unknown Pi"


def generate_recommendations(system_info: dict, pytorch_info: dict, tf_info: dict, tflite_info: dict) -> dict:
    """Génère des recommandations basées sur la détection."""
    recommendations = {
        "batch_size": 32,
        "learning_rate": 1e-3,
        "weight_decay": 1e-4,
        "num_epochs": 100,
        "early_stopping_patience": 20,
        "inference_latency_target_ms": None,
    }

    # Adapter batch_size selon la RAM
    ram_gb = system_info.get("ram_gb", 4)
    if ram_gb < 2:
        recommendations["batch_size"] = 16
    elif ram_gb < 4:
        recommendations["batch_size"] = 32
    else:
        recommendations["batch_size"] = 64

    # Cible de latence pour TFLite
    if is_raspberry_pi():
        recommendations["inference_latency_target_ms"] = 10
    else:
        recommendations["inference_latency_target_ms"] = None

    # Adapter learning rate si GPU disponible
    if pytorch_info.get("cuda_available") or tf_info.get("gpu_available"):
        recommendations["learning_rate"] = 1e-2

    return recommendations


def generate_config(verbose: bool = False) -> dict:
    """Génère la configuration complète d'environnement."""
    print("\n" + "=" * 70)
    print("VALIDATION D'ENVIRONNEMENT MLP")
    print("=" * 70 + "\n")

    # Collecte d'info
    system_info = get_system_info()
    pytorch_info = detect_pytorch()
    tf_info = detect_tensorflow()
    tflite_info = detect_tflite()
    recommendations = generate_recommendations(system_info, pytorch_info, tf_info, tflite_info)

    # Affichage
    print("📊 SYSTÈME")
    print(f"  Platform: {system_info['os_name']} ({system_info['architecture']})")
    print(f"  Python: {system_info['python_version']}")
    print(f"  CPU: {system_info['cpu_count']} cœurs")
    print(f"  RAM: {system_info['ram_gb']} GB")

    if is_raspberry_pi():
        print(f"  🍓 Détecté: {detect_pi_model()}")
    print()

    print("🔧 PYTORCH")
    if pytorch_info["available"]:
        print(f"  ✅ Disponible: {pytorch_info['version']}")
        print(f"  Device: {pytorch_info['device']}")
        if pytorch_info["cuda_available"]:
            print(f"  🎮 CUDA: {pytorch_info['cuda_version']}")
            print(f"  GPU: {pytorch_info['gpu_name']}")
            print(f"  GPU Memory: {pytorch_info['gpu_memory_gb']} GB")
        else:
            print(f"  CPU Mode (CUDA non disponible)")
        print(f"  Threads: {pytorch_info['num_threads']}")
    else:
        print(f"  ❌ Non disponible")
    print()

    print("🔧 TENSORFLOW")
    if tf_info["available"]:
        print(f"  ✅ Disponible: {tf_info['version']}")
        if tf_info["gpu_available"]:
            print(f"  🎮 GPUs détectés: {', '.join(tf_info['gpus'])}")
        else:
            print(f"  CPU Mode")
        print(f"  Threads: {tf_info['num_threads']}")
    else:
        print(f"  ❌ Non disponible")
    print()

    print("⚡ TENSORFLOW LITE")
    if tflite_info["available"]:
        print(f"  ✅ Disponible: {tflite_info['version']}")
        print(f"  Delegates: {', '.join(tflite_info['delegates'])}")
        print(f"  Threads recommandés: {tflite_info['num_threads_recommended']}")
    else:
        print(f"  ❌ Non disponible")
    print()

    print("💡 RECOMMANDATIONS")
    print(f"  Batch Size: {recommendations['batch_size']}")
    print(f"  Learning Rate: {recommendations['learning_rate']}")
    if recommendations['inference_latency_target_ms']:
        print(f"  Latence Cible (TFLite): {recommendations['inference_latency_target_ms']} ms")
    print()

    # Configuration complète
    config = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "system": system_info,
        "pytorch": pytorch_info,
        "tensorflow": tf_info,
        "tflite": tflite_info,
        "recommendations": recommendations,
        "device_type": "raspberry_pi" if is_raspberry_pi() else "pc",
    }

    if verbose:
        print("📋 Configuration complète (JSON):")
        print(json.dumps(config, indent=2))
        print()

    return config


def save_config(config: dict, output_path: Path = None) -> Path:
    """Sauvegarde la config en JSON."""
    if output_path is None:
        output_path = Path(__file__).parent / "environment_config.json"

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Configuration sauvegardée: {output_path}")
    return output_path


def load_config(config_path: Path = None) -> dict:
    """Charge la configuration depuis JSON."""
    if config_path is None:
        config_path = Path(__file__).parent / "environment_config.json"

    if not config_path.exists():
        print(f"⚠️  Fichier config non trouvé: {config_path}")
        return None

    with open(config_path, "r") as f:
        return json.load(f)


def apply_pytorch_config(config: dict) -> None:
    """Applique les paramètres PyTorch optimaux."""
    if not config["pytorch"]["available"]:
        return

    import torch

    torch.set_num_threads(config["pytorch"]["num_threads"])

    if config["pytorch"]["cuda_available"]:
        torch.cuda.set_device(0)

    print(f"[PyTorch] Configuré: device={config['pytorch']['device']}, threads={config['pytorch']['num_threads']}")


def apply_tensorflow_config(config: dict) -> None:
    """Applique les paramètres TensorFlow optimaux."""
    if not config["tensorflow"]["available"]:
        return

    import tensorflow as tf

    tf.config.threading.set_intra_op_parallelism_threads(config["tensorflow"]["num_threads"])
    tf.config.threading.set_inter_op_parallelism_threads(1)

    # Désactiver le logging verbeux
    tf.get_logger().setLevel("ERROR")

    print(f"[TensorFlow] Configuré: threads={config['tensorflow']['num_threads']}")


def get_tflite_config(config: dict) -> dict:
    """Retourne la configuration TFLite optimale à utiliser."""
    if not config["tflite"]["available"]:
        return {}

    return {
        "num_threads": config["tflite"]["num_threads_recommended"],
        "allow_fp16": config["device_type"] == "raspberry_pi",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validation d'environnement MLP")
    parser.add_argument("--verbose", action="store_true", help="Mode verbeux")
    parser.add_argument("--apply", action="store_true", help="Appliquer les configs")
    
    args = parser.parse_args()

    # Générer la config
    config = generate_config(verbose=args.verbose)

    # Toujours sauvegarder
    save_config(config)
    
    # Appliquer si demandé
    if args.apply:
        print("\n🔧 Application des configurations...")
        try:
            apply_pytorch_config(config)
        except Exception as e:
            print(f"⚠️  PyTorch: {e}")

        try:
            apply_tensorflow_config(config)
        except Exception as e:
            print(f"⚠️  TensorFlow: {e}")

    print("\n" + "=" * 70)
    print("✅ Validation terminée!")
    print("=" * 70 + "\n")

    return config


if __name__ == "__main__":
    main()