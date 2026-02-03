#!/bin/bash
#  zumi_prepare.sh
# -----------------------------------------------------------------------------
# Script de préparation de Zumi en mode DEV il sert a désactiver les services automatiques
# du Zumi et à connecter le Zumi au wifi désigné pour le développement. ce script doit être
# lancé via une connexion SSH. 

# procédure d'utilisation :
# 1. Allumer Zumi
# 2. Se connecter au wifi du zumi et en SSH via un terminal (ssh  pi@192.168.10.1)
# 3. lancer le script et choisir 1 ou 2 au clavier :
#    sudo ~/PFE/zumi_prepare.sh
#    (Optionnel) mode direct:
#       - préparation complète (après power cycle): sudo ~/PFE/zumi_prepare.sh full
#       - préparation rapide (entre deux tests):    sudo ~/PFE/zumi_prepare.sh fast
# 4. une fois le script terminé, se connecter au Zumi via l'IP affichée (ssh pi@<IP>)
# mot de passe par défaut : pi
# ces normal si il faut attendre 3-5 minutes avant que la connexion SSH soit active


MODE="$1"

# Menu interactif si aucun argument fourni
if [ -z "$MODE" ]; then
    echo "Choisir le mode de préparation :"
    echo "  1) préparation complète (services + réseau)"
    echo "  2) préparation rapide (kill Flask seulement)"
    while true; do
        read -r -p "Votre choix [1/2]: " CHOICE
        case "$CHOICE" in
            1)
                MODE="full"; break ;;
            2)
                MODE="fast"; break ;;
            *)
                echo "Choix invalide. Entrez 1 ou 2." ;;
        esac
    done
fi

# Chemin rapide: libérer uniquement Flask/port 5000 sans toucher au réseau
if [ "$MODE" = "fast" ]; then
    echo "⚡ Mode FAST: libération du serveur Flask (port 5000)"
    # Tenter de libérer via fuser si disponible
    if command -v fuser >/dev/null 2>&1; then
        sudo fuser -k 5000/tcp 2>/dev/null || true
    fi
    # Kill Flask / Werkzeug
    sudo pkill -f flask || true
    sudo pkill -f werkzeug || true
    # Kill les python qui écoutent sur 5000
    for pid in $(sudo ss -lptn | awk '/:5000/ {print $7}' | sed -E 's/.*pid=([0-9]+).*/\1/'); do
        echo "🔥 Kill PID $pid (port 5000)"
        sudo kill -9 "$pid" || true
    done
    # Dernier recours: tuer le programme principal
    sudo pkill -9 -f main.py || true
    echo "✅ FAST prepare terminé. Vous pouvez relancer votre programme."
    exit 0
fi

echo "🛑 Désactivation des services Zumi..."

# --- Stop programmes Zumi ---
echo "Arrêt du dashboard..."
sudo pkill -f dashboard.py
sleep 1

echo "Arrêt du service zumidashboard..."
sudo pkill -f zumidashboard
sleep 1

echo "Arrêt des gestures..."
sudo pkill -f gesture.py
sleep 1

echo "Arrêt de l'Interface_Opérateur.py..."
sudo pkill -f Interface_Operateur.py
sleep 1
echo "Arrêt de Jupyter et des scripts Python..."
sudo pkill -f jupyter
sleep 1
sudo pkill -f python3
sleep 1

echo "🧹 Nettoyage des processus Python..."
ps aux | grep python | grep -v grep

echo "✅ Tous les services Zumi ont été désactivés."


sleep 3

# --- Libérer les ports web potentiellement occupés (ex: Flask:5000, Dashboard:8080/80) ---
kill_port() {
    local PORT="$1"
    echo "🔎 Vérification du port $PORT..."
    if command -v fuser >/dev/null 2>&1; then
        # fuser est le moyen le plus simple pour tuer les processus liés à un port
        if sudo fuser -k "${PORT}/tcp" 2>/dev/null; then
            echo "✅ Port $PORT libéré (processus tués)."
        else
            echo "ℹ️ Aucun processus en écoute sur le port $PORT."
        fi
    elif command -v ss >/dev/null 2>&1; then
        # fallback via ss + awk pour extraire les PID
        PIDS=$(sudo ss -tulpn | awk -v p=":${PORT}" '$5 ~ p {print $7}' | sed -E 's/.*pid=([0-9]+).*/\1/' | tr '\n' ' ')
        if [ -n "$PIDS" ]; then
            echo "🔧 PIDs détectés sur le port $PORT: $PIDS"
            sudo kill -9 $PIDS 2>/dev/null || true
            echo "✅ Port $PORT libéré (kill -9)."
        else
            echo "ℹ️ Aucun processus en écoute sur le port $PORT."
        fi
    elif command -v lsof >/dev/null 2>&1; then
        PIDS=$(sudo lsof -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null)
        if [ -n "$PIDS" ]; then
            echo "🔧 PIDs détectés via lsof: $PIDS"
            sudo kill -9 $PIDS 2>/dev/null || true
            echo "✅ Port $PORT libéré (kill -9)."
        else
            echo "ℹ️ Aucun processus en écoute sur le port $PORT."
        fi
    else
        echo "⚠️ Outils manquants (fuser/ss/lsof). Impossible de forcer la libération du port $PORT."
    fi
}

echo "🛑 Arrêt des services HTTP courants (nginx/apache)…"
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true

# Libérer explicitement les ports utilisés par l'UI du fabricant et par notre Flask
kill_port 5000
kill_port 8080
kill_port 80

# configuration du wifi dev
echo "📶 Connexion au Wi-Fi maison..."

cat << EOF | sudo tee /tmp/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="dlink-8D39"
    psk="xdvxj79799"
    key_mgmt=WPA-PSK
}
EOF

sudo ip link set wlan0 up

sleep 2

# Éviter le conflit avec un wpa_supplicant déjà en cours
if pgrep -x wpa_supplicant >/dev/null; then
    echo "🧯 wpa_supplicant déjà actif: arrêt propre + nettoyage..."
    sudo pkill -x wpa_supplicant 2>/dev/null || true
    sudo rm -f /var/run/wpa_supplicant/wlan0 2>/dev/null || true
fi

sudo wpa_supplicant -B -i wlan0 -c /tmp/wpa_supplicant.conf


echo "🔄 Attente de connexion..."
sleep 4

# Renouveler proprement l'IP pour éviter les erreurs RTNETLINK
sudo dhclient -r wlan0 2>/dev/null || true
sudo dhclient wlan0

sleep 3



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


echo "🧨 Nettoyage agressif des serveurs Flask / Python..."

# Tuer Flask / Werkzeug
sudo pkill -f flask || true
sudo pkill -f werkzeug || true

# Tuer les python qui écoutent sur 5000
for pid in $(sudo ss -lptn | awk '/:5000/ {print $7}' | sed -E 's/.*pid=([0-9]+).*/\1/'); do
    echo "🔥 Kill PID $pid (port 5000)"
    sudo kill -9 $pid || true
done

# Dernier recours
sudo pkill -9 -f main.py || true



echo "🚀 Zumi prêt pour ton utilisation (dev mode)"
echo "👉 SSH sur $IP via le réseau Wi-Fi"


exit 0

# chmod +x ~/zumi_prepare.sh
# sudo ~/zumi_prepare.sh
