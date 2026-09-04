#!/usr/bin/env bash
# Start the Hydenlyne stack from this checkout only.  A port collision is a
# hard failure: serving a different worktree is worse than failing visibly.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! command -v podman >/dev/null 2>&1; then
  echo "Podman is required. Install Podman, then run this command again." >&2
  exit 1
fi

assert_port_available() {
  local port="$1"
  local listener
  listener="$(ss -ltn "sport = :${port}" | tail -n +2)"
  if [[ -n "$listener" ]]; then
    echo "Port ${port} is already in use. Refusing to start a mixed checkout." >&2
    echo "Stop the process or stack that owns port ${port}, then retry." >&2
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS --max-time 2 "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "${name} did not become ready. Run './scripts/local-stack.sh status' for service state." >&2
  exit 1
}

case "${1:-start}" in
  start)
    # Stop only containers belonging to this checkout/project. No volumes are removed.
    podman compose down --remove-orphans
    assert_port_available 8000
    assert_port_available 5173
    podman compose up --detach --build
    wait_for_url "http://127.0.0.1:8000/health/" "Backend"
    wait_for_url "http://127.0.0.1:5173/health" "Frontend"
    echo "Hydenlyne is ready at http://localhost:5173"
    ;;
  stop)
    podman compose down --remove-orphans
    ;;
  status)
    podman compose ps
    ;;
  *)
    echo "Usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
