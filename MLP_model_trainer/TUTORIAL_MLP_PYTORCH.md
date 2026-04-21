# Tutoriel Complet : Implémentation d'un MLP avec PyTorch pour Systèmes Embarqués

> **Objectif** : Ce document est un guide de référence complet pour la conception, l'entraînement et le déploiement d'un réseau de neurones MLP (Multilayer Perceptron) en utilisant PyTorch, avec conversion vers TensorFlow Lite pour déploiement sur systèmes embarqués (ex: Raspberry Pi Zero).

**Auteur** : Cédric Senécal
**Date** : 18 Mars 2026
**Inspiré de** : [Machine Learning Expedition - How to Train MLP in PyTorch](https://www.machinelearningexpedition.com/how-to-train-multilayer-perceptron-in-pytorch/)

---

## Table des matières

1. [Introduction aux MLPs](#1-introduction-aux-mlps)
2. [Environnement et dépendances](#2-environnement-et-dépendances)
3. [Architecture du pipeline complet](#3-architecture-du-pipeline-complet)
4. [Préparation des données](#4-préparation-des-données)
5. [Construction du modèle MLP](#5-construction-du-modèle-mlp)
6. [Entraînement du modèle](#6-entraînement-du-modèle)
7. [Évaluation et validation](#7-évaluation-et-validation)
8. [Sauvegarde et chargement](#8-sauvegarde-et-chargement)
9. [Conversion vers TensorFlow Lite](#9-conversion-vers-tensorflow-lite)
10. [Déploiement sur système embarqué](#10-déploiement-sur-système-embarqué)
11. [Bonnes pratiques et optimisations](#11-bonnes-pratiques-et-optimisations)
12. [Dépannage et problèmes courants](#12-dépannage-et-problèmes-courants)

---

## 1. Introduction aux MLPs

### 1.1 Qu'est-ce qu'un MLP ?

Un **Multilayer Perceptron (MLP)** est l'architecture de réseau de neurones la plus fondamentale. C'est un réseau **feedforward** (sans cycles) composé de :

```
┌─────────────┐      ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Entrée    │────▶│  Cachée 1   │────▶│  Cachée 2   │────▶│   Sortie    │
│  (input)    │      │  (hidden)   │     │  (hidden)   │     │  (output)   │
└─────────────┘      └─────────────┘     └─────────────┘     └─────────────┘
   n entrées          64 neurones        32 neurones         m sorties
```

**Caractéristiques clés :**
- **Fully Connected** : Chaque neurone est connecté à tous les neurones de la couche suivante
- **Non-linéarité** : Des fonctions d'activation (ReLU, Tanh, Sigmoid) permettent d'apprendre des relations non-linéaires
- **Apprentissage supervisé** : Le modèle apprend à partir d'exemples étiquetés (input → output attendu)

### 1.2 Quand utiliser un MLP ?

| Cas d'usage | Adapté ? | Alternative |
|-------------|----------|-------------|
| Données tabulaires (capteurs, features extraites) | ✅ Excellent | - |
| Régression (prédire des valeurs continues) | ✅ Excellent | - |
| Classification simple | ✅ Bon | - |
| Images brutes | ❌ Non | CNN (Convolutional Neural Network) |
| Séquences temporelles | ⚠️ Limité | RNN, LSTM, Transformer |
| Données avec structure spatiale | ❌ Non | GNN (Graph Neural Network) |

### 1.3 Notre cas d'usage : Contrôle robotique

Dans notre projet, le MLP est utilisé pour l'**apprentissage par imitation** (Imitation Learning) :

```
┌─────────────────────────────────────────────────────────────┐
│                    ENTRÉE (17+N dimensions)                 │
├─────────────────────────────────────────────────────────────┤
│  IR Sensors [6]  │  Détection [9]  │  IMU [6]               │
│  ├─ front_r      │  ├─ detected    │  ├─ ax, ay, az         │
│  ├─ bottom_r     │  ├─ class[N]    │  └─ gx, gy, gz         │
│  ├─ back_r       │  └─ bbox[4]     │                        │
│  ├─ bottom_l     │                 │                        │
│  ├─ back_l       │                 │                        │
│  └─ front_l      │                 │                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │      MLP        │
                    │   [64 → 32]     │
                    └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SORTIE (2 dimensions)                    │
├─────────────────────────────────────────────────────────────┤
│           left_speed [-1, 1]  │  right_speed [-1, 1]        │
└─────────────────────────────────────────────────────────────┘
```

Le robot "apprend" à reproduire les commandes d'un opérateur humain en fonction de l'état des capteurs.

---

## 2. Environnement et dépendances

### 2.1 Installation des dépendances côté PC

```bash
# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

```

### 2.2 Installation des dépendances côté Raspberry Pi Zero 2

```bash
cd PFE/
pip install -r requirements-robot.txt
```


### 2.3 Imports de base PyTorch

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
import numpy as np
```

**Explication des modules :**

| Module | Rôle |
|--------|------|
| `torch` | Tenseurs et opérations de base (équivalent NumPy sur GPU) |
| `torch.nn` | Couches de réseaux de neurones (Linear, ReLU, etc.) |
| `torch.optim` | Optimiseurs (Adam, SGD, etc.) |
| `torch.utils.data` | Utilitaires pour charger et batacher les données |

### 2.3 Vérification de l'environnement

```python
# Vérifier la version de PyTorch
print(f"PyTorch version: {torch.__version__}")

# Vérifier la disponibilité de CUDA (GPU)
print(f"CUDA disponible: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# Device à utiliser
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device utilisé: {device}")
```

---

## 3. Architecture du pipeline complet

### 3.1 Vue d'ensemble

Notre pipeline complet se décompose en plusieurs étapes :

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: COLLECTE                                │
│                        (Sur le robot)                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  Opérateur humain  ──▶  Contrôle manuel  ──▶  Sampling (JSONL)          │
│                                                                          │
│  captures.jsonl : vecteurs d'état normalisés                            │
│  labels.jsonl   : commandes moteur correspondantes                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       PHASE 2: ENTRAÎNEMENT                              │
│                        (Sur le PC)                                       │
├──────────────────────────────────────────────────────────────────────────┤
│  JSONL  ──▶  Dataset PyTorch  ──▶  DataLoader  ──▶  Entraînement MLP    │
│                                                            │             │
│                                                            ▼             │
│                                                    best_model.pt         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       PHASE 3: CONVERSION                                │
│                        (Sur le PC)                                       │
├──────────────────────────────────────────────────────────────────────────┤
│  PyTorch (.pt)  ──▶  ONNX (.onnx)  ──▶  TensorFlow  ──▶  TFLite (.tflite)│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       PHASE 4: DÉPLOIEMENT                               │
│                        (Sur le robot)                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  MLController  ◀──  TFLite Interpreter  ◀──  zumi_mlp.tflite            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Structure des fichiers

```
MLP_model_trainer/
├── data/                      # Données d'entraînement
│   ├── captures.jsonl         # Vecteurs d'état (entrées)
│   └── labels.jsonl           # Commandes moteur (sorties)
├── checkpoints/               # Modèles sauvegardés
│   ├── best_model.pt          # Meilleur modèle PyTorch
│   └── training_report.json   # Rapport d'entraînement
├── export/                    # Modèles convertis
│   ├── zumi_mlp.onnx          # Format ONNX intermédiaire
│   ├── zumi_mlp_tf/           # SavedModel TensorFlow
│   └── zumi_mlp.tflite        # Modèle final pour déploiement
├── dataset.py                 # Chargement des données
├── model.py                   # Architecture du MLP
├── train.py                   # Script d'entraînement
├── convert_to_tflite.py       # Script de conversion
└── requirements.txt           # Dépendances Python
```

### 3.3 Pourquoi cette architecture ?

| Choix | Justification |
|-------|---------------|
| **PyTorch pour l'entraînement** | API intuitive, debugging facile, écosystème riche |
| **TFLite pour le déploiement** | Optimisé pour ARM, faible empreinte mémoire, quantization native |
| **JSONL pour les données** | Simple, lisible, streaming possible, pas de dépendances |
| **Séparation train/deploy** | Le Pi Zero n'a pas assez de ressources pour entraîner |

---

## 4. Préparation des données

### 4.1 Comprendre le format des données

Nos données sont stockées au format **JSONL** (JSON Lines) : un objet JSON par ligne.

**captures.jsonl** (entrées) :
```json
[0.45, 0.32, 0.18, 0.67, 0.23, 0.89, 1.0, 0.0, 0.0, 1.0, 0.0, 0.5, 0.3, 0.1, 0.2, 0.01, -0.02, 0.98, 0.001, 0.003, -0.002]
[0.44, 0.31, 0.19, 0.68, 0.22, 0.88, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.02, -0.01, 0.97, 0.002, 0.001, -0.001]
```

**labels.jsonl** (sorties) :
```json
[0.4, 0.35]
[-0.2, 0.3]
```

### 4.2 Créer un Dataset PyTorch

Un `Dataset` PyTorch doit implémenter trois méthodes :

```python
class Dataset:
    def __init__(self):      # Initialisation et chargement des données
        pass

    def __len__(self):       # Nombre d'échantillons
        return 0

    def __getitem__(self, idx):  # Retourne un échantillon par index
        return None
```

**Implémentation complète :**

```python
import json
import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path


class ZumiControlDataset(Dataset):
    """Dataset pour l'apprentissage par imitation.

    Charge des fichiers JSONL contenant:
    - captures.jsonl : vecteurs d'état normalisés
    - labels.jsonl : commandes moteur [-1, 1]
    """

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Répertoire contenant captures.jsonl et labels.jsonl
        """
        self.data_dir = Path(data_dir)
        self.captures = []
        self.labels = []

        self._load_data()

    def _load_data(self):
        """Charge les fichiers JSONL en mémoire."""
        captures_path = self.data_dir / "captures.jsonl"
        labels_path = self.data_dir / "labels.jsonl"

        # Vérifier que les fichiers existent
        if not captures_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {captures_path}")
        if not labels_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {labels_path}")

        # Charger les captures (une ligne = un vecteur JSON)
        with open(captures_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:  # Ignorer les lignes vides
                    self.captures.append(json.loads(line))

        # Charger les labels
        with open(labels_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.labels.append(json.loads(line))

        # Validation: même nombre d'entrées et de sorties
        if len(self.captures) != len(self.labels):
            raise ValueError(
                f"Incohérence: {len(self.captures)} captures vs {len(self.labels)} labels"
            )

        # Convertir en numpy pour efficacité
        self.captures = np.array(self.captures, dtype=np.float32)
        self.labels = np.array(self.labels, dtype=np.float32)

        print(f"[Dataset] Chargé {len(self)} échantillons")
        print(f"[Dataset] Entrée: {self.input_dim}D, Sortie: {self.output_dim}D")

    @property
    def input_dim(self) -> int:
        """Dimension du vecteur d'entrée."""
        return self.captures.shape[1] if len(self.captures) > 0 else 0

    @property
    def output_dim(self) -> int:
        """Dimension du vecteur de sortie."""
        return self.labels.shape[1] if len(self.labels) > 0 else 0

    def __len__(self) -> int:
        """Nombre total d'échantillons."""
        return len(self.captures)

    def __getitem__(self, idx: int):
        """Retourne un échantillon (état, commande) en tenseurs PyTorch."""
        state = torch.from_numpy(self.captures[idx])
        command = torch.from_numpy(self.labels[idx])
        return state, command
```

### 4.3 Créer des DataLoaders

Un `DataLoader` encapsule un `Dataset` et fournit :
- **Batching** : Regrouper les échantillons en mini-batches
- **Shuffling** : Mélanger les données à chaque epoch
- **Parallélisme** : Charger les données en arrière-plan

```python
from torch.utils.data import DataLoader, random_split

def create_data_loaders(
    data_dir: str,
    batch_size: int = 32,
    train_ratio: float = 0.8,
    seed: int = 42
):
    """Crée les DataLoaders pour train et validation.

    Args:
        data_dir: Répertoire des données
        batch_size: Taille des mini-batches
        train_ratio: Proportion pour l'entraînement (0.8 = 80%)
        seed: Graine aléatoire pour reproductibilité

    Returns:
        tuple: (train_loader, val_loader, dataset)
    """
    # Charger le dataset complet
    dataset = ZumiControlDataset(data_dir)

    # Calculer les tailles
    n_train = int(len(dataset) * train_ratio)
    n_val = len(dataset) - n_train

    # Split avec graine fixe pour reproductibilité
    generator = torch.Generator().manual_seed(seed)
    train_dataset, val_dataset = random_split(
        dataset, [n_train, n_val], generator=generator
    )

    # Créer les DataLoaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,       # Mélanger à chaque epoch
        num_workers=0,      # 0 pour compatibilité Windows
        pin_memory=True     # Accélère le transfert CPU→GPU
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,      # Pas de shuffle pour la validation
        num_workers=0,
        pin_memory=True
    )

    print(f"[DataLoader] Train: {n_train}, Val: {n_val}")

    return train_loader, val_loader, dataset
```

### 4.4 Comprendre le batching

```python
# Exemple d'utilisation
train_loader, val_loader, dataset = create_data_loaders("data/", batch_size=32)

# Itérer sur les batches
for batch_idx, (states, commands) in enumerate(train_loader):
    print(f"Batch {batch_idx}:")
    print(f"  States shape: {states.shape}")    # [32, 21] - 32 échantillons, 21 features
    print(f"  Commands shape: {commands.shape}")  # [32, 2]  - 32 échantillons, 2 sorties
    break
```

**Pourquoi utiliser des batches ?**

| Aspect | Batch size = 1 | Batch size = 32 | Batch size = N (tout) |
|--------|----------------|-----------------|----------------------|
| Bruit du gradient | Très bruité | Équilibré | Très stable |
| Vitesse | Lent | Rapide | Très rapide |
| Mémoire | Minimal | Modéré | Maximum |
| Généralisation | Bonne | Très bonne | Risque d'overfitting |

**Règle empirique** : Commencer avec `batch_size=32`, ajuster si nécessaire.

---

## 5. Construction du modèle MLP

### 5.1 Anatomie d'un module PyTorch

En PyTorch, un modèle est une classe qui hérite de `nn.Module` :

```python
import torch.nn as nn

class MonModele(nn.Module):
    def __init__(self):
        super().__init__()  # OBLIGATOIRE: initialiser nn.Module

        # Définir les couches ici
        self.couche1 = nn.Linear(10, 5)

    def forward(self, x):
        # Définir le flux de données
        return self.couche1(x)
```

### 5.2 Les couches essentielles

| Couche | Usage | Exemple |
|--------|-------|---------|
| `nn.Linear(in, out)` | Transformation linéaire (Wx + b) | `nn.Linear(21, 64)` |
| `nn.ReLU()` | Activation ReLU: max(0, x) | `nn.ReLU()` |
| `nn.Tanh()` | Activation Tanh: sortie dans [-1, 1] | `nn.Tanh()` |
| `nn.Sigmoid()` | Activation Sigmoid: sortie dans [0, 1] | `nn.Sigmoid()` |
| `nn.Dropout(p)` | Régularisation: désactive p% des neurones | `nn.Dropout(0.1)` |

### 5.3 Implémentation du MLP

```python
import torch
import torch.nn as nn


class ZumiMLP(nn.Module):
    """Réseau MLP pour le contrôle du robot Zumi.

    Architecture:
        Input → [Linear → ReLU → Dropout] × N → Linear → Tanh → Output

    La couche de sortie utilise Tanh pour garantir des sorties dans [-1, 1],
    correspondant aux commandes moteur normalisées.
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int = 2,
        hidden_dims: list = None,
        dropout: float = 0.1
    ):
        """
        Args:
            input_dim: Dimension d'entrée (ex: 21 pour notre vecteur d'état)
            output_dim: Dimension de sortie (2 = vitesses gauche/droite)
            hidden_dims: Liste des dimensions des couches cachées
            dropout: Taux de dropout (0.1 = 10% des neurones désactivés)
        """
        super().__init__()

        # Valeurs par défaut
        if hidden_dims is None:
            hidden_dims = [64, 32]

        # Sauvegarder pour référence
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dims = hidden_dims

        # Construire le réseau dynamiquement
        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            prev_dim = hidden_dim

        # Couche de sortie avec Tanh
        layers.append(nn.Linear(prev_dim, output_dim))
        layers.append(nn.Tanh())

        # nn.Sequential enchaîne les couches automatiquement
        self.network = nn.Sequential(*layers)

        # Initialisation des poids
        self._init_weights()

    def _init_weights(self):
        """Initialisation Xavier pour une meilleure convergence."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                # Xavier uniform: variance adaptée à la taille des couches
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass: calcule la sortie du réseau.

        Args:
            x: Tensor de forme (batch_size, input_dim)

        Returns:
            Tensor de forme (batch_size, output_dim) dans [-1, 1]
        """
        return self.network(x)

    def count_parameters(self) -> int:
        """Compte le nombre de paramètres entraînables."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
```

### 5.4 Comprendre les dimensions

```python
# Créer le modèle
model = ZumiMLP(input_dim=21, output_dim=2, hidden_dims=[64, 32])

# Afficher l'architecture
print(model)
# Output:
# ZumiMLP(
#   (network): Sequential(
#     (0): Linear(in_features=21, out_features=64, bias=True)
#     (1): ReLU()
#     (2): Dropout(p=0.1, inplace=False)
#     (3): Linear(in_features=64, out_features=32, bias=True)
#     (4): ReLU()
#     (5): Dropout(p=0.1, inplace=False)
#     (6): Linear(in_features=32, out_features=2, bias=True)
#     (7): Tanh()
#   )
# )

# Calcul des paramètres
# Couche 1: 21 * 64 + 64 = 1408 paramètres
# Couche 2: 64 * 32 + 32 = 2080 paramètres
# Couche 3: 32 * 2 + 2 = 66 paramètres
# Total: 3554 paramètres
print(f"Paramètres: {model.count_parameters()}")
```

### 5.5 Variantes d'architecture

```python
# Modèle compact (pour Pi Zero avec ressources limitées)
class ZumiMLPSmall(ZumiMLP):
    def __init__(self, input_dim, output_dim=2):
        super().__init__(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=[32, 16],  # Plus petit
            dropout=0.05           # Moins de dropout
        )

# Modèle large (si plus de données disponibles)
class ZumiMLPLarge(ZumiMLP):
    def __init__(self, input_dim, output_dim=2):
        super().__init__(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=[128, 64, 32],  # Plus profond
            dropout=0.2                  # Plus de régularisation
        )
```

### 5.6 Choix de la fonction d'activation de sortie

| Activation | Plage | Cas d'usage |
|------------|-------|-------------|
| `Tanh` | [-1, 1] | Régression bornée (notre cas: vitesses moteur) |
| `Sigmoid` | [0, 1] | Classification binaire, probabilités |
| `Softmax` | [0, 1], somme=1 | Classification multi-classes |
| Aucune | (-∞, +∞) | Régression non bornée |

**Pourquoi Tanh pour notre cas ?**
Les commandes moteur sont normalisées dans [-1, 1]. Tanh garantit que le modèle ne peut jamais prédire de valeurs hors de cette plage.

---

## 6. Entraînement du modèle

### 6.1 La boucle d'entraînement PyTorch

L'entraînement suit toujours ce schéma :

```python
for epoch in range(num_epochs):
    model.train()  # Mode entraînement (active Dropout)

    for batch in train_loader:
        # 1. Récupérer les données
        inputs, targets = batch
        inputs = inputs.to(device)
        targets = targets.to(device)

        # 2. Réinitialiser les gradients
        optimizer.zero_grad()

        # 3. Forward pass
        outputs = model(inputs)

        # 4. Calculer la perte
        loss = criterion(outputs, targets)

        # 5. Backward pass (calcul des gradients)
        loss.backward()

        # 6. Mise à jour des poids
        optimizer.step()
```

### 6.2 Comprendre chaque étape

#### Étape 2: `optimizer.zero_grad()`

PyTorch accumule les gradients par défaut. Si on ne les remet pas à zéro, les gradients du batch précédent s'ajoutent aux nouveaux.

```python
# MAUVAIS: gradients accumulés
for batch in loader:
    loss = compute_loss(batch)
    loss.backward()  # Gradients s'accumulent!
    optimizer.step()

# BON: gradients remis à zéro
for batch in loader:
    optimizer.zero_grad()  # Remise à zéro
    loss = compute_loss(batch)
    loss.backward()
    optimizer.step()
```

#### Étape 4: La fonction de perte

Pour la régression, on utilise généralement **MSE (Mean Squared Error)** :

```python
criterion = nn.MSELoss()

# Exemple
predictions = torch.tensor([0.5, 0.3])
targets = torch.tensor([0.6, 0.2])

loss = criterion(predictions, targets)
# loss = mean((0.5-0.6)² + (0.3-0.2)²) = mean(0.01 + 0.01) = 0.01
```

| Fonction de perte | Formule | Cas d'usage |
|-------------------|---------|-------------|
| `MSELoss` | mean((y - ŷ)²) | Régression |
| `L1Loss` | mean(\|y - ŷ\|) | Régression robuste aux outliers |
| `BCELoss` | Binary Cross Entropy | Classification binaire |
| `CrossEntropyLoss` | Cross Entropy | Classification multi-classes |

#### Étape 5: `loss.backward()`

Cette ligne calcule les gradients de la perte par rapport à tous les paramètres du modèle via la **rétropropagation** (backpropagation).

```python
# PyTorch construit un graphe de calcul automatiquement
x = torch.tensor([2.0], requires_grad=True)
y = x ** 2  # y = 4
y.backward()  # dy/dx = 2x = 4
print(x.grad)  # tensor([4.])
```

#### Étape 6: `optimizer.step()`

L'optimiseur met à jour les poids selon sa stratégie :

```python
# SGD: w = w - lr * gradient
# Adam: plus sophistiqué (momentum + adaptation du learning rate)
optimizer = optim.Adam(model.parameters(), lr=0.001)
```

### 6.3 Implémentation complète

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau


class Trainer:
    """Classe d'entraînement du modèle MLP."""

    def __init__(
        self,
        model: nn.Module,
        train_loader,
        val_loader,
        device: torch.device,
        lr: float = 1e-3,
        weight_decay: float = 1e-4
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device

        # Fonction de perte: MSE pour régression
        self.criterion = nn.MSELoss()

        # Optimiseur: AdamW (Adam avec weight decay correct)
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=lr,
            weight_decay=weight_decay  # Régularisation L2
        )

        # Scheduler: réduit le LR si la validation stagne
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',       # Minimiser la perte
            factor=0.5,       # LR = LR * 0.5
            patience=10,      # Attendre 10 epochs sans amélioration
            verbose=True
        )

        # Historique pour visualisation
        self.history = {"train_loss": [], "val_loss": [], "lr": []}
        self.best_val_loss = float('inf')

    def train_epoch(self) -> float:
        """Entraîne le modèle pour une epoch."""
        self.model.train()  # Mode entraînement
        total_loss = 0.0
        n_batches = 0

        for states, commands in self.train_loader:
            # Transférer sur le device (CPU ou GPU)
            states = states.to(self.device)
            commands = commands.to(self.device)

            # Forward pass
            self.optimizer.zero_grad()
            predictions = self.model(states)
            loss = self.criterion(predictions, commands)

            # Backward pass
            loss.backward()

            # Gradient clipping (évite l'explosion des gradients)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            # Update
            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        return total_loss / n_batches

    @torch.no_grad()  # Désactive le calcul des gradients
    def validate(self) -> float:
        """Évalue le modèle sur le set de validation."""
        self.model.eval()  # Mode évaluation (désactive Dropout)
        total_loss = 0.0
        n_batches = 0

        for states, commands in self.val_loader:
            states = states.to(self.device)
            commands = commands.to(self.device)

            predictions = self.model(states)
            loss = self.criterion(predictions, commands)

            total_loss += loss.item()
            n_batches += 1

        return total_loss / n_batches

    def train(
        self,
        epochs: int,
        save_path: str,
        early_stopping_patience: int = 20
    ):
        """Boucle d'entraînement principale."""
        no_improve_count = 0

        for epoch in range(1, epochs + 1):
            # Entraînement et validation
            train_loss = self.train_epoch()
            val_loss = self.validate()

            # Enregistrer l'historique
            current_lr = self.optimizer.param_groups[0]['lr']
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["lr"].append(current_lr)

            # Mise à jour du scheduler
            self.scheduler.step(val_loss)

            # Sauvegarder si meilleur modèle
            is_best = val_loss < self.best_val_loss
            if is_best:
                self.best_val_loss = val_loss
                no_improve_count = 0
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'val_loss': val_loss,
                    'input_dim': self.model.input_dim,
                    'output_dim': self.model.output_dim,
                    'hidden_dims': self.model.hidden_dims,
                }, save_path)
            else:
                no_improve_count += 1

            # Affichage
            marker = " *" if is_best else ""
            print(f"Epoch {epoch:3d} | Train: {train_loss:.6f} | Val: {val_loss:.6f} | LR: {current_lr:.2e}{marker}")

            # Early stopping
            if no_improve_count >= early_stopping_patience:
                print(f"Early stopping après {epoch} epochs")
                break

        return self.history
```

### 6.4 Techniques d'optimisation avancées

#### Learning Rate Scheduling

Le learning rate est crucial. Trop grand = instabilité, trop petit = convergence lente.

```python
# Option 1: ReduceLROnPlateau (utilisé ci-dessus)
# Réduit le LR quand la métrique stagne

# Option 2: StepLR
# Réduit le LR tous les N epochs
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)

# Option 3: CosineAnnealingLR
# LR suit une courbe cosinus
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
```

#### Early Stopping

Arrête l'entraînement quand le modèle commence à sur-apprendre :

```
Epoch 50: Val loss = 0.0120
Epoch 51: Val loss = 0.0118 *  ← Meilleur
Epoch 52: Val loss = 0.0119
Epoch 53: Val loss = 0.0121    ← Commence à remonter
...
Epoch 71: Val loss = 0.0145    ← 20 epochs sans amélioration → STOP
```

#### Gradient Clipping

Empêche l'explosion des gradients en les bornant :

```python
# Norme maximale des gradients = 1.0
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
```

---

## 7. Évaluation et validation

### 7.1 Métriques pour la régression

```python
import numpy as np

def evaluate_model(model, test_loader, device):
    """Évalue le modèle avec plusieurs métriques."""
    model.eval()

    all_predictions = []
    all_targets = []

    with torch.no_grad():
        for states, commands in test_loader:
            states = states.to(device)
            predictions = model(states)

            all_predictions.append(predictions.cpu().numpy())
            all_targets.append(commands.numpy())

    predictions = np.concatenate(all_predictions)
    targets = np.concatenate(all_targets)

    # MSE (Mean Squared Error)
    mse = np.mean((predictions - targets) ** 2)

    # MAE (Mean Absolute Error)
    mae = np.mean(np.abs(predictions - targets))

    # RMSE (Root Mean Squared Error)
    rmse = np.sqrt(mse)

    # R² (coefficient de détermination)
    ss_res = np.sum((targets - predictions) ** 2)
    ss_tot = np.sum((targets - np.mean(targets)) ** 2)
    r2 = 1 - (ss_res / ss_tot)

    return {
        "mse": mse,
        "mae": mae,
        "rmse": rmse,
        "r2": r2
    }
```

### 7.2 Interprétation des métriques

| Métrique | Interprétation |
|----------|----------------|
| **MSE** | Erreur quadratique moyenne. Pénalise fortement les grandes erreurs. |
| **MAE** | Erreur absolue moyenne. Plus robuste aux outliers. |
| **RMSE** | Racine de MSE. Même unité que les données. |
| **R²** | Proportion de variance expliquée. 1.0 = parfait, 0 = aléatoire. |

Pour notre cas (commandes moteur dans [-1, 1]) :
- **RMSE < 0.1** : Excellent
- **RMSE < 0.2** : Bon
- **RMSE > 0.3** : À améliorer

### 7.3 Visualisation des prédictions

```python
import matplotlib.pyplot as plt

def plot_predictions(model, test_loader, device, n_samples=100):
    """Visualise les prédictions vs les cibles."""
    model.eval()

    predictions = []
    targets = []

    with torch.no_grad():
        for states, commands in test_loader:
            states = states.to(device)
            pred = model(states).cpu().numpy()
            predictions.extend(pred)
            targets.extend(commands.numpy())
            if len(predictions) >= n_samples:
                break

    predictions = np.array(predictions[:n_samples])
    targets = np.array(targets[:n_samples])

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Vitesse gauche
    axes[0].scatter(targets[:, 0], predictions[:, 0], alpha=0.5)
    axes[0].plot([-1, 1], [-1, 1], 'r--', label='Parfait')
    axes[0].set_xlabel('Cible')
    axes[0].set_ylabel('Prédiction')
    axes[0].set_title('Vitesse Gauche')
    axes[0].legend()

    # Vitesse droite
    axes[1].scatter(targets[:, 1], predictions[:, 1], alpha=0.5)
    axes[1].plot([-1, 1], [-1, 1], 'r--', label='Parfait')
    axes[1].set_xlabel('Cible')
    axes[1].set_ylabel('Prédiction')
    axes[1].set_title('Vitesse Droite')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig('predictions.png')
    plt.show()
```

### 7.4 Intégration dans le pipeline d'entraînement (train.py)

Notre implémentation `train.py` intègre automatiquement l'évaluation détaillée à la fin de l'entraînement.

#### Flux d'exécution:

```
1. Entraînement (loop epochs)
   └─ train_epoch()      → Descente de gradient sur les données
   └─ validate()         → Loss simple de validation
   └─ scheduler.step()   → Ajuste learning rate

2. Post-Entraînement (Automatique)
   ├─ Charger le meilleur modèle (best_model.pt)
   ├─ evaluate()         → Calcul des métriques (MSE, MAE, RMSE, R²)
   └─ visualize_results()→ 4 graphiques:
      1. Prédictions vs Cibles (scatter plot)
      2. Erreurs vs Cibles (residuals)
      3. Courbe de perte d'entraînement
      4. Évolution du learning rate
```

#### Méthode `evaluate()` (Trainer class):

```python
metrics = trainer.evaluate()  # Utilise val_loader par défaut

# Retourne: MSE, MAE, RMSE, R² + predictions/targets brutes
print(f"RMSE: {metrics['rmse']:.6f}")
print(f"R²:   {metrics['r2']:.6f}")
```

**Interprétation RMSE pour [-1, 1]:**
- `RMSE < 0.1` → Excellent (commandes moteur très précises)
- `RMSE < 0.2` → Bon
- `RMSE < 0.3` → Acceptable
- `RMSE > 0.3` → À améliorer

#### Méthode `visualize_results()` (Trainer class):

```python
trainer.visualize_results(metrics, save_dir)
```

Génère 4 fichiers PNG dans `save_dir/`:
1. **predictions.png**: Chaque output (vitesse gauche/droite) en scatter plot
2. **residuals.png**: Analyse des erreurs
3. **training_loss.png**: Courbe MSE train vs validation
4. **learning_rate.png**: Évolution du LR (échelle log)

#### Exemple de sortie (affichage):

```
============================================================
ÉVALUATION DÉTAILLÉE DU MODÈLE
============================================================

📊 Métriques d'évaluation:
  MSE:  0.001234
  MAE:  0.025678
  RMSE: 0.035124
  R²:   0.985432

Interprétation RMSE: ✅ Excellent

📈 Génération des visualisations...
  Graphique sauvegardé: checkpoints/predictions.png
  Graphique sauvegardé: checkpoints/residuals.png
  Graphique sauvegardé: checkpoints/training_loss.png
  Graphique sauvegardé: checkpoints/learning_rate.png

Rapport sauvegardé: checkpoints/training_report.json
```

#### Rapport JSON enrichi:

Le fichier `training_report.json` inclut maintenant:

```json
{
  "evaluation": {
    "mse": 0.001234,
    "mae": 0.025678,
    "rmse": 0.035124,
    "r2": 0.985432
  },
  "training": {
    "epochs": 87,
    "best_val_loss": 0.001234,
    ...
  }
}
```

---

## 8. Sauvegarde et chargement

### 8.1 Sauvegarder un modèle

PyTorch offre deux approches :

```python
# Méthode 1: Sauvegarder seulement les poids (RECOMMANDÉ)
torch.save(model.state_dict(), 'model_weights.pt')

# Méthode 2: Sauvegarder le modèle complet (moins portable)
torch.save(model, 'model_complete.pt')
```

**Pourquoi préférer state_dict ?**
- Plus portable entre versions de PyTorch
- Plus petit en taille
- Plus flexible (peut charger dans une architecture légèrement différente)

### 8.2 Sauvegarder un checkpoint complet

Pour pouvoir reprendre l'entraînement :

```python
checkpoint = {
    'epoch': epoch,
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'scheduler_state_dict': scheduler.state_dict(),
    'val_loss': val_loss,
    'history': history,
    # Métadonnées du modèle
    'input_dim': model.input_dim,
    'output_dim': model.output_dim,
    'hidden_dims': model.hidden_dims,
}
torch.save(checkpoint, 'checkpoint.pt')
```

### 8.3 Charger un modèle

```python
def load_model(checkpoint_path: str, device: torch.device):
    """Charge un modèle depuis un checkpoint."""
    # Charger le checkpoint
    checkpoint = torch.load(checkpoint_path, map_location=device)

    # Recréer l'architecture
    model = ZumiMLP(
        input_dim=checkpoint['input_dim'],
        output_dim=checkpoint['output_dim'],
        hidden_dims=checkpoint['hidden_dims']
    )

    # Charger les poids
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()  # Mode évaluation par défaut

    print(f"Modèle chargé (epoch {checkpoint['epoch']}, val_loss={checkpoint['val_loss']:.6f})")

    return model
```

---

## 9. Conversion vers TensorFlow Lite

### 9.1 Pourquoi convertir ?

| Aspect | PyTorch | TensorFlow Lite |
|--------|---------|-----------------|
| Taille runtime | ~500 MB | ~5 MB (tflite-runtime) |
| Support ARM | Limité | Excellent |
| Quantization | Manuel | Intégré |
| Optimisation embarquée | Non | Oui (XNNPack, GPU delegate) |

### 9.2 Pipeline de conversion

PyTorch ne peut pas être converti directement en TFLite. On passe par ONNX :

```
PyTorch (.pt) → ONNX (.onnx) → TensorFlow (SavedModel) → TFLite (.tflite)
```

### 9.3 Étape 1: Export vers ONNX

```python
import torch

def export_to_onnx(model, input_dim, output_path):
    """Exporte un modèle PyTorch vers ONNX."""
    model.eval()

    # Créer une entrée factice de la bonne forme
    dummy_input = torch.randn(1, input_dim)

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=['state'],      # Nom de l'entrée
        output_names=['command'],   # Nom de la sortie
        dynamic_axes={              # Permettre des tailles de batch variables
            'state': {0: 'batch_size'},
            'command': {0: 'batch_size'}
        },
        opset_version=13,           # Version des opérations ONNX
        do_constant_folding=True    # Optimisation: pré-calculer les constantes
    )
    print(f"Exporté vers: {output_path}")


# Usage
model = load_model('best_model.pt', device='cpu')
export_to_onnx(model, input_dim=21, output_path='model.onnx')
```

### 9.4 Étape 2: ONNX vers TensorFlow

```python
import onnx
from onnx_tf.backend import prepare

def convert_onnx_to_tf(onnx_path, tf_output_dir):
    """Convertit ONNX vers TensorFlow SavedModel."""
    # Charger le modèle ONNX
    onnx_model = onnx.load(onnx_path)

    # Convertir vers TensorFlow
    tf_rep = prepare(onnx_model)

    # Exporter comme SavedModel
    tf_rep.export_graph(tf_output_dir)
    print(f"SavedModel créé: {tf_output_dir}")


# Usage
convert_onnx_to_tf('model.onnx', 'model_tf/')
```

### 9.5 Étape 3: TensorFlow vers TFLite

```python
import tensorflow as tf

def convert_tf_to_tflite(tf_dir, tflite_path, quantize=False):
    """Convertit TensorFlow SavedModel vers TFLite."""
    converter = tf.lite.TFLiteConverter.from_saved_model(tf_dir)

    if quantize:
        # Quantization dynamique: poids en int8, calculs en float
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        print("Quantization activée")

    # Convertir
    tflite_model = converter.convert()

    # Sauvegarder
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)

    # Afficher la taille
    size_kb = len(tflite_model) / 1024
    print(f"TFLite créé: {tflite_path} ({size_kb:.1f} KB)")


# Usage
convert_tf_to_tflite('model_tf/', 'model.tflite', quantize=True)
```

### 9.6 Quantization

La quantization réduit la taille et accélère l'inférence en utilisant des entiers au lieu de floats :

| Type | Poids | Activations | Taille | Vitesse |
|------|-------|-------------|--------|---------|
| Float32 | float32 | float32 | 100% | 1x |
| Dynamic | int8 | float32 | ~25% | ~2x |
| Full int8 | int8 | int8 | ~25% | ~4x |

Pour notre MLP de ~3500 paramètres :
- Float32 : ~14 KB
- Quantized : ~4 KB

### 9.7 Vérification du modèle converti

```python
import tensorflow as tf
import numpy as np

def verify_tflite(tflite_path, input_dim):
    """Vérifie que le modèle TFLite fonctionne."""
    # Charger l'interpréteur
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()

    # Obtenir les détails des tenseurs
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"Input: {input_details[0]['shape']} ({input_details[0]['dtype']})")
    print(f"Output: {output_details[0]['shape']} ({output_details[0]['dtype']})")

    # Test avec données aléatoires
    test_input = np.random.uniform(-1, 1, (1, input_dim)).astype(np.float32)
    interpreter.set_tensor(input_details[0]['index'], test_input)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])

    print(f"Test output: {output.flatten()}")
    print(f"Output range: [{output.min():.3f}, {output.max():.3f}]")


verify_tflite('model.tflite', input_dim=21)
```

---

## 10. Déploiement sur système embarqué

### 10.1 Installation sur Raspberry Pi

```bash
# Sur le Pi Zero 2 W (ARM64)
pip install tflite-runtime

# Vérifier l'installation
python -c "import tflite_runtime.interpreter as tflite; print('OK')"
```

### 10.2 Classe d'inférence pour le robot

```python
import numpy as np

class TFLiteInference:
    """Wrapper pour l'inférence TFLite sur systèmes embarqués."""

    def __init__(self, model_path: str):
        # Importer le runtime approprié
        try:
            import tflite_runtime.interpreter as tflite
        except ImportError:
            import tensorflow.lite as tflite

        # Charger le modèle
        self._interpreter = tflite.Interpreter(model_path=model_path)
        self._interpreter.allocate_tensors()

        # Cacher les détails pour performances
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()
        self._input_index = self._input_details[0]['index']
        self._output_index = self._output_details[0]['index']

    def predict(self, state_vector: np.ndarray) -> np.ndarray:
        """Prédit les commandes moteur à partir de l'état.

        Args:
            state_vector: Vecteur d'état normalisé (shape: [dim])

        Returns:
            Commandes moteur [left, right] dans [-1, 1]
        """
        # Reshape pour batch de 1
        input_data = state_vector.reshape(1, -1).astype(np.float32)

        # Inférence
        self._interpreter.set_tensor(self._input_index, input_data)
        self._interpreter.invoke()
        output = self._interpreter.get_tensor(self._output_index)

        return output[0]  # Retirer la dimension batch


# Usage
model = TFLiteInference('zumi_mlp.tflite')

# Exemple avec un vecteur d'état
state = np.array([0.5, 0.3, 0.2, 0.8, 0.1, 0.9,  # IR sensors
                  1.0, 0, 0, 1, 0,                 # Detection
                  0.5, 0.3, 0.1, 0.2,              # Bbox
                  0.01, -0.02, 0.98, 0.001, 0.003, -0.002])  # IMU

commands = model.predict(state)
print(f"Commandes: left={commands[0]:.3f}, right={commands[1]:.3f}")
```

### 10.3 Intégration dans le contrôleur

Voir [`core/control/controlers/ml_controller.py`](../core/control/controlers/ml_controller.py) pour l'implémentation complète intégrée au système de contrôle du robot.

### 10.4 Considérations de performance

| Aspect | Valeur typique Pi Zero 2 |
|--------|--------------------------|
| Temps d'inférence (MLP small) | ~1-2 ms |
| Temps d'inférence (MLP medium) | ~3-5 ms |
| Fréquence de contrôle visée | 20-50 Hz |
| Mémoire utilisée | ~5-10 MB |

---

## 11. Bonnes pratiques et optimisations

### 11.1 Collecte des données

- **Diversité** : Varier les situations (ligne droite, virages, obstacles)
- **Équilibre** : Éviter la sur-représentation d'une action (ex: tout droit)
- **Qualité** : Supprimer les données aberrantes (opérateur distrait)
- **Quantité** : Minimum ~1000 échantillons, idéalement 5000+

### 11.2 Prétraitement

```python
def analyze_dataset(dataset):
    """Analyse la distribution des données."""
    stats = {
        'n_samples': len(dataset),
        'input_mean': dataset.captures.mean(axis=0),
        'input_std': dataset.captures.std(axis=0),
        'output_mean': dataset.labels.mean(axis=0),
        'output_std': dataset.labels.std(axis=0),
    }

    # Vérifier les problèmes
    # - Features avec variance nulle (inutiles)
    zero_var = np.where(stats['input_std'] < 1e-6)[0]
    if len(zero_var) > 0:
        print(f"ATTENTION: Features {zero_var} ont variance nulle")

    # - Déséquilibre des sorties
    print(f"Distribution des sorties:")
    print(f"  Left:  mean={stats['output_mean'][0]:.3f}, std={stats['output_std'][0]:.3f}")
    print(f"  Right: mean={stats['output_mean'][1]:.3f}, std={stats['output_std'][1]:.3f}")

    return stats
```

### 11.3 Choix des hyperparamètres

| Hyperparamètre | Valeur de départ | Ajustement |
|----------------|------------------|------------|
| Learning rate | 1e-3 | Réduire si instable, augmenter si lent |
| Batch size | 32 | Augmenter si assez de mémoire |
| Hidden layers | [64, 32] | Augmenter si sous-apprentissage |
| Dropout | 0.1 | Augmenter si sur-apprentissage |
| Epochs | 100 | Avec early stopping, pas critique |

### 11.4 Debugging courant

```python
# 1. Vérifier que le modèle apprend
# Si train_loss ne diminue pas:
# - Réduire le learning rate
# - Vérifier les données (valeurs aberrantes?)
# - Augmenter la capacité du modèle

# 2. Vérifier le sur-apprentissage
# Si val_loss remonte alors que train_loss diminue:
# - Augmenter le dropout
# - Réduire la capacité du modèle
# - Collecter plus de données
# - Utiliser data augmentation

# 3. Vérifier les gradients
def check_gradients(model):
    for name, param in model.named_parameters():
        if param.grad is not None:
            grad_norm = param.grad.norm()
            print(f"{name}: grad_norm = {grad_norm:.6f}")
            if grad_norm > 100:
                print("  ATTENTION: gradient explosion!")
            if grad_norm < 1e-7:
                print("  ATTENTION: gradient vanishing!")
```

---

## 12. Dépannage et problèmes courants

### 12.1 Erreurs de conversion

**Problème** : ONNX export échoue avec "Unsupported operator"

**Solution** : Utiliser une opset_version plus récente ou remplacer l'opération

```python
# Remplacer
x = torch.where(condition, a, b)
# Par
x = condition.float() * a + (1 - condition.float()) * b
```

### 12.2 Différence de comportement PyTorch vs TFLite

**Problème** : Les prédictions diffèrent entre PyTorch et TFLite

**Causes possibles** :
1. Différence de précision float32/float16
2. Quantization mal calibrée
3. Opérations implémentées différemment

**Diagnostic** :
```python
def compare_outputs(pytorch_model, tflite_path, input_dim, n_tests=10):
    """Compare les sorties PyTorch et TFLite."""
    pytorch_model.eval()

    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()

    for i in range(n_tests):
        test_input = np.random.uniform(-1, 1, (1, input_dim)).astype(np.float32)

        # PyTorch
        with torch.no_grad():
            pt_out = pytorch_model(torch.from_numpy(test_input)).numpy()

        # TFLite
        interpreter.set_tensor(0, test_input)
        interpreter.invoke()
        tfl_out = interpreter.get_tensor(interpreter.get_output_details()[0]['index'])

        diff = np.abs(pt_out - tfl_out).max()
        print(f"Test {i+1}: max_diff = {diff:.6f}")
```

### 12.3 Performance insuffisante sur Pi

**Problème** : Inférence trop lente

**Solutions** :
1. Utiliser un modèle plus petit (ZumiMLPSmall)
2. Activer la quantization
3. Réduire la fréquence de contrôle
4. Utiliser XNNPack delegate :
```python
interpreter = tf.lite.Interpreter(
    model_path='model.tflite',
    num_threads=4  # Utiliser tous les cœurs
)
```

---

## Annexe A: Références

- [PyTorch Documentation](https://pytorch.org/docs/stable/index.html)
- [TensorFlow Lite Guide](https://www.tensorflow.org/lite/guide)
- [ONNX Tutorials](https://onnx.ai/onnx/intro/index.html)
- [Machine Learning Expedition - MLP Tutorial](https://www.machinelearningexpedition.com/how-to-train-multilayer-perceptron-in-pytorch/)

## Annexe B: Commandes rapides

```bash
# Entraînement
python train.py --epochs 100 --model-size medium

# Conversion
python convert_to_tflite.py --quantize

# Déploiement
scp export/zumi_mlp.tflite pi@raspberrypi:~/robot/models/
```

---

*Document créé le 17 mars 2026 - Projet PFE GPA 793*
