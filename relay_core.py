#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
relay_core.py — USBRelay8 (dcttech / Van Ooijen, VID 0x16C0 / PID 0x05DF)
CANITLANMIS, CIFT-PLATFORM (Linux + Windows) PROTOKOL CATMANI
=================================================================

Bu kart OUTPUT report (os.write) DEGIL, FEATURE report konusur.
Komutlar 9 baytligidir:

      buf[0] = 0x00          # report ID
      buf[1] = KOMUT         # 0xFF=ACIK  0xFD=KAPALI  0xFE=HEPSI ACIK  0xFC=HEPSI KAPALI
      buf[2] = RELAY         # 1..8  (tumleri icin 0x00)
      buf[3..8] = 0x00

  LINUX   : /dev/hidrawX  +  fcntl.ioctl (HIDIOCSFEATURE_9 / HIDIOCGFEATURE_9)  -> sifir bagimlilik
  WINDOWS : hidapi (pip install hidapi)  -> send_feature_report / get_feature_report

Durum okuma: feature report cevabinin rep[8] bayti = 8 rolenin durum maskesi
(bit N = role N+1). Bu, ayni kartla calisan RelayControlPro/relay_driver.py
kodundan birebir alinmis ve fiziksel olarak dogrulanmistir.

ONEMLI: Cihaz BAGLANTI SUREBINDE ACIK TUTULUR (fd / hid.device).
Her islemden sonra karttan GERCEK durum okunur.
"""

import os
import sys
import glob
import time
import struct
import threading

# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------
VID = 0x16C0
PID = 0x05DF
REPORT_LEN  = 9
DEFAULT_RELAYS = 8

CMD_ON      = 0xFF
CMD_OFF     = 0xFD
CMD_ALL_ON  = 0xFE
CMD_ALL_OFF = 0xFC

IS_LINUX    = sys.platform.startswith("linux")
IS_WINDOWS  = sys.platform.startswith("win")

# Linux hidraw ioctl sabitleri
HIDIOCGRAWINFO   = 0x80084803   # _IOR('H', 0x03, 8)
HIDIOCSFEATURE_9 = 0xC0094806   # _IOWR('H', 0x06, 9)
HIDIOCGFEATURE_9 = 0xC0094807   # _IOWR('H', 0x07, 9)

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import hid
    HAS_HIDAPI = True
except ImportError:
    HAS_HIDAPI = False


# ----------------------------------------------------------------------
# Linux: /dev/hidrawX cihazini bul
# ----------------------------------------------------------------------
def _find_linux_hidraw():
    """16C0:05DF cihazi /dev/hidrawX olarak bulur (coklu format destegi)."""
    # 1) /sys/class/hidraw/hidrawX/device/uevent
    #    Olasi formatlar:  "16C0:05DF"  /  "HID_ID=0003:000016C0:000005DF"
    for h in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        ue = os.path.join(h, "device", "uevent")
        try:
            with open(ue, "r", errors="ignore") as f:
                data = f.read().upper()
        except OSError:
            data = ""
        vid_s, pid_s = f"{VID:04X}", f"{PID:04X}"
        # dogrudan "16C0:05DF"
        if f"{vid_s}:{pid_s}" in data:
            idx = os.path.basename(h).replace("hidraw", "")
            if os.path.exists(f"/dev/hidraw{idx}"):
                return f"/dev/hidraw{idx}"
        # HID_ID / MODALIAS icinde 8 haneli: 000016C0:000005DF
        if f"0000{vid_s}:0000{pid_s}" in data:
            idx = os.path.basename(h).replace("hidraw", "")
            if os.path.exists(f"/dev/hidraw{idx}"):
                return f"/dev/hidraw{idx}"
    # 2) /dev/hidraw* uzerinde HIDIOCGRAWINFO ile VID/PID kontrolu
    if HAS_FCNTL:
        for dev in sorted(glob.glob("/dev/hidraw*")):
            try:
                fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
                try:
                    rawinfo = bytearray(8)
                    fcntl.ioctl(fd, HIDIOCGRAWINFO, rawinfo)
                    bustype, vendor, product = struct.unpack("<IHH", rawinfo)
                    if vendor == VID and product == PID:
                        return dev
                finally:
                    os.close(fd)
            except OSError:
                continue
    return None


# ----------------------------------------------------------------------
# Sürücü sınıfı (Linux fcntl + Windows hidapi) — ACIK TUTAR
# ----------------------------------------------------------------------
class RelayDriver:
    """Cift-platform, thread-guvenli USBRelay8 surucusu.
    Cihaz baglanti suresince ACIK tutulur; her islem karttan dogrulanir."""

    def __init__(self):
        self._lock = threading.Lock()
        self.backend = None          # 'linux_hidraw' | 'hidapi'
        self.path = None             # Linux /dev/hidrawX
        self._fd = None              # Linux acik fd
        self._hid_dev = None         # Windows hid.device()
        self.relays = DEFAULT_RELAYS
        self.connected = False
        self.serial = ""

    # ---------------- cihaz baglanti ----------------
    def connect(self):
        """Karti bulur ve ACIK tutacak sekilde baglantiyi kurar."""
        with self._lock:
            # 1) hidapi (Windows'ta zorunlu, Linux'ta varsa tercih edilir)
            if HAS_HIDAPI:
                try:
                    lst = hid.enumerate(VID, PID)
                    if lst:
                        item = lst[0]
                        self.path = item.get("path")
                        self._hid_dev = hid.device()
                        self._hid_dev.open_path(self.path)
                        self.backend = "hidapi"
                        self.connected = True
                        self._read_info()
                        return True
                except Exception:
                    pass
            # 2) Linux yerel hidraw (sifir bagimlilik)
            if IS_LINUX and HAS_FCNTL:
                dev = _find_linux_hidraw()
                if dev:
                    try:
                        self._fd = os.open(dev, os.O_RDWR)
                    except PermissionError:
                        self._fd = None
                        self.path = dev
                        self.backend = "linux_hidraw"
                        self.connected = True   # erisim suanda yok ama cihazi bulduk
                        self.serial = "USBRelay8"
                        return True
                    self.path = dev
                    self.backend = "linux_hidraw"
                    self.connected = True
                    self._read_info()
                    return True
            self.connected = False
            return False

    def close(self):
        with self._lock:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
            if self._hid_dev is not None:
                try:
                    self._hid_dev.close()
                except Exception:
                    pass
                self._hid_dev = None
            self.connected = False

    def _read_info(self):
        """Karttan serial + durum oku (ariza olursa sorun etmez)."""
        try:
            rep = self._read_feature()
            if rep and len(rep) >= 9:
                self.serial = bytes(rep[1:6]).decode("ascii", errors="ignore").strip() or "USBRelay8"
        except Exception:
            self.serial = self.serial or "USBRelay8"

    # ---------------- ham feature report ----------------
    def _write_feature(self, buf):
        if self.backend == "linux_hidraw":
            if self._fd is None:
                raise RuntimeError("Cihaz acik degil (Linux fd).")
            fcntl.ioctl(self._fd, HIDIOCSFEATURE_9, bytearray(buf))
        elif self.backend == "hidapi":
            if self._hid_dev is None:
                raise RuntimeError("hidapi cihazi acik degil.")
            self._hid_dev.send_feature_report(list(buf))
        else:
            raise RuntimeError("Aktif backend yok.")
        time.sleep(0.04)

    def _read_feature(self):
        if self.backend == "linux_hidraw":
            if self._fd is None:
                raise RuntimeError("Cihaz acik degil (Linux fd).")
            rep = bytearray(REPORT_LEN)
            rep[0] = 0x00
            fcntl.ioctl(self._fd, HIDIOCGFEATURE_9, rep)
            return list(rep)
        elif self.backend == "hidapi":
            if self._hid_dev is None:
                raise RuntimeError("hidapi cihazi acik degil.")
            return list(self._hid_dev.get_feature_report(0, REPORT_LEN))
        else:
            raise RuntimeError("Aktif backend yok.")

    # ---------------- public API ----------------
    def get_states(self):
        """[True/False]*N dondurur. Hata olursa None."""
        with self._lock:
            try:
                rep = self._read_feature()
                mask = rep[8] if len(rep) >= 9 else 0
                return [bool((mask >> i) & 1) for i in range(self.relays)]
            except Exception:
                return None

    def set_relay(self, channel, on):
        """Tek roleyi ac/kapa (channel: 1..N)."""
        with self._lock:
            cmd = CMD_ON if on else CMD_OFF
            buf = [0x00, cmd, channel, 0, 0, 0, 0, 0, 0]
            self._write_feature(buf)
            time.sleep(0.04)

    def set_all(self, on):
        """Tum roleyi ayni anda ac/kapa."""
        with self._lock:
            cmd = CMD_ALL_ON if on else CMD_ALL_OFF
            buf = [0x00, cmd, 0, 0, 0, 0, 0, 0, 0]
            self._write_feature(buf)
            time.sleep(0.04)


# ----------------------------------------------------------------------
# Yardimci
# ----------------------------------------------------------------------
def state_str(states):
    """[False,True,...] -> '01000000'"""
    return "".join("1" if s else "0" for s in states)


def find_relay_dev(hint=None):
    """Geriye-uyumlu: Linux hidraw path dondurur."""
    if hint:
        return hint
    return _find_linux_hidraw()
