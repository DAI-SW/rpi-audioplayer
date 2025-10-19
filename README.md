# 🎵 Touchscreen Audioplayer für Raspberry Pi (CustomTkinter Edition)

Ein vollwertiger, touchscreen-optimierter Audioplayer mit **echter Audio-Analyse**, 10-Band Equalizer, Shuffle, Favoriten und modernem UI - entwickelt für Raspberry Pi mit 7-12" Display.

## ✨ Features

### 🎛️ Audio & Wiedergabe
- **10-Band Equalizer** (VLC-basiert, 60Hz - 16kHz)
- **5 EQ-Presets** (Flat, Rock, Pop, Jazz, Classical)
- **Repeat-Modi** (Aus / Alle / Eins)
- **Shuffle-Modus** mit intelligenter Wiedergabe-Reihenfolge
- **Schnellspul-Buttons** (+/- 10 Sekunden)
- **Fortschrittsbalken** mit Cue-Funktion (Springen zu Position)
- **Lautstärke-Kontrolle** (0-100%) mit +/- Buttons

### 📊 Audio-Visualisierung (Optional)
- **VU-Meter** (Stereo L/R mit Echtzeit-RMS)
- **Spektrum-Analyzer** (16-20 Frequenz-Bänder via FFT)
- **Wellenform** (Ringpuffer mit 120ms Historie, Echtzeit-Audio)
- **None-Modus** (minimale CPU-Last)
- Wechsel während der Laufzeit mit **'V'** Taste

### 📁 Dateiverwaltung
- **Ordner-Dropdown** mit vordefinierten Pfaden
- **Ordner wählen** Dialog (grafisch)
- **Dateien hinzufügen** Dialog (Mehrfachauswahl)
- **Favoriten-System** (★) mit Persistierung
- **Scrollbare Playlist** mit visueller Markierung

### ⚙️ Einstellungen & Konfiguration
- **Settings-Dialog** mit:
  - Auto-Loopback Toggle
  - Audio-Senken Auswahl (PulseAudio/PipeWire)
  - Analyzer Input-Device Auswahl
  - Device-Listen (Sinks & Inputs)
- **Theme-Wechsel** (Light / Dark / System)
- **Config-Persistierung** (~/.audioplayer_ctk_config.json)
- **Favoriten-Persistierung** (~/.audioplayer_ctk_favorites.json)

### 🎨 Benutzeroberfläche
- **CustomTkinter** - Modernes, anpassbares Design
- **Touchscreen-optimiert** mit großen Buttons
- **Responsive Layout** für verschiedene Auflösungen
- **Fullscreen-Modus** (Standard)
- **Umfangreiche Tastatur-Shortcuts**

## 📋 Unterstützte Formate

MP3, WAV, OGG, FLAC, M4A, AAC, WMA

## 🛠️ Installation

### Voraussetzungen

```bash
sudo apt-get update
sudo apt-get install python3-vlc vlc python3-mutagen \
                     fonts-noto-color-emoji fonts-dejavu-core

# CustomTkinter installieren
pip3 install customtkinter

# Optional: Für echte Audio-Visualisierung
sudo apt-get install python3-numpy portaudio19-dev
pip3 install sounddevice numpy
```

### Download & Start

```bash
# Datei speichern als audioplayer_ctk.py
chmod +x audioplayer_ctk.py

# Starten (minimal, ohne Visualisierung)
python3 audioplayer_ctk.py

# Mit Visualisierung
python3 audioplayer_ctk.py --visualizer spectrum

# Mit Auto-Loopback (für echte Audio-Daten)
python3 audioplayer_ctk.py --visualizer spectrum --auto-loopback
```

### 🔊 Audio-Setup (für Visualisierung mit echten Daten)

**Option 1: Automatisch (empfohlen)**
```bash
# Player erstellt automatisch Loopback
python3 audioplayer_ctk.py --auto-loopback --visualizer spectrum
```

**Option 2: Manuell**
```bash
# PulseAudio Loopback
pactl load-module module-loopback latency_msec=1

# Oder über Settings-Dialog im Player:
# ⚙️ Einstellungen → Auto-Loopback aktivieren
```

**Option 3: Settings-Dialog**
- Starte Player ohne `--auto-loopback`
- Klicke auf **⚙️ Einstellungen**
- Aktiviere "Auto-Loopback beim Start"
- Wähle gewünschte Audio-Senke
- Klicke "Übernehmen"

## 🎮 Bedienung

