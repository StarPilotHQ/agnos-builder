import ast
import contextlib
import itertools
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[1]
RADIO = ROOT / 'userspace/root/usr/comma/bluetooth-radio'
VALID = b'\x04\xff\x0e\x00\x02' + bytes(range(12))


def load_radio():
  source = RADIO.read_text().split("BRING_UP_PY=$(cat <<'PY'\n", 1)[1].split('\nPY\n)', 1)[0]
  tree = ast.parse(source)
  assert isinstance(tree.body[-1], ast.Expr) and isinstance(tree.body[-1].value, ast.Call)
  assert tree.body[-1].value.func.id == 'main'
  tree.body.pop()
  module = types.ModuleType('bluetooth_radio')
  exec(compile(tree, str(RADIO), 'exec'), module.__dict__)
  return module


class Attached(Exception):
  pass


class RadioTests(unittest.TestCase):
  def setUp(self):
    self.radio = load_radio()

  @contextlib.contextmanager
  def bring_up(self, answers, baud=True, flush_error=False):
    r = self.radio
    with contextlib.ExitStack() as stack:
      for name, value in {'power': Mock(), 'pulse': Mock(), 'answer': Mock(side_effect=answers),
                          'to_3mbaud': Mock(side_effect=baud if isinstance(baud, Exception) else None,
                                            return_value=baud)}.items():
        stack.enter_context(patch.object(r, name, value))
      stack.enter_context(patch.object(r.os, 'open', return_value=7))
      stack.enter_context(patch.object(r.os, 'close'))
      stack.enter_context(patch.object(r.os, 'set_inheritable'))
      stack.enter_context(patch.object(r.os, 'execv', side_effect=Attached))
      stack.enter_context(patch.object(r.subprocess, 'run'))
      stack.enter_context(patch.object(r.termios, 'tcflush', side_effect=OSError('flush') if flush_error else None))
      stack.enter_context(patch.object(r.time, 'sleep'))
      stack.enter_context(patch.object(r.time, 'monotonic', side_effect=itertools.count()))
      yield r

  def test_failed_baud_switch_cannot_reuse_previous_readiness(self):
    with self.bring_up([VALID] * 4, OSError('baud change')) as r:
      with self.assertRaises(SystemExit) as error:
        r.main(True)
      self.assertEqual(error.exception.code, 1)
      r.os.execv.assert_not_called()
      self.assertEqual(r.os.close.call_count, 4)

  def test_flush_failure_invalidates_readiness(self):
    with self.bring_up([VALID] * 4, flush_error=True) as r:
      with self.assertRaises(SystemExit):
        r.main(True)
      r.os.execv.assert_not_called()
      self.assertEqual(r.os.close.call_count, 4)

  def test_timeout_is_bounded_and_never_attaches(self):
    with self.bring_up([None] * 4) as r:
      with self.assertRaises(SystemExit):
        r.main(True)
      self.assertEqual(r.answer.call_count, 4)
      self.assertEqual(r.os.close.call_count, 4)
      r.os.execv.assert_not_called()

  def test_retry_then_verified_attachment_keeps_port_open(self):
    with self.bring_up([None, VALID]) as r:
      with self.assertRaises(Attached):
        r.main(True)
      self.assertEqual(r.pulse.call_count, 2)
      r.os.close.assert_called_once_with(7)
      r.os.set_inheritable.assert_called_once_with(7, True)
      r.os.execv.assert_called_once_with(r.BTATTACH[0], r.BTATTACH)

  def test_failed_high_baud_probe_requires_new_low_baud_answer(self):
    with self.bring_up([VALID, VALID], baud=False) as r:
      with self.assertRaises(Attached):
        r.main(True)
      self.assertEqual(r.pulse.call_count, 2)
      self.assertEqual(r.answer.call_count, 2)
      r.os.set_inheritable.assert_called_once_with(7, True)

  def answer(self, chunks):
    r = self.radio
    chunks = list(chunks)
    def select(*args):
      return ([7], [], []) if chunks else ([], [], [])
    with patch.object(r, 'rts'), patch.object(r.termios, 'tcflush'), patch.object(r.termios, 'tcdrain'), \
         patch.object(r.os, 'write', side_effect=lambda fd, data: len(data)), \
         patch.object(r.os, 'read', side_effect=lambda *args: chunks.pop(0)), \
         patch.object(r.select, 'select', side_effect=select), \
         patch.object(r.time, 'monotonic', side_effect=itertools.count(0, 0.01)):
      return r.answer(7)

  def test_partial_valid_version_response(self):
    self.assertEqual(self.answer([bytes([b]) for b in VALID]), VALID)

  def test_empty_or_unrelated_vendor_events_are_not_readiness(self):
    for invalid in [b'\x04\xff\x00', b'\x04\xff\x0e\x01\x02' + bytes(12),
                    b'\x04\xff\x02\x00\x02', b'\x04\xff\x0e\x00', b'']:
      with self.subTest(invalid=invalid):
        self.assertIsNone(self.answer([invalid]))

  def test_noise_and_unrelated_events_before_valid_response(self):
    bad = b'\x04\xff\x0e\x00\x19' + bytes(12)
    self.assertEqual(self.answer([b'noise\x04', b'\xff\x00' + bad + VALID]), VALID)

  def test_timeout_without_serial_data(self):
    self.assertIsNone(self.answer([]))

  def test_partial_writes_complete_or_fail(self):
    r = self.radio
    with patch.object(r.os, 'write', side_effect=[2, 2, 1]) as write:
      r.write(7, b'abcde')
      self.assertEqual(write.call_args_list, [call(7, b'abcde'), call(7, b'cde'), call(7, b'e')])
    with patch.object(r.os, 'write', return_value=0):
      with self.assertRaises(OSError):
        r.write(7, b'a')

  def test_high_baud_retry_bound_and_confirmation(self):
    r = self.radio
    for answers, expected in [([None, None, VALID], True), ([None, None, None], False)]:
      with self.subTest(answers=answers), patch.object(r, 'configure') as configure, \
           patch.object(r, 'rts'), patch.object(r, 'write'), patch.object(r, 'answer', side_effect=answers) as answer, \
           patch.object(r.termios, 'tcflush'), patch.object(r.termios, 'tcdrain'), \
           patch.object(r.termios, 'B3000000', 3000000, create=True), patch.object(r.time, 'sleep'):
        self.assertEqual(r.to_3mbaud(7), expected)
        self.assertEqual(answer.call_count, 3)
        self.assertEqual(configure.call_args_list, [call(7, r.termios.B115200), call(7, 3000000)] * 3)


