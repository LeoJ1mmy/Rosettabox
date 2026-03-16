#!/bin/bash
# Monitoring daemon management script
# Manages background monitoring processes with PID tracking

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs/monitoring"
PID_FILE="$LOG_DIR/monitor.pid"
RETENTION_DAYS=7

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Auto cleanup old logs (7 days)
auto_cleanup_logs() {
    if [ -d "$LOG_DIR" ]; then
        find "$LOG_DIR" -type d -name "20*" -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true
        local cleaned=$(find "$LOG_DIR" -type d -name "20*" -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)
        if [ "$cleaned" -gt 0 ]; then
            echo -e "${BLUE}🗑️  Cleaned up $cleaned old log directories (>$RETENTION_DAYS days)${NC}"
        fi
    fi
}

# Check if monitoring is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Start monitoring
start_monitoring() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "${YELLOW}⚠️  Monitoring already running (PID: $pid)${NC}"
        return 1
    fi

    echo -e "${BLUE}🚀 Starting background monitoring...${NC}"

    # Auto cleanup old logs
    auto_cleanup_logs

    # Start background monitoring
    nohup "$SCRIPT_DIR/monitor_background.sh" > /dev/null 2>&1 &
    local monitor_pid=$!

    # Start hardware watchdog
    nohup "$SCRIPT_DIR/hardware_watchdog.sh" > /dev/null 2>&1 &
    local watchdog_pid=$!

    # Save PIDs (using monitor PID as main)
    echo "$monitor_pid" > "$PID_FILE"
    echo -e "${GREEN}✅ Monitoring started${NC}"
    echo -e "   Monitor PID: $monitor_pid"
    echo -e "   Watchdog PID: $watchdog_pid"
    echo -e "   Logs: $LOG_DIR/$(date +%Y-%m-%d)/"
}

# Stop monitoring
stop_monitoring() {
    if ! is_running; then
        echo -e "${YELLOW}⚠️  Monitoring not running${NC}"
        return 1
    fi

    local pid=$(cat "$PID_FILE")
    echo -e "${BLUE}🛑 Stopping monitoring (PID: $pid)...${NC}"

    # Kill monitor process and its children
    pkill -P $pid 2>/dev/null || true
    kill $pid 2>/dev/null || true

    # Kill hardware watchdog
    pkill -f "hardware_watchdog.sh" 2>/dev/null || true

    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ Monitoring stopped${NC}"
}

# Show monitoring status
show_status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "${GREEN}✅ Monitoring is running${NC}"
        echo -e "   PID: $pid"
        echo -e "   Log directory: $LOG_DIR"

        # Show today's log size
        local today=$(date +%Y-%m-%d)
        if [ -d "$LOG_DIR/$today" ]; then
            local log_size=$(du -sh "$LOG_DIR/$today" 2>/dev/null | cut -f1)
            echo -e "   Today's logs: $log_size"
        fi
    else
        echo -e "${YELLOW}⚠️  Monitoring is not running${NC}"
        echo -e "   Use './manage.sh monitor-start' to start"
    fi
}

# Show recent logs
show_logs() {
    local today=$(date +%Y-%m-%d)
    local log_file="$LOG_DIR/$today/monitor.log"

    if [ -f "$log_file" ]; then
        echo -e "${BLUE}📊 Latest monitoring logs (last 50 lines):${NC}"
        echo ""
        tail -n 50 "$log_file"
    else
        echo -e "${YELLOW}⚠️  No logs found for today${NC}"
        echo -e "   Log file: $log_file"
    fi
}

# Main command handler
case "${1:-}" in
    start)
        start_monitoring
        ;;
    stop)
        stop_monitoring
        ;;
    restart)
        stop_monitoring
        sleep 1
        start_monitoring
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
