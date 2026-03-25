#!/bin/bash

# ============================================================================
# Script d'automatisation du setup DNS pour Raspberry Pi (Bookworm/Debian)
# ============================================================================
# Usage: sudo bash setup_dns_rpi.sh
# ============================================================================

set -e  # Arrêter en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Vérifier que le script est exécuté en tant que root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Ce script doit être exécuté en tant que root (sudo)${NC}"
   exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Setup automatisé du DNS${NC}"
echo -e "${BLUE}========================================${NC}\n"

# ============================================================================
# 1. DÉTECTION DE LA CONFIGURATION RÉSEAU ACTUELLE
# ============================================================================
echo -e "${YELLOW}[1/5] Détection de la configuration réseau...${NC}"

# Déterminer le gestionnaire de réseau
if systemctl is-active --quiet systemd-networkd; then
    DNS_MANAGER="systemd-networkd"
    echo -e "${GREEN}✓ systemd-networkd détecté${NC}"
elif command -v dhcpcd &> /dev/null; then
    DNS_MANAGER="dhcpcd"
    echo -e "${GREEN}✓ dhcpcd détecté${NC}"
else
    DNS_MANAGER="resolv.conf"
    echo -e "${GREEN}✓ Configuration manuelle via /etc/resolv.conf${NC}"
fi

echo -e "  Configuration actuelle :"
cat /etc/resolv.conf | head -5
echo ""

# ============================================================================
# 2. SAUVEGARDER LA CONFIGURATION ACTUELLE
# ============================================================================
echo -e "${YELLOW}[2/5] Sauvegarde de la configuration actuelle...${NC}"

BACKUP_DIR="/etc/network_config_backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
cp /etc/resolv.conf "$BACKUP_DIR/resolv.conf.bak.$BACKUP_DATE"

if [ -f /etc/dhcpcd.conf ]; then
    cp /etc/dhcpcd.conf "$BACKUP_DIR/dhcpcd.conf.bak.$BACKUP_DATE"
fi

if [ -d /etc/systemd/network ]; then
    cp -r /etc/systemd/network "$BACKUP_DIR/systemd_network.bak.$BACKUP_DATE"
fi

echo -e "${GREEN}✓ Sauvegarde créée dans $BACKUP_DIR${NC}\n"

# ============================================================================
# 3. CONFIGURATION DES SERVEURS DNS
# ============================================================================
echo -e "${YELLOW}[3/5] Configuration des serveurs DNS...${NC}"

# Serveurs DNS de secours (Cloudflare, Google, Quad9)
DNS_SERVERS=(
    "1.1.1.1"        # Cloudflare
    "8.8.8.8"        # Google
    "9.9.9.9"        # Quad9
)

DNS_SERVERS_IPV6=(
    "2606:4700:4700::1111"  # Cloudflare IPv6
    "2001:4860:4860::8888"  # Google IPv6
)

case "$DNS_MANAGER" in
    "systemd-networkd")
        echo -e "  Mise à jour de systemd-networkd..."
        
        # Créer/mettre à jour les fichiers de configuration
        cat > /etc/systemd/resolved.conf << 'EOF'
[Resolve]
# Serveurs DNS primaires
DNS=1.1.1.1 8.8.8.8 9.9.9.9
DNS=2606:4700:4700::1111 2001:4860:4860::8888

# Serveurs DNS de secours
FallbackDNS=8.8.8.8 8.8.4.4 1.1.1.2

# Domaines de recherche locaux (optionnel)
# Domains=local home.arpa

# Options de cache et de timeout
Cache=yes
CacheFromLocalhost=yes
DNSSECNegativeTrustAnchors=

# Mode strict DNSSEC (optional)
DNSSEC=allow-downgrade
EOF
        
        # Lier /etc/resolv.conf à systemd-resolved
        rm -f /etc/resolv.conf
        ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
        
        # Redémarrer le service
        systemctl restart systemd-resolved
        echo -e "  ${GREEN}✓ systemd-resolved configuré et redémarré${NC}"
        ;;
        
    "dhcpcd")
        echo -e "  Mise à jour de dhcpcd.conf..."
        
        # Créer une sauvegarde si elle n'existe pas
        if [ ! -f /etc/dhcpcd.conf.orig ]; then
            cp /etc/dhcpcd.conf /etc/dhcpcd.conf.orig
        fi
        
        # Ajouter les serveurs DNS statiques à la fin du fichier
        cat >> /etc/dhcpcd.conf << 'EOF'

