#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# PROTOCOL — Agent Operating System
# One-command launcher for all 6 modules
# ──────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ${BOLD}PROTOCOL v0.2.0${NC}${BLUE} — Agent Operating System  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ─── Check Python ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}ERROR: python3 not found${NC}"
    exit 1
fi

# ─── Check required packages ─────────────────────────────────────────────────
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import sqlite3" 2>/dev/null || {
    echo -e "${RED}ERROR: sqlite3 module required${NC}"
    exit 1
}
echo -e "  ${GREEN}✓${NC} sqlite3"

# ─── Clean old DBs ───────────────────────────────────────────────────────────
echo -e "${YELLOW}Cleaning databases...${NC}"
rm -f "$SCRIPT_DIR"/*.db
echo -e "  ${GREEN}✓${NC} Databases reset"

# ─── Start modules ───────────────────────────────────────────────────────────
PIDS=()
MODULES=(
    "MEMSTORE:8500:memstore_server.py"
    "TRAKR:8501:trakr_server.py"
    "GUARDRAIL:8502:guardrail_server.py"
    "VITALS:8503:vitals_server.py"
    "HEALER:8504:healer_server.py"
    "ORCHESTRATOR:8505:orchestrator_server.py"
)

echo ""
echo -e "${BLUE}Starting PROTOCOL modules...${NC}"

for module in "${MODULES[@]}"; do
    IFS=':' read -r name port script <<< "$module"
    if [ ! -f "$SCRIPT_DIR/$script" ]; then
        echo -e "  ${RED}✗${NC} $script not found — skipping $name"
        continue
    fi
    python3 "$SCRIPT_DIR/$script" &
    PID=$!
    PIDS+=($PID)
    echo -e "  ${GREEN}✓${NC} $name (port $port) — PID $PID"
    sleep 0.5
done

echo ""
echo -e "${GREEN}${BOLD}All modules started.${NC}"
echo -e "  ORCHESTRATOR health: http://127.0.0.1:8505/health"
echo -e "  Module status:       http://127.0.0.1:8505/modules"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all modules.${NC}"

# ─── Trap and cleanup ────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down PROTOCOL modules...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null && echo -e "  ${RED}✗${NC} Stopped PID $pid" || true
    done
    echo -e "${GREEN}All modules stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ─── Wait for all background processes ───────────────────────────────────────
wait
