#!/bin/bash
# ===========================================
# Voice Processor Management Script
# ===========================================
# Production: Docker containers (stable, isolated)
# Development: Supervisor process management (rapid development)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Supervisor configuration
SUPERVISOR_CONF="$SCRIPT_DIR/supervisord.conf"
SUPERVISORCTL="supervisorctl -c $SUPERVISOR_CONF"
SUPERVISORD="supervisord -c $SUPERVISOR_CONF"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============================================
# Helper Functions - Platform Detection
# ============================================

detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "darwin";;
        *)          echo "unknown";;
    esac
}

get_supervisor_config_path() {
    local platform=$(detect_platform)
    case $platform in
        linux)
            echo "/etc/supervisor/supervisord.conf"
            ;;
        darwin)
            echo "/usr/local/etc/supervisord.conf"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ============================================
# Helper Functions - Supervisor Verification
# ============================================

check_supervisor_installed() {
    if ! command -v supervisord >/dev/null 2>&1; then
        echo -e "${RED}Supervisor not found${NC}"
        echo ""
        echo "Install Supervisor:"
        if [ "$(detect_platform)" = "linux" ]; then
            echo "  sudo apt install supervisor"
        elif [ "$(detect_platform)" = "darwin" ]; then
            echo "  brew install supervisor"
        fi
        echo ""
        return 1
    fi
    return 0
}

# ============================================
# Helper Functions - Preflight Checks
# ============================================

run_preflight_checks() {
    echo -e "${BLUE}Running preflight checks...${NC}"

    # Check environment
    if [ -x "./scripts/check_env.sh" ]; then
        if ! ./scripts/check_env.sh; then
            echo -e "${RED}Environment check failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}Warning: check_env.sh not found or not executable${NC}"
    fi

    # Clean up ports
    if [ -x "./scripts/port_cleaner.sh" ]; then
        echo -e "${BLUE}Cleaning up ports...${NC}"
        ./scripts/port_cleaner.sh --force
    else
        echo -e "${YELLOW}Warning: port_cleaner.sh not found or not executable${NC}"
    fi

    # Verify logs directory
    if [ ! -d "./logs" ]; then
        echo -e "${BLUE}Creating logs directory...${NC}"
        mkdir -p ./logs
    fi

    echo -e "${GREEN}Preflight checks passed!${NC}"
    return 0
}

# ============================================
# Helper Functions - Supervisor Operations
# ============================================

supervisor_start_all() {
    # Ensure supervisord is running
    if ! pgrep -f "supervisord.*$SUPERVISOR_CONF" > /dev/null; then
        echo -e "${BLUE}Starting Supervisor daemon...${NC}"
        $SUPERVISORD
        sleep 2
    fi

    echo -e "${BLUE}Starting services via Supervisor...${NC}"
    $SUPERVISORCTL start voice-text-processor-backend voice-text-processor-frontend
    sleep 2

    # Verify services started
    if $SUPERVISORCTL status voice-text-processor-backend | grep -q RUNNING && \
       $SUPERVISORCTL status voice-text-processor-frontend | grep -q RUNNING; then
        echo -e "${GREEN}Services started successfully!${NC}"
        display_service_urls
        return 0
    else
        echo -e "${RED}Failed to start services${NC}"
        echo "Check status: ./manage.sh status-dev"
        echo "Check logs: ./manage.sh logs-dev"
        return 1
    fi
}

supervisor_stop_all() {
    echo -e "${BLUE}Stopping services via Supervisor...${NC}"
    $SUPERVISORCTL stop voice-text-processor-backend voice-text-processor-frontend
    sleep 1

    # Verify services stopped
    if $SUPERVISORCTL status voice-text-processor-backend | grep -q STOPPED && \
       $SUPERVISORCTL status voice-text-processor-frontend | grep -q STOPPED; then
        echo -e "${GREEN}Services stopped successfully!${NC}"
        return 0
    else
        echo -e "${YELLOW}Some services may still be running${NC}"
        echo "Check status: ./manage.sh status-dev"
        return 1
    fi
}

