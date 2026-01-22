# 📋 Aide-Mémoire Git - Commandes Essentielles

*Guide de référence rapide pour le projet Zumi*

---

## ⚙️ Configuration Initiale (Une seule fois)

```bash
git config --global user.name "Votre Nom"
git config --global user.email "votre.email@example.com"
```

---

## 🚀 Démarrer avec le Projet

```bash
# Cloner le projet Zumi
git clone https://github.com/Sympoziium/PFE.git
cd PFE
```

---

## 📝 Workflow Quotidien

### 1️⃣ Début de Journée

```bash
# Mettre à jour main
git checkout main
git pull origin main

# Créer/basculer sur votre branche
git checkout -b feature/ma-fonctionnalite
# OU si la branche existe déjà
git checkout feature/ma-fonctionnalite
```

### 2️⃣ Pendant le Travail

```bash
# Vérifier l'état
git status

# Ajouter vos modifications
git add .                              # Tous les fichiers
git add nom_fichier.py                 # Un fichier spécifique

# Faire un commit
git commit -m "Description de la modification"
```

### 3️⃣ Envoyer vers GitHub

```bash
# Première fois
git push -u origin feature/ma-fonctionnalite

# Ensuite
git push
```

---

## 🌿 Commandes Branches

```bash
# Créer une nouvelle branche
git checkout -b feature/nom-feature

# Voir toutes les branches
git branch

# Changer de branche
git checkout nom-branche

# Supprimer une branche
git branch -d nom-branche
```

---

## 🔄 Mettre à Jour Votre Branche

```bash
# Récupérer les dernières modifications de main
git checkout main
git pull origin main

# Retourner à votre branche et fusionner
git checkout votre-branche
git merge main
```

---

## ↩️ Annuler des Modifications

```bash
# Annuler les modifications d'un fichier (avant git add)
git restore nom_fichier.py

# Retirer un fichier de staging (après git add)
git restore --staged nom_fichier.py

# Annuler le dernier commit (garder les modifications)
git reset --soft HEAD~1
```

---

## 🔍 Consulter l'Historique

```bash
# Voir les commits
git log --oneline

# Voir les modifications
git diff

# Voir l'état actuel
git status
```

---

## ⚠️ Résoudre les Conflits

```bash
# 1. Voir les fichiers en conflit
git status

# 2. Ouvrir et éditer les fichiers marqués en conflit
# 3. Supprimer les marqueurs <<<<<<, ======, >>>>>>

# 4. Marquer comme résolu
git add fichier_resolu.py

# 5. Finaliser
git commit -m "Résolution des conflits"
```

---

## 💡 Exemples de Noms de Branches

```bash
git checkout -b feature/detection-obstacles
git checkout -b bugfix/correction-capteur
git checkout -b docs/mise-a-jour-readme
git checkout -b test/ajout-tests-navigation
```

---

## ✅ Exemples de Messages de Commit

```bash
git commit -m "Ajout de la fonction de navigation autonome"
git commit -m "Correction du bug de calibration gyroscope"
git commit -m "Mise à jour de la documentation"
git commit -m "Amélioration des performances du détecteur d'obstacles"
```

---

## 🆘 Commandes d'Aide

```bash
# Aide générale
git help

# Aide sur une commande spécifique
git help commit
git help branch
```

---

## 📞 En Cas de Problème

1. **Ne paniquez pas !** 😊
2. Utilisez `git status` pour voir où vous en êtes
3. Consultez le **GUIDE_GIT.md** pour plus de détails
4. Demandez de l'aide à l'équipe

---

## 🎯 Workflow Complet Exemple

```bash
# 1. Cloner le projet (première fois seulement)
git clone https://github.com/Sympoziium/PFE.git
cd PFE

# 2. Créer une branche pour votre travail
git checkout -b feature/reconnaissance-objets

# 3. Travailler sur votre code
# ... (vous codez) ...

# 4. Vérifier les modifications
git status

# 5. Ajouter les fichiers modifiés
git add detection.py utils.py

# 6. Faire un commit
git commit -m "Ajout du module de reconnaissance d'objets"

# 7. Envoyer vers GitHub
git push -u origin feature/reconnaissance-objets

# 8. Créer une Pull Request sur GitHub
# (aller sur le site web GitHub)

# 9. Après validation, mettre à jour main
git checkout main
git pull origin main
```

---

**Bon codage sur le projet Zumi ! 🤖✨**

*Pour plus de détails, consultez le fichier GUIDE_GIT.md*
