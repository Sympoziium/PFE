#!/usr/bin/env bash
# =============================================================================
# zumi_ap_setup.sh — Création du profil AP dans NetworkManager
# Exécuter UNE SEULE FOIS lors de la post-migration.
# Usage : sudo ./script/zumi_ap_setup.sh
# =============================================================================

set -e

AP_PROFILE="ZumiAP"
AP_SSID="zumi-robot-B"
AP_PASSWORD="zumirobot"
AP_IP="192.168.0.1/24"
VIRT_IF="wlan1"

echo "═══════════════════════════════════════════════════════════"
echo "  📡 Zumi — Configuration initiale du profil AP"
echo "═══════════════════════════════════════════════════════════"

[ "$EUID" -ne 0 ] && { echo "❌ Requis : sudo"; exit 1; }

# --- Supprimer l'ancien profil si existant ---
if nmcli connection show "$AP_PROFILE" &>/dev/null; then
    echo "  🗑️  Suppression de l'ancien profil '$AP_PROFILE'..."
    nmcli connection delete "$AP_PROFILE"
fi

# --- Créer l'interface virtuelle temporairement pour que nmcli accepte wlan1 ---
if ! ip link show "$VIRT_IF" &>/dev/null; then
    echo "  ⚙️  Création temporaire de $VIRT_IF pour l'enregistrement du profil..."
    iw dev wlan0 interface add "$VIRT_IF" type __ap
    ip link set "$VIRT_IF" up
    sleep 1
fi

# --- Créer le profil AP sur wlan1 ---
echo "  ⚙️  Création du profil '$AP_PROFILE' sur $VIRT_IF..."
nmcli connection add \
    type wifi \
    ifname "$VIRT_IF" \
    con-name "$AP_PROFILE" \
    ssid "$AP_SSID" \
    -- \
    wifi.mode ap \
    wifi.band bg \
    wifi.channel 6 \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$AP_PASSWORD" \
    ipv4.method shared \
    ipv4.addresses "$AP_IP" \
    ipv6.method disabled \
    connection.autoconnect no

# autoconnect=no car c'est zumi_ap_sta_start.sh qui le monte après avoir créé wlan1

echo ""
echo "  ✅ Profil AP créé."
echo "  📶 SSID     : $AP_SSID"
echo "  🔑 Password : $AP_PASSWORD"
echo "  🌐 IP robot : ${AP_IP%/*}"
echo ""
echo "  ⚠️  autoconnect est DÉSACTIVÉ intentionnellement."
echo "      L'activation est gérée par zumi-ap.service au boot."
echo ""
echo "═══════════════════════════════════════════════════════════"