### Touchscreen-Buttons

| Button | Funktion |
|--------|----------|
| **⏮** | Vorheriger Song |
| **▶/⏸** | Play/Pause |
| **⏭** | Nächster Song |
| **⏪ -10s** | 10 Sekunden zurück |
| **+10s ⏩** | 10 Sekunden vor |
| **🔀** | Shuffle an/aus |
| **🔁** | Repeat-Modus wechseln |
| **❌ EXIT** | Beenden |
| **−/+** | Lautstärke leiser/lauter |
| **★/☆** | Favorit hinzufügen/entfernen |
| **⚙️** | Einstellungen öffnen |

### ⌨️ Tastatur-Shortcuts

| Taste | Funktion |
|-------|----------|
| `SPACE` | Play/Pause |
| `←/→` | Vorheriger/Nächster Song |
| `↑/↓` | Lautstärke +/- 5% |
| `+/-` | Schnellspul +/- 10s |
| `R` | Repeat-Modus wechseln |
| `S` | Shuffle an/aus |
| `V` | Visualizer-Style wechseln |
| `F` | Fullscreen an/aus |
| `Q` oder `ESC` | Beenden |

### 🎛️ Equalizer

**Presets:**
- Klicke auf `Flat`, `Rock`, `Pop`, `Jazz` oder `Clas`

**Manuell:**
- Ziehe die 10 vertikalen Slider für einzelne Frequenzen
- Frequenzen: 60Hz, 170Hz, 310Hz, 600Hz, 1kHz, 3kHz, 6kHz, 12kHz, 14kHz, 16kHz
- Bereich: -20dB bis +20dB

### ⭐ Favoriten

- **Hinzufügen:** Klicke auf **☆** Button neben dem Song-Titel
- **Entfernen:** Klicke auf **★** Button
- **In Playlist:** Favoriten sind mit ★ markiert
- **Persistiert:** Favoriten bleiben nach Neustart erhalten

### 🔀 Shuffle

- **Aktivieren:** Klicke auf **🔀 AUS** oder drücke **'S'**
- **Deaktivieren:** Klicke erneut oder drücke **'S'**
- **Intelligente Wiedergabe:** Aktueller Song bleibt, Rest wird gemischt

### 📁 Dateiverwaltung

**Ordner laden:**
1. Wähle aus Dropdown-Liste ODER
2. Klicke "Ordner wählen…" für Dialog ODER
3. Klicke **↻** zum Neu-Laden

**Dateien hinzufügen:**
1. Klicke "Dateien hinzufügen…"
2. Wähle mehrere Audiodateien aus
3. Diese werden an Playlist angehängt

## 🚀 Kommandozeilen-Parameter

```bash
# Repeat-Modus festlegen
python3 audioplayer_ctk.py --repeat all      # Alle wiederholen (Standard)
python3 audioplayer_ctk.py --repeat one      # Ein Lied wiederholen
python3 audioplayer_ctk.py --repeat off      # Kein Repeat

# Startordner festlegen
python3 audioplayer_ctk.py --folder /media/usb/music

# Lautstärke beim Start
python3 audioplayer_ctk.py --volume 80

# Visualizer auswählen
python3 audioplayer_ctk.py --visualizer spectrum     # Spektrum-Analyzer
python3 audioplayer_ctk.py --visualizer vu_meter     # Stereo VU-Meter
python3 audioplayer_ctk.py --visualizer wave         # Wellenform
python3 audioplayer_ctk.py --visualizer none         # Keine Viz (minimal)

# Auto-Loopback aktivieren
python3 audioplayer_ctk.py --auto-loopback

# Autoplay deaktivieren
python3 audioplayer_ctk.py --no-autoplay

# Kombinationen
python3 audioplayer_ctk.py --repeat all --volume 80 \
  --folder ~/Music/Jazz --visualizer spectrum --auto-loopback
```

### Alle Parameter

| Parameter | Werte | Standard | Beschreibung |
|-----------|-------|----------|--------------|
| `--repeat` | off, all, one | all | Repeat-Modus |
| `--folder` | PATH | ~/Music | Musik-Ordner |
| `--volume` | 0-100 | 70 | Start-Lautstärke |
| `--visualizer` | none, vu_meter, spectrum, wave | **none** | Visualisierungs-Style |
| `--auto-loopback` | - | Aus | Automatisches Audio-Loopback erstellen |
| `--autoplay` | - | **Ein** | Automatisch starten |
| `--no-autoplay` | - | - | Nicht automatisch starten |

