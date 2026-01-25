#!/bin/bash

# Script de préparation de Zumi en mode DEV il sert a désactiver les services automatiques
# du Zumi et à connecter le Zumi au hotspot du PC pour le développement. ce script doit être
# lancé via une connexion SSH. 

# procédure d'utilisation :
# 1. Allumer Zumi
# 2. Se connecter au wifi du zumi et en SSH via un terminal (ssh  pi@192.168.10.1)
# 3. lancer le script : sudo ~/zumi_prepare.sh
# 4. une fois le script terminé, se connecter au Zumi via l'IP affichée (ssh pi@<IP>)
# mot de passe par défaut : pi


# --- Stop programmes Zumi ---
echo "Arrêt du dashboard..."
sudo pkill -f dashboard.py
sleep 3

echo "Arrêt du service zumidashboard..."
sudo pkill -f zumidashboard
sleep 3

echo "Arrêt des gestures..."
sudo pkill -f gesture.py
sleep 3

echo "Arrêt de l'Interface_Opérateur.py..."
sudo pkill -f Interface_Operateur.py
sleep 3
echo "Arrêt de Jupyter et des scripts Python..."
sudo pkill -f jupyter
sleep 3
sudo pkill -f python3
sleep 3

echo "🧹 Nettoyage des processus Python..."
ps aux | grep python | grep -v grep

echo "✅ Tous les services Zumi ont été désactivés."


sleep 10

# Ajout temporaire du hotspot
echo "📶 Connexion temporaire au Wi-Fi maison..."

cat << EOF | sudo tee /tmp/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="Moroni_Guest"
    psk="4504691075"
    key_mgmt=WPA-PSK
}
EOF

sudo ip link set wlan0 up

sleep 2

sudo wpa_supplicant -B -i wlan0 -c /tmp/wpa_supplicant.conf


echo "🔄 Attente de connexion..."
sleep 10

sudo dhclient wlan0

sleep 5

sudo dhclient wlan0
sleep 5


# Vérifie la connexion
if ping -c 2 8.8.8.8 &> /dev/null; then
    echo "🌐 Connexion Wi-Fi OK"
else
    echo "❌ Échec de la connexion Wi-Fi"
    exit 1
fi




# Vérification IP
IP=$(ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
if [[ -z "$IP" ]]; then
    echo "❌ Connexion au wifi échouée !"
    exit 1
else
    echo "✅ Connecté temporairement au wifi avec IP $IP"
fi

echo "🛑 Désactivation des services Zumi..."



echo "🚀 Zumi prêt pour ton utilisation (dev mode)"
echo "👉 SSH sur $IP via le réseau Wi-Fi"


# --- Désactivation du point d'accès AP0 ---
echo "❌ Désactivation du AP0..."
sudo ip link set ap0 down
sudo systemctl stop hostapd 2>/dev/null
sudo systemctl stop dnsmasq 2>/dev/null
sleep 2
echo "✅ AP0 désactivé."


exit 0

# chmod +x ~/zumi_prepare.sh
# sudo ~/zumi_prepare.sh