supervisor_status() {
    echo -e "${BLUE}Development Status (Supervisor):${NC}"
    echo ""
    $SUPERVISORCTL status voice-text-processor-backend voice-text-processor-frontend 2>&1 | while read line; do
        if echo "$line" | grep -q RUNNING; then
            echo -e "${GREEN}  ✓ $line${NC}"
        elif echo "$line" | grep -q STOPPED; then
            echo -e "${YELLOW}  ✗ $line${NC}"
        else
            echo -e "${RED}  ! $line${NC}"
        fi
    done
    echo ""

    # Display URLs if running
    if supervisorctl status voice-text-processor-backend | grep -q RUNNING; then
        display_service_urls
    fi
}

# ============================================
# Helper Functions - Log Management
# ============================================

tail_backend_log() {
    if [ ! -f "logs/backend.log" ]; then
        echo -e "${YELLOW}Backend log not found${NC}"
        echo "Start development first: ./manage.sh start-dev"
        return 1
    fi

    echo -e "${BLUE}Streaming backend log (Ctrl+C to exit)...${NC}"
    tail -f logs/backend.log
}

tail_frontend_log() {
    if [ ! -f "logs/frontend.log" ]; then
        echo -e "${YELLOW}Frontend log not found${NC}"
        echo "Start development first: ./manage.sh start-dev"
        return 1
    fi

    echo -e "${BLUE}Streaming frontend log (Ctrl+C to exit)...${NC}"
    tail -f logs/frontend.log
}

