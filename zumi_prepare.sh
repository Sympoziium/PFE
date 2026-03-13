#!/bin/bash
# zumi_prepare.sh
# -----------------------------------------------------------------------------
# Script de préparation de Zumi en mode DEV.
# Désactive les services automatiques du fabricant et configure le réseau Wi-Fi
# pour le développement. Ce script doit être lancé via SSH.
#
# Utilisation :
#   sudo ~/PFE/zumi_prepare.sh          # Menu interactif
#   sudo ~/PFE/zumi_prepare.sh full     # Préparation complète (après power cycle)
#   sudo ~/PFE/zumi_prepare.sh fast     # Préparation rapide (entre deux tests)
# -----------------------------------------------------------------------------

MODE="${1:-}"

# ═══════════════════════════════════════════════════════════════════════
#  FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════

# Vérifie si un port est libre (return 0 = libre, 1 = occupé)
port_is_free() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        local count
        count=$(sudo ss -tlnp 2>/dev/null | grep -c ":${port} " || true)
        [ "$count" -eq 0 ]
        return $?
    elif command -v fuser >/dev/null 2>&1; then
        ! sudo fuser "${port}/tcp" >/dev/null 2>&1
        return $?
    else
        return 0  # impossible de vérifier, on assume libre
    fi
}

# Récupère les PIDs écoutant sur un port (via ss, puis fuser en fallback)
get_pids_on_port() {
    local port="$1"
    local pids=""
    if command -v ss >/dev/null 2>&1; then
        pids=$(sudo ss -tlnp 2>/dev/null | grep ":${port} " \
               | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u)
    fi
    if [ -z "$pids" ] && command -v fuser >/dev/null 2>&1; then
        pids=$(sudo fuser "${port}/tcp" 2>/dev/null | tr -s ' ' '\n' | grep '^[0-9]')
    fi
    echo "$pids"
}

# Libère un port avec retry loop + vérification.
# C'est LA fonction critique : elle ne déclare succès que quand le port est
# réellement libre, et réessaie jusqu'à max_attempts fois avec 1s entre chaque.
free_port() {
    local port="$1"
    local max_attempts=10
    local attempt=0

    if port_is_free "$port"; then
        echo "  ✓ Port $port déjà libre."
        return 0
    fi

    echo "  🔒 Port $port occupé, libération en cours..."

    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt + 1))

        # 1. Kill par PIDs détectés sur le port
        local pids
        pids=$(get_pids_on_port "$port")
        if [ -n "$pids" ]; then
            for pid in $pids; do
                local cmd
                cmd=$(ps -p "$pid" -o args= 2>/dev/null || echo "???")
                echo "    Kill PID $pid ($cmd)"
                sudo kill -9 "$pid" 2>/dev/null || true
            done
        fi

        # 2. Kill par nom de processus (backup)
        sudo pkill -9 -f "main\.py" 2>/dev/null || true
        sudo pkill -9 -f "flask" 2>/dev/null || true
        sudo pkill -9 -f "werkzeug" 2>/dev/null || true

        # 3. fuser -k (backup)
        if command -v fuser >/dev/null 2>&1; then
            sudo fuser -k "${port}/tcp" 2>/dev/null || true
        fi

        # Délai pour laisser le kernel libérer le socket
        sleep 1

        # Vérification
        if port_is_free "$port"; then
            echo "  ✅ Port $port libéré (tentative $attempt)."
            return 0
        fi

        echo "    ⏳ Port $port encore occupé... ($attempt/$max_attempts)"
    done

    echo "  ❌ Impossible de libérer le port $port après $max_attempts tentatives."
    echo "  Processus bloquants :"
    sudo ss -tlnp 2>/dev/null | grep ":${port} " || true
    return 1
}

# Kill un pattern de processus avec -9 et log
kill_by_pattern() {
    local pattern="$1"
    local label="${2:-$pattern}"
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        echo "  Arrêt de $label..."
        sudo pkill -9 -f "$pattern" 2>/dev/null || true
    fi
}

# ═══════════════════════════════════════════════════════════════════════
#  MENU INTERACTIF
# ═══════════════════════════════════════════════════════════════════════

if [ -z "$MODE" ]; then
    echo "Choisir le mode de préparation :"
    echo "  1) Préparation complète (services + réseau)"
    echo "  2) Préparation rapide (kill Flask seulement)"
    while true; do
        read -r -p "Votre choix [1/2]: " CHOICE
        case "$CHOICE" in
            1) MODE="full"; break ;;
            2) MODE="fast"; break ;;
            *) echo "Choix invalide. Entrez 1 ou 2." ;;
        esac
    done
fi

# ═══════════════════════════════════════════════════════════════════════
#  MODE FAST — Libère uniquement le port 5000
# ═══════════════════════════════════════════════════════════════════════

run_fast() {
    echo "⚡ Mode FAST : libération du port 5000..."
    if free_port 5000; then
        echo "✅ Port 5000 libre. Vous pouvez relancer votre programme."
        return 0
    else
        echo "❌ Le port 5000 n'a pas pu être libéré."
        return 1
    fi
}

if [ "$MODE" = "fast" ]; then
    run_fast
    exit $?
