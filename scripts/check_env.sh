#!/bin/bash
# Environment Check Script
# Validates Python, Node, Supervisor, and dependencies
# Version: 1.0.0

set -e
set -o pipefail

# Color definitions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error tracking
declare -a ERRORS
HAS_ERROR=false

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ERRORS+=("$1")
    HAS_ERROR=true
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

# Version checks
check_python_version() {
    log_info "Checking Python version..."

    if ! check_command python3; then
        log_error "Python 3 not found. Install with: sudo apt install python3"
        return
    fi

    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
        log_info "Python $PYTHON_VERSION (OK)"
    else
        log_error "Python $PYTHON_VERSION < 3.11. Upgrade to Python 3.11+"
    fi
}

check_node_version() {
    log_info "Checking Node.js version..."

    if ! check_command node; then
        log_error "Node.js not found. Install with: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
        return
    fi

    NODE_VERSION=$(node --version 2>&1 | sed 's/v//')
    MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)

    if [ "$MAJOR" -ge 20 ]; then
        log_info "Node.js $NODE_VERSION (OK)"
    else
        log_error "Node.js $NODE_VERSION < 20. Upgrade with: nvm install 20"
    fi
}

check_venv() {
    log_info "Checking virtual environment..."

    if [ ! -f "venv/bin/python" ]; then
        log_error "Virtual environment not found. Create with: python3 -m venv venv"
        return
    fi

    VENV_PYTHON_VERSION=$(venv/bin/python --version 2>&1 | awk '{print $2}')
    log_info "Virtual environment Python $VENV_PYTHON_VERSION (OK)"
}

check_supervisor() {
    log_info "Checking Supervisor..."

    if ! check_command supervisord; then
        log_error "Supervisor not found. Install with: sudo apt install supervisor"
        return
    fi

    SUPERVISOR_VERSION=$(supervisord --version 2>&1)
    log_info "Supervisor $SUPERVISOR_VERSION (OK)"
}

check_python_dependencies() {
    log_info "Checking Python dependencies..."

    if [ ! -f "venv/bin/python" ]; then
        log_error "Virtual environment not found, skipping Python dependencies check"
        return
    fi

    # Check site-packages directory for faster results (avoid slow find on WSL)
    SITE_PACKAGES=$(ls -d venv/lib/python*/site-packages 2>/dev/null | head -1)

    if [ -z "$SITE_PACKAGES" ]; then
        log_error "Could not find site-packages directory"
        return
    fi

    REQUIRED_PACKAGES=("flask" "faster_whisper" "gunicorn" "torch" "ctranslate2")

    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        # Check if package directory exists (much faster than pip list or import)
        pkg_dir=$(echo "$pkg" | tr '-' '_')
        if [ -d "$SITE_PACKAGES/$pkg_dir" ] || [ -d "$SITE_PACKAGES/${pkg_dir}-"* ] 2>/dev/null || ls "$SITE_PACKAGES/${pkg_dir}"*.dist-info >/dev/null 2>&1; then
            log_info "  ${pkg} (OK)"
        else
            log_error "  ${pkg} not found. Install with: venv/bin/pip install ${pkg}"
        fi
    done
}

check_node_dependencies() {
    log_info "Checking Node.js dependencies..."

    if [ ! -d "frontend/node_modules" ]; then
        log_error "Node modules not found. Install with: cd frontend && npm install"
        return
    fi

    REQUIRED_PACKAGES=("vite" "react" "react-dom")

    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if npm list --prefix frontend "$pkg" >/dev/null 2>&1; then
            log_info "  ${pkg} (OK)"
        else
            log_error "  ${pkg} not found. Install with: cd frontend && npm install"
        fi
    done
}

# Main execution
main() {
    echo "=================================="
    echo "Environment Check Script"
    echo "=================================="
    echo ""

    check_python_version
    check_node_version
    check_venv
    check_supervisor
    check_python_dependencies
    check_node_dependencies

    echo ""
    echo "=================================="
    if [ "$HAS_ERROR" = true ]; then
        echo -e "${RED}Environment check FAILED${NC}"
        echo "Errors found:"
        for error in "${ERRORS[@]}"; do
            echo "  - $error"
        done
        exit 1
    else
        echo -e "${GREEN}Environment check PASSED${NC}"
        exit 0
    fi
}

main
