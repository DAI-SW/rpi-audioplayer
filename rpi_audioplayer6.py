#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Touchscreen Audioplayer für Raspberry Pi (CustomTkinter)
------------------------------------------------------
Refactor + Features: Shuffle, Favoriten, Datei-/Ordnerauswahl
Engine:    python-vlc
Optional:  sounddevice + numpy (Echtzeit-Visualizer)

Installationen:
    sudo apt-get install python3-vlc vlc python3-mutagen
    pip3 install customtkinter
    # Optional für Audio-Visualisierung:
    sudo apt-get install python3-numpy portaudio19-dev
    pip3 install sounddevice numpy
    sudo apt-get install fonts-noto-color-emoji fonts-dejavu-core

Start-Beispiele:
    python3 audioplayer_ctk.py --repeat all --visualizer spectrum
    python3 audioplayer_ctk.py --folder ~/Music/Jazz --volume 60 --autoplay

Optionale Auto-Loopback (PulseAudio/PipeWire):
    # Script kann das automatisch erledigen (Flag --auto-loopback)
    # Manuell wäre es in etwa:
    #   pactl load-module module-null-sink sink_name=ctk_loop sink_properties=device.description=CTK_LoopSink
    #   pactl load-module module-loopback source=ctk_loop.monitor sink=@DEFAULT_SINK@ latency_msec=1
    # sudo apt install fonts-noto-color-emoji  fonts-dejavu-core
