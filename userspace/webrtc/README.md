# Connect ICE compatibility

AGNOS 19.8.2 permanently includes the native-library hotfix verified with live
Connect video on a comma device. No runtime bind mount or openpilot-side package
installation is needed on this image.

## Why this is needed

StarPilot's August 24, 2026 AGNOS update (`05140149fb`) switched WebRTC from
aiortc to `libdatachannel-py==2026.1.0.dev2`. Its embedded libjuice treats a zero
ICE tie-breaker as an absent role attribute. Captured browser nominations had a
present `ICE-CONTROLLING` attribute with value zero; the device rejected them
with STUN 400. Outgoing checks succeeded, but nomination/DTLS did not complete,
and Connect reported "No direct peer-to-peer routes were found to device".

The fix records role-attribute presence separately from its 64-bit value. It
keeps authentication, nonzero tie-breakers, and role-conflict comparisons intact;
missing roles and requests containing both role attributes are rejected. Camera
ownership, Sentry, codecs, and the Python WebRTC API are unchanged.

## Release integration

`Dockerfile.agnos` builds `libdatachannel-py==2026.1.0.dev2+starpilot.ice1`
in a separate compiler stage on the target architecture, using:

- Python bindings tag `2026.1.0.dev2`, checked against commit
  `989d29a32968046a002b5b9deb7a00f5012c530c`;
- the bindings' existing libdatachannel v0.24.0 and embedded libjuice commit
  `5948a4162d37bc213d6051b67ee2876ccc5a99a6`;
- checked-in build/role-presence patches and pinned build-tool versions.

Only the wheel enters the final image. It is installed into `/usr/local/venv`
after `uv sync --frozen`, with `--no-index --no-deps`. The existing lockfile and
all unrelated dependency versions are deliberately preserved. A later dependency
sync must repeat this override and its test; otherwise it may undo the fix.
`scripts/validate_starpilot_inputs.sh` checks the patch hashes and build hooks.

Both the isolated build environment and the image's managed environment run
`check_ice.py`. It sends authenticated STUN probes over loopback UDP and checks:

- nonzero and zero controlling tie-breakers succeed;
- missing or simultaneous controlling/controlled roles receive STUN 400;
- invalid authentication is rejected.

Any failed check stops the image build. No cameras, external STUN servers,
Connect accounts, or live sessions are used by these checks.

## Standalone checks

Build a wheel without modifying the current runtime (requires git, uv, a C/C++
compiler, and Python 3.12 with development headers):

```sh
bash userspace/webrtc/build_libdatachannel.sh /absolute/path/to/wheels /usr/bin/python3.12
```

On a device booted into the new image:

```sh
/usr/local/venv/bin/python /usr/comma/tests/webrtc_ice_check.py
```

The original library fails the zero-tie-breaker test. Passing these checks is
necessary but does not test the whole video path: verify live Connect video
after flashing. The earlier device bind-mount hotfix is temporary and disappears
on reboot; it is not a substitute for deploying this image.

Sources: [Python bindings](https://github.com/shiguredo/libdatachannel-py/tree/989d29a32968046a002b5b9deb7a00f5012c530c),
[libjuice](https://github.com/paullouisageneau/libjuice/tree/5948a4162d37bc213d6051b67ee2876ccc5a99a6).
The libjuice source modification is covered by its MPL-2.0 license.
