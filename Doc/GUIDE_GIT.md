# Guide Git Bash pour Débutants

## 📚 Table des Matières
1. [Introduction à Git](#introduction-à-git)
2. [Installation et Configuration](#installation-et-configuration)
3. [Concepts Fondamentaux](#concepts-fondamentaux)
4. [Commandes de Base](#commandes-de-base)
5. [Travailler avec les Branches](#travailler-avec-les-branches)
6. [Synchronisation avec GitHub](#synchronisation-avec-github)
7. [Workflow Collaboratif](#workflow-collaboratif)
8. [Résolution de Problèmes Courants](#résolution-de-problèmes-courants)
9. [Bonnes Pratiques](#bonnes-pratiques)

---

## Introduction à Git

### Qu'est-ce que Git ?
Git est un système de contrôle de version distribué qui permet de :
- 📝 Suivre l'historique des modifications du code
- 👥 Collaborer efficacement en équipe
- 🔄 Gérer différentes versions du projet
- ↩️ Revenir à une version antérieure en cas de problème

### Qu'est-ce que Git Bash ?
Git Bash est une application qui fournit une interface en ligne de commande pour Git sur Windows. Elle émule un environnement Bash (comme sous Linux/Mac).

---

## Installation et Configuration

### Installation de Git
1. Téléchargez Git depuis [git-scm.com](https://git-scm.com/downloads)
2. Exécutez l'installateur
3. Utilisez les options par défaut (recommandé pour les débutants)

### Configuration Initiale
Après l'installation, ouvrez Git Bash et configurez votre identité :

```bash
# Configuration de votre nom (utilisé dans les commits)
git config --global user.name "Votre Nom"

# Configuration de votre email (utilisé dans les commits)
git config --global user.email "votre.email@example.com"

# Vérifier votre configuration
git config --list
```

**Exemple concret :**
```bash
git config --global user.name "Ahmed Ben Ali"
git config --global user.email "ahmed.benali@example.com"
```

---

## Concepts Fondamentaux

### Les Trois États de Git
1. **Working Directory** (Répertoire de travail) : où vous modifiez vos fichiers
2. **Staging Area** (Zone de préparation) : où vous préparez vos modifications
3. **Repository** (Dépôt) : où Git stocke l'historique permanent

### Schéma de Flux
```
Working Directory → (git add) → Staging Area → (git commit) → Repository → (git push) → GitHub
```

---

## Commandes de Base

### 1. Cloner un Dépôt Existant

Pour télécharger le projet depuis GitHub :

```bash
# faites un fork du dépôt du projet Zumi puis clonez votre fork
git clone https://github.com/VOTRE-ORG/PFE.git



# Se déplacer dans le dossier du projet
cd PFE
```

### 2. Vérifier l'État du Dépôt

```bash
# Voir les fichiers modifiés
git status

# Voir les modifications détaillées
git diff
```

**Exemple de sortie de `git status` :**
```
On branch main
Changes not staged for commit:
  modified:   robot_code.py
  
Untracked files:
  new_feature.py
```

### 3. Ajouter des Modifications

```bash
# Ajouter un fichier spécifique
git add nom_du_fichier.py

# Ajouter plusieurs fichiers
git add fichier1.py fichier2.py

# Ajouter tous les fichiers modifiés
git add .

# Ajouter tous les fichiers Python
git add *.py
```

**Exemple concret :**
```bash
# Vous avez modifié un fichier de contrôle du robot
git add zumi_controller.py
```

### 4. Enregistrer les Modifications (Commit)

```bash
# Faire un commit avec un message
git commit -m "Description de vos modifications"

# Exemple avec un message descriptif
git commit -m "Ajout de la fonction de détection d'obstacles"
```

**Bonnes pratiques pour les messages de commit :**
- ✅ "Ajout de la fonction de navigation autonome"
- ✅ "Correction du bug de calibration des capteurs"
- ✅ "Mise à jour de la documentation du module IA"
- ❌ "modifs"
- ❌ "test"
- ❌ "ça marche"

### 5. Voir l'Historique

```bash
# Voir l'historique des commits
git log

# Voir l'historique de manière condensée
git log --oneline

# Voir les 5 derniers commits
git log -5

# Voir l'historique avec un graphique des branches
git log --graph --oneline --all
```

---

## Travailler avec les Branches

### Qu'est-ce qu'une Branche ?
Une branche est une version parallèle du code qui permet de développer des fonctionnalités sans affecter la branche principale.

### 1. Créer une Nouvelle Branche

```bash
# Créer une nouvelle branche
git branch nom-de-la-branche

# Créer et basculer directement sur la nouvelle branche
git checkout -b nom-de-la-branche

# Syntaxe moderne (Git 2.23+)
git switch -c nom-de-la-branche
```

**Exemple concret pour le projet Zumi :**
```bash
# Créer une branche pour développer la reconnaissance d'objets
git checkout -b feature/reconnaissance-objets

# Créer une branche pour corriger un bug
git checkout -b bugfix/correction-capteur-distance

# Créer une branche pour votre travail personnel
git checkout -b dev/ahmed/navigation-autonome
```

### 2. Lister les Branches

```bash
# Voir toutes les branches locales
git branch

# Voir toutes les branches (locales et distantes)
git branch -a

# Voir les branches avec le dernier commit
git branch -v
```

### 3. Basculer entre les Branches

```bash
# Changer de branche
git checkout nom-de-la-branche

# Syntaxe moderne
git switch nom-de-la-branche

# Revenir à la branche principale
git checkout main
```

**Exemple :**
```bash
# Passer à votre branche de développement
git checkout feature/reconnaissance-objets

# Revenir à la branche principale
git checkout main
```

### 4. Mettre à Jour une Branche

#### Mettre à jour depuis la branche principale (main/master)

```bash
# Étape 1 : Assurez-vous d'être sur votre branche
git checkout votre-branche

# Étape 2 : Récupérer les dernières modifications de main
git checkout main
git pull origin main

# Étape 3 : Retourner à votre branche
git checkout votre-branche

# Étape 4 : Fusionner les modifications de main dans votre branche
git merge main
```

**Exemple complet :**
```bash
# Vous travaillez sur la reconnaissance d'objets
git checkout feature/reconnaissance-objets

# Vous voulez récupérer les dernières modifications de l'équipe
git checkout main
git pull origin main
git checkout feature/reconnaissance-objets
git merge main
```

#### Alternative avec rebase (plus avancé)

```bash
# Sur votre branche
git checkout votre-branche

# Récupérer et appliquer les modifications de main
git fetch origin
git rebase origin/main
```

### 5. Supprimer une Branche

```bash
# Supprimer une branche locale (après fusion)
git branch -d nom-de-la-branche

# Forcer la suppression (si la branche n'est pas fusionnée)
git branch -D nom-de-la-branche

# Supprimer une branche distante
git push origin --delete nom-de-la-branche
```

---

## Synchronisation avec GitHub

### 1. Récupérer les Modifications (Pull)

```bash
# Récupérer et fusionner les modifications depuis GitHub
git pull origin nom-de-la-branche

# Exemple : récupérer les modifications de la branche main
git pull origin main
```

### 2. Envoyer les Modifications (Push)

```bash
# Envoyer vos commits vers GitHub
git push origin nom-de-la-branche

# Première fois : créer la branche sur GitHub
git push -u origin nom-de-la-branche

# Ensuite, vous pouvez simplement faire
git push
```

**Exemple complet d'un workflow :**
```bash
# 1. Créer une branche pour une nouvelle fonctionnalité
git checkout -b feature/detection-visage

# 2. Modifier des fichiers
# ... (vous codez la détection de visage)

# 3. Vérifier les modifications
git status

# 4. Ajouter les fichiers modifiés
git add face_detection.py
git add utils.py

# 5. Faire un commit
git commit -m "Ajout du module de détection de visage avec OpenCV"

# 6. Envoyer vers GitHub
git push -u origin feature/detection-visage
```

### 3. Récupérer les Informations sans Fusionner (Fetch)

```bash
# Télécharger les informations depuis GitHub sans modifier votre code
git fetch origin

# Voir les différences avec la version distante
git diff origin/main
```

---

## Workflow Collaboratif

### Procédure Quotidienne Recommandée

#### Début de Journée

```bash
# 1. Récupérer les dernières modifications
git checkout main
git pull origin main

# 2. Créer ou basculer sur votre branche de travail
git checkout votre-branche
# OU créer une nouvelle branche
git checkout -b feature/nouvelle-fonctionnalite

# 3. Mettre à jour votre branche avec les dernières modifications de main
git merge main
```

#### Pendant le Travail

```bash
# 1. Vérifier régulièrement l'état
git status

# 2. Faire des commits réguliers (plusieurs fois par jour)
git add fichiers_modifiés
git commit -m "Message descriptif"

# 3. Enregistrer votre travail sur GitHub
git push origin votre-branche
```

#### Fin de Travail

```bash
# 1. S'assurer que tout est commité
git status

# 2. Pousser vos modifications
git push origin votre-branche

# 3. Créer une Pull Request sur GitHub pour faire réviser votre code
# (se fait sur l'interface web de GitHub)
```

### Créer une Pull Request (sur GitHub)

1. Allez sur https://github.com/VOTRE-ORG/PFE
2. Cliquez sur "Pull requests" → "New pull request"
3. Sélectionnez votre branche
4. Ajoutez un titre et une description
5. Demandez une révision à vos collègues
6. Une fois approuvée, fusionnez la Pull Request

---

## Résolution de Problèmes Courants

### Problème 1 : Conflits de Fusion

**Symptôme :** Message "CONFLICT" lors d'un merge ou pull

```bash
# Voir les fichiers en conflit
git status

# Les fichiers en conflit contiennent des marqueurs comme :
# <<<<<<< HEAD
# votre code
# =======
# code de l'autre personne
# >>>>>>> branche-autre
```

**Solution :**
```bash
# 1. Ouvrir les fichiers en conflit
# 2. Éditer manuellement pour résoudre les conflits
# 3. Supprimer les marqueurs <<<<, ====, >>>>
# 4. Ajouter les fichiers résolus
git add fichier_resolu.py

# 5. Finaliser la fusion
git commit -m "Résolution des conflits de fusion"
```

### Problème 2 : Annuler des Modifications

```bash
# Annuler les modifications d'un fichier (avant git add)
git checkout -- nom_du_fichier.py

# Syntaxe moderne
git restore nom_du_fichier.py

# Retirer un fichier de la staging area (après git add)
git reset HEAD nom_du_fichier.py

# Syntaxe moderne
git restore --staged nom_du_fichier.py

# Annuler le dernier commit (garde les modifications)
git reset --soft HEAD~1

# Annuler le dernier commit (supprime les modifications - ATTENTION!)
git reset --hard HEAD~1
```

### Problème 3 : Oublié de Créer une Branche

```bash
# Vous avez commencé à travailler sur main par erreur
# Créer une branche avec vos modifications actuelles
git checkout -b nouvelle-branche

# Vos modifications sont maintenant sur la nouvelle branche
```

### Problème 4 : Fichiers Non Désirés Ajoutés

```bash
# Retirer un fichier du suivi Git (mais le garder localement)
git rm --cached nom_du_fichier

# Ajouter le fichier à .gitignore pour l'ignorer à l'avenir
echo "nom_du_fichier" >> .gitignore
git add .gitignore
git commit -m "Ajout de nom_du_fichier à .gitignore"
```

### Problème 5 : Message d'Erreur "Your branch is behind"

```bash
# Votre branche est en retard par rapport à GitHub
# Solution : récupérer les modifications
git pull origin votre-branche

# Si vous avez des commits locaux, Git va faire une fusion automatique
```

### Problème 6 : Message d'Erreur "Failed to push"

```bash
# Quelqu'un a poussé des modifications avant vous
# Solution :
# 1. Récupérer les modifications
git pull origin votre-branche

# 2. Résoudre les éventuels conflits
# 3. Pousser à nouveau
git push origin votre-branche
```

---

## Bonnes Pratiques

### 1. Nommage des Branches

**Convention recommandée :**
```
type/description-courte

Types :
- feature/   : nouvelle fonctionnalité
- bugfix/    : correction de bug
- hotfix/    : correction urgente
- docs/      : documentation
- test/      : ajout de tests
- refactor/  : refactorisation
```

**Exemples :**
```bash
git checkout -b feature/suivi-ligne
git checkout -b bugfix/correction-vitesse-moteur
git checkout -b docs/guide-utilisation
git checkout -b test/ajout-tests-capteurs
```

### 2. Messages de Commit

**Format recommandé :**
```
Type: Description courte (50 caractères max)

Description détaillée si nécessaire (optionnel)
```

**Exemples :**
```bash
git commit -m "Feature: Ajout de la navigation autonome avec évitement d'obstacles"
git commit -m "Fix: Correction du bug de calibration du gyroscope"
git commit -m "Docs: Mise à jour du README avec les instructions d'installation"
git commit -m "Refactor: Restructuration du code de détection de ligne"
```

### 3. Commits Fréquents

- ✅ Faire des petits commits réguliers
- ✅ Chaque commit = une unité de travail logique
- ❌ Éviter les gros commits avec beaucoup de modifications

### 4. Synchronisation Régulière

```bash
# Au moins une fois par jour :
# 1. Récupérer les modifications de l'équipe
git pull origin main

# 2. Mettre à jour votre branche
git checkout votre-branche
git merge main

# 3. Pousser votre travail
git push origin votre-branche
```

### 5. Ne Jamais Travailler Directement sur Main

```bash
# ❌ MAUVAIS
git checkout main
# ... modifications ...
git commit -m "..."

# ✅ BON
git checkout -b feature/ma-fonctionnalite
# ... modifications ...
git commit -m "..."
git push origin feature/ma-fonctionnalite
```

### 6. Fichiers à Ignorer (.gitignore)

Créez un fichier `.gitignore` à la racine du projet :

```gitignore
# Fichiers Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/

# Fichiers IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Fichiers système
.DS_Store
Thumbs.db

# Fichiers de configuration locaux
config_local.py
*.local

# Fichiers de logs
*.log

# Données temporaires
/tmp/
/temp/
```

---

## Commandes Git - Aide-Mémoire Rapide

### Configuration
```bash
git config --global user.name "Votre Nom"
git config --global user.email "votre@email.com"
```

### Démarrer
```bash
git clone <url>                    # Cloner un dépôt
git init                           # Initialiser un nouveau dépôt
```

### Modifications
```bash
git status                         # Voir l'état
git diff                           # Voir les modifications
git add <fichier>                  # Ajouter un fichier
git add .                          # Ajouter tous les fichiers
git commit -m "message"            # Faire un commit
```

### Branches
```bash
git branch                         # Lister les branches
git branch <nom>                   # Créer une branche
git checkout <nom>                 # Changer de branche
git checkout -b <nom>              # Créer et changer de branche
git merge <branche>                # Fusionner une branche
git branch -d <nom>                # Supprimer une branche
```

### Synchronisation
```bash
git fetch                          # Récupérer les informations
git pull                           # Récupérer et fusionner
git push                           # Envoyer les commits
git push -u origin <branche>       # Envoyer une nouvelle branche
```

### Historique
```bash
git log                            # Voir l'historique
git log --oneline                  # Historique condensé
git log --graph --all              # Historique graphique
```

### Annulation
```bash
git restore <fichier>              # Annuler les modifications
git restore --staged <fichier>    # Retirer de staging
git reset --soft HEAD~1            # Annuler le dernier commit
```

---

## Ressources Supplémentaires

### Documentation Officielle
- [Documentation Git (EN)](https://git-scm.com/doc)
- [Git Book (EN/FR)](https://git-scm.com/book/fr/v2)

### Tutoriels Interactifs
- [Learn Git Branching](https://learngitbranching.js.org/?locale=fr_FR) - Tutoriel visuel interactif
- [Git-it](https://github.com/jlord/git-it-electron) - Application de tutoriel Git

### Aide en Ligne de Commande
```bash
# Obtenir de l'aide sur une commande
git help <commande>
git <commande> --help

# Exemples
git help commit
git help branch
```

---

## Contact et Support

Pour toute question sur Git ou des problèmes avec le dépôt :
1. Consultez d'abord ce guide
2. Cherchez sur [Stack Overflow](https://stackoverflow.com/questions/tagged/git)
3. Demandez de l'aide à vos collègues de l'équipe

**Bon courage avec le projet Zumi ! 🤖**

---

*Document créé pour le projet PFE - Robot Zumi*
*Version 1.0 - Janvier 2026*
