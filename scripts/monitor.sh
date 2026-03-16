#!/bin/bash
# Real-time monitoring dashboard - 5 second refresh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INTERVAL=5

# Auto-detect environment
cd "$PROJECT_DIR"
OLLAMA_URL=$(grep "^OLLAMA_URL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "http://localhost:11434")
API_BASE="http://localhost:3082/api"
USER_ID=$(ls backend/task_storage/*.json 2>/dev/null | head -1 | xargs basename 2>/dev/null | cut -d'_' -f2-3 || echo "unknown")

while true; do
    clear
    TIMESTAMP=$(date '+%H:%M:%S')

    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  📊 Real-time Monitoring - $TIMESTAMP                       ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    # GPU Status
    echo "┌─ 🎮 GPU Status"
    GPU_INFO=$(nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null)
    if [ $? -eq 0 ]; then
        TEMP=$(echo $GPU_INFO | cut -d',' -f1 | xargs)
        GPU_UTIL=$(echo $GPU_INFO | cut -d',' -f2 | xargs)
        MEM_UTIL=$(echo $GPU_INFO | cut -d',' -f3 | xargs)
        MEM_USED=$(echo $GPU_INFO | cut -d',' -f4 | xargs)
        MEM_TOTAL=$(echo $GPU_INFO | cut -d',' -f5 | xargs)

        # Progress bar
        BAR_LEN=$((GPU_UTIL / 2))
        BAR=$(printf '█%.0s' $(seq 1 $BAR_LEN) 2>/dev/null)
        EMPTY=$(printf '░%.0s' $(seq 1 $((50 - BAR_LEN))) 2>/dev/null)

        echo "│  Utilization: [$BAR$EMPTY] ${GPU_UTIL}%"
        echo "│  Temperature: ${TEMP}°C"
        echo "│  VRAM: ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_UTIL}%)"
    else
        echo "│  ❌ GPU not available"
    fi
    echo "└────────────────────────────────────────────────────────────────"
    echo ""

    # Ollama Status
    echo "┌─ 🤖 Ollama Status"
    OLLAMA_HOST=$(echo $OLLAMA_URL | sed 's|http://||' | sed 's|https://||')
    OLLAMA_STATUS=$(curl -s --connect-timeout 2 ${OLLAMA_URL}/api/ps 2>/dev/null)
    if [ $? -eq 0 ]; then
        RUNNING_MODEL=$(echo "$OLLAMA_STATUS" | python3 -c "import sys,json; data=json.load(sys.stdin); models=[m['name'] for m in data.get('models',[])] if 'models' in data else []; print(models[0] if models else 'None')" 2>/dev/null)
        if [ "$RUNNING_MODEL" = "None" ]; then
            echo "│  ✅ Connected ($OLLAMA_HOST)"
            echo "│  💤 No model running"
        else
            echo "│  ✅ Connected ($OLLAMA_HOST)"
            echo "│  🔄 Running: $RUNNING_MODEL"
        fi
    else
        echo "│  ❌ Connection failed ($OLLAMA_HOST)"
    fi
    echo "└────────────────────────────────────────────────────────────────"
    echo ""

    # Backend Status
    echo "┌─ ⚙️  Backend Status"
    BACKEND_PROC=$(ps aux | grep "gunicorn: worker" | grep -v grep)
    if [ -n "$BACKEND_PROC" ]; then
        CPU=$(echo $BACKEND_PROC | awk '{print $3}')
        MEM=$(echo $BACKEND_PROC | awk '{print $4}')
        echo "│  ✅ Gunicorn Worker Running"
        echo "│  CPU: ${CPU}% | RAM: ${MEM}%"
    else
        echo "│  ❌ Not Running"
    fi
    echo "└────────────────────────────────────────────────────────────────"
    echo ""

    # Task Status
    echo "┌─ 📋 Task Status"
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

        echo "│  Progress: [$PROG_BAR$PROG_EMPTY] ${PCT}%"
        echo "│  Stage: $STAGE"
        echo "│  Queue: ⚡${ACTIVE} Active | ⏳${PENDING} Pending | ✅${COMPLETED} Completed"
    else
        echo "│  ❌ Unable to fetch status"
    fi
    echo "└────────────────────────────────────────────────────────────────"
    echo ""

    echo "Press Ctrl+C to exit"

    sleep $INTERVAL
done