## ⚙️ Konfiguration

### Config-Datei

Einstellungen werden automatisch gespeichert in:
```
~/.audioplayer_ctk_config.json
```

**Inhalt:**
```json
{
  "auto_loopback": true,
  "target_sink": "alsa_output.platform-bcm2835_audio.analog-stereo",
  "analyzer_input": "ctk_loop.monitor"
}
```

### Favoriten-Datei

Favoriten werden gespeichert in:
```
~/.audioplayer_ctk_favorites.json
```

### Ordner-Dropdown anpassen

Öffne `audioplayer_ctk.py` und suche nach `self.preset_folders`:

```python
self.preset_folders = [
    str(Path.home() / "Music"),
    str(Path.home() / "Music" / "Rock"),
    str(Path.home() / "Music" / "Jazz"),
    str(Path.home() / "Music" / "Classical"),
    str(Path.home() / "Downloads"),
    "/media/usb/music",
    # Füge weitere Ordner hinzu
]
```

### Autostart bei Raspberry Pi Boot

Erstelle `/home/pi/start_player.sh`:

```bash
#!/bin/bash
export DISPLAY=:0
cd /home/pi/

# Audio auf Line Out
amixer cset numid=3 1
amixer set PCM 90%

# Player starten
python3 audioplayer_ctk.py --repeat all --volume 80 \
  --visualizer spectrum --auto-loopback
```

```bash
chmod +x /home/pi/start_player.sh
```

In `/etc/rc.local` vor `exit 0` einfügen:

```bash
sudo -u pi /home/pi/start_player.sh &
```

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'customtkinter'"

```bash
pip3 install customtkinter
```

### "ModuleNotFoundError: No module named 'vlc'"

```bash
sudo apt-get install python3-vlc vlc
```

### "No audio output"

```bash
# Audio auf 3.5mm Klinke (Line Out) umstellen
amixer cset numid=3 1
amixer set PCM 90%

# Oder mit raspi-config
sudo raspi-config
# System Options -> Audio -> wähle Headphones
```

### Audio-Visualisierung zeigt keine Reaktion

**Prüfung:**
```bash
# Liste Audio-Devices
python3 -c "import sounddevice; print(sounddevice.query_devices())"

# Sollte Device mit max_input_channels > 0 zeigen!
```

**Lösung 1: Auto-Loopback**
```bash
python3 audioplayer_ctk.py --auto-loopback --visualizer spectrum
```

**Lösung 2: Settings-Dialog**
1. Öffne **⚙️ Einstellungen**
2. Aktiviere "Auto-Loopback beim Start"
3. Wähle Analyzer-Input (z.B. "ctk_loop.monitor")
4. Klicke "Übernehmen"

**Lösung 3: Manuell**
```bash
# Vor dem Start:
pactl load-module module-loopback latency_msec=1

# Dann:
python3 audioplayer_ctk.py --visualizer spectrum
```

### X-Server stürzt ab / Performance-Probleme

**Für minimale X-Server (Openbox, etc.):**

```bash
# 1. OHNE Visualisierung starten (minimal)
python3 audioplayer_ctk.py --visualizer none

# 2. GPU-Beschleunigung aktivieren
sudo raspi-config
# Advanced Options -> GL Driver -> GL (Full KMS)
sudo reboot

# 3. Nur einfache Visualisierung
python3 audioplayer_ctk.py --visualizer wave
```

### Equalizer funktioniert nicht

- VLC muss korrekt installiert sein
- Teste: `vlc --version`
- Bei älteren VLC-Versionen kann EQ eingeschränkt sein

### "pactl: Kommando nicht gefunden"

```bash
# PulseAudio installieren (optional)
sudo apt-get install pulseaudio pulseaudio-utils
pulseaudio --start

# Oder nutze Player ohne --auto-loopback
python3 audioplayer_ctk.py --visualizer wave
```

## 📱 Layout-Übersicht (1024x600 optimiert)

