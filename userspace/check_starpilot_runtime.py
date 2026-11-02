#!/usr/bin/env python3
"""Check required image dependencies without opening display or audio devices."""
import importlib
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

assert Path('/VERSION').read_text().strip() == '20.2-starpilot.1'
for name in ('crcmod', 'serial', 'kaitaistruct', 'capnp', 'aiohttp', 'jsonrpc', 'mapbox_earcut',
             'onnx', 'cv2', 'pyaudio', 'xattr'):
  importlib.import_module(name)
assert importlib.metadata.version('pycapnp') == '2.1.0'
assert importlib.metadata.version('libusb1') == '3.1.0'
assert importlib.metadata.version('comma-deps-raylib') == '6.0.0.1.post106'

for name in ('pyray', 'raylib_nb'):
  code = f'import {name} as r; v=r.Vector2(2,3); assert v.x==2 and v.y==3; c=r.Color(1,2,3,4); assert c.a==4'
  subprocess.run([sys.executable, '-I', '-c', code], env=dict(os.environ, RAYLIB_BACKEND='headless'),
                 check=True, timeout=30)
for package in ('raylib', 'raylib_nb'):
  folder = Path(importlib.util.find_spec(package).origin).parent
  libraries = list(folder.glob('*comma*.so'))
  assert len(libraries) == 1, (package, libraries)
  result = subprocess.run(['ldd', str(libraries[0])], check=True, capture_output=True, text=True)
  assert 'not found' not in result.stdout, result.stdout

assert '/dev/nvme0n1 /data/media' in Path('/etc/fstab').read_text()
assert Path('/lib/firmware/qca').is_dir()
assert Path('/usr/comma/bluetooth-radio').is_file()
assert Path('/usr/lib/systemd/system/starpilot-bluetooth-radio.service').is_file()
assert 'HandlePowerKeyLongPress=ignore' in Path('/etc/systemd/logind.conf').read_text()
for name in ('setup', 'installer', 'reset', 'updater'):
  assert os.access(Path('/usr/comma') / name, os.X_OK), name
print('StarPilot image runtime checks passed; display, audio and vehicle hardware were not opened.')
