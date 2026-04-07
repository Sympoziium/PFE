#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'agrégation modulaire des séquences d'entraînement.

Consolide les fichiers captures.jsonl et labels.jsonl des dossiers de
séquences sampling_* organisés par scénario.

Structure de répertoires supportée:
    sequences/
      baseline/
        sampling_01/ -> captures.jsonl, labels.jsonl
        sampling_02/
        ...
      pieton/
        sampling_01/
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
    # Format: "scenario/sampling_name" -> ID unique incremental
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

    # Sauvegarder les fichiers globaux
    global_captures_file = output_dir / "captures.jsonl"
    global_labels_file = output_dir / "labels.jsonl"
    global_seqids_file = output_dir / "sequence_ids.jsonl"

    with open(global_captures_file, 'w') as f:
        for capture in global_captures:
            f.write(json.dumps(capture) + '\n')

    with open(global_labels_file, 'w') as f:
        for label in global_labels:
            f.write(json.dumps(label) + '\n')

    with open(global_seqids_file, 'w') as f:
        for sid in global_seq_ids:
            f.write(str(sid) + '\n')

    # Sauvegarder le mapping ID -> nom de sequence
    seq_map_file = output_dir / "sequence_map.json"
    # Inverser: ID -> nom
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
        print(f"  -> {global_seqids_file}")
        print(f"  -> {seq_map_file}")

    if verbose:
        print(f"[GLOBAL] Fichiers consolides:")
        print(f"  -> {global_captures_file}")
        print(f"  -> {global_labels_file}")
        print()

        # Résumé statistiques
        total_samples = 0
        for scenario_stats in all_scenario_stats.values():
            total_samples += sum(s['samples'] for s in scenario_stats.values())

        print(f"[STATS] Résumé global:")
        print(f"  * Total scenarios: {len(scenarios)}")
        print(f"  * Total echantillons: {total_samples}")

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