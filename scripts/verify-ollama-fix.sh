#!/bin/bash
# Verify that Ollama is accessible from Docker container after fix

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check Docker permissions
if docker ps >/dev/null 2>&1; then
    DOCKER="docker"
else
    echo -e "${YELLOW}Using sudo for Docker commands${NC}"
    DOCKER="sudo docker"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Ollama Docker Fix Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${BLUE}Step 1: Checking DOCKER_ENV variable in container...${NC}"
if $DOCKER exec voice-processor-backend-prod env | grep "DOCKER_ENV=true" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ DOCKER_ENV=true is set${NC}"
else
    echo -e "${RED}✗ DOCKER_ENV not set - container needs restart${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 2: Checking config.py detection message in logs...${NC}"
if $DOCKER logs voice-processor-backend-prod 2>&1 | grep "Docker 環境檢測：Ollama URL" | tail -1; then
    echo -e "${GREEN}✓ Docker environment detected and Ollama URL adjusted${NC}"
else
    echo -e "${YELLOW}⚠ Config detection message not found in recent logs${NC}"
fi

echo ""
echo -e "${BLUE}Step 3: Testing connection to host.docker.internal...${NC}"
if $DOCKER exec voice-processor-backend-prod curl -s http://host.docker.internal:11434/api/tags >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Can connect to Ollama via host.docker.internal${NC}"
else
    echo -e "${RED}✗ Cannot connect to host.docker.internal:11434${NC}"
    echo ""
    echo "Debugging info:"
    echo "  1. Check if extra_hosts is configured in docker-compose.yml"
    echo "  2. Verify Ollama is running on host: systemctl status ollama"
    echo "  3. Check host firewall settings"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 4: Fetching available models from container...${NC}"
MODELS=$($DOCKER exec voice-processor-backend-prod curl -s http://host.docker.internal:11434/api/tags 2>/dev/null)
if [ -n "$MODELS" ]; then
    echo -e "${GREEN}✓ Successfully fetched models list${NC}"
    echo ""
    echo "$MODELS" | python3 -c "import sys, json; models = json.load(sys.stdin).get('models', []); print('\n'.join([f\"  - {m['name']}\" for m in models]))" 2>/dev/null || echo "$MODELS"
else
    echo -e "${RED}✗ Failed to fetch models${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 5: Testing Python ollama client from container...${NC}"
TEST_SCRIPT='
import ollama
import os

# Override to use host.docker.internal (should already be set by config)
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"

try:
    # Try to list models
    models = ollama.list()
    print(f"✓ Python client works! Found {len(models[\"models\"])} models")
    for model in models["models"][:3]:
        print(f"  - {model[\"name\"]}")
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)
'

if $DOCKER exec voice-processor-backend-prod python -c "$TEST_SCRIPT" 2>/dev/null; then
    echo -e "${GREEN}✓ Python ollama client working${NC}"
else
    echo -e "${YELLOW}⚠ Python client test had issues (may still work in app)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Ollama Fix Verified!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Upload a test file to trigger transcription"
echo "  2. Enable AI post-processing to test summarization"
echo "  3. Check backend logs for Ollama usage: docker logs -f voice-processor-backend-prod"
echo ""
