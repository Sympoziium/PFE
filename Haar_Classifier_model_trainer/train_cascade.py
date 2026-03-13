#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_cascade.py — Point d'entrée du pipeline d'entraînement de classificateurs Haar/LBP.

Menu interactif :
  [1] Pipeline complet (préparation → entraînement → évaluation)
  [2] Préparer les données seulement (split + augment + .vec)
  [3] Lancer / reprendre l'entraînement
  [4] Finaliser cascade.xml à partir des stages existants
  [5] Hard Negative Mining
  [6] Analyse avancée du modèle
  [7] Ré-entraîner un modèle à un stage intermédiaire
  [Q] Quitter

Toute la logique métier est dans le package cascade/.
Ce fichier ne contient que le menu, l'état des données et le dispatch.
"""

import os
import re

from cascade import (
    DETECTION_PRESETS, HNM_PRESETS, WINDOW_SIZE, MAX_FALSE_ALARM_RATE,
    validate_environment,
    prepare_data, create_samples,
    train_cascade, generate_cascade_xml,
    evaluate_model, generate_model_plaque,
    hard_negative_mining, iterative_hnm,
    advanced_model_analysis,
)
from cascade.training import check_cascade_resume


# ══════════════════════════════════════════════════════════════
#  Utilitaires du menu
# ══════════════════════════════════════════════════════════════

def check_data_state(data_dir):
    """
    Analyse l'état actuel des données préparées.
    Retourne un dict indiquant quelles étapes ont déjà été complétées.
    """
    state = {}

    pos_dir = os.path.join(data_dir, 'positive')
    neg_dir = os.path.join(data_dir, 'negative')

    def count_files(d):
        if not os.path.isdir(d):
            return 0
        return len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])

    state['n_orig_pos'] = count_files(pos_dir)
    state['n_orig_neg'] = count_files(neg_dir)
    state['has_positive'] = state['n_orig_pos'] > 0
    state['has_negative'] = state['n_orig_neg'] > 0

    train_pos = os.path.join(data_dir, 'train', 'positive')
    train_neg = os.path.join(data_dir, 'train', 'negative')
    test_pos = os.path.join(data_dir, 'test', 'positive')
    test_neg = os.path.join(data_dir, 'test', 'negative')

    state['n_train_pos'] = count_files(train_pos)
    state['n_train_neg'] = count_files(train_neg)
    state['n_test_pos'] = count_files(test_pos)
    state['n_test_neg'] = count_files(test_neg)
    state['has_split'] = all(state[k] > 0 for k in
                             ['n_train_pos', 'n_train_neg', 'n_test_pos', 'n_test_neg'])

    annotations_file = os.path.join(data_dir, 'annotations.txt')
    bg_file = os.path.join(data_dir, 'bg.txt')

    state['n_annotations'] = 0
    state['has_annotations'] = False
    if os.path.isfile(annotations_file):
        with open(annotations_file, 'r', encoding='utf-8') as f:
            state['n_annotations'] = sum(1 for line in f if line.strip())
        state['has_annotations'] = state['n_annotations'] > 0

    state['n_negatives'] = 0
    state['has_bg'] = False
    if os.path.isfile(bg_file):
        with open(bg_file, 'r', encoding='utf-8') as f:
            state['n_negatives'] = sum(1 for line in f if line.strip())
        state['has_bg'] = state['n_negatives'] > 0

    vec_file = os.path.join(data_dir, 'samples.vec')
    state['has_vec'] = os.path.isfile(vec_file) and os.path.getsize(vec_file) > 0

    cascade_dir = os.path.join(data_dir, 'model_output')
    print(f"Vérification des stages dans {cascade_dir}...")
    state['n_stages'] = 0
    state['has_cascade_xml'] = False
    state['has_params_xml'] = False
    if os.path.isdir(cascade_dir):
        stage_files = sorted([f for f in os.listdir(cascade_dir)
                              if re.match(r'stage\d+\.xml', f)])
        state['n_stages'] = len(stage_files)
        state['has_cascade_xml'] = os.path.exists(os.path.join(cascade_dir, 'cascade.xml'))
        state['has_params_xml'] = os.path.exists(os.path.join(cascade_dir, 'params.xml'))

    hn_dir = os.path.join(data_dir, 'hard_negatives')
    state['n_hard_negatives'] = count_files(hn_dir)
    state['has_hard_negatives'] = state['n_hard_negatives'] > 0

    state['data_ready'] = (state['has_split'] and state['has_annotations']
                           and state['has_bg'] and state['has_vec'])

    return state


def show_main_menu(data_dir):
    """
    Affiche le menu principal interactif avec l'état actuel des données.
    Retourne (choix, state).
    """
    state = check_data_state(data_dir)

    def status(ok, text):
        return f"    {'✓' if ok else '✗'} {text}"

    print("\n" + "=" * 60)
    print("  Haar Cascade Trainer — Menu Principal")
    print("=" * 60)

    # ── État actuel ──
    print("\n  État actuel :")
    print(status(state['has_positive'],
                 f"Images positives originales ({state['n_orig_pos']})"))
    print(status(state['has_negative'],
                 f"Images négatives originales ({state['n_orig_neg']})"))

    if state['has_split']:
        print(status(True,
            f"Split train/test ({state['n_train_pos']} train pos, "
            f"{state['n_train_neg']} train neg, "
            f"{state['n_test_pos']} test pos, {state['n_test_neg']} test neg)"))
    else:
        print(status(False, "Split train/test non effectué"))

    print(status(state['has_annotations'],
                 f"Annotations ({state['n_annotations']} entrées)"
                 if state['has_annotations'] else "Fichier annotations.txt absent"))
    print(status(state['has_bg'],
                 f"Fichier bg.txt ({state['n_negatives']} négatifs)"
                 if state['has_bg'] else "Fichier bg.txt absent"))
    print(status(state['has_vec'], "Fichier samples.vec"))

    if state['n_stages'] > 0:
        print(status(True,
            f"Stages entraînés : {state['n_stages']} "
            f"(stage0.xml → stage{state['n_stages']-1}.xml)"))
    else:
        print(status(False, "Aucun stage entraîné"))

    if state['has_cascade_xml']:
        cascade_path = os.path.join(data_dir, 'model_output', 'cascade.xml')
        size_kb = os.path.getsize(cascade_path) / 1024
        print(status(True, f"Modèle final cascade.xml ({size_kb:.1f} KB)"))
    else:
        print(status(False, "Modèle final cascade.xml absent"))

    if state['has_hard_negatives']:
        print(status(True,
            f"Hard negatives prêts ({state['n_hard_negatives']}) "
            f"— seront intégrés au train set"))
    else:
        print(status(False,
            "Pas de hard negatives (data/hard_negatives/ vide ou absent)"))

    # ── Options du menu (nouvel ordre) ──
    print(f"\n  Options :")
    print(f"    [1] Pipeline complet (préparation → entraînement → évaluation)")
    print(f"    [2] Préparer les données seulement (split + augmentation + .vec)")
    print(f"    [3] Lancer / reprendre l'entraînement (skip préparation données)")

    if state['n_stages'] > 0 and not state['has_cascade_xml']:
        print(f"    [4] Finaliser cascade.xml à partir des {state['n_stages']} stages existants")

    if state['has_cascade_xml']:
        print(f"    [5] Hard Negative Mining (extraire les FP → améliorer précision)")
        print(f"    [8] HNM Itératif (mine → retrain × N rounds automatiques)")

    if state['has_cascade_xml'] or state['n_stages'] > 0:
        print(f"    [6] Analyse avancée (FN visuels + métriques par stage + graphiques)")

    if state['n_stages'] > 0 and state['has_cascade_xml']:
        print(f"    [7] Ré-entraîner un modèle à un stage intermédiaire choisi")

    print(f"    [Q] Quitter")

    # ── Validation du choix ──
    valid_choices = {'1', '2', '3', 'Q'}
    if state['n_stages'] > 0 and not state['has_cascade_xml']:
        valid_choices.add('4')
    if state['has_cascade_xml']:
        valid_choices.add('5')
        valid_choices.add('8')
    if state['has_cascade_xml'] or state['n_stages'] > 0:
        valid_choices.add('6')
    if state['n_stages'] > 0 and state['has_cascade_xml']:
        valid_choices.add('7')

    while True:
        choice = input(f"\n  Choix : ").strip().upper()
        if choice in valid_choices:
            return choice, state
        print(f"  Choix invalide. Options disponibles : "
              f"{', '.join(sorted(valid_choices))}")


def choose_training_config():
    """Demande à l'utilisateur le profil d'entraînement."""
    print(f"\n  Profil d'entraînement :")
    print(f"    [1] Rapide    — LBP, 14 stages  (~1-2h, test rapide)")
    print(f"    [2] Équilibre — HAAR, 14 stages  (~6-12h, bon compromis)")
    print(f"    [3] Précision — HAAR, 18 stages  (~12-24h+, meilleure qualité)")
    print(f"    [4] Test      — Tout personnalisé (feature, stages, minHitRate, maxFalseAlarmRate)")

    while True:
        c = input(f"\n  Choix (1/2/3/4) : ").strip()
        if c == '1':
            return {'name': 'Rapide', 'feature': 'LBP',
                    'stages': 14, 'min_hit_rate': 0.995}
        elif c == '2':
            return {'name': 'Équilibre', 'feature': 'HAAR',
                    'stages': 14, 'min_hit_rate': 0.995}
        elif c == '3':
            return {'name': 'Précision', 'feature': 'HAAR',
                    'stages': 18, 'min_hit_rate': 0.999}
        elif c == '4':
            try:
                feature = input("    Type de feature (HAAR [1] ou LBP [2]) : ").strip().upper()
                if feature == '1':
                    feature = 'HAAR'
                elif feature == '2':
                    feature = 'LBP'
                elif feature not in ('HAAR', 'LBP'):
                    print("    Choix invalide pour le type de feature.")
                    continue

                stages = int(input("    Nombre de stages (ex: 10) : ").strip())
                if stages < 1 or stages > 30:
                    print("    Nombre de stages doit être entre 1 et 30.")
                    continue

                min_hr = float(input("    minHitRate (ex: 0.995) : ").strip())
                if min_hr < 0.9 or min_hr > 0.9999:
                    print("    minHitRate doit être entre 0.9 et 0.9999.")
                    continue

                max_fa_input = input(f"    maxFalseAlarmRate (défaut: {MAX_FALSE_ALARM_RATE}, ex: 0.4 plus bas = plus strict) : ").strip()
                if max_fa_input:
                    max_fa = float(max_fa_input)
                    if max_fa < 0.1 or max_fa > 0.7:
                        print("    maxFalseAlarmRate doit être entre 0.1 et 0.7.")
                        continue
                else:
                    max_fa = MAX_FALSE_ALARM_RATE

                width = int(input("    Largeur de la fenêtre (ex: 24) : ").strip())
                height = int(input("    Hauteur de la fenêtre (ex: 24) : ").strip())
                if width < 12 or width > 200 or height < 12 or height > 200:
                    print("    Largeur et hauteur doivent être entre 12 et 200.")
                    continue

                return {'name': 'Test', 'feature': feature, 'stages': stages,
                        'min_hit_rate': min_hr, 'max_false_alarm_rate': max_fa,
                        'w': width, 'h': height}
            except ValueError:
                print("    Valeur invalide.")
        print("  Choix invalide. Entrer 1, 2, 3 ou 4.")


# ══════════════════════════════════════════════════════════════
#  Point d'entrée
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":

    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, 'data')
    positive_images_dir = os.path.join(data_dir, 'positive')
    negative_images_dir = os.path.join(data_dir, 'negative')
    output_dir = os.path.join(data_dir, 'model_output')

    sample_width = WINDOW_SIZE['recommended'][0]
    sample_height = WINDOW_SIZE['recommended'][1]

    # Vérification de l'environnement
    validate_environment()

    # Menu principal
    choice, state = show_main_menu(data_dir)

    # ──────────────────────────────────────────────────────
    #  [1] Pipeline complet
    # ──────────────────────────────────────────────────────
    if choice == '1':
        config = choose_training_config()

        train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, \
            nb_annotations, nb_negatives, annotations_file, bg_file = \
            prepare_data(positive_images_dir, negative_images_dir, data_dir, w = config.get('w', sample_width), h = config.get('h', sample_height))

        create_samples(
            annotations_file=annotations_file,
            vec_file=os.path.join(data_dir, 'samples.vec'),
            num_samples=nb_annotations,
            width=config.get('w', sample_width), height=config.get('h', sample_height)
        )

        check_cascade_resume(output_dir)
        model_path = train_cascade(
            nb_annotations, nb_negatives,
            config.get('w', sample_width), config.get('h', sample_height),
            data_dir, output_dir, config=config
        )

        if model_path:
            eval_results, best_idx = evaluate_model(
                model_path, test_pos_dir, test_neg_dir)
            generate_model_plaque(
                model_path=model_path, config=config,
                sample_width=config.get('w', sample_width), sample_height=config.get('h', sample_height),
                eval_results=eval_results, best_idx=best_idx,
                data_dir=data_dir, base_dir=base_dir,
                state_checker=check_data_state
            )
        else:
            print("\n  Aucun modèle produit. "
                  "Utilisez l'option [4] pour finaliser cascade.xml "
                  "à partir des stages existants.")

    # ──────────────────────────────────────────────────────
    #  [2] Préparer les données seulement
    # ──────────────────────────────────────────────────────
    elif choice == '2':
        config = choose_training_config()
        train_pos_dir, train_neg_dir, test_pos_dir, test_neg_dir, \
            nb_annotations, nb_negatives, annotations_file, bg_file = \
            prepare_data(positive_images_dir, negative_images_dir, data_dir, w = config.get('w', sample_width), h = config.get('h', sample_height))
        
        create_samples(
            annotations_file=annotations_file,
            vec_file=os.path.join(data_dir, 'samples.vec'),
            num_samples=nb_annotations,
            width=config.get('w', sample_width), height=config.get('h', sample_height)
        )

        print("\n  ✓ Données préparées avec succès.")
        print("  → Relancez le script et choisissez l'option [3] pour entraîner.")

    # ──────────────────────────────────────────────────────
    #  [3] Entraîner / reprendre (données déjà préparées)
    # ──────────────────────────────────────────────────────
    elif choice == '3':
        if not state['data_ready']:
            print("\n  ERREUR : Les données ne sont pas prêtes pour l'entraînement.")
            missing = []
            if not state['has_split']:
                missing.append("split train/test")
            if not state['has_annotations']:
                missing.append("annotations.txt")
            if not state['has_bg']:
                missing.append("bg.txt")
            if not state['has_vec']:
                missing.append("samples.vec")
            print(f"  Manquant : {', '.join(missing)}")
            print(f"  → Utilisez l'option [1] ou [2] pour préparer les données d'abord.")
            exit(1)

        config = choose_training_config()
        nb_annotations = state['n_annotations']
        nb_negatives = state['n_negatives']

        print(f"\n  Données existantes utilisées :")
        print(f"    Annotations : {nb_annotations} | Négatifs : {nb_negatives}")
        print(f"    Train : {state['n_train_pos']} pos, {state['n_train_neg']} neg")
        print(f"    Test  : {state['n_test_pos']} pos, {state['n_test_neg']} neg")

        check_cascade_resume(output_dir)
        model_path = train_cascade(
            nb_annotations, nb_negatives,
            sample_width, sample_height,
            data_dir, output_dir, config=config
        )

        if model_path:
            test_pos_dir = os.path.join(data_dir, 'test', 'positive')
            test_neg_dir = os.path.join(data_dir, 'test', 'negative')
            eval_results, best_idx = evaluate_model(
                model_path, test_pos_dir, test_neg_dir)
            generate_model_plaque(
                model_path=model_path, config=config,
                sample_width=sample_width, sample_height=sample_height,
                eval_results=eval_results, best_idx=best_idx,
                data_dir=data_dir, base_dir=base_dir,
                state_checker=check_data_state
            )
        else:
            print("\n  Aucun modèle produit. "
                  "Utilisez l'option [4] pour finaliser cascade.xml "
                  "à partir des stages existants.")

    # ──────────────────────────────────────────────────────
    #  [4] Finaliser cascade.xml
    # ──────────────────────────────────────────────────────
    elif choice == '4':
        model_path = generate_cascade_xml(
            output_dir, data_dir, state_checker=check_data_state)
        if model_path and state['has_split']:
            test_pos_dir = os.path.join(data_dir, 'test', 'positive')
            test_neg_dir = os.path.join(data_dir, 'test', 'negative')
            _results, _best = evaluate_model(
                model_path, test_pos_dir, test_neg_dir)
        elif model_path:
            print("\n  cascade.xml généré. "
                  "Pas de données de test disponibles — évaluation ignorée.")

    # ──────────────────────────────────────────────────────
    #  [5] Hard Negative Mining
    # ──────────────────────────────────────────────────────
    elif choice == '5':
        cascade_file = os.path.join(output_dir, 'cascade.xml')

        print(f"\n  Paramètres du Hard Negative Mining :")
        print(f"    Des paramètres sensibles captent plus de faux positifs.")
        hnm_presets = list(HNM_PRESETS.values())
        for i, p in enumerate(hnm_presets, 1):
            print(f"    [{i}] {p['label']:<12} — SF={p['sf']}, MN={p['mn']}  "
                  f"({p['desc']})")

        while True:
            hn_choice = input(f"\n  Choix (1/2/3) : ").strip()
            if hn_choice in ('1', '2', '3'):
                preset = hnm_presets[int(hn_choice) - 1]
                sf, mn = preset['sf'], preset['mn']
                break
            print("  Choix invalide.")

        nb_hn = hard_negative_mining(
            model_path=cascade_file,
            negative_images_dir=negative_images_dir,
            output_dir=negative_images_dir,
            data_dir=data_dir,
            scaleFactor=sf, minNeighbors=mn,
            min_crop_w=sample_width * 2,
            min_crop_h=sample_height * 2
        )

        if nb_hn > 0:
            print(f"  Prochaines étapes :")
            print(f"    1. Relancez le script")
            print(f"    2. Choisissez [1] Pipeline complet pour ré-entraîner")
            print(f"       Les hard negatives seront inclus automatiquement")

    # ──────────────────────────────────────────────────────
    #  [6] Analyse avancée
    # ──────────────────────────────────────────────────────
    elif choice == '6':
        cascade_file = os.path.join(output_dir, 'cascade.xml')
        test_pos_dir = os.path.join(data_dir, 'test', 'positive')
        test_neg_dir = os.path.join(data_dir, 'test', 'negative')

        if not os.path.exists(cascade_file) and state['n_stages'] > 0:
            print(f"\n  cascade.xml absent mais {state['n_stages']} stages détectés.")
            gen = input("  Générer cascade.xml maintenant ? (O/N) : ").strip().upper()
            if gen == 'O':
                cascade_file = generate_cascade_xml(
                    output_dir, data_dir, state_checker=check_data_state)
                if not cascade_file:
                    print("  Échec de la génération. Abandon.")
                    exit(1)
            else:
                print("  Abandon.")
                exit(0)

        if not state['has_split']:
            print("\n  ERREUR : Dossiers de test manquants.")
            print(f"  → Utilisez l'option [1] ou [2] pour préparer les données d'abord.")
            exit(1)

        advanced_model_analysis(
            model_path=cascade_file,
            cascade_dir=output_dir,
            data_dir=data_dir,
            test_pos_dir=test_pos_dir,
            test_neg_dir=test_neg_dir
        )

    # ──────────────────────────────────────────────────────
    #  [7] Stage intermédiaire → cascade.xml
    # ──────────────────────────────────────────────────────
    elif choice == '7':
        print(f"\n  Génération de cascade.xml à partir d'un stage intermédiaire.")
        print("  Recommandation : ne pas choisir un stage inférieur à 5, "
              "le modèle est souvent encore trop simple (beaucoup de FP).")
        stage_num = input(
            f"\n  Entrez le numéro du stage (1 à {state['n_stages']}) : ").strip()

        if not stage_num.isdigit() or int(stage_num) < 1 \
                or int(stage_num) > state['n_stages']:
            print(f"  Numéro invalide. Génération avec le dernier stage "
                  f"({state['n_stages']}).")
            stage_num = state['n_stages']
        elif int(stage_num) < 5:
            confirm = input(
                f"  Attention : le stage {stage_num} est très précoce. "
                f"Êtes-vous sûr ? (O/N) : ").strip().upper()
            if confirm != 'O':
                print("  Génération annulée.")
                exit(0)

        stage_num = int(stage_num)
        cascade_file = generate_cascade_xml(
            output_dir, data_dir,
            stage=stage_num, state_checker=check_data_state)
        if cascade_file:
            print(f"  ✓ Généré : {cascade_file}")
        else:
            print("  ✗ Échec de la génération.")

    # ──────────────────────────────────────────────────────
    #  [8] HNM Itératif
    # ──────────────────────────────────────────────────────
    elif choice == '8':
        cascade_file = os.path.join(output_dir, 'cascade.xml')

        # Nombre de rounds
        rounds_input = input(
            f"\n  Nombre de rounds HNM (1-5, défaut 3) : ").strip()
        try:
            num_rounds = int(rounds_input) if rounds_input else 3
            num_rounds = max(1, min(5, num_rounds))
        except ValueError:
            num_rounds = 3

        # Paramètres de mining
        print(f"\n  Paramètres de détection pour le mining :")
        hnm_presets = list(HNM_PRESETS.values())
        for i, p in enumerate(hnm_presets, 1):
            print(f"    [{i}] {p['label']:<12} — SF={p['sf']}, MN={p['mn']}  "
                  f"({p['desc']})")

        while True:
            hn_choice = input(f"\n  Choix (1/2/3, défaut 2) : ").strip()
            if not hn_choice:
                hn_choice = '2'
            if hn_choice in ('1', '2', '3'):
                preset = hnm_presets[int(hn_choice) - 1]
                sf, mn = preset['sf'], preset['mn']
                break
            print("  Choix invalide.")

        # Profil d'entraînement pour chaque round
        config = choose_training_config()

        print(f"\n  Configuration : {num_rounds} rounds, SF={sf}, MN={mn}, "
              f"profil={config['name']}")
        confirm = input("  Lancer le HNM itératif ? (O/N) : ").strip().upper()
        if confirm != 'O':
            print("  Annulé.")
            exit(0)

        iterative_hnm(
            model_path=cascade_file,
            negative_images_dir=negative_images_dir,
            data_dir=data_dir,
            output_dir=output_dir,
            num_rounds=num_rounds,
            scaleFactor=sf,
            minNeighbors=mn,
            config=config,
            sample_width=config.get('w', sample_width),
            sample_height=config.get('h', sample_height),
        )

    # ──────────────────────────────────────────────────────
    #  [Q] Quitter
    # ──────────────────────────────────────────────────────
    elif choice == 'Q':
        print("\n  Au revoir !")
        exit(0)
