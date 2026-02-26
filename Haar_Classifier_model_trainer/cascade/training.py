# cascade/training.py
# ---------------------
# Entraînement de la cascade : création des échantillons .vec,
# vérification de reprise, entraînement opencv_traincascade et
# génération du cascade.xml final.

import os
import re
import time
import subprocess
from tqdm import tqdm


from cascade.config import MAX_FALSE_ALARM_RATE


def create_samples(annotations_file, vec_file, num_samples, width=24, height=24):
    """
    Crée le fichier .vec à partir des annotations pour l'entraînement.
    
    Utilise l'outil opencv_createsamples en mode "fichier d'annotations".
    
    :param annotations_file: Chemin du fichier annotations.txt
    :param vec_file: Chemin du fichier .vec à créer
    :param num_samples: Nombre d'échantillons à générer
    :param width: Largeur des échantillons (default 24)
    :param height: Hauteur des échantillons (default 24)
    """
    print("\n")
    print(f"Création du fichier .vec avec opencv_createsamples...")
    print("-----------------------------------")
    
    command = f"opencv_createsamples -info {annotations_file} -vec {vec_file} -num {num_samples} -w {width} -h {height}"
    
    start_time = time.time()
    print("Création des échantillons...")
    pbar = tqdm(total=num_samples, unit="sample", colour="green", ncols=80)
    created_count = 0
    
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    
    for line in process.stdout:
        line = line.strip()
        
        done_match = re.search(r'Done\.\s*Created\s+(\d+)\s+samples', line)
        if done_match:
            final_count = int(done_match.group(1))
            pbar.update(final_count - created_count)
            created_count = final_count
        elif 'Unable to open image' in line or 'Error' in line:
            pbar.write(f"  ERREUR : {line}")
    
    process.wait()
    pbar.close()
    
    elapsed = time.time() - start_time
    
    if process.returncode != 0:
        print(f"  opencv_createsamples a échoué (code retour {process.returncode})")
        exit(1)
    
    print(f"  {created_count} échantillons créés en {elapsed:.1f}s → {vec_file}")
    print("-----------------------------------\n")


