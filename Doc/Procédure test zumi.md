# Procédure de mise en place pour les tests sur Zumi
## 1️⃣ Allumer et connecter le Zumi

1. Allume ton robot Zumi.

2. Connecte-toi au Wi-Fi du Zumi (réseau type ZumiXXXX).

3. Ouvre un terminal sur ton PC et établis une connexion SSH vers le Zumi :
```bash
ssh pi@192.168.10.1
```

Le mot de passe par défaut est `pi`

---

## 2️⃣ Préparer le robot pour le développement

1. Téléverse ou clone ton projet sur le Zumi si ce n’est pas déjà fait :
```bash
cd ~
git clone https://github.com/Sympoziium/PFE.git
cd PFE
```

2. Rends le script de préparation exécutable et lance-le pour désactiver les services automatiques et connecter le Zumi à ton réseau Wi-Fi :
```bash
chmod +x ~/zumi_prepare.sh
sudo ~/zumi_prepare.sh
```

Le script fait plusieurs choses :
**Il faut donc le modifier pour mettre les param de ton wifi**
- Arrête les services automatiques du Zumi (dashboard.py, zumidashboard, gesture.py, etc.)

- Configure wlan0 pour se connecter à ton réseau Wi-Fi local

- Obtient automatiquement une adresse IP pour le Zumi sur ton réseau

- Note l’IP attribuée sur ton réseau Wi-Fi affichée à la fin du script (ex. 192.168.68.73).

---

## 3️⃣ Vérifier la connexion réseau

Depuis ton PC, teste la connectivité avec un ping ex :
```powershell
ping 192.168.68.73
```

Si tu reçois des réponses, le Zumi est accessible sur le réseau Wi-Fi.

---

## 4️⃣ Lancer ton programme principal

Connecte-toi au Zumi via SSH sur l’IP Wi-Fi :
```bash
ssh pi@192.168.68.73
```

Navigue jusqu’au dossier de ton projet :
```bash
cd ~/PFE
```

Lance ton script principal (main.py) avec Python 3 :
```bash
python3 main.py
```

Le script fait :

- Initialisation de la caméra via from zumi.util.camera import Camera

- Mise en place du pipeline de vision et des détecteurs

- Lancement du serveur Flask sur le port 5000

Le terminal affichera :
```bash
Flask server démarré
* Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
```
--- 

## 5️⃣ Accéder au serveur Flask depuis ton PC

- Dans ton navigateur, ouvre l’adresse IP du Zumi suivie du port 5000 :

http://192.168.68.73:5000/


Tu devrais voir ton interface web Flask, prête à interagir avec ton robot.

## 6️⃣ Conseils pratiques

- Toujours tuer les instances Flask en cours avant de relancer main.py si le port 5000 est occupé :
```bash
sudo netstat -tulpn | grep :5000
sudo kill -9 <PID> # remplace <PID> par le num de celui actif
```

- Pour éviter de perdre la connexion SSH pendant les tests, garde le terminal ouvert.

- Le script zumi_prepare.sh doit être lancé une seule fois par session, sauf si tu redémarres le robot.