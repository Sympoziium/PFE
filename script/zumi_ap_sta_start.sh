#!/usr/bin/env bash
# =============================================================================
# zumi_ap_sta_start.sh — Activation du mode AP+STA au démarrage
# Appelé par : zumi-ap.service (systemd)
# NE PAS exécuter manuellement après le premier boot
# =============================================================================

set -e

LOG="[zumi-ap]"
VIRT_IF="wlan1"
PHYS_IF="wlan0"
AP_PROFILE="ZumiAP"
STA_PROFILE="ZumiSTA"

echo "$LOG Démarrage du mode AP+STA..."

# --- Attente que wlan0 soit disponible ---
TIMEOUT=30
ELAPSED=0
until ip link show "$PHYS_IF" &>/dev/null; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "$LOG ERREUR : $PHYS_IF non disponible après ${TIMEOUT}s. Abandon."
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo "$LOG $PHYS_IF disponible."

# --- Désactivation du power save (critique sur Pi Zero 2W 64-bit) ---
iw dev "$PHYS_IF" set power_save off || true
echo "$LOG Power save désactivé sur $PHYS_IF."

# --- Création de l'interface virtuelle AP ---
# Supprimer si elle existe déjà (cas de redémarrage du service)
if ip link show "$VIRT_IF" &>/dev/null; then
    echo "$LOG $VIRT_IF existe déjà — suppression..."
    iw dev "$VIRT_IF" del || true
    sleep 1
fi

echo "$LOG Création de $VIRT_IF (type __ap)..."
iw dev "$PHYS_IF" interface add "$VIRT_IF" type __ap
sleep 2

iw dev "$VIRT_IF" set power_save off || true
ip link set "$VIRT_IF" up
echo "$LOG $VIRT_IF créé et actif."

# --- Activation du profil AP dans NetworkManager ---
echo "$LOG Activation du profil AP '$AP_PROFILE'..."
nmcli connection up "$AP_PROFILE" || {
    echo "$LOG AVERTISSEMENT : Impossible d'activer '$AP_PROFILE'."
    echo "$LOG Vérifier que le profil existe : nmcli connection show"
    exit 1
}

echo "$LOG Mode AP+STA actif."
echo "$LOG   AP  → $VIRT_IF (ssh pi@192.168.0.1)"
echo "$LOG   STA → $PHYS_IF (IP dynamique via DHCP)"