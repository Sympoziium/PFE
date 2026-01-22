# Workflow Git – Procédure pour Débutants

Ce guide décrit pas à pas le workflow recommandé pour travailler en équipe avec Git sur le projet Zumi. Il est conçu pour des utilisateurs débutants.

---

## Objectif
- Travailler proprement sans casser la branche `main`.
- Utiliser une branche par tâche (feature, bugfix, docs, tests).
- Synchroniser régulièrement votre travail avec GitHub.
- Proposer vos changements via une Pull Request (PR).

## Pré-requis
- Git installé (Windows: installer depuis https://git-scm.com/downloads).
- Identité Git configurée (une seule fois):

```bash
git config --global user.name "Votre Nom"
git config --global user.email "votre.email@example.com"
```

Sur Windows, vous pouvez utiliser Git Bash ou le terminal intégré de VS Code.

---

## 1. Première utilisation (clonage du dépôt)

```bash
# Cloner le dépôt du projet
git clone https://github.com/Sympoziium/PFE.git

# Entrer dans le dossier du projet
cd PFE
```

---

## 2. Début de journée

```bash
# Se placer sur la branche principale et la mettre à jour
git checkout main
git pull origin main

# Créer ou basculer sur votre branche de travail
git checkout -b feature/ma-fonctionnalite        # création
# ou
git checkout feature/ma-fonctionnalite           # si elle existe déjà
```

Convention de nommage des branches:
- `feature/nom-fonctionnalite`
- `bugfix/description-correctif`
- `docs/mise-a-jour-doc`
- `test/ajout-tests`

---

## 3. Pendant le travail

```bash
# Vérifier l’état / voir la liste des fichiers modifié
git status

# Ajouter vos modifications
git add .                      # tous les fichiers modifiés
# ou
git add chemin/fichier.py      # fichier spécifique

# Commit avec un message clair et descriptif
git commit -m "Ajout de la détection d’obstacles"
```

Bonnes pratiques pour les commits:
- Petites unités cohérentes (code + message clair).
- Éviter les messages vagues (ex: "fix", "misc").

---

## 4. Sauvegarder sur GitHub

```bash
# Première fois sur cette branche
git push -u origin feature/ma-fonctionnalite

# Ensuite (les fois suivantes)
git push
```

---

## 5. Fin de journée

```bash
# S’assurer que tout est commité
git status

# Pousser votre travail pour le partager et le sauvegarder
git push
```

---

## 6. Mettre à jour votre branche avec `main`

Régulièrement (et avant d’ouvrir une PR), synchronisez votre branche:

```bash
# Mettre main à jour
git checkout main
git pull origin main

# Revenir à votre branche et fusionner
git checkout feature/ma-fonctionnalite
git merge main
```

## 7. Ouvrir une Pull Request (PR)

1. Pousser votre branche (`git push`).
2. Aller sur GitHub: `Sympoziium/PFE` → onglet "Pull requests" → "New pull request".
3. Choisir la base: `main` et votre branche en comparaison.
4. Décrire clairement la modification (but, fichiers impactés, tests).
5. Demander une revue à un collègue.
6. Après approbation, fusionner la PR.

Après fusion:
```bash
git checkout main
git pull origin main
```

---

## 8. Résoudre des conflits (cas fréquent)

```bash
# Voir les fichiers en conflit
git status

# Ouvrir les fichiers marqués et résoudre les sections entre
# <<<<<<<, =======, >>>>>>>

# Marquer comme résolu
git add fichier_resolu.py

# Finaliser
git commit -m "Résolution de conflits"
```

Astuce VS Code: le comparateur intégré propose des boutons "Accepter la modification entrante/locale" pour faciliter la résolution.

---

## 9. Bonnes pratiques d’équipe

- Ne jamais développer directement sur `main`.
- Une branche par sujet; fusion via PR uniquement.
- Mettre `main` à jour chaque matin et avant d’ouvrir une PR.
- Commits fréquents et messages explicites.
- Ignorer les fichiers temporaires via `.gitignore`.

---

## 10. Aide rapide

```bash
git status              # état
git branch              # lister les branches
git checkout -b ...     # créer + basculer
git add .               # ajouter toutes les modifs
git commit -m "..."     # enregistrer
git push                # envoyer sur GitHub
git pull origin main    # mettre main à jour
git merge main          # fusionner main dans votre branche
git log --oneline       # historique condensé
```

Pour plus de détails, voir aussi: `AIDE_MEMOIRE_GIT.md` et `GUIDE_GIT.md`.