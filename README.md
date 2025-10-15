# 🎵 Touchscreen Audioplayer für Raspberry Pi

Ein vollwertiger, touchscreen-optimierter Audioplayer mit 10-Band Equalizer, entwickelt für Raspberry Pi mit 12" Display.

## ✨ Features

- 🎛️ **10-Band Equalizer** (VLC-basiert, funktioniert wirklich!)
- 🎚️ **Touchscreen-optimiert** mit großen Buttons
- ⏯️ **Vollständige Wiedergabesteuerung** (Play/Pause/Next/Prev)
- ⏩ **Schnellspul-Buttons** (+/- 10 Sekunden)
- 📊 **Fortschrittsanzeige** mit Cue-Funktion (Springen zu Position)
- 🔁 **Repeat-Modi** (Aus/Alle/Eins)
- 📁 **Ordner-Dropdown** für schnellen Zugriff
- 🔊 **Lautstärke-Kontrolle** mit +/- Buttons und Slider
- 🎵 **Animierte Visualisierung** beim Abspielen
- ⌨️ **Tastatur-Shortcuts** für alle Funktionen
- 🎸 **EQ-Presets** (Rock, Pop, Jazz, Classical, Flat)
- 📋 **Playlist-Verwaltung** mit scrollbarer Liste
- 🎨 **Modernes dunkles Theme**

## 📋 Unterstützte Formate

MP3, WAV, OGG, FLAC, M4A, AAC, WMA

## 🛠️ Installation

### Voraussetzungen

```bash
sudo apt-get update
sudo apt-get install python3-vlc vlc python3-mutagen python3-tk
```

### Download & Start

```bash
# Datei speichern als audioplayer.py
chmod +x audioplayer.py
python3 audioplayer.py
```

## 🎮 Bedienung

### Touchscreen-Buttons

| Button | Funktion |
|--------|----------|
| **⏮** | Vorheriger Song |
| **▶/⏸** | Play/Pause |
| **⏭** | Nächster Song |
| **⏪ -10s** | 10 Sekunden zurück |
| **+10s ⏩** | 10 Sekunden vor |
| **🔁** | Repeat-Modus wechseln |
| **❌ EXIT** | Beenden |
| **−/+** | Lautstärke leiser/lauter |

### ⌨️ Tastatur-Shortcuts

| Taste | Funktion |
|-------|----------|
| `SPACE` | Play/Pause |
| `←/→` | Vorheriger/Nächster Song |
| `↑/↓` | Lautstärke +/- 5% |
| `+/-` | Schnellspul +/- 10s |
| `R` | Repeat-Modus wechseln |
| `F` | Fullscreen an/aus |
| `Q` oder `ESC` | Beenden |

### 🎛️ Equalizer

**Presets:**
- Klicke auf `Flat`, `Rock`, `Pop`, `Jazz` oder `Classical`

**Manuell:**
- Ziehe die 10 Slider für einzelne Frequenzen (60Hz - 16kHz)
- Bereich: -20dB bis +20dB

### 📊 Fortschrittsbalken

- **Klicken/Ziehen** auf dem grünen Balken um zu Position zu springen
- Zeit-Anzeige zeigt aktuelle und Gesamt-Zeit

## 🚀 Kommandozeilen-Parameter

```bash
# Repeat-Modus festlegen
python3 audioplayer.py --repeat all      # Alle wiederholen (Standard)
python3 audioplayer.py --repeat one      # Ein Lied wiederholen
python3 audioplayer.py --repeat off      # Kein Repeat

# Startordner festlegen
python3 audioplayer.py --folder /media/usb/music

# Lautstärke beim Start
python3 audioplayer.py --volume 80

# Autoplay deaktivieren
python3 audioplayer.py --no-autoplay

# Kombinationen
python3 audioplayer.py --repeat all --volume 80 --folder ~/Music/Rock
```

### Alle Parameter

| Parameter | Werte | Standard | Beschreibung |
|-----------|-------|----------|--------------|
| `--repeat` | off, all, one | all | Repeat-Modus |
| `--folder` | PATH | ~/Music | Musik-Ordner |
| `--volume` | 0-100 | 70 | Start-Lautstärke |
| `--autoplay` | - | Ein | Automatisch starten |
| `--no-autoplay` | - | - | Nicht automatisch starten |

## ⚙️ Konfiguration

### Ordner-Dropdown anpassen

Öffne `audioplayer.py` und bearbeite Zeilen 65-72:

```python
self.preset_folders = [
    str(Path.home() / "Music"),
    str(Path.home() / "Music" / "Rock"),
    str(Path.home() / "Music" / "Jazz"),
    "/media/usb/music",  # USB-Stick
    # Füge weitere Ordner hinzu
]
```

### Autostart bei Raspberry Pi Boot

Erstelle `/home/pi/start_player.sh`:

```bash
#!/bin/bash
export DISPLAY=:0
cd /home/pi/
python3 audioplayer.py --repeat all --volume 80
```

```bash
chmod +x /home/pi/start_player.sh
```

In `/etc/rc.local` vor `exit 0` einfügen:

```bash
sudo -u pi /home/pi/start_player.sh &
```

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'vlc'"

```bash
sudo apt-get install python3-vlc vlc
```

### "No audio output"

```bash
# Audio auf 3.5mm Klinke umstellen
sudo raspi-config
# System Options -> Audio -> wähle Klinke
```

### Equalizer funktioniert nicht

- VLC muss korrekt installiert sein
- Bei älteren VLC-Versionen kann EQ eingeschränkt sein
- Teste: `vlc --version`

### Display zu klein / Layout passt nicht

- Passe Font-Größen in `audioplayer.py` an
- Suche nach `font=('Arial', XX)` und ändere die Zahl

## 📱 Layout-Übersicht

```
┌─────────────────────────────────────────────────┐
│ 🎵 Animierte Wellenlinien                       │
│ Song-Titel                                      │
│ [0:00] ━━━━━━━━━━━━━━━━━━━━━━━━━━━ [3:45]     │
│ Ordner: [Dropdown ▼]  [↻]                      │
│                                                 │
│ [⏪-10s][⏮][▶ PLAY][⏭][+10s⏩][🔁][❌EXIT]    │
│                                                 │
│ 🔊 Lautstärke      🎛️ 10-Band Equalizer       │
│ [−] ═══╪═══ [+]    [Flat][Rock][Pop]...        │
│                     │││││││││││                 │
│ Playlist:          Slider für jede Frequenz     │
│ ▶ Song1.mp3                                     │
│   Song2.mp3                                     │
│   Song3.mp3                                     │
└─────────────────────────────────────────────────┘
```

## 🎯 Entwickelt für

- **Hardware:** Raspberry Pi 3/4/5
- **Display:** 12" Touchscreen (funktioniert auch mit anderen Größen)
- **OS:** Raspberry Pi OS (Bullseye/Bookworm)
- **Python:** 3.7+

## 📝 Lizenz

Open Source - frei verwendbar für private und kommerzielle Zwecke.

## 👨‍💻 Entwicklung

Erstellt mit Python, Tkinter und python-vlc.

### Technische Details

- **GUI Framework:** Tkinter
- **Audio Engine:** VLC (libvlc)
- **Metadaten:** Mutagen
- **Equalizer:** VLC 10-Band EQ

---


