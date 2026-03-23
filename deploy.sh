#!/bin/bash
# ============================================================
# Production Deployment Script — Data Extraction Platform
# ============================================================
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh                  # Full deploy
#   ./deploy.sh --update         # Update only (no DB reset)
#   ./deploy.sh --ssl-setup      # Generate self-signed SSL
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Data Extraction Platform — Production Deploy ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"

# ─── Pre-flight checks ──────────────────────────────────────
check_prerequisites() {
    echo -e "\n${YELLOW}[1/6] Checking prerequisites...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker is not installed. Install it first:${NC}"
        echo "  https://docs.docker.com/engine/install/"
        exit 1
    fi
    echo "  ✓ Docker $(docker --version | cut -d' ' -f3)"

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}✗ Docker Compose is not installed.${NC}"
        exit 1
    fi
    echo "  ✓ Docker Compose available"
}

# ─── Environment file ───────────────────────────────────────
setup_env() {
    echo -e "\n${YELLOW}[2/6] Setting up environment...${NC}"

    if [ ! -f .env.production ]; then
        echo -e "${RED}✗ .env.production not found!${NC}"
        echo "  Copy .env.production.example and update values."
        exit 1
    fi

    # Warn about default passwords
    if grep -q "changeme_in_production" .env.production; then
        echo -e "${RED}  ⚠  WARNING: Default database password detected!${NC}"
        echo -e "${RED}     Change DB_PASSWORD in .env.production${NC}"
    fi

    if grep -q "CHANGE_THIS_TO_A_STRONG_PASSWORD" .env.production; then
        echo -e "${RED}  ⚠  WARNING: Default admin password detected!${NC}"
        echo -e "${RED}     Change ADMIN_PASSWORD in .env.production${NC}"
    fi

    echo "  ✓ Environment file loaded"
}

# ─── SSL Certificates ───────────────────────────────────────
setup_ssl() {
    echo -e "\n${YELLOW}[3/6] Checking SSL certificates...${NC}"

    mkdir -p nginx/ssl

    if [ ! -f nginx/ssl/cert.pem ] || [ "$1" = "--ssl-setup" ]; then
        echo "  Generating self-signed SSL certificate (for testing)..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/CN=localhost" 2>/dev/null
        echo "  ✓ Self-signed certificate created"
        echo -e "${YELLOW}  → For production, use Let's Encrypt (see below)${NC}"
    else
        echo "  ✓ SSL certificates found"
    fi
}

# ─── Build & Deploy ─────────────────────────────────────────
deploy() {
    echo -e "\n${YELLOW}[4/6] Building Docker images...${NC}"
    docker compose build --no-cache

    echo -e "\n${YELLOW}[5/6] Starting services...${NC}"
    docker compose up -d

    echo -e "\n${YELLOW}[6/6] Waiting for services to be healthy...${NC}"
    sleep 10

    # Check if services are running
    if docker compose ps | grep -q "running"; then
        echo -e "${GREEN}  ✓ All services are running!${NC}"
    else
        echo -e "${RED}  ✗ Some services failed to start. Check logs:${NC}"
        echo "    docker compose logs"
        exit 1
    fi
}

# ─── Update only (no rebuild from scratch) ──────────────────
update() {
    echo -e "\n${YELLOW}Updating application...${NC}"
    docker compose build app
    docker compose up -d app
    echo -e "${GREEN}  ✓ Application updated!${NC}"
}

# ─── Print summary ──────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Deployment Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo "  🌐 Application:  https://YOUR_SERVER_IP"
    echo "  📊 Dashboard:    https://YOUR_SERVER_IP/"
    echo "  📖 API Docs:     https://YOUR_SERVER_IP/docs"
    echo "  🔐 Admin Login:  https://YOUR_SERVER_IP/login"
    echo ""
    echo "  Useful commands:"
    echo "    docker compose logs -f app     # View app logs"
    echo "    docker compose ps              # Check service status"
    echo "    docker compose restart app     # Restart app"
    echo "    docker compose down            # Stop everything"
    echo ""
    echo -e "${YELLOW}  ⚠  For production SSL, use Let's Encrypt:${NC}"
    echo "    sudo apt install certbot"
    echo "    sudo certbot certonly --webroot -w /var/www/certbot -d yourdomain.com"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────
case "${1:-}" in
    --update)
        update
        ;;
    --ssl-setup)
        setup_ssl --ssl-setup
        ;;
    *)
        check_prerequisites
        setup_env
        setup_ssl
        deploy
        print_summary
        ;;
esac
