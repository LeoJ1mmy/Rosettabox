#!/bin/bash
# Background monitoring script with auto-shutdown and date-based logging
# Interval: 30 seconds

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INTERVAL=30

# Auto-detect environment
cd "$PROJECT_DIR"

# Detect Ollama URL (use host_detector if available)
OLLAMA_URL=$(grep "^OLLAMA_URL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "http://localhost:11434")
API_BASE="http://localhost:3082/api"
USER_ID=$(ls backend/task_storage/*.json 2>/dev/null | head -1 | xargs basename 2>/dev/null | cut -d'_' -f2-3 || echo "unknown")

# Date-based log directory
get_log_file() {
    local today=$(date +%Y-%m-%d)
    local log_dir="$PROJECT_DIR/logs/monitoring/$today"
    mkdir -p "$log_dir"

    # Create/update 'current' symlink
    ln -sfn "$today" "$PROJECT_DIR/logs/monitoring/current"

    echo "$log_dir/monitor.log"
}

# Check if service is running
is_service_running() {
    # Check if backend is running via supervisorctl or process
    if command -v supervisorctl &> /dev/null; then
        supervisorctl status backend-dev 2>/dev/null | grep -q "RUNNING" && return 0
    fi

    # Fallback: check for gunicorn process
    pgrep -f "gunicorn.*app:app" > /dev/null && return 0

    return 1
}

# Initialize logging
LOG_FILE=$(get_log_file)
{
    echo "════════════════════════════════════════════════════════════════"
    echo "🔄 Background monitoring started - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "   Interval: ${INTERVAL}s | Ollama: $OLLAMA_URL"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
} > "$LOG_FILE"

ITERATION=0
LAST_DATE=$(date +%Y-%m-%d)

while true; do
    # Check if service is still running (auto-shutdown)
    if ! is_service_running; then
        {
            echo ""
            echo "⚠️  Service stopped, monitoring auto-shutdown - $(date '+%Y-%m-%d %H:%M:%S')"
        } >> "$LOG_FILE"
        exit 0
    fi

    # Check if date changed (rotate log file)
    CURRENT_DATE=$(date +%Y-%m-%d)
    if [ "$CURRENT_DATE" != "$LAST_DATE" ]; then
        LOG_FILE=$(get_log_file)
        LAST_DATE=$CURRENT_DATE
    fi

    ITERATION=$((ITERATION + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    {
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⏰ Update #$ITERATION - $TIMESTAMP"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""

        # GPU Status
        GPU_INFO=$(nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw --format=csv,noheader,nounits 2>/dev/null)
        if [ $? -eq 0 ]; then
            TEMP=$(echo $GPU_INFO | cut -d',' -f1 | xargs)
            GPU_UTIL=$(echo $GPU_INFO | cut -d',' -f2 | xargs)
            MEM_UTIL=$(echo $GPU_INFO | cut -d',' -f3 | xargs)
            MEM_USED=$(echo $GPU_INFO | cut -d',' -f4 | xargs)
            MEM_TOTAL=$(echo $GPU_INFO | cut -d',' -f5 | xargs)
            POWER=$(echo $GPU_INFO | cut -d',' -f6 | xargs)

            # Progress bar
            BAR_LEN=$((GPU_UTIL / 2))
            BAR=$(printf '█%.0s' $(seq 1 $BAR_LEN) 2>/dev/null)
            EMPTY=$(printf '░%.0s' $(seq 1 $((50 - BAR_LEN))) 2>/dev/null)

            # Status indicator
            if [ "$GPU_UTIL" -gt 80 ]; then
                GPU_STATUS="🔥 High Load"
            elif [ "$GPU_UTIL" -gt 30 ]; then
                GPU_STATUS="⚡ Processing"
            else
                GPU_STATUS="💤 Idle"
            fi

            echo "🎮 GPU: [$BAR$EMPTY] ${GPU_UTIL}% ${GPU_STATUS}"
            echo "   🌡️  Temp: ${TEMP}°C | ⚡ Power: ${POWER}W"
            echo "   💾 VRAM: ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_UTIL}%)"
        else
            echo "🎮 GPU: ❌ Not available"
        fi
        echo ""

        # Ollama Status
        OLLAMA_HOST=$(echo $OLLAMA_URL | sed 's|http://||' | sed 's|https://||')
        OLLAMA_STATUS=$(curl -s --connect-timeout 2 ${OLLAMA_URL}/api/ps 2>/dev/null)
        if [ $? -eq 0 ]; then
            RUNNING_MODEL=$(echo "$OLLAMA_STATUS" | python3 -c "import sys,json; data=json.load(sys.stdin); models=[m['name'] for m in data.get('models',[])] if 'models' in data else []; print(models[0] if models else 'None')" 2>/dev/null)
            if [ "$RUNNING_MODEL" = "None" ]; then
                echo "🤖 Ollama: ✅ Connected ($OLLAMA_HOST) | 💤 No model running"
            else
                echo "🤖 Ollama: ✅ Connected ($OLLAMA_HOST) | 🔄 Running: $RUNNING_MODEL"
            fi
        else
            echo "🤖 Ollama: ❌ Connection failed ($OLLAMA_HOST)"
        fi
        echo ""

        # Backend Process Status
        BACKEND_PROC=$(ps aux | grep "gunicorn: worker" | grep -v grep)
        if [ -n "$BACKEND_PROC" ]; then
            CPU=$(echo $BACKEND_PROC | awk '{print $3}')
            MEM=$(echo $BACKEND_PROC | awk '{print $4}')
            echo "⚙️  Backend: ✅ Gunicorn Worker Running"
            echo "   CPU: ${CPU}% | RAM: ${MEM}%"
        else
            echo "⚙️  Backend: ❌ Not Running"
        fi
        echo ""

        # Task Status (via API)
        GLOBAL_STATUS=$(curl -s "$API_BASE/task/global/status?user_id=$USER_ID" 2>/dev/null)
        if [ -n "$GLOBAL_STATUS" ]; then
            TASK_INFO=$(echo "$GLOBAL_STATUS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    current = data.get('current_processing', {})
    stats = data.get('queue_stats', {})

    if current and current.get('task_id'):
        progress = current.get('progress', {})
        pct = progress.get('percentage', 0)
        stage = progress.get('stage', 'unknown')
        print(f'{pct}|{stage}|{stats.get(\"active_tasks\", 0)}|{stats.get(\"pending_tasks\", 0)}|{stats.get(\"completed_tasks\", 0)}')
    else:
        print(f'0|No Task|{stats.get(\"active_tasks\", 0)}|{stats.get(\"pending_tasks\", 0)}|{stats.get(\"completed_tasks\", 0)}')
except:
    print('0|Error|0|0|0')
" 2>/dev/null)

            IFS='|' read -r PCT STAGE ACTIVE PENDING COMPLETED <<< "$TASK_INFO"

            PROG_BAR_LEN=$((PCT / 2))
            PROG_BAR=$(printf '█%.0s' $(seq 1 $PROG_BAR_LEN) 2>/dev/null)
            PROG_EMPTY=$(printf '░%.0s' $(seq 1 $((50 - PROG_BAR_LEN))) 2>/dev/null)

            echo "📋 Task: [$PROG_BAR$PROG_EMPTY] ${PCT}%"
            echo "   Stage: $STAGE"
            echo "   📊 Queue: ⚡${ACTIVE} Active | ⏳${PENDING} Pending | ✅${COMPLETED} Completed"
        else
            echo "📋 Task: ❌ Unable to fetch status"
        fi

        echo ""
    } >> "$LOG_FILE"

    sleep $INTERVAL
done
