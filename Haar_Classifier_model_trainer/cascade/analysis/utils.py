# cascade/analysis/utils.py
# -------------------------
# Utilitaires internes partagés par les modules d'analyse.

import os
import xml.etree.ElementTree as ET
import cv2


def _load_images_grayscale(directory, max_dim=320):
    """Charge toutes les images d'un dossier en grayscale, redimensionnées si trop grandes.
    
    :param directory: Dossier contenant les images
    :param max_dim: Dimension maximale (côté long) — les images plus grandes sont réduites
    :return: Liste d'images numpy (grayscale)
    """
    images = []
    for f in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, f)
        if not os.path.isfile(fpath):
            continue
        img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        h_img, w_img = img.shape[:2]
        if max(h_img, w_img) > max_dim:
            scale = max_dim / max(h_img, w_img)
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)
        images.append(img)
    return images


def _build_truncated_cascade_xml(cascade_xml_path, n_stages, output_path):
    """
    Construit un cascade.xml tronqué contenant uniquement les N premiers stages.
    
    Fonctionne par manipulation XML directe du cascade.xml existant :
    - Supprime les stages au-delà de N
    - Met à jour <stageNum>
    - Conserve les <features> intactes (partagées entre tous les stages)
    
    RAPIDE : pas d'appel à opencv_traincascade, juste du parsing XML.
    
    :param cascade_xml_path: Chemin du cascade.xml complet
    :param n_stages: Nombre de stages à conserver (1 → N)
    :param output_path: Chemin du fichier XML de sortie
    :return: True si succès
    """
    tree = ET.parse(cascade_xml_path)
    root = tree.getroot()
    cascade = root.find('cascade')
    
    # Mettre à jour <stageNum>
    stage_num_el = cascade.find('stageNum')
    stage_num_el.text = str(n_stages)
    
    # Récupérer le bloc <stages> et ses enfants <_>
    stages_el = cascade.find('stages')
    stage_list = stages_el.findall('_')
    
    # Supprimer les stages excédentaires
    for stage in stage_list[n_stages:]:
        stages_el.remove(stage)
    
    tree.write(output_path, xml_declaration=True, encoding='unicode')
    return True
