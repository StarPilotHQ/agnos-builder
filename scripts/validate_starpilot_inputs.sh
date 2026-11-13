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
[[ "$version" == "20.5.2" ]]
expect_hash userspace/root/usr/comma/setup e04c63448610dbeaf57c8139450f8a314a7430336f3b3fc71eab4714a64d3129
expect_hash userspace/root/usr/comma/reset 3b088e5a51d0823f99228a78e778adf1d18ba3b43e4aac881c6b353292c09df4
expect_hash userspace/root/usr/comma/updater 1430b368162d714a1a3898663e8cede403a50427372d92a2fb9a2dea7e6a2a87
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
[[ "$kernel_ref" == "1df457b12c1b81a358deb22e7c216370c6819f1d" ]]

echo "StarPilot AGNOS inputs validated (20.5.2, C3/Bluetooth, factory installer, WebRTC ICE fix)."

grep -Fq "/dev/nvme0n1 /data/media" "$DIR/userspace/root/etc/fstab"
grep -Fq "mkdir -p /data/media" "$DIR/userspace/root/usr/comma/boot.sh"
grep -Fq "x-systemd.before=comma.service" "$DIR/userspace/root/etc/fstab"
grep -Fq "sudo chown comma: /data/media" "$DIR/userspace/root/usr/comma/comma.sh"
grep -Fq "x-systemd.after=boot.service" "$DIR/userspace/root/etc/fstab"
expect_hash userspace/recovery_raylib/__init__.py aaf8fd1f33a49f75c3437f476f8af9eb88116d05dd1fcf1dfe723f793dff62fa
expect_hash userspace/recovery_raylib/_backend.py b225028e1b9318dca15e5e6f02587c46490a4ab7b6d47bbbcd434d2ce6476129
expect_hash userspace/recovery_raylib/colors.py 6a760d1c196abffc61277147c7a918fa84181bf4fd73a28e21843b22a3b2900a
expect_hash userspace/recovery_raylib/enums.py f042c81a16644f4465131e2a5463da466d0ac35ab4685e8b74885bb299d702eb
expect_hash userspace/recovery_raylib/licenses/LICENSE.nanobind f305091a4e57805870b217a28ea4b1f16610eece8457d2370f822a9696b75836
expect_hash userspace/recovery_raylib/licenses/LICENSE.raylib 882a5a819cf562aa3583aae3af3f2211dda15c63de9fc8cc4b399a2f9e78d799
expect_hash userspace/recovery_raylib/licenses/LICENSE.robin-map 34bbaea469971f0274e5df342ae23d8f15267e279e8a50dc75ea0c5e969b5e2c
expect_hash userspace/root/usr/comma/agnos-apps.tar.xz 19e29afc2c21677bb41dd84e2305076040bb8e242a34077ff33dcc520c0c8773
