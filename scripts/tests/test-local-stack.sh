#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT

fake_bin="$fixture_root/bin"
power_root="$fixture_root/power"
gpu_device="$fixture_root/nvidia0"
gpu_cdi_spec="$fixture_root/nvidia.yaml"
mkdir -p "$fake_bin" "$power_root/AC"
printf 'Mains\n' > "$power_root/AC/type"
printf '1\n' > "$power_root/AC/online"
touch "$gpu_device" "$gpu_cdi_spec"

printf '%s\n' '#!/usr/bin/env bash' "echo 'GPU 0'" > "$fake_bin/nvidia-smi"
chmod +x "$fake_bin/nvidia-smi"

mode_output="$(
  PATH="$fake_bin:$PATH" \
  HYDENLYNE_POWER_SUPPLY_ROOT="$power_root" \
  HYDENLYNE_GPU_DEVICE_PATH="$gpu_device" \
  HYDENLYNE_GPU_CDI_SPEC_PATH="$gpu_cdi_spec" \
  "$project_root/scripts/local-stack.sh" mode
)"
[[ "$mode_output" == "gpu (external power and NVIDIA GPU available)" ]]

printf '0\n' > "$power_root/AC/online"
mode_output="$(
  PATH="$fake_bin:$PATH" \
  HYDENLYNE_POWER_SUPPLY_ROOT="$power_root" \
  HYDENLYNE_GPU_DEVICE_PATH="$gpu_device" \
  HYDENLYNE_GPU_CDI_SPEC_PATH="$gpu_cdi_spec" \
  "$project_root/scripts/local-stack.sh" mode
)"
[[ "$mode_output" == "cpu (battery power)" ]]

if PATH="$fake_bin:$PATH" \
  HYDENLYNE_COMPUTE_MODE=gpu \
  HYDENLYNE_POWER_SUPPLY_ROOT="$power_root" \
  HYDENLYNE_GPU_DEVICE_PATH="$gpu_device" \
  HYDENLYNE_GPU_CDI_SPEC_PATH="$gpu_cdi_spec" \
  "$project_root/scripts/local-stack.sh" mode >/dev/null 2>&1; then
  echo "GPU mode must reject battery power" >&2
  exit 1
fi

echo "local-stack compute mode tests passed"