tail_all_logs() {
    if [ ! -d "logs" ] || [ -z "$(ls -A logs 2>/dev/null)" ]; then
        echo -e "${YELLOW}No log files found${NC}"
        echo "Start development first: ./manage.sh start-dev"
        return 1
    fi

    echo -e "${BLUE}Streaming all logs (Ctrl+C to exit)...${NC}"
    tail -f logs/*.log
}

# ============================================
# Helper Functions - Display
# ============================================

display_service_urls() {
    echo ""
    echo "Service URLs:"
    echo "  Backend:  http://localhost:3082"
    echo "  Frontend: http://localhost:5175"
    echo ""
    echo "View logs:"
    echo "  All:      ./manage.sh logs-dev"
    echo "  Backend:  ./manage.sh logs-backend-dev"
    echo "  Frontend: ./manage.sh logs-frontend-dev"
}

show_help() {
    echo ""
    echo "Voice Text Processor - Environment Manager"
    echo "=========================================="
    echo ""
    echo "Production runs in Docker (stable, isolated)"
    echo "Development runs via Supervisor (rapid development)"
    echo ""
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo ""
    echo "  Production (Docker):"
    echo "    start-prod              Start production containers"
    echo "    stop-prod               Stop production containers"
    echo "    restart-prod            Restart all production containers"
    echo "    restart-backend-prod    Restart backend container only"
    echo "    restart-frontend-prod   Restart frontend container only"
    echo "    status-prod             Check production status"
    echo "    logs-prod               View all production logs"
    echo "    logs-backend-prod       View backend production logs"
    echo "    logs-frontend-prod      View frontend production logs"
    echo ""
    echo "  Auth Gateway (port 5180):"
    echo "    restart-auth-gateway    Restart auth gateway"
    echo "    logs-auth-gateway       View auth gateway logs"
    echo "    rebuild-auth-gateway    Rebuild auth gateway (no cache)"
    echo ""
    echo "  Development (Supervisor):"
    echo "    start-dev               Start development services"
    echo "    stop-dev                Stop development services"
    echo "    restart-dev             Restart development services"
    echo "    status-dev              Check development status"
    echo "    logs-dev                View all development logs"
    echo "    logs-backend-dev        View backend logs only"
    echo "    logs-frontend-dev       View frontend logs only"
    echo ""
    echo "  Both Environments:"
    echo "    start-all               Start both prod and dev"
    echo "    stop-all                Stop both environments"
    echo "    status                  Show status of all services"
    echo ""
    echo "  Docker Build:"
    echo "    rebuild-prod            Rebuild all production containers"
    echo "    rebuild-prod-force      Force rebuild (no cache)"
    echo "    rebuild-backend-prod    Rebuild backend only"
    echo "    rebuild-backend-prod-force   Force rebuild backend (no cache)"
    echo "    rebuild-frontend-prod   Rebuild frontend only"
    echo "    rebuild-frontend-prod-force  Force rebuild frontend (no cache)"
    echo ""
    echo "  Docker Cleanup (project-specific):"
    echo "    clean-status            Show project Docker resource usage"
    echo "    clean-cache             Clean build cache only (safe)"
    echo "    clean-volumes           Clean project volumes"
    echo "    clean-images            Clean project images (requires rebuild)"
    echo "    clean-prod              Clean containers and volumes"
    echo "    clean-all               Full cleanup with confirmation"
    echo ""
    echo "  Port Management:"
    echo "    port-check              Check port usage (3080, 3082, 5173, 5175, 5180)"
    echo "    port-clean              Kill processes on occupied ports"
    echo ""
    echo "  Ollama Connectivity:"
    echo "    check-ollama            Check both dev and prod Ollama"
    echo "    check-ollama-dev        Check dev Ollama only"
    echo "    check-ollama-prod       Check prod Docker Ollama only"
    echo "    verify-ollama           Detailed Docker verification (legacy)"
    echo ""
    echo "  Environment:"
    echo "    check-env               Verify development environment setup"
    echo ""
    echo "  Monitoring:"
    echo "    monitor-start           Start background monitoring"
    echo "    monitor-stop            Stop background monitoring"
    echo "    monitor-status          Check monitoring status"
    echo "    monitor-logs            View latest monitoring logs"
    echo "    monitor-realtime        Real-time monitoring dashboard"
    echo ""
}

# ============================================
# Command Router
# ============================================

case "$1" in
    # Production commands (Docker)
    start-prod)
        echo -e "${BLUE}Starting production (Docker mode)...${NC}"
        docker compose up -d backend-prod frontend-prod auth-gateway
        echo -e "${GREEN}Production started!${NC}"
        echo "  Auth Gateway: http://localhost:5180 (login required)"
        echo "  Frontend:     http://localhost:5173 (direct, no auth)"
        echo "  Backend:      http://localhost:3080 (direct, no auth)"
        ;;

    stop-prod)
        echo -e "${BLUE}Stopping production (Docker mode)...${NC}"
        docker compose stop backend-prod frontend-prod auth-gateway
        echo -e "${GREEN}Production stopped!${NC}"
        ;;

    restart-prod)
        echo -e "${BLUE}Restarting production (Docker mode)...${NC}"
        docker compose restart backend-prod frontend-prod auth-gateway
        echo -e "${GREEN}Production restarted!${NC}"
        ;;

    logs-prod)
        docker compose logs -f backend-prod frontend-prod auth-gateway
        ;;

    status-prod)
        echo -e "${BLUE}Production Status (Docker):${NC}"
        docker compose ps backend-prod frontend-prod auth-gateway
        ;;

    # Development commands (Supervisor)
    start-dev)
        check_supervisor_installed || exit 1
        run_preflight_checks || exit 1
        supervisor_start_all || exit 1
        ;;

    stop-dev)
        check_supervisor_installed || exit 1
        supervisor_stop_all || exit 1
        ;;

    restart-dev)
        check_supervisor_installed || exit 1
        echo -e "${BLUE}Restarting development...${NC}"
        supervisor_stop_all
        sleep 2
        run_preflight_checks || exit 1
        supervisor_start_all || exit 1
        ;;

    logs-dev)
        tail_all_logs
        ;;

    logs-backend-dev)
        tail_backend_log
        ;;

    logs-frontend-dev)
        tail_frontend_log
        ;;

    status-dev)
        check_supervisor_installed || exit 1
        supervisor_status
        ;;

    # Both environments
    start-all)
        echo -e "${BLUE}Starting all environments...${NC}"
        echo ""
        docker compose up -d backend-prod frontend-prod auth-gateway
        echo ""
        check_supervisor_installed || exit 1
        run_preflight_checks || exit 1
        supervisor_start_all || exit 1
        echo ""
        echo -e "${GREEN}All environments started!${NC}"
        echo ""
        echo "Production (Docker):"
        echo "  Auth Gateway: http://localhost:5180 (login required)"
        echo "  Frontend:     http://localhost:5173 (direct, no auth)"
        echo "  Backend:      http://localhost:3080 (direct, no auth)"
        echo "  Logs:         ./manage.sh logs-prod"
        echo ""
        echo "Development (Supervisor):"
        echo "  Backend:  http://localhost:3082"
        echo "  Frontend: http://localhost:5175"
        echo "  Logs:     ./manage.sh logs-dev"
        ;;

    stop-all)
        echo -e "${BLUE}Stopping all environments...${NC}"
        docker compose down
        if check_supervisor_installed 2>/dev/null; then
            supervisor_stop_all
        fi
        echo -e "${GREEN}All environments stopped!${NC}"
        ;;

    status)
        echo ""
        echo -e "${BLUE}Production Status (Docker):${NC}"
        docker compose ps backend-prod frontend-prod auth-gateway
        echo ""
        if check_supervisor_installed 2>/dev/null; then
            supervisor_status
        else
            echo -e "${YELLOW}Development Status: Supervisor not installed${NC}"
        fi
        echo ""
        ;;

    # Utilities
    clean-prod)
        echo -e "${YELLOW}Cleaning up production Docker containers and volumes...${NC}"
        docker compose down -v
        echo -e "${GREEN}Production cleanup complete!${NC}"
        ;;

    # Docker cleanup commands (project-specific only)
    clean-cache)
        echo -e "${BLUE}Cleaning Docker build cache (project-specific)...${NC}"
        echo ""
        # 只清理 build cache，不影響其他資源
        docker builder prune -f
        echo ""
        echo -e "${GREEN}Build cache cleaned!${NC}"
        ;;

    clean-images)
        echo -e "${BLUE}Cleaning unused project images...${NC}"
        echo ""
        # 先停止容器
        docker compose down 2>/dev/null || true
        # 刪除本專案的映像
        echo "Removing project images..."
        docker images | grep -E "voice-text-processor|voice-processor" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
        # 清理 dangling images
        docker image prune -f
        echo ""
        echo -e "${GREEN}Project images cleaned!${NC}"
        echo -e "${YELLOW}Note: Run 'rebuild-prod-force' before 'start-prod' to rebuild images.${NC}"
        ;;

    clean-volumes)
        echo -e "${BLUE}Cleaning project volumes...${NC}"
        echo ""
        # 停止容器
        docker compose down 2>/dev/null || true
        # 刪除本專案的 volumes
        docker volume ls | grep -E "voice-text-processor|voice-processor" | awk '{print $2}' | xargs -r docker volume rm 2>/dev/null || true
        echo ""
        echo -e "${GREEN}Project volumes cleaned!${NC}"
        ;;

    clean-all)
        echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║  WARNING: Full project Docker cleanup                  ║${NC}"
        echo -e "${RED}║  This will remove ALL project containers, images,      ║${NC}"
        echo -e "${RED}║  volumes, and build cache.                             ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${YELLOW}This will clean:${NC}"
        echo "  • Project containers (voice-processor-*)"
        echo "  • Project images (voice-text-processor-*)"
        echo "  • Project volumes"
        echo "  • Docker build cache"
        echo ""
        read -p "Are you sure? (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            echo ""
            echo -e "${BLUE}[1/4] Stopping and removing containers...${NC}"
            docker compose down -v 2>/dev/null || true

            echo -e "${BLUE}[2/4] Removing project images...${NC}"
            docker images | grep -E "voice-text-processor|voice-processor" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true

            echo -e "${BLUE}[3/4] Removing dangling images...${NC}"
            docker image prune -f

            echo -e "${BLUE}[4/4] Cleaning build cache...${NC}"
            docker builder prune -f

            echo ""
            echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}║  Full project cleanup complete!                        ║${NC}"
            echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
            echo ""
            echo "To rebuild and start production:"
            echo "  ./manage.sh rebuild-prod-force"
            echo "  ./manage.sh start-prod"
        else
            echo -e "${YELLOW}Cleanup cancelled.${NC}"
        fi
        ;;

    clean-status)
        echo -e "${BLUE}Docker Resource Status (Project-specific)${NC}"
        echo "=========================================="
        echo ""
        echo -e "${BLUE}Containers:${NC}"
        docker ps -a --filter "name=voice-processor" --format "table {{.Names}}\t{{.Status}}\t{{.Size}}" 2>/dev/null || echo "  No containers found"
        echo ""
        echo -e "${BLUE}Images:${NC}"
        docker images | grep -E "voice-text-processor|voice-processor" || echo "  No project images found"
        echo ""
        echo -e "${BLUE}Volumes:${NC}"
        docker volume ls | grep -E "voice-text-processor|voice-processor" || echo "  No project volumes found"
        echo ""
        echo -e "${BLUE}Build Cache:${NC}"
        docker system df --format "table {{.Type}}\t{{.Size}}\t{{.Reclaimable}}" | grep -E "Type|Build"
        echo ""
        echo -e "${BLUE}Disk Usage Summary:${NC}"
        df -h / | awk 'NR==1 || /\/$/'
        ;;

    rebuild-prod)
        echo -e "${BLUE}Rebuilding production containers...${NC}"
        docker compose build backend-prod frontend-prod
        echo -e "${GREEN}Production rebuilt! Run 'start-prod' to start.${NC}"
        ;;

    rebuild-prod-force)
        echo -e "${YELLOW}Force rebuilding production (no cache)...${NC}"
        echo -e "${BLUE}This will take longer but ensures all changes are included.${NC}"
        docker compose build --no-cache backend-prod frontend-prod
        echo -e "${GREEN}Production rebuilt without cache! Run 'start-prod' to start.${NC}"
        ;;

    rebuild-backend-prod)
        echo -e "${BLUE}Rebuilding backend container...${NC}"
        docker compose build backend-prod
        echo -e "${GREEN}Backend rebuilt!${NC}"
        echo ""
        echo -e "${YELLOW}To apply changes, run:${NC}"
        echo "  ./manage.sh restart-backend-prod"
        ;;

    rebuild-backend-prod-force)
        echo -e "${YELLOW}Force rebuilding backend container (no cache)...${NC}"
        docker compose build --no-cache backend-prod
        echo -e "${GREEN}Backend rebuilt without cache!${NC}"
        echo ""
        echo -e "${YELLOW}To apply changes, run:${NC}"
        echo "  ./manage.sh restart-backend-prod"
        ;;

    rebuild-frontend-prod)
        echo -e "${BLUE}Rebuilding frontend container...${NC}"
        docker compose build frontend-prod
        echo -e "${GREEN}Frontend rebuilt!${NC}"
        echo ""
        echo -e "${YELLOW}To apply changes, run:${NC}"
        echo "  ./manage.sh restart-frontend-prod"
        ;;

    rebuild-frontend-prod-force)
        echo -e "${YELLOW}Force rebuilding frontend container (no cache)...${NC}"
        docker compose build --no-cache frontend-prod
        echo -e "${GREEN}Frontend rebuilt without cache!${NC}"
        echo ""
        echo -e "${YELLOW}To apply changes, run:${NC}"
        echo "  ./manage.sh restart-frontend-prod"
        ;;

    restart-backend-prod)
        echo -e "${BLUE}Restarting backend container...${NC}"
        docker compose restart backend-prod
        sleep 3
        echo -e "${GREEN}Backend restarted!${NC}"
        echo ""
        echo "Recent logs:"
        docker logs voice-processor-backend-prod 2>&1 | tail -15
        ;;

    restart-frontend-prod)
        echo -e "${BLUE}Restarting frontend container...${NC}"
        docker compose restart frontend-prod
        sleep 3
        echo -e "${GREEN}Frontend restarted!${NC}"
        ;;

    logs-backend-prod)
        docker compose logs -f backend-prod
        ;;

    logs-frontend-prod)
        docker compose logs -f frontend-prod
        ;;

    # Auth Gateway commands
    restart-auth-gateway)
        echo -e "${BLUE}Restarting auth gateway...${NC}"
        docker compose restart auth-gateway
        sleep 2
        echo -e "${GREEN}Auth gateway restarted!${NC}"
        echo ""
        echo "Recent logs:"
        docker logs voice-processor-auth-gateway 2>&1 | tail -10
        ;;

    logs-auth-gateway)
        docker compose logs -f auth-gateway
        ;;

    rebuild-auth-gateway)
        echo -e "${BLUE}Rebuilding auth gateway...${NC}"
        docker compose build --no-cache auth-gateway
        echo -e "${GREEN}Auth gateway rebuilt! Run 'restart-auth-gateway' or 'start-prod' to apply.${NC}"
        ;;

    port-check)
        echo -e "${BLUE}Checking port usage...${NC}"
        if [ -x "./scripts/port_cleaner.sh" ]; then
            ./scripts/port_cleaner.sh --check-only
        else
            echo -e "${RED}Error: port_cleaner.sh not found or not executable${NC}"
            exit 1
        fi
        ;;

    port-clean)
        echo -e "${YELLOW}Cleaning occupied ports...${NC}"
        if [ -x "./scripts/port_cleaner.sh" ]; then
            ./scripts/port_cleaner.sh --force
        else
            echo -e "${RED}Error: port_cleaner.sh not found or not executable${NC}"
            exit 1
        fi
        ;;

    check-env)
        echo -e "${BLUE}Checking development environment...${NC}"
        if [ -x "./scripts/check_env.sh" ]; then
            ./scripts/check_env.sh
        else
            echo -e "${RED}Error: check_env.sh not found or not executable${NC}"
            exit 1
        fi
        ;;

    check-ollama)
        "./scripts/check_ollama.sh" all
        ;;

    check-ollama-dev)
        "./scripts/check_ollama.sh" dev
        ;;

    check-ollama-prod)
        "./scripts/check_ollama.sh" prod
        ;;

    verify-ollama)
        echo -e "${BLUE}Verifying Ollama Docker connectivity...${NC}"
        if [ -x "./scripts/verify-ollama-fix.sh" ]; then
            ./scripts/verify-ollama-fix.sh
        else
            echo -e "${RED}Error: verify-ollama-fix.sh not found or not executable${NC}"
            exit 1
        fi
        ;;

    monitor-start)
        "./scripts/monitor_daemon.sh" start
        ;;

    monitor-stop)
        "./scripts/monitor_daemon.sh" stop
        ;;

    monitor-status)
        "./scripts/monitor_daemon.sh" status
        ;;

    monitor-logs)
        "./scripts/monitor_daemon.sh" logs
        ;;

    monitor-realtime)
        "./scripts/monitor.sh"
        ;;

    # Help or unknown
    help|--help|-h|"")
        show_help
        ;;

    *)
        echo -e "${YELLOW}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
