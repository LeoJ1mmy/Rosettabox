#!/bin/bash
# Hardware anomaly watchdog with auto-shutdown
# Interval: 30 seconds

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INTERVAL=30

# Thresholds
GPU_TEMP_WARN=75
GPU_TEMP_CRITICAL=85
GPU_UTIL_STUCK=95
VRAM_WARN_PCT=90
STUCK_DETECTION_COUNT=5

# Date-based log directory
get_log_file() {
    local today=$(date +%Y-%m-%d)
    local log_dir="$PROJECT_DIR/logs/monitoring/$today"
    mkdir -p "$log_dir"
    echo "$log_dir/alerts.log"
}

# Check if service is running
is_service_running() {
    if command -v supervisorctl &> /dev/null; then
        supervisorctl status backend-dev 2>/dev/null | grep -q "RUNNING" && return 0
    fi
    pgrep -f "gunicorn.*app:app" > /dev/null && return 0
    return 1
}

# Initialize
LOG_FILE=$(get_log_file)
{
    echo "════════════════════════════════════════════════════════════════"
    echo "🔍 Hardware watchdog started - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "   Interval: ${INTERVAL}s"
    echo "   Thresholds: Temp ${GPU_TEMP_WARN}°C/${GPU_TEMP_CRITICAL}°C | Stuck ${STUCK_DETECTION_COUNT}x"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
} > "$LOG_FILE"

# Tracking variables
PREV_GPU_UTIL=0
STUCK_COUNT=0
LAST_DATE=$(date +%Y-%m-%d)

while true; do
    # Check if service is still running (auto-shutdown)
    if ! is_service_running; then
        {
            echo ""
            echo "⚠️  Service stopped, watchdog auto-shutdown - $(date '+%Y-%m-%d %H:%M:%S')"
        } >> "$LOG_FILE"
        exit 0
    fi

    # Check if date changed (rotate log file)
    CURRENT_DATE=$(date +%Y-%m-%d)
    if [ "$CURRENT_DATE" != "$LAST_DATE" ]; then
        LOG_FILE=$(get_log_file)
        LAST_DATE=$CURRENT_DATE
    fi

    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Get GPU info
    GPU_INFO=$(nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)

    if [ $? -eq 0 ]; then
        TEMP=$(echo $GPU_INFO | cut -d',' -f1 | xargs)
        GPU_UTIL=$(echo $GPU_INFO | cut -d',' -f2 | xargs)
        MEM_USED=$(echo $GPU_INFO | cut -d',' -f3 | xargs)
        MEM_TOTAL=$(echo $GPU_INFO | cut -d',' -f4 | xargs)
        THROTTLE=$(echo $GPU_INFO | cut -d',' -f5 | xargs)

        ALERTS=""

        # Temperature check
        if [ "$TEMP" -ge "$GPU_TEMP_CRITICAL" ]; then
            ALERTS="${ALERTS}🚨 CRITICAL: GPU temperature ${TEMP}°C >= ${GPU_TEMP_CRITICAL}°C\n"
        elif [ "$TEMP" -ge "$GPU_TEMP_WARN" ]; then
            ALERTS="${ALERTS}⚠️  WARNING: GPU temperature ${TEMP}°C >= ${GPU_TEMP_WARN}°C\n"
        fi

        # VRAM check
        VRAM_PCT=$((MEM_USED * 100 / MEM_TOTAL))
        if [ "$VRAM_PCT" -ge "$VRAM_WARN_PCT" ]; then
            ALERTS="${ALERTS}⚠️  WARNING: VRAM usage ${VRAM_PCT}% >= ${VRAM_WARN_PCT}%\n"
        fi

        # Throttling check
        if [ "$THROTTLE" != "0x0000000000000000" ]; then
            ALERTS="${ALERTS}⚠️  WARNING: GPU throttling active (${THROTTLE})\n"
        fi

        # Stuck detection (utilization not changing)
        if [ "$GPU_UTIL" -eq "$PREV_GPU_UTIL" ] && [ "$GPU_UTIL" -ge "$GPU_UTIL_STUCK" ]; then
            STUCK_COUNT=$((STUCK_COUNT + 1))
            if [ "$STUCK_COUNT" -ge "$STUCK_DETECTION_COUNT" ]; then
                ALERTS="${ALERTS}⚠️  WARNING: GPU possibly stuck at ${GPU_UTIL}% for ${STUCK_COUNT} checks\n"
            fi
        else
            STUCK_COUNT=0
        fi
        PREV_GPU_UTIL=$GPU_UTIL

        # Log alerts if any
        if [ -n "$ALERTS" ]; then
            {
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "⚠️  HARDWARE ALERT - $TIMESTAMP"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo -e "$ALERTS"
                echo "Current Status:"
                echo "  GPU: ${GPU_UTIL}% | Temp: ${TEMP}°C | VRAM: ${MEM_USED}MB/${MEM_TOTAL}MB (${VRAM_PCT}%)"
                echo ""
            } >> "$LOG_FILE"
        fi
    fi

    sleep $INTERVAL
done
