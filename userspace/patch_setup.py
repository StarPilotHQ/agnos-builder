#!/usr/bin/env python3
"""Select DRM installers from comma's installer service in the pinned setup zipapp."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def patch_setup(path: Path) -> None:
  old_header = b'headers = {"User-Agent": USER_AGENT,'
  # Comma's installer service uses an exact upstream release identifier to
  # select the display backend, including when it serves a fork installer.
  installer_header = b'''installer_hosts = ("installer.comma.ai", "openpilot.comma.ai",
                         "openpilot-test.comma.ai", "openpilot-nightly.comma.ai")
      user_agent = "AGNOSSetup-20.6" if urlparse(self.download_url).hostname in installer_hosts else USER_AGENT
      headers = {"User-Agent": user_agent,'''
  targets = {f'openpilot/system/ui/{model}_setup.py' for model in ('tici', 'mici')}
  with TemporaryDirectory(dir=path.parent) as temp:
    output = Path(temp) / path.name
    with path.open('rb') as source, output.open('wb') as destination:
      destination.write(source.readline())
      with ZipFile(source) as original, ZipFile(destination, 'w') as patched:
        for entry in original.infolist():
          content = original.read(entry)
          if entry.filename in targets:
            if content.count(old_header) != 1:
              raise ValueError(f'Unexpected installer request in {entry.filename}')
            content = content.replace(old_header, installer_header)
            targets.remove(entry.filename)
          patched.writestr(entry, content)
    if targets:
      raise ValueError(f'Missing setup modules: {targets}')
    output.chmod(path.stat().st_mode & 0o777)
    output.replace(path)


if __name__ == '__main__':
  patch_setup(Path(sys.argv[1]))
