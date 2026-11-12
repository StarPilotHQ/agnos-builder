#!/usr/bin/env python3
"""Check required image dependencies without opening display or audio devices."""
import ctypes
import importlib
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

assert Path('/VERSION').read_text().strip() == '20.5.1'
for name in ('crcmod', 'serial', 'kaitaistruct', 'capnp', 'aiohttp', 'jsonrpc', 'mapbox_earcut',
             'onnx', 'cv2', 'pyaudio', 'xattr', 'zmq'):
  importlib.import_module(name)
assert importlib.metadata.version('pycapnp') == '2.1.0'
assert importlib.metadata.version('libusb1') == '3.1.0'
assert importlib.metadata.version('comma-deps-raylib') == '6.0.0.1.post106'

for name in ('libzmq.so.5', 'libusb-1.0.so.0', 'libstdc++.so.6', 'libgcc_s.so.1', 'libc.so.6', 'libm.so.6', 'libzstd.so.1'):
  ctypes.CDLL(name)
ffmpeg = importlib.import_module('ffmpeg')
for name in ('libavformat.so.61', 'libavcodec.so.61', 'libavutil.so.59'):
  ctypes.CDLL(str(Path(ffmpeg.LIB_DIR) / name))

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
for backend in ('comma', 'headless'):
  code = """
from pathlib import Path
import sys
recovery = Path(sys.prefix) / 'share/starpilot-recovery'
sys.path.insert(0, str(recovery))
import raylib_nb
assert Path(raylib_nb.native.__file__).resolve().parent == recovery / 'raylib_nb'
assert callable(raylib_nb.cpu.screen)
"""
  subprocess.run([sys.executable, '-I', '-c', code],
                 env=dict(os.environ, RAYLIB_BACKEND=backend), check=True, timeout=30)

for name in ('setup', 'reset', 'updater'):
  for model in ('tici', 'tizi', 'mici'):
    code = """
import importlib, os, site, sys
from pathlib import Path
archive, name, model = sys.argv[1:]
recovery = Path(sys.prefix) / 'share/starpilot-recovery'
sys.path[:0] = [archive, str(recovery)]
from openpilot.common.hardware import HARDWARE
HARDWARE.get_device_type = lambda: model
module = importlib.import_module('openpilot.system.ui.' + name)
assert callable(module.main)
import raylib_nb
assert Path(raylib_nb.__file__).resolve().parent == recovery / 'raylib_nb'
assert Path(raylib_nb.native.__file__).resolve().parent == recovery / 'raylib_nb'
allowed = [os.path.realpath(p) for p in (archive, sys.prefix, sys.base_prefix, *site.getsitepackages())]
outside = [n for n, m in list(sys.modules.items()) if getattr(m, '__file__', None)
           and not (n == 'sitecustomize' and os.path.realpath(m.__file__) == os.path.realpath('/usr/lib/python3.12/sitecustomize.py'))
           and not any(os.path.realpath(m.__file__).startswith(p + os.sep) for p in allowed)]
assert not outside, outside
"""
    subprocess.run([sys.executable, '-I', '-B', '-c', code, '/usr/comma/' + name, name, model],
                   cwd='/tmp', env=dict(os.environ, SCALE='1', PWD='/tmp', PYTHONDONTWRITEBYTECODE='1'),
                   check=True, timeout=30)
print('StarPilot image runtime and nine standalone recovery imports passed; no display, audio or reset actions.')
