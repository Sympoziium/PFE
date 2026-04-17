#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'agrégation modulaire des séquences d'entraînement.

Consolide les fichiers captures.jsonl et labels.jsonl des dossiers de
séquences sampling_* organisés par scénario.

Structure de répertoires supportée:
    sequences/
      baseline/
        sampling 01/ -> captures.jsonl, labels.jsonl
        sampling 02/
        ...
      pieton/
        sampling 01/
        ...
      ...

Usage:
    python aggregate_sequences.py                      # Tous les scenarios
    python aggregate_sequences.py --scenario baseline   # Scenario spécifique
    python aggregate_sequences.py --output-dir ./data   # Sortie personnalisée
    python aggregate_sequences.py --list               # Lister les scenarios
"""

import json
import argparse
from pathlib import Path


def discover_scenarios(sequences_root: Path) -> list:
    """Découvre tous les scénarios sous sequences_root.

    Un scénario est un dossier qui contient des sous-dossiers sampling_*.
    """
    scenarios = []

    if not sequences_root.exists():
        return scenarios

    for item in sorted(sequences_root.iterdir()):
        if item.is_dir():
            # Vérifier que le dossier contient au moins un sampling *
            sampling_dirs = list(item.glob('sampling *'))
            if sampling_dirs:
                scenarios.append(item.name)

    return scenarios


def aggregate_scenario(scenario_dir: Path, scenario_name: str,
                       add_scenario_id: bool = False, verbose: bool = True):
    """
    Agrège tous les fichiers captures.jsonl et labels.jsonl d'un scénario.

    Args:
        scenario_dir: Répertoire du scénario (ex: sequences/baseline/)
        scenario_name: Nom du scénario pour traçabilité
        add_scenario_id: Ajouter une colonne scenario_id aux captures
        verbose: Afficher les informations

    Returns:
        tuple: (all_captures, all_labels, sequence_stats) ou (None, None, {}) en cas erreur
    """

    # Trouver tous les dossiers sampling *
    sampling_dirs = sorted([d for d in scenario_dir.iterdir()
                           if d.is_dir() and d.name.startswith('sampling')])

    if not sampling_dirs:
        if verbose:
            print(f"[WARN] Aucun dossier sampling * trouvé dans {scenario_dir}")
        return [], [], {}

    if verbose:
        print(f"[SCENARIO] {scenario_name}: {len(sampling_dirs)} sequences trouvees")

    sequence_stats = {}
    all_captures = []
    all_labels = []
    total_samples = 0

    for seq_dir in sampling_dirs:
        captures_file = seq_dir / "captures.jsonl"
        labels_file = seq_dir / "labels.jsonl"

        if not captures_file.exists() or not labels_file.exists():
            if verbose:
                print(f"  [WARN] {seq_dir.name}: fichiers incomplets")
            continue

        # Charger les captures
        seq_captures = []
        with open(captures_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    seq_captures.append(json.loads(line))

        # Charger les labels
        seq_labels = []
        with open(labels_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    seq_labels.append(json.loads(line))

        # Validation
        if len(seq_captures) != len(seq_labels):
            if verbose:
                print(f"  [WARN] {seq_dir.name}: incohérence (samples mismatch)")
            continue

        n_samples = len(seq_captures)

        # Ajouter scenario_id si demandé
        if add_scenario_id:
            all_captures.extend([c + [scenario_name] for c in seq_captures])
        else:
            all_captures.extend(seq_captures)

        all_labels.extend(seq_labels)
        total_samples += n_samples

        sequence_stats[seq_dir.name] = {
            'samples': n_samples,
            'scenario': scenario_name
        }

        if verbose:
            print(f"  [OK] {seq_dir.name}: {n_samples} echantillons")

    if verbose and total_samples > 0:
        print(f"  [TOTAL] {scenario_name}: {total_samples} echantillons")
        print()

    return all_captures, all_labels, sequence_stats


def aggregate_all_scenarios(sequences_root: Path, output_dir: Path,
                            add_scenario_id: bool = False, verbose: bool = True):
    """
    Agrège tous les scénarios trouvés sous sequences_root.

    Crée:
    - data/captures.jsonl + data/labels.jsonl  (global)
    - data/baseline_captures.jsonl + data/baseline_labels.jsonl (par scenario)
    - etc.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    # Nettoyer les fichiers augmentes et le global stale avant re-agregation.
    # Sans ca, l'augmentation precedente reste fusionnee dans train/captures.jsonl
    # et le menu affiche un compte d'echantillons obsolete.
    train_dir = output_dir / "train"
    val_dir = output_dir / "val"
    stale_files = [
        output_dir / "captures.jsonl",
        output_dir / "labels.jsonl",
        output_dir / "sequence_ids.jsonl",
        output_dir / "augmentation_log.json",
    ]
    for subdir in [train_dir, val_dir]:
        if subdir.exists():
            for f in subdir.glob("*_augmented.jsonl"):
                stale_files.append(f)
            for f in subdir.glob("augmentation_log.json"):
                stale_files.append(f)

    removed = 0
    for f in stale_files:
        if f.exists():
            f.unlink()
            removed += 1
    if removed and verbose:
        print(f"[CLEAN] {removed} fichiers stale/augmentes supprimes")

    # Découvrir les scénarios
    scenarios = discover_scenarios(sequences_root)

    if not scenarios:
        print("[ERREUR] Aucun scenario trouve!")
        return False

    if verbose:
        print(f"[SCENARIOS] Trouves: {', '.join(scenarios)}")
        print()

    # Agrégation globale
    global_captures = []
    global_labels = []
    all_scenario_stats = {}

    # Agréger chaque scénario
    for scenario_name in scenarios:
        scenario_dir = sequences_root / scenario_name

        captures, labels, stats = aggregate_scenario(
            scenario_dir, scenario_name,
            add_scenario_id=add_scenario_id,
            verbose=verbose
        )

        if captures:
            global_captures.extend(captures)
            global_labels.extend(labels)
            all_scenario_stats[scenario_name] = stats

            # Sauvegarder les fichiers du scénario individuellement
            scenario_captures_file = output_dir / f"{scenario_name}_captures.jsonl"
            scenario_labels_file = output_dir / f"{scenario_name}_labels.jsonl"

            with open(scenario_captures_file, 'w') as f:
                for capture in captures:
                    f.write(json.dumps(capture) + '\n')

            with open(scenario_labels_file, 'w') as f:
                for label in labels:
                    f.write(json.dumps(label) + '\n')

            if verbose:
                print(f"  -> {scenario_captures_file}")
                print(f"  -> {scenario_labels_file}")
                print()

    if not global_captures:
        print("[ERREUR] Aucune donnee a agreger!")
        return False

    # Generer les IDs de sequence pour chaque echantillon
    global_seq_ids = []
    seq_id_map = {}  # "scenario/seq_name" -> int
    next_id = 0

    for scenario_name, stats in all_scenario_stats.items():
        for seq_name, seq_info in stats.items():
            full_name = f"{scenario_name}/{seq_name}"
            seq_id_map[full_name] = next_id
            for _ in range(seq_info['samples']):
                global_seq_ids.append(next_id)
            next_id += 1

    global_seq_ids = [int(s) for s in global_seq_ids]

    # Sauvegarder le mapping ID -> nom de sequence
    seq_map_file = output_dir / "sequence_map.json"
    id_to_name = {v: k for k, v in seq_id_map.items()}
    with open(seq_map_file, 'w') as f:
        json.dump({
            "n_sequences": next_id,
            "n_samples": len(global_seq_ids),
            "id_to_name": {str(k): v for k, v in id_to_name.items()},
            "name_to_id": seq_id_map,
        }, f, indent=2)

    if verbose:
        print(f"[SEQ-IDS] {next_id} sequences uniques, {len(global_seq_ids)} echantillons")

    # ══════════════════════════════════════════════════════════════
    #  Split train/val par sequence entiere
    # ══════════════════════════════════════════════════════════════
    import numpy as np

    seq_ids_arr = np.array(global_seq_ids, dtype=np.int32)
    unique_seqs = list(range(next_id))

    # Charger l'historique de split si disponible
    history_path = output_dir / "split_history.json"
    known_train = set()
    known_val = set()
    load_split_history = input("Charger l'historique de split ? (y/n): ").lower() == 'y'  # A activer pour conserver les splits entre runs (utile pour augmentation)
    
    if history_path.exists() and load_split_history:
        with open(history_path, 'r') as f:
            history = json.load(f)
        known_train = set(history.get('train_sequences', []))
        known_val = set(history.get('val_sequences', []))
        if verbose:
            print(f"[SPLIT] Historique chargé: {len(known_train)} train, {len(known_val)} val")

    train_seqs = [s for s in unique_seqs if s in known_train]
    val_seqs = [s for s in unique_seqs if s in known_val]
    new_seqs = [s for s in unique_seqs if s not in known_train and s not in known_val]

    # Repartir les nouvelles sequences (90/10)
    if new_seqs:
        rng = __import__('random')
        rng.seed(42)
        rng.shuffle(new_seqs)

        # Compter les samples par sequence
        seq_sample_counts = {}
        for sid in unique_seqs:
            seq_sample_counts[sid] = int(np.sum(seq_ids_arr == sid))

        train_n = sum(seq_sample_counts.get(s, 0) for s in train_seqs)
        total_n = len(global_seq_ids)
        target_train = int(total_n * 0.90)

        for sid in new_seqs:
            if train_n < target_train:
                train_seqs.append(sid)
                train_n += seq_sample_counts.get(sid, 0)
            else:
                val_seqs.append(sid)

        if verbose:
            print(f"[SPLIT] {len(new_seqs)} nouvelles sequences reparties")

    # Sauvegarder l'historique
    with open(history_path, 'w') as f:
        json.dump({
            'train_sequences': sorted(train_seqs),
            'val_sequences': sorted(val_seqs),
        }, f, indent=2)

    # Ecrire dans data/train/ et data/val/
    train_set = set(train_seqs)
    train_dir = output_dir / "train"
    val_dir = output_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    n_train = 0
    n_val = 0

    train_cap_f = open(train_dir / "captures.jsonl", 'w')
    train_lab_f = open(train_dir / "labels.jsonl", 'w')
    train_sid_f = open(train_dir / "sequence_ids.jsonl", 'w')
    val_cap_f = open(val_dir / "captures.jsonl", 'w')
    val_lab_f = open(val_dir / "labels.jsonl", 'w')
    val_sid_f = open(val_dir / "sequence_ids.jsonl", 'w')

    for i in range(len(global_captures)):
        cap_line = json.dumps(global_captures[i]) + '\n'
        lab_line = json.dumps(global_labels[i]) + '\n'
        sid_line = str(global_seq_ids[i]) + '\n'

        if global_seq_ids[i] in train_set:
            train_cap_f.write(cap_line)
            train_lab_f.write(lab_line)
            train_sid_f.write(sid_line)
            n_train += 1
        else:
            val_cap_f.write(cap_line)
            val_lab_f.write(lab_line)
            val_sid_f.write(sid_line)
            n_val += 1

    for f in [train_cap_f, train_lab_f, train_sid_f,
              val_cap_f, val_lab_f, val_sid_f]:
        f.close()

    if verbose:
        print(f"[SPLIT] {len(train_seqs)} train / {len(val_seqs)} val sequences")
        print(f"[SPLIT] {n_train} train / {n_val} val echantillons")
        print(f"  -> {train_dir}/")
        print(f"  -> {val_dir}/")
        print()

        # Resume statistiques
        total_samples = n_train + n_val
        print(f"[STATS] Resume global:")
        print(f"  * Total scenarios: {len(scenarios)}")
        print(f"  * Total echantillons: {total_samples}")
        print(f"  * Train: {n_train} ({n_train/total_samples*100:.1f}%)")
        print(f"  * Val:   {n_val} ({n_val/total_samples*100:.1f}%)")
        print()

        for scenario_name, stats in all_scenario_stats.items():
            scenario_total = sum(s['samples'] for s in stats.values())
            pct = (scenario_total / total_samples) * 100 if total_samples > 0 else 0
            print(f"  * {scenario_name:15s}: {scenario_total:6d} ({pct:5.1f}%)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Agrege les sequences d'entrainement par scenario"
    )
    parser.add_argument(
        "--sequences-dir",
        type=str,
        default="sequences",
        help="Repertoire racine contenant les scenarios (defaut: sequences)"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Scenario specifique a agreger (defaut: tous)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Repertoire de sortie (defaut: data)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister les scenarios disponibles et quitter"
    )
    parser.add_argument(
        "--add-scenario-id",
        action="store_true",
        help="Ajouter une colonne scenario_id aux captures"
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    sequences_root = script_dir / args.sequences_dir
    output_dir = script_dir / args.output_dir

    # Mode listing
    if args.list:
        scenarios = discover_scenarios(sequences_root)
        if scenarios:
            print("[SCENARIOS] Disponibles:")
            for scenario in scenarios:
                n_seqs = len(list((sequences_root / scenario).glob('sampling_*')))
                print(f"  * {scenario:15s}: {n_seqs} sequences")
        else:
            print("[INFO] Aucun scenario trouve")
        return True

    if not sequences_root.exists():
        print(f"[ERREUR] Repertoire non trouve: {sequences_root}")
        return False

    print(f"[*] Agregation des sequences")
    print(f"{'='*70}")
    print(f"Source: {sequences_root}")
    print(f"Destination: {output_dir}")
    print(f"{'='*70}")
    print()

    # Mode scénario spécifique
    if args.scenario:
        scenario_dir = sequences_root / args.scenario
        if not scenario_dir.exists():
            print(f"[ERREUR] Scenario non trouve: {args.scenario}")
            return False

        output_dir.mkdir(parents=True, exist_ok=True)
        captures, labels, stats = aggregate_scenario(
            scenario_dir, args.scenario,
            add_scenario_id=args.add_scenario_id,
            verbose=True
        )

        if captures:
            # Sauvegarder
            captures_file = output_dir / "captures.jsonl"
            labels_file = output_dir / "labels.jsonl"

            with open(captures_file, 'w') as f:
                for capture in captures:
                    f.write(json.dumps(capture) + '\n')

            with open(labels_file, 'w') as f:
                for label in labels:
                    f.write(json.dumps(label) + '\n')

            print(f"[OK] Fichiers du scenario '{args.scenario}' saves:")
            print(f"  -> {captures_file}")
            print(f"  -> {labels_file}")
            print()

            total = sum(s['samples'] for s in stats.values())
            print(f"[STATS] Total echantillons: {total}")

            print(f"{'='*70}")
            print("[OK] Agregation terminee!")
            print(f"{'='*70}")
            return True
        else:
            return False

    # Mode tous les scénarios
    else:
        success = aggregate_all_scenarios(
            sequences_root, output_dir,
            add_scenario_id=args.add_scenario_id,
            verbose=True
        )

        if success:
            print()
            print(f"{'='*70}")
            print("[OK] Agregation terminee!")
            print(f"{'='*70}")
            print()
            print("[NEXT] Pour l'entrainement:")
            print(f"  python train.py --data-dir {args.output_dir}")

        return success


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)