class CleanupTests(unittest.TestCase):
  def cleanup(self, fail_stop=False):
    with tempfile.TemporaryDirectory() as directory:
      folder = Path(directory)
      state = folder / 'paired-key'
      state.write_bytes(b'pairing remains across service restarts')
      definitions = RADIO.read_text().split('case "${1:-}" in', 1)[0]
      log = folder / 'calls'
      for name in ['systemctl', 'rfkill', 'mountpoint', 'umount']:
        script = folder / name
        script.write_text('#!/bin/bash\necho "' + name + ' $*" >> "$BT_TEST_LOG"\n' +
                          ('[[ "$BT_FAIL_STOP" != 1 ]]\n' if name == 'systemctl' else 'exit 0\n'))
        script.chmod(0o755)
      script = folder / 'cleanup.sh'
      script.write_text(definitions + '\npower() { echo "power $*" >> "$BT_TEST_LOG"; }\ncleanup\n')
      env = dict(os.environ, PATH=str(folder) + os.pathsep + os.environ['PATH'],
                 BT_TEST_LOG=str(log), BT_FAIL_STOP=str(int(fail_stop)))
      result = subprocess.run(['bash', '-e', str(script)], env=env, capture_output=True, timeout=5)
      self.assertEqual(state.read_bytes(), b'pairing remains across service restarts')
      return result.returncode, log.read_text().splitlines()

  def test_failed_start_cleanup_stops_daemons_before_unmount(self):
    for _ in range(3):
      code, calls = self.cleanup()
      self.assertEqual(code, 0)
      self.assertEqual(calls[0], 'systemctl stop bluealsa.service bluetooth.service')
      self.assertEqual(sum(c.startswith('umount ') for c in calls), 3)

  def test_failed_daemon_stop_keeps_pairing_storage_mounted(self):
    code, calls = self.cleanup(True)
    self.assertNotEqual(code, 0)
    self.assertEqual(calls, ['systemctl stop bluealsa.service bluetooth.service'])

  def test_start_is_queued_before_continuing_and_failure_cleanup_is_registered(self):
    source = RADIO.read_text()
    self.assertIn('systemctl --no-block start bluetooth.service >/dev/null 2>&1\n', source)
    self.assertNotIn('start bluetooth.service >/dev/null 2>&1 &', source)
    service = (ROOT / 'userspace/root/usr/lib/systemd/system/starpilot-bluetooth-radio.service').read_text()
    self.assertIn('ExecStopPost=/usr/comma/bluetooth-radio cleanup', service)
    self.assertIn('ExecStart=/usr/comma/bluetooth-radio start', service)
    self.assertIn('TimeoutStartSec=60', service)


if __name__ == '__main__':
  unittest.main()
