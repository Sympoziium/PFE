#!/usr/bin/env bash
# =============================================================================
# zumi_wifi_config.sh — Configuration de la connexion STA (réseau externe)
# Usage : sudo ./zumi_wifi_config.sh
# =============================================================================

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  📶 Zumi — Configuration Wi-Fi STA"
echo "═══════════════════════════════════════════════════════════"
echo ""

# --- Vérification des droits ---
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté en root (sudo)."
    exit 1
fi

# --- Saisie des identifiants ---
read -r -p "  SSID du réseau Wi-Fi : " WIFI_SSID
read -r -s -p "  Mot de passe         : " WIFI_PSK
echo ""

if [ -z "$WIFI_SSID" ] || [ -z "$WIFI_PSK" ]; then
    echo "❌ SSID ou mot de passe vide. Annulé."
    exit 1
fi

PROFILE_NAME="ZumiSTA"

# --- Supprimer l'ancien profil STA s'il existe ---
if nmcli connection show "$PROFILE_NAME" &>/dev/null; then
    echo "  🗑️  Suppression de l'ancien profil '$PROFILE_NAME'..."
    nmcli connection delete "$PROFILE_NAME"
fi

# --- Créer le nouveau profil STA avec priorité haute ---
echo "  ⚙️  Création du profil '$PROFILE_NAME'..."
nmcli connection add \
    type wifi \
    ifname wlan0 \
    con-name "$PROFILE_NAME" \
    ssid "$WIFI_SSID" \
    -- \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$WIFI_PSK" \
    connection.autoconnect yes \
    connection.autoconnect-priority 10

echo ""
echo "  ✅ Profil '$PROFILE_NAME' créé pour le réseau '$WIFI_SSID'."
echo "  ℹ️  Priorité : 10 (supérieure à l'AP — le STA sera préféré au démarrage)"
echo ""
echo "  Pour activer maintenant : sudo nmcli connection up $PROFILE_NAME"
echo "═══════════════════════════════════════════════════════════"

# --- Optionnel : activer immédiatement (peut échouer si hors de portée) ---
sudo nmcli connection up $PROFILE_NAME || {
    echo "⚠️  Impossible d'activer '$PROFILE_NAME' immédiatement."
    echo "Vérifiez que le réseau est à portée et que les identifiants sont corrects."
}