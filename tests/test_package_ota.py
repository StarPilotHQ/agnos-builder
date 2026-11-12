import hashlib
import importlib.util
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
  def test_sparse_image_never_advertises_a_false_raw_alternative(self):
    spec = importlib.util.spec_from_file_location('package_ota', ROOT / 'scripts/package_ota.py')
    ota = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ota)
    with tempfile.TemporaryDirectory() as directory:
      folder = Path(directory)
      image = folder / 'system.img'
      payload = (struct.pack('<I4H4I', 0xED26FF3A, 1, 0, 28, 12, 4096, 2, 2, 0) +
                 struct.pack('<2H2I', 0xCAC1, 0, 1, 4108) + b'a' * 4096 +
                 struct.pack('<2H2I', 0xCAC2, 0, 1, 16) + bytes(4))
      image.write_bytes(payload)
      entry = ota.Partition('system', image, True, True, False, True)
      with patch.object(ota, 'OTA_OUTPUT_DIR', folder), patch.object(ota, 'compress', side_effect=shutil.copyfile):
        manifest = ota.process_file(entry, ota.checksum(entry))
      self.assertEqual(manifest['hash'], hashlib.sha256(payload).hexdigest())
      self.assertEqual(manifest['hash_raw'], hashlib.sha256(b'a' * 4096 + bytes(4096)).hexdigest())
      self.assertEqual(manifest['ondevice_hash'], hashlib.sha256(b'a' * 4096).hexdigest())
      self.assertEqual(manifest['size'], 8192)
      self.assertTrue(manifest['sparse'])
      self.assertNotIn('alt', manifest)


if __name__ == '__main__':
  unittest.main()
