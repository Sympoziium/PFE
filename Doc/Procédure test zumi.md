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
**TU DOIS MODIFIER LE SCRIPT DE PRÉPARATION AVANT DE CONTINUER**
tu dois simplement mettre le SSID et le mot de passe de ton Wifi dans le script

#### Sur le robot 
- dans le terminal bash du robot colle cette `cmd` pour modifier le fichier:
    
    ```bash
    nano ~/PFE/zumi_prepare.sh
    ```

- dans le code de `zumi_prepare.sh` trouve cette partie et change le `SSID` et le `mdp` pour ton wifi:

    ```bash
    # configuration du wifi dev
    echo "📶 Connexion au Wi-Fi maison..."

    cat << EOF | sudo tee /tmp/wpa_supplicant.conf
    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
    update_config=1
    network={
        ssid="TON_SSID"
        psk="TON_MDP"
        key_mgmt=WPA-PSK
    }
    EOF
    ``` 
- pour sauvegarder et revenir au terminal tu dois appuyé sur les macros `CTRL+o` puis `ENTER` pour **sauvegarder** et `CTRL+x` pour **retourner** au terminal.

- Rends le script de préparation **exécutable** et lance-le pour désactiver les services automatiques et connecter le Zumi à ton réseau Wi-Fi :

    ```bash
    chmod +x ~/PFE/zumi_prepare.sh
    sudo ~/PFE/zumi_prepare.sh
    ```

Le script fait plusieurs choses :
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
ex: http://192.168.68.73:5000/


Tu devrais voir ton interface web Flask, prête à interagir avec ton robot.

## 6️⃣ Conseils pratiques

- Toujours tuer les instances Flask en cours avant de relancer main.py si le port 5000 est occupé :
```bash
sudo ~/PFE/zumi_prepare.sh fast
```

**TYPE d'erreur a **
```
OSError: [Errno 98] Address already in use
```
si tu vois une erreur du genre ces que tu dois executer le script: 

- Pour éviter de perdre la connexion SSH pendant les tests, garde le terminal ouvert.
