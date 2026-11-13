#!/usr/bin/env bash
# RUNWAY — one-command setup and launch.
#
#   ./run.sh setup     install dependencies and seed the demo workspace
#   ./run.sh dev       start the API and the web app together
#   ./run.sh api       start only the API            (http://127.0.0.1:8000)
#   ./run.sh web       start only the web app        (http://localhost:3000)
#   ./run.sh seed [A-E] regenerate the demo workspace for a scenario
#   ./run.sh test      run the full backend test suite
#   ./run.sh verify    check every accounting invariant
#   ./run.sh evaluate  reproduce every published accuracy figure
#   ./run.sh build     production build of the web app
#   ./run.sh reset     wipe the database and reseed from scratch
#
#   ./run.sh migrate            apply migrations up to head
#   ./run.sh migrate-status     show the current and head revisions
#   ./run.sh migrate-new "msg"  autogenerate a new revision from the models
#   ./run.sh audit-schema       check every VARCHAR is wide enough
#   ./run.sh test-pg            run the whole suite against PostgreSQL
#   ./run.sh test-web           run the frontend test suite
#   ./run.sh test-all           backend + frontend
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PY="$BACKEND/.venv/bin/python"
DEMO_DATE="${RUNWAY_DEMO_DATE:-2026-11-07}"

c()  { printf "\033[38;5;141m%s\033[0m\n" "$*"; }
ok() { printf "\033[38;5;79m  ✓ %s\033[0m\n" "$*"; }
die(){ printf "\033[38;5;203merror: %s\033[0m\n" "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed"; }

setup() {
  c "Setting up RUNWAY"
  need python3
  if [ ! -x "$PY" ]; then
    python3 -m venv "$BACKEND/.venv" --system-site-packages
    ok "created backend/.venv"
  fi
  "$BACKEND/.venv/bin/pip" install -q --upgrade pip
  "$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"
  ok "python dependencies installed"

  if command -v pnpm >/dev/null 2>&1; then PKG=pnpm; else need npm; PKG=npm; fi
  # Not --silent. pnpm 10+ exits 1 when it skips a dependency build script,
  # and --silent swallowed the reason entirely: setup died after the Python
  # step with no message at all. An installer that fails must say why.
  (cd "$FRONTEND" && $PKG install) || die "$PKG install failed in frontend/ (see the output above)"
  ok "web dependencies installed ($PKG)"

  seed "${1:-B}"
  # alembic.ini sets a RELATIVE script_location (migrations), so this has to
  # run from backend/ like every other alembic call in this file. It did not,
  # so it printed alembic's "Path doesn't exist" error behind a green tick.
  local heads
  heads="$(cd "$BACKEND" && "$BACKEND/.venv/bin/alembic" heads 2>/dev/null | head -1 || true)"
  if [ -n "$heads" ] && [[ "$heads" != *FAILED* ]]; then
    ok "migrations at $heads"
  else
    printf "\033[38;5;215m  ! could not read the migration head\033[0m\n"
  fi
  c "Done. Start everything with:  ./run.sh dev"
}

seed_real() {
  c "Loading the real UCI Online Retail II statement (see data/real/uci_online_retail_ii/SOURCE.md)"
  (cd "$BACKEND" && "$PY" -m app.seed.real_uci)
}

seed() {
  local scenario="${1:-B}"
  c "Seeding demo workspace (scenario $scenario, as of $DEMO_DATE)"
  (cd "$BACKEND" && "$PY" -m app.seed.seed --scenario "$scenario" --reset --date "$DEMO_DATE")
}

api() {
  port_free 8000 || die "port 8000 is already in use"
  c "API on http://127.0.0.1:8000   (docs at /docs)"
  (cd "$BACKEND" && exec "$BACKEND/.venv/bin/uvicorn" app.main:app \
      --host 127.0.0.1 --port 8000 --reload)
}