def check_cascade_resume(output_dir):
    """
    Vérifie si le dossier cascade contient des fichiers d'un entraînement précédent.
    Demande à l'utilisateur s'il veut reprendre ou recommencer à zéro.
    
    :param output_dir: Dossier de sortie cascade/
    :return: 'resume' si reprise, 'restart' si on recommence
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        return 'restart'
    
    stage_files = sorted([f for f in os.listdir(output_dir) if re.match(r'stage\d+\.xml', f)])
    cascade_file = os.path.join(output_dir, 'cascade.xml')
    has_cascade = os.path.exists(cascade_file)
    
    if not stage_files and not has_cascade:
        return 'restart'
    
    print(f"\n  Fichiers d'entraînement détectés dans {output_dir} :")
    if stage_files:
        print(f"    Stages complétés : {len(stage_files)} ({stage_files[0]} → {stage_files[-1]})")
    if has_cascade:
        size_kb = os.path.getsize(cascade_file) / 1024
        print(f"    Modèle final     : cascade.xml ({size_kb:.1f} KB)")
    
    print(f"\n  Options :")
    print(f"    [R] Reprendre l'entraînement à partir du stage {len(stage_files)}")
    print(f"    [N] Nouvel entraînement (supprimer les fichiers existants)")
    print(f"    [Q] Quitter")
    
    while True:
        choice = input("\n  Choix (R/N/Q) : ").strip().upper()
        if choice == 'R':
            print(f"  → Reprise de l'entraînement au stage {len(stage_files)}...")
            return 'resume'
        elif choice == 'N':
            for f in os.listdir(output_dir):
                file_path = os.path.join(output_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            print(f"  → Dossier cascade nettoyé. Nouvel entraînement...")
            return 'restart'
        elif choice == 'Q':
            print("  → Entraînement annulé.")
            exit(0)
        else:
            print("  Choix invalide. Entrer R, N ou Q.")


def train_cascade(nb_annotations, nb_negatives, sample_width, sample_height,
                  data_dir, output_dir, config=None):
    """
    Entraîne le modèle de cascade avec opencv_traincascade.
    
    :param config: dict avec clés name, feature, stages, min_hit_rate
    :return: Chemin vers cascade.xml si succès, None sinon
    """
    print("\n")
    print(f"Entraînement en cascade du classifieur...")
    print("-----------------------------------")

    num_pos = int(nb_annotations * 0.80)
    num_neg = min(nb_negatives, num_pos * 3)
    dedicated_RAM_MB = 8192

    # Diagnostic du ratio effectif (utile pour le HNM itératif)
    neg_usage_pct = num_neg / nb_negatives * 100 if nb_negatives > 0 else 0
    if neg_usage_pct < 60 and nb_negatives > num_neg + 500:
        print(f"  ⚠ Utilisation partielle des négatifs : {num_neg}/{nb_negatives} "
              f"({neg_usage_pct:.0f}%) — plafonné par numPos×3")
        print(f"    → Pour utiliser plus de négatifs, augmenter l'augmentation des positives")
    
    if config is None:
        config = {'name': 'Rapide', 'feature': 'LBP', 'stages': 14, 'min_hit_rate': 0.995}
    
    num_stages = config['stages']
    feature = config['feature']
    min_hit_rate = config['min_hit_rate']
    max_fa_rate = config.get('max_false_alarm_rate', MAX_FALSE_ALARM_RATE)
    print(f"Mode {config['name']} : {feature}, {num_stages} stages, minHitRate={min_hit_rate}, maxFalseAlarmRate={max_fa_rate}")

    command = (
        f"opencv_traincascade"
        f" -data {output_dir}"
        f" -vec {os.path.join(data_dir, 'samples.vec')}"
        f" -bg {os.path.join(data_dir, 'bg.txt')}"
        f" -numPos {num_pos}"
        f" -numNeg {num_neg}"
        f" -numStages {num_stages}"
        f" -featureType {feature}"
        f" -minHitRate {min_hit_rate}"
        f" -maxFalseAlarmRate {max_fa_rate}"
        f" -w {sample_width} -h {sample_height}"
        f" -precalcValBufSize {dedicated_RAM_MB}"
        f" -precalcIdxBufSize {dedicated_RAM_MB}"
        f" -mode ALL"
        f" -maxDepth 1"
        f" -weightTrimRate 0.95"
    )

    print(f"  Paramètres : {num_stages} stages, {feature}, numPos={num_pos}, numNeg={num_neg}, {sample_width}x{sample_height}")
    print(f"  Détection globale théorique : ~{min_hit_rate**num_stages:.1%}  |  Faux positifs théoriques : ~{0.5**num_stages:.6%}")
    print()
    
    start_time = time.time()
    
    pbar = tqdm(
        total=num_stages,
        unit="stage", colour="green", ncols=80,
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} stages [{elapsed}<{remaining}]'
    )
    
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    
    current_stage = -1
    stage_hr = None
    stage_fa = None
    stage_features = 0
    stage_start_time = time.time()
    acceptance_ratio = None
    stages_summary = []
    
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        
        stage_match = re.search(r'TRAINING\s+(\d+)-stage', line)
        if stage_match:
            new_stage = int(stage_match.group(1))
            
            if current_stage >= 0 and stage_hr is not None:
                stage_duration = time.time() - stage_start_time
                summary = f"Stage {current_stage:2d}/{num_stages} : HR={stage_hr:.4f}  FA={stage_fa:.4f}  [{stage_features} features]  ({stage_duration:.0f}s)"
                stages_summary.append({
                    'stage': current_stage, 'hr': stage_hr, 'fa': stage_fa,
                    'features': stage_features, 'duration': stage_duration,
                    'acceptance_ratio': acceptance_ratio
                })
                pbar.update(1)
                pbar.write(f"  ✓ {summary}")
            
            current_stage = new_stage
            stage_hr = None
            stage_fa = None
            stage_features = 0
            stage_start_time = time.time()
            continue
        
        pos_match = re.search(r'POS count\s*:\s*consumed\s+(\d+)\s*:\s*(\d+)', line)
        if pos_match:
            pos_used = int(pos_match.group(1))
            pos_consumed = int(pos_match.group(2))
            if pos_consumed > pos_used:
                pbar.write(f"    Positifs : {pos_used} utilisés, {pos_consumed} consommés du .vec ({pos_consumed - pos_used} rejetés)")
            continue
        
        neg_match = re.search(r'NEG count\s*:\s*acceptanceRatio\s+(\d+)\s*:\s*([\d.e+-]+)', line)
        if neg_match:
            neg_count = int(neg_match.group(1))
            acceptance_ratio = float(neg_match.group(2))
            pbar.write(f"    Négatifs : {neg_count} utilisés, acceptance ratio = {acceptance_ratio:.4f} ({acceptance_ratio:.2%} passent encore)")
            continue
        
        hr_fa_match = re.search(r'\|\s*(\d+)\|\s*([\d.]+)\|\s*([\d.]+)\|', line)
        if hr_fa_match:
            stage_features = int(hr_fa_match.group(1))
            stage_hr = float(hr_fa_match.group(2))
            stage_fa = float(hr_fa_match.group(3))
            continue
        
        if 'Can not get new positive sample' in line:
            pbar.write(f"\n  ERREUR : {line}")
            pbar.write(f"  → numPos est trop élevé. Réduire à ~85% du .vec.")
        elif 'Train dataset for temp stage can not be filled' in line:
            pbar.write(f"\n  ERREUR : {line}")
            pbar.write(f"  → Pas assez d'images négatives. Ajouter plus de négatifs.")
        elif 'Required leaf false alarm rate achieved' in line:
            pbar.write(f"\n  INFO : Taux de faux positifs cible atteint avant le dernier stage.")
            pbar.write(f"  → L'entraînement s'est terminé plus tôt — c'est un BON signe.")
    
    process.wait()
    
    if current_stage >= 0 and stage_hr is not None:
        stage_duration = time.time() - stage_start_time
        summary = f"Stage {current_stage:2d}/{num_stages} : HR={stage_hr:.4f}  FA={stage_fa:.4f}  [{stage_features} features]  ({stage_duration:.0f}s)"
        stages_summary.append({
            'stage': current_stage, 'hr': stage_hr, 'fa': stage_fa,
            'features': stage_features, 'duration': stage_duration,
            'acceptance_ratio': acceptance_ratio
        })
        pbar.update(1)
        pbar.write(f"  ✓ {summary}")
    
    pbar.close()
    
    total_elapsed = time.time() - start_time
    hours, remainder = divmod(int(total_elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    print(f"\n{'='*60}")
    print(f"  ENTRAÎNEMENT TERMINÉ en {hours}h{minutes:02d}m{seconds:02d}s")
    print(f"{'='*60}")
    
    if stages_summary:
        total_features = sum(s['features'] for s in stages_summary)
        overall_hr = 1.0
        for s in stages_summary:
            overall_hr *= s['hr']
        final_ar = stages_summary[-1].get('acceptance_ratio', None)
        
        print(f"\n  Résumé :")
        print(f"    Stages complétés    : {len(stages_summary)} / {num_stages}")
        print(f"    Features totales    : {total_features}")
        print(f"    Détection globale   : {overall_hr:.2%}  (produit des HR de chaque stage)")
        if final_ar is not None:
            print(f"    Faux positifs       : {final_ar:.4%} des négatifs passent encore")
        print(f"    Durée totale        : {hours}h{minutes:02d}m{seconds:02d}s")
    
    cascade_file = os.path.join(output_dir, 'cascade.xml')
    if os.path.exists(cascade_file):
        size_kb = os.path.getsize(cascade_file) / 1024
        print(f"\n  Modèle sauvegardé : {cascade_file} ({size_kb:.1f} KB)")
    else:
        print(f"\n  ATTENTION : cascade.xml non trouvé dans {output_dir}")
        print(f"  L'entraînement a peut-être échoué. Vérifier les erreurs ci-dessus.")
    
    print(f"{'='*60}\n")
    return cascade_file if os.path.exists(cascade_file) else None


def generate_cascade_xml(output_dir, data_dir, state_checker, stage=None):
    """
    Génère le fichier cascade.xml à partir des stages existants.
    
    Relance opencv_traincascade avec -numStages = nombre de stages déjà entraînés,
    ce qui force la génération du modèle final sans entraîner de nouveau stage.
    
    :param output_dir: Dossier cascade/ contenant les stageN.xml
    :param data_dir: Dossier data/ contenant samples.vec et bg.txt
    :param state_checker: fonction check_data_state
    :param stage: nombre de stages à utiliser (None = tous)
    :return: Chemin vers cascade.xml si succès, None sinon
    """
    print("\n")
    print("Génération de cascade.xml à partir des stages existants...")
    print("-----------------------------------")

    stage_files = sorted([f for f in os.listdir(output_dir) if re.match(r'stage\d+\.xml', f)])
    if not stage_files:
        print("  ERREUR : Aucun fichier stage trouvé.")
        return None

    if stage is None:
        num_existing = len(stage_files)
    else:
        num_existing = min(stage, len(stage_files))
        stage_files = stage_files[:num_existing]
    print(f"  {num_existing} stages trouvés ({stage_files[0]} → {stage_files[-1]})")

    # Lire les paramètres d'entraînement depuis params.xml
    params_file = os.path.join(output_dir, 'params.xml')
    if not os.path.isfile(params_file):
        print("  ERREUR : params.xml non trouvé. Impossible de déterminer les paramètres.")
        return None

    with open(params_file, 'r', encoding='utf-8') as f:
        content = f.read()

    width_match = re.search(r'<width>(\d+)</width>', content)
    height_match = re.search(r'<height>(\d+)</height>', content)
    feature_match = re.search(r'<featureType>(\w+)</featureType>', content)

    if not all([width_match, height_match, feature_match]):
        print("  ERREUR : Impossible de lire les paramètres depuis params.xml")
        return None

    w = int(width_match.group(1))
    h = int(height_match.group(1))
    feature_type = feature_match.group(1)
    print(f"  Paramètres lus : featureType={feature_type}, fenêtre={w}x{h}")

    state = state_checker(data_dir)
    if not state['has_vec'] or not state['has_bg']:
        print("  ERREUR : samples.vec ou bg.txt manquant. Préparer les données d'abord.")
        return None

    num_pos = int(state['n_annotations'] * 0.80)
    num_neg = min(state['n_negatives'], num_pos * 2)

    command = (
        f"opencv_traincascade"
        f" -data {output_dir}"
        f" -vec {os.path.join(data_dir, 'samples.vec')}"
        f" -bg {os.path.join(data_dir, 'bg.txt')}"
        f" -numPos {num_pos}"
        f" -numNeg {num_neg}"
        f" -numStages {num_existing}"
        f" -featureType {feature_type}"
        f" -w {w} -h {h}"
        f" -minHitRate 0.995"
        f" -maxFalseAlarmRate 0.5"
        f" -mode ALL"
        f" -maxDepth 1"
        f" -weightTrimRate 0.95"
    )

    print(f"  Lancement de opencv_traincascade avec -numStages {num_existing}...")
    print(f"  (Aucun nouveau stage ne sera entraîné — génération du XML final uniquement)")
    process = subprocess.run(command, shell=True, capture_output=True, text=True)

    cascade_file = os.path.join(output_dir, 'cascade.xml')
    if os.path.exists(cascade_file):
        size_kb = os.path.getsize(cascade_file) / 1024
        print(f"\n  ✓ cascade.xml généré avec succès ({size_kb:.1f} KB)")
        print(f"    → {cascade_file}")
        print("-----------------------------------\n")
        return cascade_file
    else:
        print(f"\n  ERREUR : Impossible de générer cascade.xml")
        if process.stdout:
            print(f"  Sortie : {process.stdout[:500]}")
        if process.stderr:
            print(f"  Erreurs : {process.stderr[:500]}")
        print("-----------------------------------\n")
        return None
