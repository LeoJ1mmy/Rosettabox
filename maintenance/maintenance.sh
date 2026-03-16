#!/bin/bash
#
# 維護模式服務器管理腳本
# 用於啟動/停止本地維護頁面服務器
#
# 使用方式:
#   ./maintenance.sh start   - 啟動維護服務器
#   ./maintenance.sh stop    - 停止維護服務器
#   ./maintenance.sh status  - 查看當前狀態
#   ./maintenance.sh restart - 重啟維護服務器
#
# 注意: 切換域名指向需在 Cloudflare Zero Trust Dashboard 手動操作
#       https://one.dash.cloudflare.com/ → Networks → Tunnels → rosettanvpc
#

set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MAINTENANCE_SERVER="$SCRIPT_DIR/maintenance_server.py"
MAINTENANCE_PID_FILE="$SCRIPT_DIR/.maintenance.pid"
MAINTENANCE_LOG="$SCRIPT_DIR/maintenance.log"
MAINTENANCE_PORT=8503

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 輔助函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查維護服務器是否運行
is_maintenance_server_running() {
    if [ -f "$MAINTENANCE_PID_FILE" ]; then
        local pid=$(cat "$MAINTENANCE_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 啟動維護服務器
start_maintenance_server() {
    if is_maintenance_server_running; then
        local pid=$(cat "$MAINTENANCE_PID_FILE")
        log_warning "維護服務器已在運行中 (PID: $pid)"
        return 0
    fi

    log_info "啟動維護服務器 (port $MAINTENANCE_PORT)..."

    # 使用項目的 venv
    if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
        PYTHON="$PROJECT_DIR/venv/bin/python"
    else
        PYTHON="python3"
    fi

    cd "$SCRIPT_DIR"
    MAINTENANCE_PORT=$MAINTENANCE_PORT nohup $PYTHON "$MAINTENANCE_SERVER" > "$MAINTENANCE_LOG" 2>&1 &
    echo $! > "$MAINTENANCE_PID_FILE"

    sleep 2

    if is_maintenance_server_running; then
        log_success "維護服務器已啟動 (PID: $(cat $MAINTENANCE_PID_FILE))"
        echo ""
        echo -e "${CYAN}========== 下一步操作 ==========${NC}"
        echo "1. 開啟 Cloudflare Zero Trust Dashboard:"
        echo "   https://one.dash.cloudflare.com/"
        echo ""
        echo "2. 前往 Networks → Tunnels → rosettanvpc → Configure"
        echo ""
        echo "3. 在 Public Hostname 中將 rosettanvpc.leopilot.com 的 Service 改為:"
        echo "   http://localhost:8503"
        echo ""
        echo "4. 儲存後等待約 30 秒生效"
        echo -e "${CYAN}=================================${NC}"
    else
        log_error "維護服務器啟動失敗，請查看 $MAINTENANCE_LOG"
        return 1
    fi
}

# 停止維護服務器
stop_maintenance_server() {
    if ! is_maintenance_server_running; then
        log_warning "維護服務器未在運行"
        return 0
    fi

    local pid=$(cat "$MAINTENANCE_PID_FILE")
    log_info "停止維護服務器 (PID: $pid)..."

    kill "$pid" 2>/dev/null || true
    rm -f "$MAINTENANCE_PID_FILE"

    sleep 1
    log_success "維護服務器已停止"
    echo ""
    echo -e "${CYAN}========== 恢復正常服務 ==========${NC}"
    echo "請在 Cloudflare Dashboard 將 Service 改回:"
    echo "  - API:      http://localhost:3080 (path: api)"
    echo "  - Frontend: http://localhost:5173"
    echo -e "${CYAN}=================================${NC}"
}

# 重啟維護服務器
restart_maintenance_server() {
    log_info "重啟維護服務器..."
    stop_maintenance_server
    sleep 1
    start_maintenance_server
}

# 查看狀態
show_status() {
    echo ""
    echo "========== 維護模式狀態 =========="
    echo ""

    # 檢查維護服務器
    if is_maintenance_server_running; then
        local pid=$(cat "$MAINTENANCE_PID_FILE")
        echo -e "維護服務器: ${GREEN}運行中${NC} (PID: $pid)"
        echo -e "監聽端口:   ${GREEN}$MAINTENANCE_PORT${NC}"
    else
        echo -e "維護服務器: ${RED}未運行${NC}"
    fi

    # 測試本地端口
    echo ""
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$MAINTENANCE_PORT 2>/dev/null | grep -q "503"; then
        echo -e "維護頁面測試: ${GREEN}可訪問${NC} (http://localhost:$MAINTENANCE_PORT)"
    else
        echo -e "維護頁面測試: ${RED}無法訪問${NC}"
    fi

    echo ""
    echo "=================================="
    echo ""
}

# 顯示幫助
show_help() {
    echo ""
    echo -e "${CYAN}維護模式服務器管理腳本${NC}"
    echo ""
    echo "使用方式:"
    echo "  $0 start    啟動維護服務器 (port $MAINTENANCE_PORT)"
    echo "  $0 stop     停止維護服務器"
    echo "  $0 restart  重啟維護服務器"
    echo "  $0 status   查看當前狀態"
    echo "  $0 help     顯示此幫助信息"
    echo ""
    echo -e "${YELLOW}注意：${NC}"
    echo "切換域名指向需要在 Cloudflare Dashboard 手動操作："
    echo "https://one.dash.cloudflare.com/ → Networks → Tunnels → rosettanvpc"
    echo ""
    echo "維護模式: 將 Service 改為 http://localhost:8503"
    echo "正常模式: 將 Service 改回 http://localhost:5173 (frontend)"
    echo "         和 http://localhost:3080 (api path)"
    echo ""
}

# 主入口
case "${1:-}" in
    start)
        start_maintenance_server
        ;;
    stop)
        stop_maintenance_server
        ;;
    restart)
        restart_maintenance_server
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -z "${1:-}" ]; then
            show_help
        else
            log_error "未知命令: $1"
            show_help
            exit 1
        fi
        ;;
esac