web() {
  port_free 3000 || die "port 3000 is already in use"
  c "Web app on http://localhost:3000"
  (cd "$FRONTEND" && exec ./node_modules/.bin/next dev -p 3000)
}

port_free() {
  # Prefer ss, fall back to lsof, and assume free if neither exists rather
  # than refusing to start on a machine without either.
  if command -v ss >/dev/null 2>&1; then
    ! ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN
  elif command -v lsof >/dev/null 2>&1; then
    ! lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 0
  fi
}

API_PID=""
cleanup() { [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true; }

dev() {
  [ -x "$PY" ] || die "run ./run.sh setup first"
  [ -d "$FRONTEND/node_modules" ] || die "run ./run.sh setup first"
  port_free 8000 || die "port 8000 is already in use. Stop the running API, or use ./run.sh web on its own."
  port_free 3000 || die "port 3000 is already in use. Stop the running web app, or use ./run.sh api on its own."

  c "Starting RUNWAY"
  trap cleanup EXIT INT TERM
  (cd "$BACKEND" && "$BACKEND/.venv/bin/uvicorn" app.main:app \
      --host 127.0.0.1 --port 8000 --reload) &
  API_PID=$!
  sleep 3
  ok "API      http://127.0.0.1:8000/docs"
  ok "Web app  http://localhost:3000"
  ok "Sign in  owner@runway.demo / demo1234"
  (cd "$FRONTEND" && ./node_modules/.bin/next dev -p 3000)
}

migrate() {
  c "Applying migrations"
  (cd "$BACKEND" && "$BACKEND/.venv/bin/alembic" upgrade head)
}

migrate_status() {
  (cd "$BACKEND" && "$BACKEND/.venv/bin/alembic" current && \
                    "$BACKEND/.venv/bin/alembic" heads)
}

migrate_new() {
  [ -n "${1:-}" ] || die 'give the revision a message: ./run.sh migrate-new "add x"'
  (cd "$BACKEND" && "$BACKEND/.venv/bin/alembic" revision --autogenerate -m "$1")
}

test_pg() {
  local url="${RUNWAY_TEST_DATABASE_URL:-postgresql+psycopg:///runway_test?host=/run/postgresql}"
  command -v createdb >/dev/null 2>&1 && createdb runway_test 2>/dev/null || true
  c "Running the suite against PostgreSQL"
  echo "  $url"
  (cd "$ROOT" && RUNWAY_TEST_DATABASE_URL="$url" exec "$PY" -m pytest tests/ -q)
}

test_web() {
  [ -d "$FRONTEND/node_modules" ] || die "run ./run.sh setup first"
  c "Frontend tests"
  (cd "$FRONTEND" && exec ./node_modules/.bin/vitest run)
}

case "${1:-dev}" in
  setup)    setup "${2:-B}" ;;
  seed)     seed "${2:-B}" ;;
  seed-real) seed_real ;;
  api)      api ;;
  web)      web ;;
  dev)      dev ;;
  reset)    seed "${2:-B}" ;;
  test)     (cd "$ROOT" && exec "$PY" -m pytest tests/ -v) ;;
  verify)   (cd "$ROOT" && exec "$PY" scripts/verify_ledger.py --date "$DEMO_DATE") ;;
  evaluate) (cd "$ROOT" && exec "$PY" scripts/evaluate_models.py --date "$DEMO_DATE") ;;
  build)    (cd "$FRONTEND" && exec ./node_modules/.bin/next build) ;;
  migrate)        migrate ;;
  migrate-status) migrate_status ;;
  migrate-new)    migrate_new "${2:-}" ;;
  audit-schema)   (cd "$ROOT" && exec "$PY" scripts/audit_schema.py) ;;
  test-pg)        test_pg ;;
  test-web)       test_web ;;
  test-all)       ("$PY" -m pytest "$ROOT/tests" -q) && \
                  (cd "$FRONTEND" && ./node_modules/.bin/vitest run) ;;
  help|-h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0" ;;
  *)        die "unknown command '${1}'. Try ./run.sh help" ;;
esac