# Serveurs DNS statiques - Configuré automatiquement
static domain_name_servers=1.1.1.1 8.8.8.8 9.9.9.9
static domain_search=local home.arpa
EOF
        
        # Redémarrer le service
        systemctl restart dhcpcd
        echo -e "  ${GREEN}✓ dhcpcd configuré et redémarré${NC}"
        ;;
        
    "resolv.conf")
        echo -e "  Configuration manuelle de /etc/resolv.conf..."
        
        # Faire une sauvegarde immédiate
        cp /etc/resolv.conf /etc/resolv.conf.bak
        
        # Générer la nouvelle configuration
        cat > /etc/resolv.conf << 'EOF'
# Configuration DNS - Générée automatiquement
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
nameserver 2606:4700:4700::1111
options edns0 trust-ad

# En cas d'échec, serveurs de secours
# nameserver 8.8.4.4
# nameserver 1.0.0.2
EOF
        
        # Protéger le fichier (immutable si possible)
        chattr +i /etc/resolv.conf 2>/dev/null || true
        echo -e "  ${GREEN}✓ /etc/resolv.conf configuré${NC}"
        ;;
esac

echo ""

# ============================================================================
# 4. TESTS DE CONNECTIVITÉ DNS
# ============================================================================
echo -e "${YELLOW}[4/5] Tests de connectivité DNS...${NC}\n"

test_dns() {
    local hostname=$1
    echo -n "  Test de résolution pour '$hostname'... "
    if timeout 5 nslookup "$hostname" 8.8.8.8 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ ÉCHEC${NC}"
        return 1
    fi
}

TESTS_PASSED=0
TESTS_TOTAL=0

for host in "github.com" "google.com" "cloudflare.com" "dns.google"; do
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    test_dns "$host" && TESTS_PASSED=$((TESTS_PASSED + 1))
done

echo ""

# ============================================================================
# 5. CONFIGURATION POUR DÉMARRAGE AUTOMATIQUE
# ============================================================================
echo -e "${YELLOW}[5/5] Configuration pour le démarrage automatique...${NC}"

# Créer un script de vérification DNS au démarrage
cat > /usr/local/bin/verify-dns.sh << 'EOF'
#!/bin/bash
# Script de vérification et correction automatique du DNS au démarrage

DNS_SERVERS="1.1.1.1 8.8.8.8 9.9.9.9"

# Attendre que l'interface réseau soit prête
sleep 5

# Vérifier la connectivité DNS
if ! timeout 5 nslookup github.com 8.8.8.8 > /dev/null 2>&1; then
    echo "$(date): DNS non fonctionnel, tentative de correction..." >> /var/log/dns-verify.log
    
    # Forcer le rechargement de la configuration réseau
    systemctl restart systemd-resolved 2>/dev/null || \
    systemctl restart dhcpcd 2>/dev/null || \
    true
    
    sleep 3
fi

echo "$(date): DNS vérifié" >> /var/log/dns-verify.log
EOF

chmod +x /usr/local/bin/verify-dns.sh
echo -e "  ${GREEN}✓ Script de vérification DNS créé${NC}"

# Créer un service systemd optionnel pour la vérification
cat > /etc/systemd/system/verify-dns.service << 'EOF'
[Unit]
Description=Verify and Fix DNS Configuration
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/verify-dns.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# Optionnel : systemctl enable verify-dns.service
echo -e "  ${GREEN}✓ Service systemd créé (disabled par défaut)${NC}"

echo ""

# ============================================================================
# RAPPORT FINAL
# ============================================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RAPPORT DE CONFIGURATION${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${YELLOW}Gestionnaire réseau utilisé:${NC} $DNS_MANAGER"
echo -e "${YELLOW}Serveurs DNS configurés:${NC}"
for dns in "${DNS_SERVERS[@]}"; do
    echo "  - $dns"
done

echo ""
echo -e "${YELLOW}Résultats des tests:${NC} $TESTS_PASSED/$TESTS_TOTAL réussis"

if [ $TESTS_PASSED -eq $TESTS_TOTAL ]; then
    echo -e "${GREEN}✓ Configuration DNS réussie!${NC}"
else
    echo -e "${RED}⚠ Certains tests ont échoué. Vérifiez votre connexion réseau.${NC}"
fi

echo ""
echo -e "${YELLOW}Configuration actuelle:${NC}"
cat /etc/resolv.conf | head -10

echo ""
echo -e "${YELLOW}Sauvegardes disponibles dans:${NC} $BACKUP_DIR"
echo ""
echo -e "${YELLOW}Pour restaurer une sauvegarde:${NC}"
echo "  sudo cp $BACKUP_DIR/resolv.conf.bak.TIMESTAMP /etc/resolv.conf"
echo ""
echo -e "${YELLOW}Pour activer le service de vérification automatique:${NC}"
echo "  sudo systemctl enable verify-dns.service"
echo "  sudo systemctl start verify-dns.service"
echo ""
