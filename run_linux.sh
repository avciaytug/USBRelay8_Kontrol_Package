#!/usr/bin/env bash
# USBRelay8 Kontrol - Linux calistirici
cd "$(dirname "$0")"
exec python3 relay_gui.py "$@"