```
┌────────────────────────────────────────────────────────────┐
│ ┌────────────────────────────────────────────────────────┐ │
│ │   📊 Visualisierung (VU / Spectrum / Wave / None)     │ │
│ └────────────────────────────────────────────────────────┘ │
│ [🔊 SPECTRUM]  [Light|Dark|System]  [⚙️ Einstellungen]    │
│                                                            │
│ Song-Titel.mp3                                   [★/☆]    │
│ [0:00] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ [3:45]      │
│                                                            │
│ 📁 [Dropdown ▼] [↻] [Ordner wählen] [Dateien hinzufügen] │
│                                                            │
│        [⏪][⏮][▶ PLAY][⏭][⏩][🔀][🔁][❌]                │
│                                                            │
│ ┌──────┬───────────────────────┬─────────────────────────┐│
│ │ 🔊   │  📋 Playlist          │  🎛️ Equalizer          ││
│ │      │                       │                         ││
│ │ [−]  │ ▶ ★ Song1.mp3         │ [Flat][Rock][Pop]...    ││
│ │ [═]  │     Song2.mp3         │ │││││││││││            ││
│ │ [+]  │     Song3.mp3         │ (10 Slider)             ││
│ │      │     Song4.mp3         │                         ││
│ └──────┴───────────────────────┴─────────────────────────┘│
└────────────────────────────────────────────────────────────┘
```

## 🎯 Entwickelt für

- **Hardware:** Raspberry Pi 3/4/5
- **Display:** 7-12" Touchscreen (optimiert für 1024x600)
- **OS:** Raspberry Pi OS (Bullseye/Bookworm)
- **Python:** 3.7+

## 🔬 Wie funktioniert die Audio-Analyse?

**Architektur:**
1. **LoopbackManager** erstellt Null-Senke (`ctk_loop`)
2. VLC spielt auf diese Senke (via `PULSE_SINK`)
3. **module-loopback** leitet zu echter Audio-Ausgabe
4. **AudioAnalyzer** liest von `ctk_loop.monitor`
5. **Ringpuffer** speichert letzte ~1 Sekunde Audio
6. **FFT/RMS** alle 100ms für Visualisierung

**Vorteile:**
- ✅ Echte Audio-Daten (nicht simuliert)
- ✅ Niedrige Latenz (~50-100ms)
- ✅ Kein Einfluss auf Audio-Qualität
- ✅ Automatisches Setup möglich
- ✅ Konfigurierbar über Settings

**Performance:**
- VU-Meter: ~2% CPU
- Spektrum: ~5% CPU
- Welle: ~3% CPU
- None: ~1% CPU

## 📝 Neue Features gegenüber Tkinter-Version

### ✨ Funktional
- 🔀 **Shuffle-Modus** mit intelligenter Wiedergabe
- ⭐ **Favoriten-System** mit Persistierung
- 📁 **Datei-/Ordner-Dialoge** (grafisch)
- ⚙️ **Settings-Dialog** mit Device-Auswahl
- 💾 **Config-Persistierung**
- 🎨 **Theme-Wechsel** (Light/Dark/System)
- 🔄 **Verbessertes Loopback-Management**

### 🎨 Design
- Moderneres UI mit **CustomTkinter**
- Bessere Skalierbarkeit
- Konsistentere Farben
- Professionelleres Aussehen
- Touchscreen-optimierte Buttons

### 🛠️ Technisch
- Ringpuffer für Wellenform (120ms Historie)
- Bessere Audio-Analyse Performance
- Robustere Fehlerbehandlung
- Sauberere Code-Struktur
- Umfassende Konfigurierbarkeit

## 📝 Lizenz

Open Source - frei verwendbar für private und kommerzielle Zwecke.

## 👨‍💻 Entwicklung

Erstellt mit Python, CustomTkinter und python-vlc.

### Technische Details

- **GUI Framework:** CustomTkinter (basiert auf Tkinter)
- **Audio Engine:** VLC (libvlc)
- **Audio-Analyse:** sounddevice + numpy (optional)
  - 44.1kHz Sampling Rate
  - 2048 Sample Block Size
  - RMS-Berechnung für VU-Meter
  - FFT für Spektrum-Analyse
  - Ringpuffer für Wellenform
  - 100ms Update-Rate
- **Metadaten:** Mutagen
- **Equalizer:** VLC 10-Band EQ
- **Loopback:** PulseAudio/PipeWire (pactl)
- **Persistierung:** JSON (Config & Favoriten)

---


## 🆘 Support

Bei Problemen:
1. Prüfe Console-Output für Fehlermeldungen
2. Teste ohne `--auto-loopback`
3. Teste mit `--visualizer none`
4. Prüfe Audio-Devices: `python3 -c "import sounddevice; print(sounddevice.query_devices())"`
5. Öffne ⚙️ Einstellungen → Tab "Inputs" für Device-Liste
