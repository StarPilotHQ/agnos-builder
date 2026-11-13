import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMA = ROOT / 'userspace/root/usr/comma'


class LegacyDeviceTests(unittest.TestCase):
  def test_build_and_runtime_keep_the_exact_release_version(self):
    version = (ROOT / 'VERSION').read_text().strip()
    self.assertIn(f'[[ "$version" == "{version}" ]]', (ROOT / 'scripts/validate_starpilot_inputs.sh').read_text())
    self.assertIn(f"== '{version}'", (ROOT / 'userspace/check_starpilot_runtime.py').read_text())

  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.sys = self.root / 'sys'
    self.dev = self.root / 'dev'
    self.sys.mkdir()
    self.dev.mkdir()

  def script(self, name):
    source = (COMMA / name).read_text().replace('/sys/', str(self.sys) + '/').replace('/dev/', str(self.dev) + '/')
    path = self.root / name
    path.write_text(source)
    path.chmod(0o755)
    return path

  def node(self, bus, dev, vendor, product):
    path = self.sys / f'bus/usb/devices/{bus}-{dev}'
    path.mkdir(parents=True)
    for name, value in [('idVendor', vendor), ('idProduct', product), ('busnum', str(bus)), ('devnum', str(dev))]:
      (path / name).write_text(value + '\n')
    node = self.dev / f'bus/usb/{bus:03}/{dev:03}'
    node.parent.mkdir(parents=True, exist_ok=True)
    node.touch()
    node.chmod(0o600)
    return node

  def test_panda_application_bootstub_and_dfu_hotplug_permissions(self):
    helper = self.script('uevent_helper.sh')
    for product in ['bbaa/ddee/200', 'bbaa/ddcc/200', '3801/ddee/200', '3801/ddcc/200',
                    '483/df11/2200', '0483/df11/0', '3801/0001/0', '2c7c/6007/0']:
      with self.subTest(product=product):
        node = self.node(1, 2, '3801', 'ddcc') if not (self.dev / 'bus/usb/001/002').exists() else self.dev / 'bus/usb/001/002'
        node.chmod(0o600)
        env = dict(os.environ, ACTION='add', SUBSYSTEM='usb', DEVTYPE='usb_device', PRODUCT=product, DEVNAME='bus/usb/001/002')
        subprocess.run([str(helper)], env=env, check=True)
        self.assertEqual(node.stat().st_mode & 0o777, 0o664 if product in ['3801/0001/0', '2c7c/6007/0'] else 0o666)

  def test_coldplug_repairs_existing_panda_and_preserves_other_usb_permissions(self):
    helper = self.script('uevent_helper.sh')
    nodes = [(self.node(1, 2, '3801', 'ddcc'), 0o666), (self.node(1, 3, '0483', 'df11'), 0o666),
             (self.node(4, 2, '3801', '0001'), 0o664)]
    subprocess.run([str(helper), '--coldplug-usb'], check=True)
    for node, mode in nodes:
      self.assertEqual(node.stat().st_mode & 0o777, mode)

  def test_remove_and_interface_events_do_not_change_permissions(self):
    helper = self.script('uevent_helper.sh')
    node = self.node(1, 2, '3801', 'ddcc')
    for action, devtype in [('remove', 'usb_device'), ('add', 'usb_interface')]:
      env = dict(os.environ, ACTION=action, SUBSYSTEM='usb', DEVTYPE=devtype, PRODUCT='3801/ddcc/0', DEVNAME='bus/usb/001/002')
      subprocess.run([str(helper)], env=env, check=True)
      self.assertEqual(node.stat().st_mode & 0o777, 0o600)

  def test_c3_hub_and_gps_setup_without_changing_other_boards(self):
    source = (COMMA / 'boot.sh').read_text().split('function setup_gpios {', 1)[1].split('\nrun_init mount_dsp', 1)[0]
    source = 'function setup_gpios {' + source + '\nsetup_gpios\n'
    source = source.replace('/sys/', str(self.sys) + '/').replace('chgrp -f gpio', 'chgrp -f "$(id -gn)"')
    model = self.sys / 'firmware/devicetree/base/model'
    model.parent.mkdir(parents=True)
    gpio = self.sys / 'class/gpio'
    gpio.mkdir(parents=True)
    (gpio / 'export').touch()
    pins = [30, 32, 33, 34, 49, 50, 52, 116, 124, 134, 1264]
    for device in ['comma tici', 'comma tizi', 'comma mici', 'ultimate provisioning']:
      with self.subTest(device=device):
        model.write_text(device)
        for pin in pins:
          path = gpio / f'gpio{pin}'
          path.mkdir(exist_ok=True)
          path.chmod(0o700)
          for attr in ['active_low', 'direction', 'edge', 'value']:
            (path / attr).write_text('in')
            (path / attr).chmod(0o600)
        subprocess.run(['bash', '-e', '-c', source], check=True)
        self.assertEqual((gpio / 'gpio30/direction').read_text().strip(), 'high' if device == 'comma tici' else 'in')
        self.assertEqual((gpio / 'gpio41').exists(), False)
        for pin in [32, 33]:
          expected = 0o770 if device in ['comma tici', 'comma mici'] else 0o600
          self.assertEqual((gpio / f'gpio{pin}/value').stat().st_mode & 0o777, expected)

  def test_service_reconciles_usb_after_installing_hotplug_helper(self):
    service = (ROOT / 'userspace/root/usr/lib/systemd/system/uevent-helper.service').read_text()
    self.assertIn('ExecStartPost=/usr/comma/uevent_helper.sh --coldplug-usb', service)
    self.assertLess(service.index('echo /usr/comma/uevent_helper.sh'), service.index('--coldplug-usb'))

  def test_bluetooth_finds_both_slots_without_udev_links(self):
    source = (COMMA / 'bluetooth-radio').read_text().split('  slot="', 1)[1].split('  [[ -b "$device" ]]', 1)[0]
    source = 'slot="' + source + '\nprintf "%s" "$device"\n'
    source = source.replace('/sys/', str(self.sys) + '/').replace('/dev/', str(self.dev) + '/')
    source = source.replace('/proc/cmdline', str(self.root / 'cmdline'))
    for suffix, name in [('_a', 'sde9'), ('_b', 'sde10')]:
      path = self.sys / f'class/block/{name}'
      path.mkdir(parents=True)
      (path / 'uevent').write_text(f'DEVNAME={name}\nPARTNAME=bluetooth{suffix}\n')
    for suffix, name in [('_a', 'sde9'), ('_b', 'sde10')]:
      (self.root / 'cmdline').write_text(f'root=/dev/sda7 androidboot.slot_suffix={suffix} quiet\n')
      result = subprocess.run(['bash', '-e', '-c', source], capture_output=True, text=True, check=True)
      self.assertEqual(result.stdout, str(self.dev / name))
    (self.root / 'cmdline').write_text('androidboot.slot_suffix=_missing\n')
    result = subprocess.run(['bash', '-e', '-c', source.replace('sleep 0.1', ':')], capture_output=True, text=True)
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual(result.stdout, '')


if __name__ == '__main__':
  unittest.main()
