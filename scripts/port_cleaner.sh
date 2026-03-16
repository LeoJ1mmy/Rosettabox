#!/bin/bash
# Port Cleaner Script
# Detects and cleans processes on configured ports
# Version: 1.0.0

set -e

# Configuration
PORTS=(3080 3082 5173 5175)
FORCE=false
CHECK_ONLY=false

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper functions
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Port Cleaner - Detect and clean processes on configured ports

OPTIONS:
    --force         Force cleanup without confirmation
    --check-only    Only check ports, don't clean
    --help          Show this help message

EXAMPLES:
    $0                  # Interactive mode
    $0 --check-only     # Only check ports
    $0 --force          # Force cleanup all ports

CONFIGURED PORTS: ${PORTS[@]}
EOF
}

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

# Tool detection - prioritize ss (works without root for all listening ports)
detect_tool() {
    if command -v ss >/dev/null 2>&1; then
        echo "ss"
    elif command -v lsof >/dev/null 2>&1; then
        echo "lsof"
    elif command -v netstat >/dev/null 2>&1; then
        echo "netstat"
    else
        log_error "No port detection tool found (ss, lsof, or netstat)"
        log_error "Install iproute2 with: sudo apt install iproute2"
        exit 1
    fi
}

# Port detection - check if port is in use
is_port_in_use() {
    local port=$1
    ss -tln 2>/dev/null | grep -qE ":${port}\s" && return 0
    return 1
}

# Check if port is used by Docker
is_docker_port() {
    local port=$1
    docker ps --format '{{.Ports}}' 2>/dev/null | grep -qE ":${port}->" && return 0
    return 1
}

# Get PIDs on port (may return empty for root processes)
get_pids_on_port() {
    local port=$1
    local tool=$2

    case $tool in
        ss)
            # ss can detect port usage, but may not get PID for root processes
            ss -tlnp 2>/dev/null | grep -E ":${port}\s" | grep -oP 'pid=\K[0-9]+' 2>/dev/null | sort -u || true
            ;;
        lsof)
            lsof -ti ":${port}" 2>/dev/null || true
            ;;
        netstat)
            netstat -tlnp 2>/dev/null | grep ":${port}" | awk '{print $7}' | cut -d'/' -f1 2>/dev/null || true
            ;;
    esac
}

# Process information extraction
get_process_info() {
    local pid=$1

    if [ ! -d "/proc/$pid" ]; then
        echo "N/A|N/A|N/A"
        return
    fi

    local user=$(ps -p "$pid" -o user= 2>/dev/null || echo "N/A")
    local command=$(ps -p "$pid" -o comm= 2>/dev/null || echo "N/A")
    local args=$(ps -p "$pid" -o args= 2>/dev/null || echo "N/A")

    echo "$user|$command|$args"
}