Hinweise:
- Visualizer "none" ist Standard (geringe CPU-Last)
- Loopback/Monitor für echte Analyzer-Daten optional – jetzt NICHT konfiguriert
- Neu: 🔀 Shuffle, ★ Favoriten (persistiert), 📂 Ordner wählen, ➕ Dateien hinzufügen
"""

import os
import json
import random
import math
import argparse
from pathlib import Path

import customtkinter as ctk
import vlc
from mutagen import File as MutagenFile
from tkinter import filedialog as fd
import subprocess
import shutil
import tkinter as tk
import threading

# --- Optionale Module für echte Audioanalyse ---
AUDIO_ANALYSIS_AVAILABLE = False
try:
    import sounddevice as sd
    import numpy as np
    AUDIO_ANALYSIS_AVAILABLE = True
except Exception:
    print("⚠️ sounddevice/numpy nicht installiert – Visualizer nutzt Fallback.")

FAV_PATH = Path.home() / ".audioplayer_ctk_favorites.json"
CFG_PATH = Path.home() / ".audioplayer_ctk_config.json"
AUDIO_EXT = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma')


# =========================
# Audio Analyzer
# =========================
class AudioAnalyzer:
    """Echte Audio-Analyse mit sounddevice & numpy (vereinfachte CPU-Variante)."""

    def __init__(self, auto_loopback: bool = False):
        self.is_active = False
        self.sample_rate = 44100
        self.block_size = 2048
        self.channels = 2
        self.auto_loopback = auto_loopback

        # dynamische Werte
        self.current_rms_l = 0.0
        self.current_rms_r = 0.0
        self.spectrum = np.zeros(20) if AUDIO_ANALYSIS_AVAILABLE else None

        self.stream = None

        # Ringpuffer für Wave-Ansicht (synchron)
        self.wave_secs = 1.0  # ca. 1 Sekunde Verlauf puffern
        buf_len = int(self.sample_rate * self.wave_secs)
        self.wave_buffer = np.zeros(buf_len, dtype=np.float32) if AUDIO_ANALYSIS_AVAILABLE else None
        self.wave_write_idx = 0
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        try:
            if self.channels == 2:
                left = indata[:, 0]
                right = indata[:, 1]
            else:
                left = right = indata[:, 0]
            # RMS
            self.current_rms_l = float(np.sqrt(np.mean(left ** 2)))
            self.current_rms_r = float(np.sqrt(np.mean(right ** 2)))

            # FFT (Mono)
            mono = (left + right) / 2.0

            # --- Wellenform in Ringpuffer schreiben ---
            if self.wave_buffer is not None:
                with self._lock:
                    n = len(mono)
                    buf = self.wave_buffer
                    L = buf.shape[0]
                    i = self.wave_write_idx % L
                    first = min(n, L - i)
                    buf[i:i + first] = mono[:first]
                    rest = n - first
                    if rest > 0:
                        buf[0:rest] = mono[first:first + rest]
                    self.wave_write_idx = (i + n) % L

            # Spektrum berechnen
            fft = np.fft.rfft(mono)
            magnitude = np.abs(fft)
            num_bands = 20
            band_size = max(1, len(magnitude) // num_bands)
            bands = []
            for i in range(num_bands):
                start = i * band_size
                end = start + band_size
                bands.append(np.mean(magnitude[start:end]))
            bands = np.array(bands)
            maxv = np.max(bands)
            if maxv > 0:
                bands = bands / maxv
            self.spectrum = bands
        except Exception:
            pass

    def start(self, prefer_device_substr: str | None = None):
        if not AUDIO_ANALYSIS_AVAILABLE:
            return
        try:
            devices = sd.query_devices()
            input_id = None
            # Wenn gewünscht, bevorzugt ein bestimmtes Device (z.B. ctk_loop.monitor)
            if prefer_device_substr:
                p = prefer_device_substr.lower()
                for idx, dev in enumerate(devices):
                    if dev.get('max_input_channels', 0) > 0 and p in str(dev.get('name','')).lower():
                        input_id = idx
                        break
            if input_id is None:
                for idx, dev in enumerate(devices):
                    if dev.get('max_input_channels', 0) > 0:
                        name = str(dev.get('name', '')).lower()
                        if 'monitor' in name or 'loopback' in name:
                            input_id = idx
                            break
                        if input_id is None:
                            input_id = idx
            if input_id is None:
                print("⚠️ Kein Input-Device für Analyzer gefunden.")
                return
            self.stream = sd.InputStream(
                device=input_id,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._callback,
            )
            self.stream.start()
            self.is_active = True
            print(f"✅ Audio-Analyse gestartet (Device ID: {input_id})")
        except Exception as e:
            print(f"⚠️ Analyzer-Startfehler: {e}")
            self.is_active = False

    def stop(self):
        self.is_active = False
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass

    def get_recent_wave(self, n_samples: int) -> np.ndarray:
        """Gibt die letzten n_samples Mono-Samples zurück (float32)."""
        if not AUDIO_ANALYSIS_AVAILABLE or self.wave_buffer is None:
            return np.zeros(max(1, n_samples), dtype=np.float32)
        with self._lock:
            buf = self.wave_buffer
            L = buf.shape[0]
            n = max(1, min(n_samples, L))
            end = self.wave_write_idx % L
            start = (end - n) % L
            if start < end:
                out = buf[start:end].copy()
            else:
                out = np.concatenate((buf[start:], buf[:end])).copy()
        return out



# =========================
# Loopback-Manager (PulseAudio / PipeWire via pactl)
# =========================
class LoopbackManager:
    """Erzeugt bei Bedarf automatisch eine Null-Senke + Loopback.
    - Setzt PULSE_SINK=ctk_loop, damit VLC auf diese Senke spielt.
    - Leitet per module-loopback zur gewünschten Senke (Default oder gewählt) weiter.
    """
    def __init__(self):
        self.nullsink_id: int | None = None
        self.loop_id: int | None = None
        self.sink_name = "ctk_loop"
        self.target_sink = None  # pactl-Sinkname (z.B. als String)
        self.env_applied = False

    @staticmethod
    def _cmd_exists(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    def _pactl(self, *args) -> tuple[int, str]:
        try:
            out = subprocess.check_output(["pactl", *map(str, args)], text=True)
            return 0, out
        except subprocess.CalledProcessError as e:
            return e.returncode, e.output or ""
        except FileNotFoundError:
            return 127, "pactl not found"

    def list_sinks(self) -> list[str]:
        rc, out = self._pactl("list", "short", "sinks")
        if rc != 0:
            return []
        # Format: index	name	driver	... -> wir nehmen Spalte 1 (name)
        names = []
        for line in out.strip().splitlines():
            parts = line.split("	")
            if len(parts) >= 2:
                names.append(parts[1])
        return names

    def get_default_sink(self) -> str | None:
        rc, out = self._pactl("get-default-sink")
        if rc == 0:
            return out.strip()
        return None

    def setup(self, target_sink: str | None = None) -> bool:
        if not self._cmd_exists("pactl"):
            print("ℹ️ Kein pactl gefunden – überspringe Auto-Loopback.")
            return False
        # gewünschte Zielsenke merken
        self.target_sink = target_sink or self.get_default_sink() or "@DEFAULT_SINK@"

        # Null-Senke anlegen
        rc, out = self._pactl("load-module", "module-null-sink",
                              f"sink_name={self.sink_name}",
                              "sink_properties=device.description=CTK_LoopSink")
        if rc == 0:
            try:
                self.nullsink_id = int(out.strip())
            except Exception:
                self.nullsink_id = None
        else:
            print("ℹ️ module-null-sink konnte nicht geladen werden (evtl. existiert schon).")

        # Loopback von ctk_loop.monitor -> Ziel-Senke
        rc, out = self._pactl("load-module", "module-loopback",
                              f"source={self.sink_name}.monitor",
                              f"sink={self.target_sink}",
                              "latency_msec=1")
        if rc == 0:
            try:
                self.loop_id = int(out.strip())
            except Exception:
                self.loop_id = None
        else:
            print("⚠️ module-loopback konnte nicht geladen werden.")

        # VLC auf die Null-Senke umleiten
        os.environ["PULSE_SINK"] = self.sink_name
        self.env_applied = True
        print(f"✅ Auto-Loopback aktiv: PULSE_SINK={self.sink_name} -> {self.target_sink}")
        return True

    def cleanup(self):
        if self.loop_id is not None:
            self._pactl("unload-module", str(self.loop_id))
            self.loop_id = None
        if self.nullsink_id is not None:
            self._pactl("unload-module", str(self.nullsink_id))
            self.nullsink_id = None

    def cleanup(self):
        # Reihenfolge: loopback zuerst, dann null-sink
        if self.loop_id is not None:
            self._pactl("unload-module", str(self.loop_id))
            self.loop_id = None
        if self.nullsink_id is not None:
            self._pactl("unload-module", str(self.nullsink_id))
            self.nullsink_id = None


# =========================
# Haupt-App
# =========================
class AudioPlayerApp(ctk.CTk):
    def __init__(self, args):
        super().__init__()

        # Konfiguration laden
        self.config = self._load_config()

        # Optional: Auto-Loopback einrichten (vor VLC-Init!)
        want_auto = args.auto_loopback or self.config.get("auto_loopback", False)
        self.loopback = LoopbackManager() if want_auto else None
        if self.loopback:
            target = self.config.get("target_sink")
            self.loopback.setup(target_sink=target)

        # Window/Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Touchscreen Audioplayer – VLC + Analyzer (CTk)")
        self.attributes('-fullscreen', True)
        self.geometry("1024x600")

        # VLC
        self.vlc_instance = vlc.Instance('--no-xlib')
        self.player = self.vlc_instance.media_player_new()
        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_song_end)

        # State
        self.playlist: list[str] = []
        self.current_index = 0
        self.is_playing = False
        self.song_length = 0.0
        self.is_seeking = False
        self.fullscreen = True
        self.update_in_progress = False
        self.animation_tick = 0

        # Shuffle
        self.shuffle_mode = False
        self.shuffled_order: list[int] = []
        self.shuf_pos = 0

        # Visualizer
        self.visualizer_styles = ['none', 'vu_meter', 'spectrum', 'wave']
        self.current_visualizer = args.visualizer if args.visualizer in self.visualizer_styles else 'none'

        # Analyzer (nur wenn Visualizer aktiv)
        self.analyzer = None
        if self.current_visualizer != 'none' and AUDIO_ANALYSIS_AVAILABLE:
            self.analyzer = AudioAnalyzer(auto_loopback=bool(self.loopback))
            prefer = self.config.get("analyzer_input") or (f"{self.loopback.sink_name}.monitor" if self.loopback else None)
            self.analyzer.start(prefer_device_substr=prefer)

        # Repeat
        repeat_map = {'off': 0, 'all': 1, 'one': 2}
        self.repeat_mode = repeat_map.get(args.repeat, 1)

        # Favoriten
        self.favorites = self._load_favorites()

        self.music_folder = args.folder if args.folder else str(Path.home() / "Music")
        self.autoplay = args.autoplay

        # UI
        self._build_ui()

        # Init-Setup
        self.volume_slider.set(args.volume)
        self.player.audio_set_volume(int(args.volume))
        self._update_repeat_button()
        self._update_shuffle_button()
        self._setup_equalizer()
        self._load_folder(self.music_folder)

        # Loops
        self._update_progress_loop()
        self._animation_loop()
        if self.analyzer:
            self._process_audio_loop()

    # ---------- UI ----------
    def _build_ui(self):
        # Top: Visualizer
        self.viz_canvas = ctk.CTkCanvas(self, height=56, bg="#111111", highlightthickness=1, highlightbackground="#333333")
        self.viz_canvas.pack(fill="x", padx=8, pady=(8, 4))

        # Visualizer-Info + Theme-Schalter
        top_bar = ctk.CTkFrame(self)
        top_bar.pack(fill="x", padx=8)
        self.viz_label = ctk.CTkLabel(top_bar, text=f"📊 {self.current_visualizer.upper()}  |  'V' wechseln")
        self.viz_label.pack(side="left", padx=8, pady=6)
        self.theme_switch = ctk.CTkSegmentedButton(top_bar, values=["Light", "Dark", "System"], command=self._on_theme_change)
        self.theme_switch.set("Dark")
        self.theme_switch.pack(side="right", padx=8)
        ctk.CTkButton(top_bar, text="⚙︎ Einstellungen", width=140, command=self._open_settings).pack(side="right", padx=8)

        # Titel + Favorit
        title_row = ctk.CTkFrame(self)
        title_row.pack(fill="x")
        self.title_label = ctk.CTkLabel(title_row, text="Kein Titel geladen", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.pack(side="left", pady=(6, 2), padx=10)
        self.fav_btn = ctk.CTkButton(title_row, text="☆", width=42, command=self._toggle_favorite)
        self.fav_btn.pack(side="right", padx=10)

        # Fortschritt + Zeiten
        times = ctk.CTkFrame(self)
        times.pack(fill="x", padx=14)
        self.current_time_label = ctk.CTkLabel(times, text="0:00")
        self.current_time_label.pack(side="left")
        self.total_time_label = ctk.CTkLabel(times, text="0:00")
        self.total_time_label.pack(side="right")
        self.progress_slider = ctk.CTkSlider(self, from_=0, to=100, number_of_steps=1000, command=self._on_seek_drag)
        self.progress_slider.bind("<Button-1>", self._on_seek_start)
        self.progress_slider.bind("<ButtonRelease-1>", self._on_seek_end)
        self.progress_slider.pack(fill="x", padx=14, pady=(2, 8))

        # Ordner/Dateien
        folder_row = ctk.CTkFrame(self)
        folder_row.pack(pady=(0, 6))
        ctk.CTkLabel(folder_row, text="📁").pack(side="left", padx=(6, 4))
        self.preset_folders = [
            str(Path.home() / "Music"),
            str(Path.home() / "Music" / "schubert"),
            str(Path.home() / "Music" / "strauss"),
            str(Path.home() / "Music" / "Classical"),
            str(Path.home() / "Downloads"),
            "/media/usb/music",
        ]
        self.folder_combo = ctk.CTkComboBox(folder_row, values=self.preset_folders, width=360, command=self._on_folder_select)
        self.folder_combo.set(self.music_folder)
        self.folder_combo.pack(side="left")
        ctk.CTkButton(folder_row, text="↻", width=44, command=self._reload_folder).pack(side="left", padx=6)
        ctk.CTkButton(folder_row, text="Ordner wählen…", command=self._choose_folder).pack(side="left", padx=6)
        ctk.CTkButton(folder_row, text="Dateien hinzufügen…", command=self._add_files).pack(side="left", padx=6)

        # Hauptsteuerung
        ctrl = ctk.CTkFrame(self)
        ctrl.pack(pady=6)
        def btn(text, cmd, w=76):
            return ctk.CTkButton(ctrl, text=text, width=w, height=56, command=cmd)
        btn("⏪\n-10s", lambda: self._skip_seconds(-10), w=66).grid(row=0, column=0, padx=4)
        btn("⏮", self._previous_song).grid(row=0, column=1, padx=4)
        self.play_btn = btn("▶\nPLAY", self._toggle_play)
        self.play_btn.grid(row=0, column=2, padx=4)
        btn("⏭", self._next_song).grid(row=0, column=3, padx=4)
        btn("⏩\n+10s", lambda: self._skip_seconds(10), w=66).grid(row=0, column=4, padx=4)
        self.shuffle_btn = ctk.CTkButton(ctrl, text="🔀\nAUS", width=66, height=56, command=self._toggle_shuffle)
        self.shuffle_btn.grid(row=0, column=5, padx=4)
        self.repeat_btn = ctk.CTkButton(ctrl, text="🔁\nAUS", width=66, height=56, command=self._toggle_repeat)
        self.repeat_btn.grid(row=0, column=6, padx=4)
        ctk.CTkButton(ctrl, text="❌\nEXIT", width=66, height=56, fg_color="#c0392b", command=self._quit).grid(row=0, column=7, padx=4)

        # Unterer Bereich: Lautstärke / Playlist / Equalizer
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Lautstärke
        vol = ctk.CTkFrame(bottom)
        vol.pack(side="left", fill="y", padx=6)
        ctk.CTkLabel(vol, text="🔊", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(6, 2))
        vrow = ctk.CTkFrame(vol)
        vrow.pack(pady=6)
        ctk.CTkButton(vrow, text="−", width=40, command=lambda: self._adjust_volume(-10)).pack(side="left", padx=4)
        self.volume_slider = ctk.CTkSlider(vrow, from_=0, to=100, number_of_steps=100, command=self._on_volume)
        self.volume_slider.set(70)
        self.volume_slider.pack(side="left", padx=6, ipadx=50)
        ctk.CTkButton(vrow, text="+", width=40, command=lambda: self._adjust_volume(10)).pack(side="left", padx=4)

        # Playlist (ScrollableFrame)
        playlist_frame = ctk.CTkFrame(bottom)
        playlist_frame.pack(side="left", fill="both", expand=True, padx=6)
        ctk.CTkLabel(playlist_frame, text="📋 Playlist", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(8, 4))
        self.playlist_sf = ctk.CTkScrollableFrame(playlist_frame, height=200)
        self.playlist_sf.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # Equalizer
        eq = ctk.CTkFrame(bottom)
        eq.pack(side="left", fill="y", padx=6)
        ctk.CTkLabel(eq, text="🎛️ Equalizer", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(8, 4))
        # Presets
        preset_row = ctk.CTkFrame(eq)
        preset_row.pack(pady=(0, 6))
        presets = [
            ("Flat", [0]*10),
            ("Rock", [5, 4, -1, -3, -1, 1, 3, 4, 4, 4]),
            ("Pop",  [-1, 2, 4, 4, 3, 0, -1, -1, -1, -1]),
            ("Jazz", [3, 2, 1, 2, -1, -1, 0, 1, 2, 3]),
            ("Clas", [4, 3, 2, 1, -1, -1, -1, 0, 2, 3]),
        ]
        for name, values in presets:
            ctk.CTkButton(preset_row, text=name, width=56, command=lambda v=values: self._apply_eq_preset(v)).pack(side="left", padx=3)
        # 10 Bänder
        self.eq_sliders = []
        eq_labels = ["60", "170", "310", "600", "1k", "3k", "6k", "12k", "14k", "16k"]
        cols = ctk.CTkFrame(eq)
        cols.pack(pady=4)
        for i, lab in enumerate(eq_labels):
            col = ctk.CTkFrame(cols)
            col.grid(row=0, column=i, padx=2)
            ctk.CTkLabel(col, text=lab).pack()
            s = ctk.CTkSlider(col, from_=20, to=-20, orientation="vertical", height=120, number_of_steps=80,
                               command=lambda val, idx=i: self._on_eq_change(idx, val))
            s.set(0)
            s.pack()
            self.eq_sliders.append(s)

        # Shortcuts
        self.bind('<space>', lambda e: self._toggle_play())
        self.bind('<Left>', lambda e: self._previous_song())
        self.bind('<Right>', lambda e: self._next_song())
        self.bind('<Up>', lambda e: self._adjust_volume(5))
        self.bind('<Down>', lambda e: self._adjust_volume(-5))
        self.bind('<plus>', lambda e: self._skip_seconds(10))
        self.bind('<minus>', lambda e: self._skip_seconds(-10))
        self.bind('r', lambda e: self._toggle_repeat())
        self.bind('R', lambda e: self._toggle_repeat())
        self.bind('f', lambda e: self._toggle_fullscreen())
        self.bind('F', lambda e: self._toggle_fullscreen())
        self.bind('v', lambda e: self._cycle_visualizer())
        self.bind('V', lambda e: self._cycle_visualizer())
        self.bind('s', lambda e: self._toggle_shuffle())
        self.bind('S', lambda e: self._toggle_shuffle())
        self.bind('q', lambda e: self._quit())
        self.bind('Q', lambda e: self._quit())
        self.bind('<Escape>', lambda e: self._quit())

    # ---------- Theme ----------
    def _on_theme_change(self, value: str):
        v = value.lower()
        if v == 'light':
            ctk.set_appearance_mode('light')
        elif v == 'dark':
            ctk.set_appearance_mode('dark')
        else:
            ctk.set_appearance_mode('system')

    # ---------- Config ----------
    def _load_config(self) -> dict:
        try:
            if CFG_PATH.exists():
                return json.loads(CFG_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    def _save_config(self):
        try:
            CFG_PATH.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
        except Exception:
            pass

    # ---------- Device Helpers ----------
    def _list_input_devices(self) -> list[str]:
        if not AUDIO_ANALYSIS_AVAILABLE:
            return []
        try:
            devs = sd.query_devices()
            names = []
            for d in devs:
                if d.get('max_input_channels', 0) > 0:
                    names.append(str(d.get('name', '')))
            return names
        except Exception:
            return []

    # ---------- Settings Dialog ----------
    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Einstellungen")
        win.geometry("520x420")
        try:
           win.wait_visibility()
           win.grab_set()
        except Exception:
           pass

        # Auto-Loopback Toggle
        auto_var = ctk.BooleanVar(value=bool(self.config.get("auto_loopback", False)))
        auto_cb = ctk.CTkCheckBox(win, text="Auto-Loopback beim Start aktivieren", variable=auto_var)
        auto_cb.pack(anchor="w", padx=12, pady=(12, 6))

        # Sinks laden
        sinks = []
        if self.loopback or LoopbackManager._cmd_exists("pactl"):
            sinks = (self.loopback.list_sinks() if self.loopback else LoopbackManager().list_sinks()) or []
        sinks_display = sinks if sinks else ["(keine gefunden)"]
        current_target = self.config.get("target_sink") or (self.loopback.target_sink if self.loopback else "") or ""

        ctk.CTkLabel(win, text="Ziel-Audiosenke für Loopback (Wiedergabe)").pack(anchor="w", padx=12, pady=(10, 4))
        sink_combo = ctk.CTkComboBox(win, values=sinks_display, width=420)
        sink_combo.set(current_target if current_target else (sinks_display[0] if sinks_display else ""))
        sink_combo.pack(padx=12, pady=4)

        # Device-Listen (Info) + Analyzer-Input
        info_tabs = ctk.CTkTabview(win, width=480, height=200)
        info_tabs.pack(fill="both", expand=True, padx=12, pady=10)
        tab_sinks = info_tabs.add("Sinks (Ausgabe)")
        tab_inputs = info_tabs.add("Inputs (Analyzer)")

        # Sinks-Textbox
        sinks_text = "\n".join(sinks) if sinks else "(keine)"
        sinks_box = ctk.CTkTextbox(tab_sinks, height=160)
        sinks_box.pack(fill="both", expand=True, pady=6)
        sinks_box.insert("1.0", sinks_text)
        sinks_box.configure(state="disabled")

        # Analyzer-Input-Auswahl
        ctk.CTkLabel(win, text="Analyzer-Input (Gerätename enthält)").pack(anchor="w", padx=12, pady=(4, 2))
        inputs = self._list_input_devices()
        inputs_display = inputs if inputs else ["(sounddevice nicht verfügbar)"]
        current_input = self.config.get("analyzer_input") or (f"{self.loopback.sink_name}.monitor" if self.loopback else "")
        input_combo = ctk.CTkComboBox(win, values=inputs_display, width=420)
        input_combo.set(current_input if current_input else (inputs_display[0] if inputs_display else ""))
        input_combo.pack(padx=12, pady=4)

        # Inputs-Textbox (Info)
        inputs_box = ctk.CTkTextbox(tab_inputs, height=160)
        inputs_box.pack(fill="both", expand=True, pady=6)
        inputs_box.insert("1.0", "\n".join(inputs) if inputs else "(keine / Modul nicht installiert)")
        inputs_box.configure(state="disabled")

        btn_row = ctk.CTkFrame(win)
        btn_row.pack(fill="x", padx=12, pady=12)
        def apply():
            self.config["auto_loopback"] = bool(auto_var.get())
            sel_sink = sink_combo.get()
            if sel_sink and "(keine" not in sel_sink:
                self.config["target_sink"] = sel_sink
            else:
                self.config.pop("target_sink", None)
            sel_input = input_combo.get() if 'input_combo' in locals() else None
            if sel_input and "(sounddevice" not in sel_input:
                self.config["analyzer_input"] = sel_input
            else:
                self.config.pop("analyzer_input", None)
            self._save_config()
            # Live anwenden
            try:
                # Loopback an-/abschalten
                if self.loopback:
                    self.loopback.cleanup()
                if self.config.get("auto_loopback", False):
                    if not self.loopback:
                        self.loopback = LoopbackManager()
                    self.loopback.setup(target_sink=self.config.get("target_sink"))
                else:
                    self.loopback = None
                # Analyzer gemäß Auswahl neu starten (nur wenn Visualizer aktiv)
                if AUDIO_ANALYSIS_AVAILABLE:
                    if self.analyzer:
                        self.analyzer.stop()
                    else:
                        self.analyzer = AudioAnalyzer(auto_loopback=bool(self.loopback))
                    prefer = self.config.get("analyzer_input") or (f"{self.loopback.sink_name}.monitor" if self.loopback else None)
                    if self.current_visualizer != 'none':
                        self.analyzer.start(prefer_device_substr=prefer)
            except Exception:
                pass
            win.destroy()
        ctk.CTkButton(btn_row, text="Übernehmen", command=apply).pack(side="right")
        ctk.CTkButton(btn_row, text="Schließen", command=win.destroy).pack(side="right", padx=8)

    # ---------- Playlist UI ----------
    def _clear_playlist_ui(self):
        for child in self.playlist_sf.winfo_children():
            child.destroy()

    def _populate_playlist_ui(self):
        self._clear_playlist_ui()
        for i, path in enumerate(self.playlist):
            filename = os.path.basename(path)
            is_fav = path in self.favorites
            star = "★ " if is_fav else ""
            prefix = "▶ " if i == self.current_index else "   "
            btn = ctk.CTkButton(self.playlist_sf, text=f"{prefix}{star}{filename}", anchor="w", height=32,
                                 command=lambda idx=i: self._on_playlist_click(idx))
            btn.pack(fill="x", padx=4, pady=2)

    def _on_playlist_click(self, index: int):
        self._load_song(index)
        if self.is_playing:
            self._play()

    # ---------- Favoriten ----------
    def _load_favorites(self) -> set:
        try:
            if FAV_PATH.exists():
                data = json.loads(FAV_PATH.read_text(encoding='utf-8'))
                return set(data if isinstance(data, list) else [])
        except Exception:
            pass
        return set()

    def _save_favorites(self):
        try:
            FAV_PATH.write_text(json.dumps(sorted(self.favorites)), encoding='utf-8')
        except Exception:
            pass

    def _toggle_favorite(self):
        path = self.playlist[self.current_index] if self.playlist else None
        if not path:
            return
        if path in self.favorites:
            self.favorites.remove(path)
        else:
            self.favorites.add(path)
        self._save_favorites()
        self._refresh_fav_ui()

    def _refresh_fav_ui(self):
        # Button-Star
        path = self.playlist[self.current_index] if self.playlist else None
        if path and path in self.favorites:
            self.fav_btn.configure(text="★")
        else:
            self.fav_btn.configure(text="☆")
        # Liste neu beschriften
        self._populate_playlist_ui()

    # ---------- Equalizer ----------
    def _setup_equalizer(self):
        try:
            self.equalizer = vlc.libvlc_audio_equalizer_new()
            if self.equalizer:
                vlc.libvlc_media_player_set_equalizer(self.player, self.equalizer)
        except Exception as e:
            print(f"EQ Init Error: {e}")
            self.equalizer = None

    def _on_eq_change(self, band_index: int, value):
        try:
            if self.equalizer:
                vlc.libvlc_audio_equalizer_set_amp_at_index(self.equalizer, float(value), band_index)
                vlc.libvlc_media_player_set_equalizer(self.player, self.equalizer)
        except Exception as e:
            print(f"EQ Error: {e}")

    def _apply_eq_preset(self, values):
        for i, val in enumerate(values):
            if i < len(self.eq_sliders):
                self.eq_sliders[i].set(val)
                self._on_eq_change(i, val)

    # ---------- Folder / Files ----------
    def _on_folder_select(self, value: str):
        self.music_folder = value
        self._load_folder(self.music_folder)

    def _reload_folder(self):
        self._load_folder(self.music_folder)

    def _choose_folder(self):
        folder = fd.askdirectory(initialdir=self.music_folder)
        if folder:
            self.music_folder = folder
            self.folder_combo.set(folder)
            self._load_folder(folder)

    def _add_files(self):
        files = fd.askopenfilenames(title="Audiodateien hinzufügen",
                                    filetypes=[("Audio", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma")])
        if files:
            # Hänge an Playlist an (duplikate vermeiden)
            add = [f for f in files if f.lower().endswith(AUDIO_EXT) and f not in self.playlist]
            if add:
                self.playlist.extend(add)
                self._populate_playlist_ui()

    def _load_folder(self, folder_path: str):
        if not os.path.exists(folder_path):
            self.title_label.configure(text=f"Ordner nicht gefunden: {folder_path}")
            return
        try:
            files = [os.path.join(folder_path, f) for f in sorted(os.listdir(folder_path)) if f.lower().endswith(AUDIO_EXT)]
            self.playlist = files
            if self.playlist:
                self.current_index = 0
                self._build_shuffled_order()
                self._populate_playlist_ui()
                self._load_song(self.current_index)
                if self.autoplay:
                    self._play()
            else:
                self.title_label.configure(text="Keine Audiodateien gefunden")
                self._clear_playlist_ui()
        except Exception as e:
            self.title_label.configure(text=f"Fehler beim Laden: {e}")

    # ---------- Shuffle ----------
    def _toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        self._update_shuffle_button()
        self._build_shuffled_order(start_from_current=True)

    def _update_shuffle_button(self):
        if self.shuffle_mode:
            self.shuffle_btn.configure(text="🔀\nAN", fg_color="#16a085")
        else:
            self.shuffle_btn.configure(text="🔀\nAUS", fg_color="#7f8c8d")

    def _build_shuffled_order(self, start_from_current: bool = False):
        n = len(self.playlist)
        if n == 0:
            self.shuffled_order = []
            self.shuf_pos = 0
            return
        order = list(range(n))
        if self.shuffle_mode:
            order = random.sample(order, n)
            if start_from_current and self.current_index in order:
                # Stelle sicher, dass aktueller Index an aktueller Position steht
                order.remove(self.current_index)
                order.insert(0, self.current_index)
                self.shuf_pos = 0
        else:
            self.shuf_pos = self.current_index
        self.shuffled_order = order

    def _next_index(self):
        n = len(self.playlist)
        if n == 0:
            return 0
        if self.repeat_mode == 2:  # one
            return self.current_index
        if self.shuffle_mode and self.shuffled_order:
            self.shuf_pos = (self.shuf_pos + 1) % n
            return self.shuffled_order[self.shuf_pos]
        else:
            return (self.current_index + 1) % n

    def _prev_index(self):
        n = len(self.playlist)
        if n == 0:
            return 0
        if self.shuffle_mode and self.shuffled_order:
            self.shuf_pos = (self.shuf_pos - 1) % n
            return self.shuffled_order[self.shuf_pos]
        else:
            return (self.current_index - 1) % n

    # ---------- Player ----------
    def _load_song(self, index: int):
        if 0 <= index < len(self.playlist):
            try:
                path = self.playlist[index]
                media = self.vlc_instance.media_new(path)
                self.player.set_media(media)
                self.current_index = index
                # Schuffle-Pos aktualisieren
                if self.shuffle_mode and self.current_index in self.shuffled_order:
                    self.shuf_pos = self.shuffled_order.index(self.current_index)
                filename = os.path.basename(path)
                self.title_label.configure(text=filename)
                self._populate_playlist_ui()
                self._refresh_fav_ui()
                self.song_length = self._probe_length(path)
                self.total_time_label.configure(text=self._fmt_time(self.song_length))
                self.current_time_label.configure(text="0:00")
                self.progress_slider.set(0)
            except Exception as e:
                self.title_label.configure(text=f"Fehler: {e}")

    def _play(self):
        try:
            self.player.play()
            self.is_playing = True
            self.play_btn.configure(text="⏸\nPAUSE", fg_color="#e67e22")
        except Exception as e:
            self.title_label.configure(text=f"Wiedergabefehler: {e}")

    def _pause(self):
        try:
            self.player.pause()
        except Exception:
            pass
        self.is_playing = False
        self.play_btn.configure(text="▶\nPLAY", fg_color="#27ae60")

    def _toggle_play(self):
        if self.is_playing:
            self._pause()
        else:
            self._play()

    def _next_song(self):
        if not self.playlist:
            return
        nxt = self._next_index()
        self._load_song(nxt)
        self._play()

    def _previous_song(self):
        if not self.playlist:
            return
        prv = self._prev_index()
        self._load_song(prv)
        if self.is_playing:
            self._play()

    def _skip_seconds(self, seconds: int):
        if self.song_length > 0:
            try:
                current = self.player.get_time() / 1000.0
                new_pos = max(0.0, min(current + seconds, self.song_length))
                self.player.set_time(int(new_pos * 1000))
            except Exception:
                pass

    def _on_volume(self, val):
        try:
            self.player.audio_set_volume(int(float(val)))
        except Exception:
            pass

    def _adjust_volume(self, delta: int):
        cur = float(self.volume_slider.get())
        new = max(0, min(100, cur + delta))
        self.volume_slider.set(new)
        self._on_volume(new)

    def _toggle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        self._update_repeat_button()

    def _update_repeat_button(self):
        if self.repeat_mode == 0:
            self.repeat_btn.configure(text="🔁\nAUS", fg_color="#7f8c8d")
        elif self.repeat_mode == 1:
            self.repeat_btn.configure(text="🔁\nALLE", fg_color="#27ae60")
        else:
            self.repeat_btn.configure(text="🔂\nEINS", fg_color="#f39c12")

    def _on_song_end(self, event):
        if self.repeat_mode == 2:  # one
            self.after(100, lambda: self._load_song(self.current_index))
            self.after(200, self._play)
        elif self.repeat_mode == 1:  # all
            self.after(100, self._next_song)
        else:  # off
            if self.current_index < len(self.playlist) - 1:
                self.after(100, self._next_song)
            else:
                self._pause()

    # ---------- Seek ----------
    def _on_seek_start(self, _event):
        self.is_seeking = True

    def _on_seek_end(self, _event):
        if self.song_length > 0:
            position = (self.progress_slider.get() / 100.0) * self.song_length
            try:
                self.player.set_time(int(position * 1000))
            except Exception:
                pass
        self.is_seeking = False

    def _on_seek_drag(self, _val):
        if self.is_seeking and self.song_length > 0:
            cur = (float(self.progress_slider.get()) / 100.0) * self.song_length
            self.current_time_label.configure(text=self._fmt_time(cur))

    # ---------- Loops ----------
    def _update_progress_loop(self):
        if self.is_playing and not self.is_seeking and self.song_length > 0 and not self.update_in_progress:
            self.update_in_progress = True
            try:
                pos_ms = self.player.get_time()
                if pos_ms >= 0:
                    pos = pos_ms / 1000.0
                    if pos <= self.song_length:
                        progress = (pos / self.song_length) * 100.0
                        self.progress_slider.set(progress)
                        self.current_time_label.configure(text=self._fmt_time(pos))
            except Exception:
                pass
            finally:
                self.update_in_progress = False
        self.after(500, self._update_progress_loop)

    def _process_audio_loop(self):
        try:
            if self.analyzer and self.analyzer.is_active:
                pass
        except Exception:
            pass
        self.after(100, self._process_audio_loop)

    def _animation_loop(self):
        try:
            self.viz_canvas.delete("all")
            width = self.viz_canvas.winfo_width() or 800
            height = int(self.viz_canvas.cget("height")) or 56
            if self.current_visualizer == 'none':
                text = "▶ SPIELT" if self.is_playing else "⏸ PAUSE"
                color = "#27ae60" if self.is_playing else "#95a5a6"
                self.viz_canvas.create_text(width // 2, height // 2, text=text, fill=color, font=("Arial", 14, "bold"))
                self.after(500, self._animation_loop)
                return
            if not self.is_playing:
                self.viz_canvas.create_text(width // 2, height // 2, text="⏸ PAUSIERT", fill="#95a5a6", font=("Arial", 12, "bold"))
                self.after(120, self._animation_loop)
                return
            if self.current_visualizer == 'vu_meter':
                self._draw_vu(width, height)
            elif self.current_visualizer == 'spectrum':
                self._draw_spectrum(width, height)
            else:
                self._draw_wave(width, height)
        except Exception:
            pass
        self.after(100, self._animation_loop)

    # ---------- Visualizer ----------
    def _cycle_visualizer(self):
        # zirkulär weiterdrehen
        if self.current_visualizer not in self.visualizer_styles:
            self.current_visualizer = self.visualizer_styles[0]

        idx = (self.visualizer_styles.index(self.current_visualizer) + 1) % len(self.visualizer_styles)
        self.current_visualizer = self.visualizer_styles[idx]

        # Label aktualisieren
        self.viz_label.configure(text=f"📊 {self.current_visualizer.upper()}  |  'V' wechseln")

        # Analyzer-Handling
        if self.current_visualizer == 'none':
            if self.analyzer:
                try:
                    self.analyzer.stop()
                except Exception:
                    pass
                self.analyzer = None
        else:
            if AUDIO_ANALYSIS_AVAILABLE:
                if not self.analyzer:
                    self.analyzer = AudioAnalyzer(auto_loopback=bool(self.loopback))
                if not getattr(self.analyzer, "is_active", False):
                    prefer = self.config.get("analyzer_input") or (
                        f"{self.loopback.sink_name}.monitor" if self.loopback else None
                    )
                    self.analyzer.start(prefer_device_substr=prefer)


    def _draw_vu(self, width: int, height: int):
        if self.analyzer and AUDIO_ANALYSIS_AVAILABLE:
            level_l = min(self.analyzer.current_rms_l * 3.0, 1.0)
            level_r = min(self.analyzer.current_rms_r * 3.0, 1.0)
        else:
            self.animation_tick += 1
            level_l = abs(math.sin(self.animation_tick * 0.08)) * 0.7 + 0.1
            level_r = abs(math.sin(self.animation_tick * 0.10 + 1)) * 0.65 + 0.15
        bar_w = width // 2 - 60
        bar_h = 18
        y0 = (height - bar_h * 2 - 6) // 2
        def draw_bar(x, y, lvl, label):
            self.viz_canvas.create_rectangle(x, y, x + bar_w, y + bar_h, fill='#0a0a0a', outline='#333333')
            fill_w = int(bar_w * lvl)
            color = '#27ae60' if lvl < 0.7 else ('#f39c12' if lvl < 0.85 else '#e74c3c')
            self.viz_canvas.create_rectangle(x + 2, y + 2, x + max(2, fill_w) - 2, y + bar_h - 2, fill=color, outline='')
            self.viz_canvas.create_text(x - 10, y + bar_h // 2, text=label, fill='white', font=('Arial', 10, 'bold'), anchor='e')
        draw_bar(30, y0, level_l, 'L')
        draw_bar(30, y0 + bar_h + 6, level_r, 'R')

    def _draw_spectrum(self, width: int, height: int):
        if self.analyzer and AUDIO_ANALYSIS_AVAILABLE and self.analyzer.spectrum is not None:
            spec = self.analyzer.spectrum
            n = len(spec)
        else:
            n = 16
            self.animation_tick += 1
            spec = [abs(math.sin((i * 0.5 + self.animation_tick * 0.1))) * 0.8 + 0.2 for i in range(n)]
        xpad = 22
        bar_w = (width - xpad * 2) / n
        for i in range(n):
            a = spec[i] if i < len(spec) else 0
            bh = int(height * a * 0.8)
            x = xpad + i * bar_w
            y = height - bh - 6
            color = '#3498db' if a < 0.4 else ('#9b59b6' if a < 0.7 else '#e74c3c')
            self.viz_canvas.create_rectangle(x + 1, y, x + bar_w - 1, height - 6, fill=color, outline='')

    def _draw_wave(self, width: int, height: int):
        # Anzahl horizontaler Punkte (= Pixelspalten)
        num_points = max(50, min(600, int(width)))  # Performance-Schutz
        if self.analyzer and AUDIO_ANALYSIS_AVAILABLE and self.analyzer.is_active:
            # ~120 ms Historie holen -> geringe Latenz, aber genügend Kontur
            want_secs = 0.12
            want_samples = int(self.analyzer.sample_rate * want_secs)
            samples = self.analyzer.get_recent_wave(want_samples)

            if samples.size < 4:
                samples = np.zeros(num_points, dtype=np.float32)

            # DC-Offset entfernen
            samples = samples - np.mean(samples) if samples.size else samples

            # Auf num_points resamplen (lineare Interpolation, schnell & stabil)
            if samples.size != num_points:
                idx = np.linspace(0, max(1, samples.size - 1), num_points, dtype=np.float32)
                i0 = np.floor(idx).astype(int)
                i1 = np.minimum(i0 + 1, samples.size - 1)
                w = idx - i0
                wave = (1.0 - w) * samples[i0] + w * samples[i1]
            else:
                wave = samples

            # Dynamik skalieren (robust gegen Ausreißer)
            peak = np.max(np.abs(wave)) if wave.size else 0.0
            scale = (height * 0.40) / peak if peak > 1e-6 else height * 0.05

            mid = height // 2
            pts = []
            for i in range(num_points):
                x = (width / (num_points - 1)) * i
                y = mid - wave[i] * scale
                pts.extend([x, y])

            if len(pts) >= 4:
                self.viz_canvas.create_line(pts, fill='#1abc9c', width=2, smooth=True)

        else:
            # Fallback: leichte Sinusbewegung
            pts = []
            n = 60
            self.animation_tick += 1
            for i in range(n):
                x = (width / n) * i
                amp = 8
                y = height // 2 + math.sin((i * 0.3) + (self.animation_tick * 0.1)) * amp
                pts.extend([x, y])
            if len(pts) >= 4:
                self.viz_canvas.create_line(pts, fill='#1abc9c', width=2, smooth=True)

    # ---------- Window ----------
    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.attributes('-fullscreen', self.fullscreen)

    def _quit(self):
        try:
            self.player.stop()
            if hasattr(self, 'equalizer') and self.equalizer:
                vlc.libvlc_audio_equalizer_release(self.equalizer)
            if self.analyzer:
                self.analyzer.stop()
        except Exception:
            pass
        # Loopback zurückbauen
        try:
            if self.loopback:
                self.loopback.cleanup()
        except Exception:
            pass
        self.destroy()

    # ---------- Helpers ----------
    @staticmethod
    def _probe_length(path: str) -> float:
        try:
            audio = MutagenFile(path)
            if audio and hasattr(audio.info, 'length'):
                return float(audio.info.length)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"


# =========================
# Main
# =========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Touchscreen Audioplayer (CustomTkinter) mit echter Audio-Analyse (optional)')
    parser.add_argument('--repeat', choices=['off', 'all', 'one'], default='all')
    parser.add_argument('--folder', type=str, default=None)
    parser.add_argument('--volume', type=int, default=70, choices=range(0, 101), metavar='0-100')
    parser.add_argument('--visualizer', choices=['vu_meter', 'spectrum', 'wave', 'none'], default='none',
                        help='Visualisierungs-Style (Standard: none für minimale Last)')
    parser.add_argument('--auto-loopback', action='store_true', help='Erzeugt automatisch Null-Senke + Loopback (pactl) und routet VLC dorthin')
    autoplay = parser.add_mutually_exclusive_group()
    autoplay.add_argument('--autoplay', action='store_true', default=True)
    autoplay.add_argument('--no-autoplay', action='store_false', dest='autoplay')
    args = parser.parse_args()

    app = AudioPlayerApp(args)
    app.mainloop()