fi

# ═══════════════════════════════════════════════════════════════════════
#  MODE FULL — Préparation complète
# ═══════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════"
echo "   PRÉPARATION COMPLÈTE DU ZUMI (mode dev)"
echo "═══════════════════════════════════════════════════════════"

# --- Phase 1 : Arrêt des services système ---
echo ""
echo "🛑 Phase 1 : Arrêt des services système..."
for svc in zumidashboard nginx apache2; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "  Arrêt du service $svc..."
        sudo systemctl stop "$svc" 2>/dev/null || true
    fi
done

# --- Phase 2 : Kill des processus du fabricant ---
echo ""
echo "🧹 Phase 2 : Arrêt des processus Zumi..."

kill_by_pattern "dashboard\.py"      "Dashboard"
kill_by_pattern "zumidashboard"      "Service Zumidashboard"
kill_by_pattern "gesture\.py"        "Gestures"
kill_by_pattern "Interface_Operateur" "Interface Opérateur"
kill_by_pattern "jupyter"            "Jupyter"
kill_by_pattern "nbconvert"          "nbconvert"

# Délai pour laisser les processus mourir
sleep 2

# Vérifier et tuer les processus Python restants (sauf ce script)
REMAINING=$(ps aux 2>/dev/null | grep '[p]ython' | grep -v "zumi_prepare" || true)
if [ -n "$REMAINING" ]; then
    echo "  ⚠️  Processus Python encore actifs :"
    echo "$REMAINING" | while IFS= read -r line; do
        pid=$(echo "$line" | awk '{print $2}')
        cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        echo "    Kill PID $pid : $cmd"
        sudo kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1
fi

STILL=$(ps aux 2>/dev/null | grep '[p]ython' | grep -v "zumi_prepare" || true)
if [ -z "$STILL" ]; then
    echo "  ✅ Tous les processus Python arrêtés."
else
    echo "  ⚠️  Certains processus Python résistent (non bloquant)."
fi

# --- Phase 3 : Libération des ports ---
echo ""
echo "🔌 Phase 3 : Libération des ports..."
for PORT in 5000 8080 80; do
    free_port "$PORT"
done

# --- Phase 4 : Configuration Wi-Fi ---
echo ""
echo "📶 Phase 4 : Configuration Wi-Fi..."

read -r -p "  SSID du réseau Wi-Fi : " WIFI_SSID
read -r -s -p "  Mot de passe : " WIFI_PSK
echo ""

if [ -z "$WIFI_SSID" ] || [ -z "$WIFI_PSK" ]; then
    echo "  ❌ SSID ou mot de passe vide. Configuration annulée."
    exit 1
fi

# Écrire la config (chmod 600 pour ne pas exposer le PSK)
WPA_CONF="/tmp/wpa_supplicant_dev.conf"
cat > "$WPA_CONF" << EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PSK"
    key_mgmt=WPA-PSK
}
EOF
chmod 600 "$WPA_CONF"

sudo ip link set wlan0 up
sleep 1

# Arrêt propre de wpa_supplicant existant
if pgrep -x wpa_supplicant >/dev/null 2>&1; then
    echo "  Arrêt de wpa_supplicant existant..."
    sudo wpa_cli -i wlan0 terminate >/dev/null 2>&1 || true
    sleep 1
    if pgrep -x wpa_supplicant >/dev/null 2>&1; then
        sudo pkill -x wpa_supplicant 2>/dev/null || true
        sleep 1
    fi
    sudo rm -f /var/run/wpa_supplicant/wlan0 2>/dev/null || true
fi

echo "  Connexion au réseau '$WIFI_SSID'..."
sudo wpa_supplicant -B -i wlan0 -c "$WPA_CONF"
sleep 3

# Obtenir une adresse IP (stdout + stderr supprimés pour éviter "Too few arguments")
echo "  🔄 Obtention d'une adresse IP..."
sudo dhclient -r wlan0 >/dev/null 2>&1 || true
sleep 1
sudo dhclient wlan0 >/dev/null 2>&1 || true
sleep 2

# Vérifier la connectivité avec retry
echo "  🔄 Vérification de la connexion..."
CONNECTED=false
for i in 1 2 3 4 5; do
    if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
        CONNECTED=true
        break
    fi
    echo "    Tentative $i/5..."
    sleep 2
done

IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)

if $CONNECTED && [ -n "$IP" ]; then
    echo "  ✅ Connecté au Wi-Fi '$WIFI_SSID' — IP : $IP"
else
    echo "  ❌ Échec de la connexion Wi-Fi."
    [ -z "$IP" ] && echo "     Aucune adresse IP obtenue." \
                 || echo "     IP : $IP mais pas d'accès Internet."
    exit 1
fi

# --- Phase 5 : Nettoyage final du port 5000 (réutilise la logique fast) ---
echo ""
echo "🔧 Phase 5 : Nettoyage final du port 5000..."
free_port 5000

# --- Résumé ---
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  🚀 Zumi prêt pour le développement !"
echo "  📡 SSH : ssh pi@$IP"
echo "═══════════════════════════════════════════════════════════"

exit 0
