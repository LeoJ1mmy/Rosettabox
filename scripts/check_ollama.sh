#!/bin/bash
# Unified Ollama connectivity check (dev + prod)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Mode: all, env, dev, prod
MODE="${1:-all}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🔍 Ollama Connectivity Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check environment detection
check_env() {
    echo -e "${BLUE}1️⃣ Environment Detection${NC}"
    echo "──────────────────────────────────────"

    # Detect environment type
    if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; then
        echo -e "${GREEN}✓ Docker Environment${NC}"
        ENV_TYPE="docker"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        echo -e "${GREEN}✓ WSL2 Environment${NC}"
        ENV_TYPE="wsl"
    else
        echo -e "${GREEN}✓ Native Linux/macOS Environment${NC}"
        ENV_TYPE="native"
    fi
    echo ""

    # Detect host IP
    echo "Host IP Detection:"
    if [ "$ENV_TYPE" == "wsl" ]; then
        WSL_HOST=$(ip route show default | awk '/default/ {print $3}' | head -1)
        if [ -z "$WSL_HOST" ]; then
            WSL_HOST=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | grep -E '^(172|192\.168)\.' | head -1)
        fi
        echo -e "  WSL Windows Host IP: ${GREEN}$WSL_HOST${NC}"
        DETECTED_HOST=$WSL_HOST
    elif [ "$ENV_TYPE" == "docker" ]; then
        echo -e "  Docker Host: ${GREEN}host.docker.internal${NC}"
        DETECTED_HOST="host.docker.internal"
    else
        echo -e "  Local Host: ${GREEN}localhost${NC}"
        DETECTED_HOST="localhost"
    fi
    echo ""

    # Check configured OLLAMA_URL
    cd "$PROJECT_DIR"
    OLLAMA_URL=$(grep "^OLLAMA_URL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "http://localhost:11434")
    echo -e "Configured OLLAMA_URL: ${GREEN}$OLLAMA_URL${NC}"
    echo ""
}

# Check dev environment
check_dev() {
    echo -e "${BLUE}2️⃣ Development Environment${NC}"
    echo "──────────────────────────────────────"

    cd "$PROJECT_DIR"
    OLLAMA_URL=$(grep "^OLLAMA_URL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "http://localhost:11434")
    OLLAMA_HOST=$(echo $OLLAMA_URL | sed 's|http://||' | sed 's|https://||')

    echo "Testing: $OLLAMA_URL"

    # Test connection
    if curl -s --connect-timeout 3 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Dev Ollama connected${NC}"

        # Get models
        MODELS=$(curl -s "${OLLAMA_URL}/api/tags" 2>/dev/null | python3 -c "import sys,json; data=json.load(sys.stdin); print('\n'.join([m['name'] for m in data.get('models',[])]))" 2>/dev/null)
        if [ -n "$MODELS" ]; then
            echo -e "Available models:"
            echo "$MODELS" | while read model; do
                echo "  - $model"
            done
        fi
    else
        echo -e "${RED}❌ Dev Ollama connection failed${NC}"
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo "  1. Check if Ollama is running"
        echo "  2. Verify OLLAMA_URL in .env: $OLLAMA_URL"
        if [[ "$OLLAMA_HOST" == 172.* ]] || [[ "$OLLAMA_HOST" == 192.168.* ]]; then
            echo "  3. Windows Ollama: Set OLLAMA_HOST=0.0.0.0"
        fi
        return 1
    fi
    echo ""
}

# Check prod environment (Docker)
check_prod() {
    echo -e "${BLUE}3️⃣ Production Environment (Docker)${NC}"
    echo "──────────────────────────────────────"

    # Check if Docker containers are running
    if ! docker ps | grep -q "voice-processor-backend-prod"; then
        echo -e "${YELLOW}⚠️  Production containers not running${NC}"
        echo "   Start with: ./manage.sh start-prod"
        return 1
    fi

    # Use existing verify-ollama-fix.sh if available
    if [ -f "$SCRIPT_DIR/verify-ollama-fix.sh" ]; then
        "$SCRIPT_DIR/verify-ollama-fix.sh"
    else
        echo -e "${YELLOW}⚠️  verify-ollama-fix.sh not found${NC}"

        # Fallback: basic check
        echo "Testing host.docker.internal:11434 from container..."
        if docker exec voice-processor-backend-prod curl -s --connect-timeout 3 http://host.docker.internal:11434/api/tags > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Prod Ollama connected${NC}"
        else
            echo -e "${RED}❌ Prod Ollama connection failed${NC}"
            echo -e "${YELLOW}Troubleshooting:${NC}"
            echo "  1. Check extra_hosts in docker-compose.yml"
            echo "  2. Restart containers: ./manage.sh restart-prod"
        fi
    fi
    echo ""
}

# Main logic
case "$MODE" in
    all)
        check_env
        check_dev || true
        check_prod || true
        ;;
    env)
        check_env
        ;;
    dev)
        check_dev
        ;;
    prod)
        check_prod
        ;;
    *)
        echo "Usage: $0 {all|env|dev|prod}"
        echo ""
        echo "Modes:"
        echo "  all   - Check environment + dev + prod (default)"
        echo "  env   - Show environment detection only"
        echo "  dev   - Check dev Ollama connection"
        echo "  prod  - Check prod Docker Ollama connection"
        exit 1
        ;;
esac

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Ollama check complete${NC}"
echo -e "${BLUE}========================================${NC}"