# Port scanning
scan_ports() {
    local tool=$1
    declare -A port_pids
    declare -A port_docker

    log_info "Scanning ports: ${PORTS[@]}"
    echo ""

    for port in "${PORTS[@]}"; do
        # First check if port is in use at all
        if ! is_port_in_use "$port"; then
            log_success "Port $port is free"
            continue
        fi

        # Port is in use - check if it's Docker
        if is_docker_port "$port"; then
            log_warning "Port $port is in use (Docker container)"
            port_docker["$port"]=1

            # Show Docker container info
            echo ""
            printf "%-15s %-30s %-s\n" "CONTAINER" "IMAGE" "STATUS"
            printf "%-15s %-30s %-s\n" "---------" "-----" "------"
            docker ps --filter "publish=$port" --format "{{.Names}}\t{{.Image}}\t{{.Status}}" 2>/dev/null | \
                while IFS=$'\t' read -r name image status; do
                    printf "%-15s %-30s %-s\n" "$name" "$image" "$status"
                done
            echo ""
            echo -e "${YELLOW}  → Use './manage.sh stop-prod' to stop Docker containers${NC}"
            echo ""
        else
            # Not Docker - try to get PIDs
            local pids=$(get_pids_on_port "$port" "$tool")

            if [ -z "$pids" ]; then
                # Port in use but can't get PID (likely root process)
                log_warning "Port $port is in use (unknown process, may need sudo)"
                echo ""
            else
                log_warning "Port $port is in use (local process)"
                echo ""
                printf "%-10s %-10s %-15s %-s\n" "PID" "USER" "COMMAND" "ARGS"
                printf "%-10s %-10s %-15s %-s\n" "---" "----" "-------" "----"

                for pid in $pids; do
                    IFS='|' read -r user command args <<< "$(get_process_info "$pid")"
                    printf "%-10s %-10s %-15s %-s\n" "$pid" "$user" "$command" "$args"
                    port_pids["$port"]+="$pid "
                done
                echo ""
            fi
        fi
    done

    # Store results in temp files for cleanup function (only non-Docker ports)
    if [ ${#port_pids[@]} -gt 0 ]; then
        echo "${!port_pids[@]}" > /tmp/port_pids_keys
        echo "${port_pids[@]}" > /tmp/port_pids_values
    else
        rm -f /tmp/port_pids_keys /tmp/port_pids_values
    fi

    # Store Docker ports info
    if [ ${#port_docker[@]} -gt 0 ]; then
        echo "${!port_docker[@]}" > /tmp/port_docker_keys
    else
        rm -f /tmp/port_docker_keys
    fi
}

# Cleanup logic
cleanup_processes() {
    if [ ! -f /tmp/port_pids_keys ]; then
        log_info "No processes to clean"
        return 0
    fi

    local keys=($(cat /tmp/port_pids_keys))
    local values=($(cat /tmp/port_pids_values))

    if [ ${#keys[@]} -eq 0 ]; then
        log_info "No processes to clean"
        return 0
    fi

    local killed_count=0
    local error_count=0

    for i in "${!keys[@]}"; do
        local port=${keys[$i]}
        local pids=${values[$i]}

        log_info "Cleaning port $port..."

        for pid in $pids; do
            if [ ! -d "/proc/$pid" ]; then
                log_warning "PID $pid already terminated"
                continue
            fi

            log_info "Sending SIGTERM to PID $pid"
            if kill -TERM "$pid" 2>/dev/null; then
                sleep 2

                if [ -d "/proc/$pid" ]; then
                    log_warning "Process $pid still running, sending SIGKILL"
                    if kill -KILL "$pid" 2>/dev/null; then
                        log_success "PID $pid killed (SIGKILL)"
                        ((killed_count++))
                    else
                        log_error "Failed to kill PID $pid"
                        ((error_count++))
                    fi
                else
                    log_success "PID $pid terminated (SIGTERM)"
                    ((killed_count++))
                fi
            else
                log_error "Failed to send SIGTERM to PID $pid (try with sudo)"
                ((error_count++))
            fi
        done
    done

    echo ""
    log_success "Cleaned $killed_count processes"
    if [ $error_count -gt 0 ]; then
        log_error "$error_count processes failed to clean"
        rm -f /tmp/port_pids_keys /tmp/port_pids_values
        return 1
    fi

    rm -f /tmp/port_pids_keys /tmp/port_pids_values
    return 0
}

# Main execution
main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                FORCE=true
                shift
                ;;
            --check-only)
                CHECK_ONLY=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo "=================================="
    echo "Port Cleaner"
    echo "=================================="
    echo ""

    local tool=$(detect_tool)
    log_info "Using detection tool: $tool"
    echo ""

    scan_ports "$tool"

    if [ "$CHECK_ONLY" = true ]; then
        log_info "Check-only mode, exiting"
        rm -f /tmp/port_docker_keys
        exit 0
    fi

    local has_docker_ports=false
    local has_local_processes=false

    if [ -f /tmp/port_docker_keys ]; then
        has_docker_ports=true
    fi

    if [ -f /tmp/port_pids_keys ]; then
        has_local_processes=true
    fi

    # No ports in use
    if [ "$has_docker_ports" = false ] && [ "$has_local_processes" = false ]; then
        log_success "All ports are free"
        exit 0
    fi

    # Only Docker ports - can't clean with kill
    if [ "$has_docker_ports" = true ] && [ "$has_local_processes" = false ]; then
        echo ""
        log_info "Docker containers detected. Use './manage.sh stop-prod' to stop them."
        rm -f /tmp/port_docker_keys
        exit 0
    fi

    # Has local processes to clean
    if [ "$FORCE" = false ]; then
        echo ""
        read -p "Do you want to clean these local processes? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Cleanup cancelled"
            rm -f /tmp/port_pids_keys /tmp/port_pids_values /tmp/port_docker_keys
            exit 0
        fi
    fi

    echo ""
    if cleanup_processes; then
        rm -f /tmp/port_docker_keys
        exit 0
    else
        rm -f /tmp/port_docker_keys
        exit 1
    fi
}

main "$@"
