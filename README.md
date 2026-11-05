# USBRelay8 Kontrol (Manuel GUI)

8 kanallı USB röle kartını **anında, elle** kontrol eden basit GUI.
Her röleye AÇ / KAPAT butonu + kart durum göstergesi.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)

> Otomatik zamanlı tetikleme istiyorsan ayrı paketi kullan:
> **`TenefusTetikleyici_Package`** (tenefus_timer.py).

## Çalıştırma

### Windows (7 / 8 / 10 / 11)
1. `python` yoksa https://www.python.org/downloads/ adresinden Python 3.10+ kur
   (kurulumda "Add Python to PATH" işaretli olsun).
2. Bu klasörde **`run_windows.bat`** dosyasına çift tıkla.
   (veya: `python relay_gui.py`)
3. Kart takılı değilse de program açılır; kart takılınca otomatik bağlanır.

### Linux
```
sudo apt install python3-hidapi     # (Debian/Ubuntu) kart sürücüsü
./run_linux.sh
# veya: python3 relay_gui.py
```
Kartın root gerektirmemesi için `udev_rule.rules` dosyasını:
```
sudo cp udev_rule.rules /etc/udev/rules.d/99-usbreelay8.rules
sudo udevadm control --reload && sudo udevadm trigger
```

## İçerik
| Dosya | İşlev |
|-------|-------|
| `relay_gui.py` | Ana program (manuel AÇ/KAPAT GUI) |
| `relay_core.py` | Kart sürücüsü (Linux/Windows, hidapi) |
| `run_linux.sh` | Linux çalıştırıcı |
| `run_windows.bat` | Windows çalıştırıcı |
| `udev_rule.rules` | Linux udev kuralı (root'suz erişim) |

## Not
- GUI'de üstte kart durumu (BAĞLI / ARIYOR) görünür.
- Her röle satırında AÇ / KAPAT butonları vardır.
