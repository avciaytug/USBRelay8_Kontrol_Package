#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USBRelay8 Kontrol — CIFT-PLATFORM (Linux + Windows), SIFIR BAGIMLILIK
======================================================================
Ayni dosya her iki sistemde calisir:

  LINUX   : python3 relay_gui.py            -> tkinter GUI
  WINDOWS : relay_gui.pyw                   -> GUI (konsolsuz)
            python  relay_gui.py            -> GUI (konsollu)

CLI (ikisi de):
  python relay_gui.py status
  python relay_gui.py on 1 2 3
  python relay_gui.py off 1
  python relay_gui.py onall
  python relay_gui.py offall
  python relay_gui.py auto

Bagimlilik:
  LINUX   : hicbir paket gerekmez (sistem fcntl + tkinter kullanir).
  WINDOWS : tkinter (Python ile gelir). Kart erisimi icin 'hidapi' gerekir:
            >  pip install hidapi
            (Yoksa Linux fcntl yontemi calisir; Windows'ta hidapi zorunludur.)
"""

import sys
import time
import argparse
import threading

from relay_core import (
    RelayDriver, DEFAULT_RELAYS, state_str,
    IS_LINUX, IS_WINDOWS, HAS_HIDAPI, HAS_FCNTL,
)


# ======================================================================
# GUI
# ======================================================================
def run_gui():
    import tkinter as tk
    from tkinter import messagebox

    drv = RelayDriver()
    ok = drv.connect()

    root = tk.Tk()
    root.title("USBRelay8 Kontrol  (dcttech 16c0:05df)")
    root.geometry("780x460")
    root.minsize(640, 400)
    root.resizable(True, True)

    # --- baslik / durum cizgisi ---
    if ok:
        conn_text = f"BAĞLI  •  {drv.backend}  •  {drv.path or ''}  •  {drv.serial}"
        conn_color = "#1f8a2e"
    else:
        conn_text = "KART BAĞLI DEĞİL — USB kablo takılı mı? (Windows: pip install hidapi)"
        conn_color = "#8a1f1f"

    tk.Label(root, text=conn_text, fg="#fff", bg=conn_color,
             font=("TkDefaultFont", 10, "bold"), anchor="w", padx=12, pady=6
             ).pack(fill="x")

    state = drv.get_states() or [False] * DEFAULT_RELAYS
    busy = [False]

    status_var = tk.StringVar(value=state_str(state))
    tk.Label(root, textvariable=status_var, font=("Consolas", 22, "bold"),
             fg="#0f0", bg="#0d1117", anchor="w", padx=16).pack(fill="x", pady=(12, 2))
    tk.Label(root, text="Bitler: soldan Role1 ... Role8   (1 = AÇIK, 0 = KAPALI)",
             fg="#888", font=("TkDefaultFont", 9)).pack(anchor="w", padx=16)

    info_var = tk.StringVar(value="Hazır" if ok else "Cihaz bulunamadı")
    tk.Label(root, textvariable=info_var, fg="#cfe",
             font=("TkDefaultFont", 10, "bold"), anchor="w", padx=16
             ).pack(fill="x", pady=(4, 0))

    # --- 8 roleyi 4x2 ızgara ---
    btn_frame = tk.Frame(root)
    btn_frame.pack(fill="both", expand=True, padx=16, pady=10)
    for c in range(4):
        btn_frame.columnconfigure(c, weight=1, uniform="col")
    for r in range(2):
        btn_frame.rowconfigure(r, weight=1, uniform="row")

    btns = []
    for i in range(DEFAULT_RELAYS):
        def make(idx):
            def toggle():
                if busy[0]:
                    return
                try:
                    drv.set_relay(idx + 1, not state[idx])
                    info_var.set(f"Role {idx+1} komutu gönderildi")
                except Exception as e:
                    info_var.set(f"[!] Yazma hatası: {e}")
                refresh()
            return toggle
        b = tk.Button(btn_frame, text=f"Role {i+1}",
                      font=("TkDefaultFont", 13, "bold"),
                      command=make(i), bd=2, relief="raised",
                      activebackground="#444", activeforeground="#fff")
        b.grid(row=i // 4, column=i % 4, padx=8, pady=8, sticky="nsew")
        btns.append(b)

    def refresh():
        real = drv.get_states()
        if real is not None:
            state[:] = real
        status_var.set(state_str(state))
        for i, b in enumerate(btns):
            if state[i]:
                b.config(bg="#1f8a2e", fg="#fff", relief="sunken")
            else:
                b.config(bg="#2b2f36", fg="#ddd", relief="raised")

    def all_on():
        if busy[0]:
            return
        try:
            drv.set_all(True)
            info_var.set("Tüm röleler AÇIK")
        except Exception as e:
            info_var.set(f"[!] Hatá: {e}")
        refresh()

    def all_off():
        if busy[0]:
            return
        try:
            drv.set_all(False)
            info_var.set("Tüm röleler KAPALI")
        except Exception as e:
            info_var.set(f"[!] Hatá: {e}")
        refresh()

    def _ui(fn):
        try:
            root.after(0, fn)
        except Exception:
            pass

    def auto():
        if busy[0]:
            return
        busy[0] = True
        info_var.set("Otomatik test çalışıyor... kart LED'lerine bakın")

        def worker():
            try:
                drv.set_all(True);  _ui(refresh); time.sleep(1.2)
                drv.set_all(False); _ui(refresh); time.sleep(1.2)
                for ch in range(1, DEFAULT_RELAYS + 1):
                    drv.set_relay(ch, True);  _ui(refresh); time.sleep(0.7)
                    drv.set_relay(ch, False); _ui(refresh); time.sleep(0.4)
                drv.set_all(False); _ui(refresh)
            finally:
                busy[0] = False
                _ui(lambda: info_var.set("Test tamam — hepsi KAPALI"))

        threading.Thread(target=worker, daemon=True).start()

    bar = tk.Frame(root); bar.pack(fill="x", padx=16, pady=(0, 14))
    tk.Button(bar, text="Tümü AÇ", command=all_on, bg="#1f8a2e", fg="#fff",
              font=("TkDefaultFont", 11, "bold"), bd=2, relief="raised").pack(side="left", padx=6)
    tk.Button(bar, text="Tümünü KAPAT", command=all_off, bg="#8a1f1f", fg="#fff",
              font=("TkDefaultFont", 11, "bold"), bd=2, relief="raised").pack(side="left", padx=6)
    tk.Button(bar, text="Otomatik Test", command=auto, bg="#1f3a8a", fg="#fff",
              font=("TkDefaultFont", 11, "bold"), bd=2, relief="raised").pack(side="right", padx=6)

    refresh()
    root.mainloop()
    drv.close()


# ======================================================================
# CLI
# ======================================================================
def cmd_status(drv):
    st = drv.get_states()
    if st is None:
        print("[!] Durum okunamadı.")
        return
    print(f"Durum: {state_str(st)}")
    for i, s in enumerate(st):
        print(f"  Role {i+1}: {'AÇIK' if s else 'kapalı'}")


def cmd_set(drv, chans, on):
    for c in chans:
        drv.set_relay(c, on)
        print(f"  Role {c}: {'AÇIK' if on else 'KAPALI'}")
    st = drv.get_states()
    if st is not None:
        print(f"  Yeni durum: {state_str(st)}")


def cmd_all(drv, on):
    drv.set_all(on)
    print(f"  Tüm röleler: {'AÇIK' if on else 'KAPALI'}")


def cmd_auto(drv, interval=1.0):
    print("=== OTOMATIK SIRALI AÇ-KAPA TESTİ ===")
    drv.set_all(True);  time.sleep(interval); print("  hepsi AÇIK")
    drv.set_all(False); time.sleep(interval); print("  hepsi KAPALI")
    for ch in range(1, DEFAULT_RELAYS + 1):
        drv.set_relay(ch, True);  time.sleep(interval / 2); print(f"  role {ch} AÇIK")
        drv.set_relay(ch, False); time.sleep(interval / 2)
    drv.set_all(False); time.sleep(0.3); print("  test tamam, hepsi kapalı")


def main():
    ap = argparse.ArgumentParser(description="USBRelay8 çift-platform sürücüsü")
    ap.add_argument("action", nargs="?", default="gui",
                    choices=["gui", "status", "on", "off", "onall", "offall", "auto"])
    ap.add_argument("chans", nargs="*", help="on/off için kanal numaraları (1-8)")
    args = ap.parse_args()

    drv = RelayDriver()
    if not drv.connect():
        print("[!] USBRelay8 (16c0:05df) bulunamadı.")
        if IS_WINDOWS and not HAS_HIDAPI:
            print("    Windows: 'pip install hidapi' çalıştırıp tekrar dene.")
        if IS_LINUX:
            print("    Linux: kart takılı mı? Gerekirse 'sudo' ile çalıştır veya udev kuralı kur.")
        if args.action == "gui":
            # GUI'de kart yoksa bile pencereyi ac (baglantisiz gosterir)
            run_gui()
        sys.exit(1)

    print(f"Kart: {drv.path}  ({drv.backend})  {drv.serial}")

    if args.action == "gui":
        run_gui()
    elif args.action == "status":
        cmd_status(drv)
    elif args.action in ("on", "off"):
        chans = [int(c) for c in args.chans] if args.chans else list(range(1, DEFAULT_RELAYS + 1))
        cmd_set(drv, chans, args.action == "on")
    elif args.action == "onall":
        cmd_all(drv, True)
    elif args.action == "offall":
        cmd_all(drv, False)
    elif args.action == "auto":
        cmd_auto(drv)

    drv.close()


if __name__ == "__main__":
    main()
