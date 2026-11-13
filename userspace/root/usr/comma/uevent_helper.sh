#!/bin/sh
# uevent-helper.service points the kernel at this, it runs for every uevent so keep it cheap
# new nodes are root only. boot.sh sets up the rest once, these are the ones that can come and go after it:
# USB and input devices, the modem's ports when it resets, and GPIOs exported later
if [ "${1:-}" = --coldplug-usb ]; then
  for path in /sys/bus/usb/devices/*; do
    [ -f "$path/idVendor" ] || continue
    bus=$(cat "$path/busnum")
    dev=$(cat "$path/devnum")
    ACTION=add SUBSYSTEM=usb DEVTYPE=usb_device \
      PRODUCT="$(cat "$path/idVendor")/$(cat "$path/idProduct")/0" \
      DEVNAME="$(printf 'bus/usb/%03d/%03d' "$bus" "$dev")" "$0" || exit 1
  done
  exit 0
fi

[ "$ACTION" = add ] || exit 0
case "$SUBSYSTEM" in
  input)
    case "$DEVNAME" in
      input/*)
        chgrp input "/dev/$DEVNAME"
        chmod 666 "/dev/$DEVNAME"
        ;;
    esac
    ;;
  usb)
    if [ "$DEVTYPE" = usb_device ]; then
      case "$PRODUCT" in
        bbaa/ddee/*|bbaa/ddcc/*|3801/ddee/*|3801/ddcc/*|483/df11/*|0483/df11/*)
          chmod 666 "/dev/$DEVNAME"
          ;;
        *) chmod 664 "/dev/$DEVNAME" ;;
      esac
    fi
    ;;
  tty)
    # the modem's ports come back when it resets, modem.py only fixes them up when it starts over
    case "$DEVNAME" in
      ttyUSB*)
        chgrp dialout "/dev/$DEVNAME"
        chmod 660 "/dev/$DEVNAME"
        ;;
    esac
    ;;
  gpio)
    d=/sys$DEVPATH
    chgrp -f gpio "$d" "$d/active_low" "$d/direction" "$d/edge" "$d/value"
    chmod -f 770 "$d" "$d/active_low" "$d/direction" "$d/edge" "$d/value"
    ;;
esac
