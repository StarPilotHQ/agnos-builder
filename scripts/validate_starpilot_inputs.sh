#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

expect_hash() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(sha256 "$DIR/$path")"
  if [[ "$actual" != "$expected" ]]; then
    echo "starpilot input hash mismatch: $path" >&2
    echo "expected: $expected" >&2
    echo "actual:   $actual" >&2
    exit 1
  fi
}

version="$(tr -d '\n' < "$DIR/VERSION")"
[[ "$version" == "20.2.3" ]]
expect_hash userspace/root/usr/comma/setup 8d44f590c656605ec74782acad4b9f262a1bb0b798525b97f0997949ecf82ef7
expect_hash userspace/root/usr/comma/reset c5b050a0dc58850dd8519ed148c209d150df9c05364895f661461831e9e661eb
expect_hash userspace/root/usr/comma/updater 3236c98fcf381eeb8935b90f29ad040660bd355a37f984ade1e7fdd14734eb71
expect_hash userspace/root/usr/comma/installer 370d154aaf7e1e9ee433c069348ae885036a9d8cc4c8babfbfae12c8d5b3f2e8
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_imu.bin.zst 9091ec887822b66b3e49b929a684a9c182057ff92340f2e7b84cba29156af3bf
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_me.bin.zst 0bf7d4b54ace8af59d5c99c289bbb1b8ce77d11114bb880df308be2c9d5e2638
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_mec.bin.zst b19544dc8138123d29d25b79116fc4354dd465640408f86c08a4c7ad6b1d32d4
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_pfp.bin.zst 06b2ba632fa1878a16b78d9734dc8211020d257c140202462f764a156e98daef
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_rlc.bin.zst c652022ab773a626da090fe448f4abd1775fdd92899bb68b6775c87f619a14b9
expect_hash userspace/root/usr/lib/firmware/amdgpu/psp_14_0_2_sos.bin.zst e81164f81e763d8de70539e7fdcc8ea58aa9b025cf9c95361a4c63bc791177f4
expect_hash userspace/root/usr/lib/firmware/amdgpu/sdma_7_0_0.bin.zst 68add1d0817164f4fde6fd971270e4652814558545cb2400a946004126986576
expect_hash userspace/root/usr/lib/firmware/amdgpu/smu_14_0_2.bin.zst b0a03edf1c7e5a171fafe0710165b6ce90540450d1cf00132d8f0033b6ad2099
expect_hash userspace/webrtc/patches/libdatachannel-build.patch 22bce5ba596589b3333ef7812ca9185a67ef3d772bfa2e90b8e2f411b105b525
expect_hash userspace/webrtc/patches/libjuice-zero-tiebreaker.patch 37273f1a52757b491a29af6652731504a135f4e3f672daa69846f04292d38958

for path in \
  userspace/root/usr/lib/systemd/system/bluealsa.service \
  userspace/root/etc/bluetooth/main.conf \
  userspace/root/usr/lib/systemd/system/starpilot-bluetooth-radio.service \
  userspace/root/etc/dbus-1/system.d/starpilot-bluetooth.conf \
  userspace/root/usr/comma/bluetooth-enabled \
  userspace/root/usr/comma/bluetooth-radio \
  userspace/webrtc/build_libdatachannel.sh \
  userspace/webrtc/check_ice.py; do
  [[ -f "$DIR/$path" ]]
done

grep -Fxq 'HandlePowerKey=ignore' "$DIR/userspace/root/etc/systemd/logind.conf"
grep -Fxq 'HandlePowerKeyLongPress=ignore' "$DIR/userspace/root/etc/systemd/logind.conf"
grep -Fxq 'ExecStop=/usr/comma/bluetooth-radio stop' "$DIR/userspace/root/usr/lib/systemd/system/starpilot-bluetooth-radio.service"
grep -Fxq 'ExecStopPost=/usr/comma/bluetooth-radio cleanup' "$DIR/userspace/root/usr/lib/systemd/system/starpilot-bluetooth-radio.service"
grep -Fxq 'Restart=on-failure' "$DIR/userspace/root/usr/lib/systemd/system/starpilot-bluetooth-radio.service"
grep -Fxq 'systemctl disable bluealsa-aplay.service' "$DIR/userspace/services.sh"
grep -Fxq 'SOURCE_REV="989d29a32968046a002b5b9deb7a00f5012c530c"' "$DIR/userspace/webrtc/build_libdatachannel.sh"
grep -Fxq 'RUN bash /tmp/agnos/webrtc/build_libdatachannel.sh /tmp/webrtc-wheels /usr/local/venv/bin/python' "$DIR/Dockerfile.agnos"
grep -Fxq 'COPY --from=agnos-compiler-webrtc /tmp/webrtc-wheels /tmp/agnos/webrtc-wheels' "$DIR/Dockerfile.agnos"
grep -Fxq '    $XDG_DATA_HOME/venv/bin/python /usr/comma/tests/webrtc_ice_check.py' "$DIR/Dockerfile.agnos"

for dependency in \
  'crcmod==1.7' \
  'pyserial==3.5' \
  'kaitaistruct==0.11' \
  'aiohttp==3.12.15' \
  'json-rpc==1.15.0' \
  'mapbox-earcut==1.0.3' \
  'onnx==1.18.0' \
  'opencv-python-headless==4.11.0.86' \
  'pyaudio==0.2.14' \
  'xattr==1.2.0'; do
  grep -Fq "\"$dependency\"" "$DIR/userspace/uv/pyproject.toml"
done

if command -v uv >/dev/null 2>&1; then
  (cd "$DIR/userspace/uv" && uv lock --check)
fi

kernel_ref="$(git -C "$DIR/agnos-kernel-sdm845" rev-parse HEAD 2>/dev/null || true)"
[[ "$kernel_ref" == "03754482cd4a86a8a4c80b9355bba27de304c4ba" ]]

echo "StarPilot AGNOS inputs validated (20.2.3, C3/Bluetooth, factory installer, WebRTC ICE fix)."

grep -Fq "/dev/nvme0n1 /data/media" "$DIR/userspace/root/etc/fstab"
grep -Fq "mkdir -p /data/media" "$DIR/userspace/root/usr/comma/fs_setup.sh"
