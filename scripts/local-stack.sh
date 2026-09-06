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

power_supply_root="${HYDENLYNE_POWER_SUPPLY_ROOT:-/sys/class/power_supply}"
gpu_device_path="${HYDENLYNE_GPU_DEVICE_PATH:-/dev/nvidia0}"
gpu_cdi_spec_path="${HYDENLYNE_GPU_CDI_SPEC_PATH:-/etc/cdi/nvidia.yaml}"
requested_compute_mode="${HYDENLYNE_COMPUTE_MODE:-auto}"
compute_mode=""
compute_reason=""
compose_command=()

is_on_external_power() {
  local supply
  local type

  for supply in "$power_supply_root"/*; do
    [[ -r "$supply/type" && -r "$supply/online" ]] || continue
    type="$(<"$supply/type")"
    if [[ "$type" != "Battery" && "$(<"$supply/online")" == "1" ]]; then
      return 0
    fi
  done
  return 1
}

detect_compute_mode() {
  case "$requested_compute_mode" in
    cpu)
      compute_mode="cpu"
      compute_reason="forced by HYDENLYNE_COMPUTE_MODE=cpu"
      ;;
    gpu)
      if ! is_on_external_power; then
        echo "GPU mode was requested, but external power is not connected." >&2
        exit 1
      fi
      if [[ ! -e "$gpu_device_path" || ! -r "$gpu_cdi_spec_path" ]]; then
        echo "GPU mode was requested, but the NVIDIA device or CDI specification is unavailable." >&2
        exit 1
      fi
      if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
        echo "GPU mode was requested, but nvidia-smi cannot access a GPU." >&2
        exit 1
      fi
      compute_mode="gpu"
      compute_reason="forced by HYDENLYNE_COMPUTE_MODE=gpu"
      ;;
    auto)
      if ! is_on_external_power; then
        compute_mode="cpu"
        compute_reason="battery power"
      elif [[ ! -e "$gpu_device_path" || ! -r "$gpu_cdi_spec_path" ]]; then
        compute_mode="cpu"
        compute_reason="NVIDIA device or CDI specification unavailable"
      elif ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
        compute_mode="cpu"
        compute_reason="nvidia-smi cannot access a GPU"
      else
        compute_mode="gpu"
        compute_reason="external power and NVIDIA GPU available"
      fi
      ;;
    *)
      echo "HYDENLYNE_COMPUTE_MODE must be auto, cpu, or gpu." >&2
      exit 2
      ;;
  esac
}

configure_compose_command() {
  compose_command=(podman compose --file docker-compose.yml)
  if [[ "$compute_mode" == "gpu" ]]; then
    compose_command+=(--file docker-compose.gpu.yml --profile gpu)
  fi
}

stop_stack() {
  # Include the optional GPU overlay while stopping so an earlier GPU-mode run
  # cannot leave its worker behind when the next launch falls back to CPU.
  podman compose --file docker-compose.yml --file docker-compose.gpu.yml --profile gpu down --remove-orphans
}

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
    detect_compute_mode
    configure_compose_command
    stop_stack
    assert_port_available 8000
    assert_port_available 5173
    echo "Compute mode: ${compute_mode} (${compute_reason})"
    "${compose_command[@]}" up --detach --build
    wait_for_url "http://127.0.0.1:8000/health/" "Backend"
    wait_for_url "http://127.0.0.1:5173/health" "Frontend"
    echo "Hydenlyne is ready at http://localhost:5173"
    ;;
  stop)
    stop_stack
    ;;
  status)
    detect_compute_mode
    configure_compose_command
    echo "Compute mode: ${compute_mode} (${compute_reason})"
    "${compose_command[@]}" ps
    ;;
  mode)
    detect_compute_mode
    echo "${compute_mode} (${compute_reason})"
    ;;
  *)
    echo "Usage: $0 {start|stop|status|mode}" >&2
    exit 2
    ;;
esac
