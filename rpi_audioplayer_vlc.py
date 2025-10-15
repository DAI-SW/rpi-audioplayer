#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Touchscreen Audioplayer für Raspberry Pi - VLC Edition
Benötigt: python-vlc für Audio-Wiedergabe
Installation: sudo apt-get install python3-vlc vlc

Startparameter:
    --repeat [off|all|one]  : Repeat-Modus beim Start (Standard: all)
    --folder PATH           : Startordner festlegen
    --volume 0-100          : Start-Lautstärke (Standard: 70)
    --autoplay              : Automatisch ersten Song abspielen
    --no-autoplay           : Nicht automatisch starten

Tastatur-Shortcuts:
    SPACE       : Play/Pause
    LEFT/RIGHT  : Vorheriger/Nächster Song
    UP/DOWN     : Lautstärke +/- 5%
    R           : Repeat-Modus wechseln
    F           : Fullscreen an/aus
    Q/ESC       : Beenden
    +/-         : Schnellspul +/- 10s

Beispiele:
    python3 audioplayer.py --repeat all
    python3 audioplayer.py --repeat one --folder /media/usb/music
    python3 audioplayer.py --volume 50 --no-autoplay
"""

import tkinter as tk
from tkinter import ttk
import vlc
import os
from pathlib import Path
from mutagen import File as MutagenFile
import time
import math
import argparse

class AudioPlayer:
    def __init__(self, root, args=None):
        self.root = root
        self.root.title("Touchscreen Audioplayer - VLC Edition")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#2c3e50')
        
        # VLC Instance und MediaPlayer erstellen
        self.vlc_instance = vlc.Instance('--no-xlib')
        self.player = self.vlc_instance.media_player_new()
        
        # Startparameter verarbeiten
        if args is None:
            args = type('obj', (object,), {
                'repeat': 'all',  # HARDCODED: Standard Repeat-Modus ('off', 'all', 'one')
                'folder': None,
                'volume': 70,
                'autoplay': True
            })
        
        # Variablen
        self.playlist = []
        self.current_index = 0
        self.is_playing = False
        self.volume = args.volume
        self.music_folder = args.folder if args.folder else str(Path.home() / "Musik")
        self.song_length = 0
        self.is_seeking = False
        self.animation_offset = 0
        self.autoplay = args.autoplay
        self.fullscreen = True
        self.update_in_progress = False
        
        # Repeat-Modus aus args setzen
        repeat_modes = {'off': 0, 'all': 1, 'one': 2}
        self.repeat_mode = repeat_modes.get(args.repeat.lower(), 1)  # Standard: 'all'
        
        # Equalizer-Werte (VLC unterstützt 10 Bänder)
        # Frequenzen: 60, 170, 310, 600, 1k, 3k, 6k, 12k, 14k, 16k Hz
        self.eq_bands = [0.0] * 10  # -20.0 bis +20.0 dB
        
        # Vordefinierte Ordner (kannst du anpassen!)
        self.preset_folders = [
            str(Path.home() / "Music"),
            str(Path.home() / "Music" / "Rock"),
            str(Path.home() / "Music" / "Jazz"),
            str(Path.home() / "Music" / "Classical"),
            str(Path.home() / "Downloads"),
            "/media/usb/music"  # USB-Stick Beispiel
        ]
        
        # Event Manager für Song-Ende
        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_song_end)
        
        # GUI erstellen
        self.create_widgets()
        
        # Tastatur-Shortcuts binden
        self.setup_keyboard_shortcuts()
        
        # Lautstärke initial setzen
        self.volume_scale.set(args.volume)
        self.player.audio_set_volume(args.volume)
        
        # Repeat-Button initial richtig setzen
        self.update_repeat_button()
        
        # Equalizer initialisieren
        self.setup_equalizer()
        
        # Ordner laden
        self.load_folder(self.music_folder)
        
        # Loops starten
        self.update_progress()
        self.animate()
        
    def create_widgets(self):
        # Hauptframe
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Animation Canvas über Titel
        self.animation_canvas = tk.Canvas(
            main_frame,
            height=60,
            bg='#2c3e50',
            highlightthickness=0
        )
        self.animation_canvas.pack(fill=tk.X, pady=10)
        
        # Titel-Label
        self.title_label = tk.Label(
            main_frame,
            text="Kein Titel geladen",
            font=('Arial', 22, 'bold'),
            bg='#2c3e50',
            fg='white',
            wraplength=800
        )
        self.title_label.pack(pady=10)
        
        # Fortschrittsanzeige Frame
        progress_frame = tk.Frame(main_frame, bg='#2c3e50')
        progress_frame.pack(pady=10, fill=tk.X)
        
        # Zeit-Labels
        time_frame = tk.Frame(progress_frame, bg='#2c3e50')
        time_frame.pack(fill=tk.X, padx=20)
        
        self.current_time_label = tk.Label(
            time_frame,
            text="0:00",
            font=('Arial', 14),
            bg='#2c3e50',
            fg='white'
        )
        self.current_time_label.pack(side=tk.LEFT)
        
        self.total_time_label = tk.Label(
            time_frame,
            text="0:00",
            font=('Arial', 14),
            bg='#2c3e50',
            fg='white'
        )
        self.total_time_label.pack(side=tk.RIGHT)
        
        # Progress Slider (Cue-Funktion)
        self.progress_var = tk.DoubleVar()
        self.progress_scale = tk.Scale(
            progress_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.progress_var,
            command=self.on_progress_change,
            showvalue=False,
            bg='#34495e',
            fg='white',
            highlightthickness=0,
            troughcolor='#1abc9c',
            length=800,
            sliderlength=30
        )
        self.progress_scale.pack(fill=tk.X, padx=20, pady=5)
        
        # Bind für Seek-Start und -Ende
        self.progress_scale.bind('<Button-1>', self.start_seek)
        self.progress_scale.bind('<ButtonRelease-1>', self.end_seek)
        
        # Ordnerauswahl mit Dropdown
        folder_frame = tk.Frame(main_frame, bg='#2c3e50')
        folder_frame.pack(pady=10)
        
        tk.Label(
            folder_frame,
            text="Ordner:",
            font=('Arial', 14),
            bg='#2c3e50',
            fg='white'
        ).pack(side=tk.LEFT, padx=10)
        
        # Dropdown für vordefinierte Ordner
        self.folder_var = tk.StringVar(value=self.music_folder)
        self.folder_dropdown = ttk.Combobox(
            folder_frame,
            textvariable=self.folder_var,
            values=self.preset_folders,
            font=('Arial', 12),
            width=35,
            state='readonly'
        )
        self.folder_dropdown.pack(side=tk.LEFT, padx=5)
        self.folder_dropdown.bind('<<ComboboxSelected>>', self.on_folder_select)
        
        self.load_folder_btn = tk.Button(
            folder_frame,
            text="↻",
            font=('Arial', 16, 'bold'),
            bg='#3498db',
            fg='white',
            activebackground='#2980b9',
            command=self.load_folder_button,
            height=1,
            width=3
        )
        self.load_folder_btn.pack(side=tk.LEFT, padx=5)
        
        # Hauptsteuerung Frame
        main_control_frame = tk.Frame(main_frame, bg='#2c3e50')
        main_control_frame.pack(pady=15)
        
        # Schnellspul-Buttons (-10s) + Hauptsteuerung + Schnellspul (+10s)
        button_config = {
            'font': ('Arial', 20, 'bold'),
            'bg': '#3498db',
            'fg': 'white',
            'activebackground': '#2980b9',
            'width': 6,
            'height': 3
        }
        
        small_button_config = {
            'font': ('Arial', 16, 'bold'),
            'bg': '#16a085',
            'fg': 'white',
            'activebackground': '#138f75',
            'width': 5,
            'height': 2
        }
        
        # -10s Button
        self.skip_back_btn = tk.Button(
            main_control_frame,
            text="⏪ -10s",
            command=lambda: self.skip_seconds(-10),
            **small_button_config
        )
        self.skip_back_btn.grid(row=0, column=0, padx=5)
        
        # Previous Button
        self.prev_btn = tk.Button(
            main_control_frame,
            text="⏮",
            command=self.previous_song,
            **button_config
        )
        self.prev_btn.grid(row=0, column=1, padx=5)
        
        # Play/Pause Button
        self.play_btn = tk.Button(
            main_control_frame,
            text="▶ PLAY",
            command=self.toggle_play,
            font=('Arial', 22, 'bold'),
            bg='#27ae60',
            fg='white',
            activebackground='#229954',
            width=8,
            height=3
        )
        self.play_btn.grid(row=0, column=2, padx=5)
        
        # Next Button
        self.next_btn = tk.Button(
            main_control_frame,
            text="⏭",
            command=self.next_song,
            **button_config
        )
        self.next_btn.grid(row=0, column=3, padx=5)
        
        # +10s Button
        self.skip_forward_btn = tk.Button(
            main_control_frame,
            text="+10s ⏩",
            command=lambda: self.skip_seconds(10),
            **small_button_config
        )
        self.skip_forward_btn.grid(row=0, column=4, padx=5)
        
        # Repeat Button (in gleicher Reihe rechts)
        self.repeat_btn = tk.Button(
            main_control_frame,
            text="🔁 AUS",
            command=self.toggle_repeat,
            font=('Arial', 14, 'bold'),
            bg='#95a5a6',
            fg='white',
            activebackground='#7f8c8d',
            width=8,
            height=3
        )
        self.repeat_btn.grid(row=0, column=5, padx=5)
        
        # Exit Button (in gleicher Reihe ganz rechts)
        exit_main_btn = tk.Button(
            main_control_frame,
            text="❌\nEXIT",
            command=self.quit_app,
            font=('Arial', 14, 'bold'),
            bg='#e74c3c',
            fg='white',
            activebackground='#c0392b',
            width=6,
            height=3
        )
        exit_main_btn.grid(row=0, column=6, padx=5)
        
        # Volume + EQ Frame (horizontal nebeneinander)
        controls_frame = tk.Frame(main_frame, bg='#2c3e50')
        controls_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # Linke Seite: Lautstärke
        volume_frame = tk.Frame(controls_frame, bg='#2c3e50')
        volume_frame.pack(side=tk.LEFT, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(
            volume_frame,
            text="🔊 Lautstärke",
            font=('Arial', 14, 'bold'),
            bg='#2c3e50',
            fg='white'
        ).pack()
        
        vol_controls = tk.Frame(volume_frame, bg='#2c3e50')
        vol_controls.pack(pady=10)
        
        # Volume - Button (links)
        self.vol_down_btn = tk.Button(
            vol_controls,
            text="−",
            command=lambda: self.adjust_volume(-10),
            font=('Arial', 20, 'bold'),
            bg='#e67e22',
            fg='white',
            activebackground='#d35400',
            width=3,
            height=2
        )
        self.vol_down_btn.pack(side=tk.LEFT, padx=5)
        
        self.volume_scale = tk.Scale(
            vol_controls,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=200,
            command=self.change_volume,
            bg='#34495e',
            fg='white',
            highlightthickness=0,
            troughcolor='#2c3e50',
            font=('Arial', 11)
        )
        self.volume_scale.set(70)
        self.volume_scale.pack(side=tk.LEFT, padx=10)
        
        # Volume + Button (rechts)
        self.vol_up_btn = tk.Button(
            vol_controls,
            text="+",
            command=lambda: self.adjust_volume(10),
            font=('Arial', 20, 'bold'),
            bg='#e67e22',
            fg='white',
            activebackground='#d35400',
            width=3,
            height=2
        )
        self.vol_up_btn.pack(side=tk.LEFT, padx=5)
        
        # Rechte Seite: Equalizer
        eq_frame = tk.Frame(controls_frame, bg='#2c3e50')
        eq_frame.pack(side=tk.LEFT, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(
            eq_frame,
            text="🎛️ 10-Band Equalizer",
            font=('Arial', 12, 'bold'),
            bg='#2c3e50',
            fg='white'
        ).pack()
        
        # EQ Preset Buttons
        preset_frame = tk.Frame(eq_frame, bg='#2c3e50')
        preset_frame.pack(pady=5)
        
        presets = [
            ("Flat", [0]*10),
            ("Rock", [5, 4, -1, -3, -1, 1, 3, 4, 4, 4]),
            ("Pop", [-1, 2, 4, 4, 3, 0, -1, -1, -1, -1]),
            ("Jazz", [3, 2, 1, 2, -1, -1, 0, 1, 2, 3]),
            ("Classical", [4, 3, 2, 1, -1, -1, -1, 0, 2, 3])
        ]
        
        for name, values in presets:
            btn = tk.Button(
                preset_frame,
                text=name,
                command=lambda v=values: self.apply_eq_preset(v),
                font=('Arial', 9),
                bg='#34495e',
                fg='white',
                width=7,
                height=1
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # 10 EQ Slider (kompakt)
        eq_sliders = tk.Frame(eq_frame, bg='#2c3e50')
        eq_sliders.pack(pady=5)
        
        self.eq_sliders = []
        eq_labels = ["60", "170", "310", "600", "1k", "3k", "6k", "12k", "14k", "16k"]
        
        for i, label in enumerate(eq_labels):
            col_frame = tk.Frame(eq_sliders, bg='#2c3e50')
            col_frame.grid(row=0, column=i, padx=2)
            
            tk.Label(
                col_frame,
                text=label,
                font=('Arial', 8),
                bg='#2c3e50',
                fg='white'
            ).pack()
            
            slider = tk.Scale(
                col_frame,
                from_=20,
                to=-20,
                orient=tk.VERTICAL,
                length=120,
                command=lambda val, idx=i: self.change_eq_band(idx, val),
                bg='#34495e',
                fg='white',
                highlightthickness=0,
                troughcolor='#2c3e50',
                showvalue=False,
                width=10
            )
            slider.set(0)
            slider.pack()
            self.eq_sliders.append(slider)
        
        # Playlist Anzeige (unten, kompakter)
        playlist_frame = tk.Frame(main_frame, bg='#2c3e50')
        playlist_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        tk.Label(
            playlist_frame,
            text="Playlist:",
            font=('Arial', 12, 'bold'),
            bg='#2c3e50',
            fg='white'
        ).pack(anchor=tk.W)
        
        # Scrollbare Listbox
        scrollbar = tk.Scrollbar(playlist_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.playlist_box = tk.Listbox(
            playlist_frame,
            font=('Arial', 10),
            bg='#34495e',
            fg='white',
            selectbackground='#3498db',
            yscrollcommand=scrollbar.set,
            height=3
        )
        self.playlist_box.pack(fill=tk.BOTH, expand=True)
        self.playlist_box.bind('<<ListboxSelect>>', self.on_playlist_select)
        scrollbar.config(command=self.playlist_box.yview)
    
    def setup_keyboard_shortcuts(self):
        """Richtet Tastatur-Shortcuts ein"""
        self.root.bind('<space>', lambda e: self.toggle_play())
        self.root.bind('<Left>', lambda e: self.previous_song())
        self.root.bind('<Right>', lambda e: self.next_song())
        self.root.bind('<Up>', lambda e: self.adjust_volume(5))
        self.root.bind('<Down>', lambda e: self.adjust_volume(-5))
        self.root.bind('<plus>', lambda e: self.skip_seconds(10))
        self.root.bind('<minus>', lambda e: self.skip_seconds(-10))
        self.root.bind('r', lambda e: self.toggle_repeat())
        self.root.bind('R', lambda e: self.toggle_repeat())
        self.root.bind('f', lambda e: self.toggle_fullscreen())
        self.root.bind('F', lambda e: self.toggle_fullscreen())
        self.root.bind('q', lambda e: self.quit_app())
        self.root.bind('Q', lambda e: self.quit_app())
        self.root.bind('<Escape>', lambda e: self.quit_app())
    
    def setup_equalizer(self):
        """Initialisiert den VLC Equalizer"""
        try:
            # VLC Equalizer erstellen
            self.equalizer = vlc.libvlc_audio_equalizer_new()
            if self.equalizer:
                # An Player binden
                vlc.libvlc_media_player_set_equalizer(self.player, self.equalizer)
        except Exception as e:
            print(f"Equalizer-Init Fehler: {e}")
    
    def change_eq_band(self, band_index, value):
        """Ändert eine Equalizer-Band"""
        try:
            if self.equalizer:
                # Wert von -20 bis +20 dB
                vlc.libvlc_audio_equalizer_set_amp_at_index(
                    self.equalizer, 
                    float(value), 
                    band_index
                )
                # Equalizer neu setzen um Änderungen anzuwenden
                vlc.libvlc_media_player_set_equalizer(self.player, self.equalizer)
                self.eq_bands[band_index] = float(value)
        except Exception as e:
            print(f"EQ-Band Fehler: {e}")
    
    def apply_eq_preset(self, values):
        """Wendet ein EQ-Preset an"""
        for i, val in enumerate(values):
            self.eq_sliders[i].set(val)
            self.change_eq_band(i, val)
    
    def toggle_fullscreen(self):
        """Wechselt zwischen Fullscreen und Fenster-Modus"""
        self.fullscreen = not self.fullscreen
        self.root.attributes('-fullscreen', self.fullscreen)
    
    def skip_seconds(self, seconds):
        """Springt X Sekunden vor oder zurück"""
        if self.song_length > 0:
            current = self.player.get_time() / 1000.0  # ms zu sekunden
            new_pos = max(0, min(current + seconds, self.song_length))
            self.player.set_time(int(new_pos * 1000))  # sekunden zu ms
    
    def adjust_volume(self, change):
        """Ändert Lautstärke um +/- change"""
        current = self.volume_scale.get()
        new_volume = max(0, min(100, current + change))
        self.volume_scale.set(new_volume)
    
    def on_folder_select(self, event):
        """Lädt Ordner aus Dropdown"""
        folder = self.folder_var.get()
        self.music_folder = folder
        self.load_folder(folder)
    
    def animate(self):
        """Animiert Wellenlinien beim Abspielen"""
        self.animation_canvas.delete("all")
        
        if self.is_playing:
            width = self.animation_canvas.winfo_width()
            if width <= 1:
                width = 800  # Fallback
            
            height = 60
            center_y = height // 2
            
            # Mehrere Wellenlinien zeichnen
            num_bars = 40
            bar_width = width / num_bars
            
            for i in range(num_bars):
                # Wellenförmige Animation
                wave = math.sin((i * 0.3) + (self.animation_offset * 0.1)) * 0.5 + 0.5
                bar_height = 5 + wave * 25
                
                x = i * bar_width + bar_width / 2
                
                # Farbverlauf von grün zu blau
                color_value = int(wave * 100 + 155)
                color = f'#{color_value:02x}{180:02x}{200:02x}'
                
                # Balken zeichnen
                self.animation_canvas.create_rectangle(
                    x - bar_width / 3,
                    center_y - bar_height / 2,
                    x + bar_width / 3,
                    center_y + bar_height / 2,
                    fill=color,
                    outline=''
                )
            
            self.animation_offset += 1
        else:
            # Statische Linie wenn pausiert
            width = self.animation_canvas.winfo_width()
            if width <= 1:
                width = 800
            self.animation_canvas.create_line(
                50, 30, width - 50, 30,
                fill='#95a5a6',
                width=3
            )
        
        # Animation wiederholen
        self.root.after(50, self.animate)
    
    def toggle_repeat(self):
        """Wechselt zwischen Repeat-Modi"""
        self.repeat_mode = (self.repeat_mode + 1) % 3
        self.update_repeat_button()
    
    def update_repeat_button(self):
        """Aktualisiert den Repeat-Button basierend auf repeat_mode"""
        if self.repeat_mode == 0:
            self.repeat_btn.config(text="🔁 AUS", bg='#95a5a6')
        elif self.repeat_mode == 1:
            self.repeat_btn.config(text="🔁 ALLE", bg='#27ae60')
        else:  # 2
            self.repeat_btn.config(text="🔂 EINS", bg='#f39c12')
    
    def get_song_length(self, filepath):
        """Ermittelt die Länge des Songs in Sekunden"""
        try:
            audio = MutagenFile(filepath)
            if audio and hasattr(audio.info, 'length'):
                return audio.info.length
        except:
            pass
        return 0
    
    def format_time(self, seconds):
        """Formatiert Sekunden zu MM:SS"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
    
    def start_seek(self, event):
        """Startet das Seeking"""
        self.is_seeking = True
    
    def end_seek(self, event):
        """Beendet das Seeking und springt zur Position"""
        self.is_seeking = False
        if self.song_length > 0:
            position = (self.progress_var.get() / 100) * self.song_length
            self.player.set_time(int(position * 1000))  # sekunden zu ms
    
    def on_progress_change(self, val):
        """Wird aufgerufen wenn der Progress-Slider bewegt wird"""
        if self.is_seeking and self.song_length > 0:
            current = (float(val) / 100) * self.song_length
            self.current_time_label.config(text=self.format_time(current))
    
    def update_progress(self):
        """Aktualisiert die Fortschrittsanzeige"""
        if self.is_playing and not self.is_seeking and self.song_length > 0 and not self.update_in_progress:
            self.update_in_progress = True
            try:
                # VLC gibt Zeit in Millisekunden
                pos_ms = self.player.get_time()
                if pos_ms >= 0:
                    pos = pos_ms / 1000.0
                    if pos <= self.song_length:
                        progress = (pos / self.song_length) * 100
                        self.progress_var.set(progress)
                        self.current_time_label.config(text=self.format_time(pos))
            except:
                pass
            finally:
                self.update_in_progress = False
        
        self.root.after(500, self.update_progress)
    
    def load_folder(self, folder_path):
        """Lädt alle Audio-Dateien aus dem Ordner"""
        if not os.path.exists(folder_path):
            self.title_label.config(text=f"Ordner nicht gefunden: {folder_path}")
            return
        
        self.playlist = []
        audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma')
        
        try:
            for file in sorted(os.listdir(folder_path)):
                if file.lower().endswith(audio_extensions):
                    self.playlist.append(os.path.join(folder_path, file))
            
            if self.playlist:
                self.current_index = 0
                self.update_playlist_display()
                self.load_song(self.current_index)
                # Autoplay starten (falls aktiviert)
                if self.autoplay:
                    self.play_song()
            else:
                self.title_label.config(text="Keine Audiodateien gefunden")
        except Exception as e:
            self.title_label.config(text=f"Fehler beim Laden: {str(e)}")
    
    def load_folder_button(self):
        """Lädt Ordner über Button"""
        folder = self.folder_var.get()
        self.music_folder = folder
        self.load_folder(folder)
    
    def update_playlist_display(self):
        """Aktualisiert die Playlist-Anzeige"""
        self.playlist_box.delete(0, tk.END)
        for i, song in enumerate(self.playlist):
            filename = os.path.basename(song)
            prefix = "▶ " if i == self.current_index else "   "
            self.playlist_box.insert(tk.END, f"{prefix}{filename}")
        
        if self.playlist:
            self.playlist_box.selection_clear(0, tk.END)
            self.playlist_box.selection_set(self.current_index)
            self.playlist_box.see(self.current_index)
    
    def load_song(self, index):
        """Lädt einen Song"""
        if 0 <= index < len(self.playlist):
            try:
                filepath = self.playlist[index]
                
                # VLC Media erstellen und laden
                media = self.vlc_instance.media_new(filepath)
                self.player.set_media(media)
                
                filename = os.path.basename(filepath)
                self.title_label.config(text=filename)
                self.current_index = index
                self.update_playlist_display()
                
                # Song-Länge ermitteln
                self.song_length = self.get_song_length(filepath)
                self.total_time_label.config(text=self.format_time(self.song_length))
                self.current_time_label.config(text="0:00")
                self.progress_var.set(0)
                
            except Exception as e:
                self.title_label.config(text=f"Fehler: {str(e)}")
    
    def play_song(self):
        """Startet die Wiedergabe"""
        try:
            self.player.play()
            self.is_playing = True
            self.play_btn.config(text="⏸ PAUSE", bg='#e67e22')
        except Exception as e:
            self.title_label.config(text=f"Wiedergabefehler: {str(e)}")
    
    def pause_song(self):
        """Pausiert die Wiedergabe"""
        self.player.pause()
        self.is_playing = False
        self.play_btn.config(text="▶ PLAY", bg='#27ae60')
    
    def toggle_play(self):
        """Wechselt zwischen Play und Pause"""
        if self.is_playing:
            self.pause_song()
        else:
            if self.player.get_state() == vlc.State.Paused:
                self.player.play()
                self.is_playing = True
                self.play_btn.config(text="⏸ PAUSE", bg='#e67e22')
            else:
                self.play_song()
    
    def next_song(self):
        """Nächster Song"""
        if self.playlist:
            if self.repeat_mode == 2:  # Repeat One
                # Gleichen Song neu starten
                self.load_song(self.current_index)
            else:
                self.current_index = (self.current_index + 1) % len(self.playlist)
                self.load_song(self.current_index)
            
            if self.is_playing or True:  # Autoplay
                self.play_song()
    
    def previous_song(self):
        """Vorheriger Song"""
        if self.playlist:
            self.current_index = (self.current_index - 1) % len(self.playlist)
            self.load_song(self.current_index)
            if self.is_playing:
                self.play_song()
    
    def change_volume(self, val):
        """Ändert die Lautstärke"""
        self.volume = int(val)
        self.player.audio_set_volume(self.volume)
    
    def on_playlist_select(self, event):
        """Song aus Playlist auswählen"""
        selection = self.playlist_box.curselection()
        if selection:
            index = selection[0]
            self.load_song(index)
            if self.is_playing:
                self.play_song()
    
    def on_song_end(self, event):
        """Wird aufgerufen wenn ein Song zu Ende ist"""
        if self.repeat_mode == 2:  # Repeat One
            self.root.after(100, lambda: self.load_song(self.current_index))
            self.root.after(200, self.play_song)
        elif self.repeat_mode == 1:  # Repeat All
            self.root.after(100, self.next_song)
        elif self.repeat_mode == 0:  # Kein Repeat
            # Nur weiterspielen wenn nicht letzter Song
            if self.current_index < len(self.playlist) - 1:
                self.root.after(100, self.next_song)
            else:
                self.is_playing = False
                self.play_btn.config(text="▶ PLAY", bg='#27ae60')
    
    def quit_app(self):
        """Beendet die Anwendung sauber"""
        try:
            self.player.stop()
            if hasattr(self, 'equalizer') and self.equalizer:
                vlc.libvlc_audio_equalizer_release(self.equalizer)
        except:
            pass
        self.root.quit()


if __name__ == "__main__":
    # Kommandozeilen-Argumente parsen
    parser = argparse.ArgumentParser(
        description='Touchscreen Audioplayer für Raspberry Pi - VLC Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s --repeat all
  %(prog)s --repeat one --folder /media/usb/music
  %(prog)s --volume 50 --no-autoplay
        """
    )
    
    parser.add_argument(
        '--repeat',
        choices=['off', 'all', 'one'],
        default='all',  # HARDCODED: Standard ist 'all'
        help='Repeat-Modus beim Start (Standard: all)'
    )
    
    parser.add_argument(
        '--folder',
        type=str,
        default=None,
        help='Musik-Ordner beim Start'
    )
    
    parser.add_argument(
        '--volume',
        type=int,
        default=70,
        choices=range(0, 101),
        metavar='0-100',
        help='Start-Lautstärke 0-100 (Standard: 70)'
    )
    
    autoplay_group = parser.add_mutually_exclusive_group()
    autoplay_group.add_argument(
        '--autoplay',
        action='store_true',
        default=True,
        help='Automatisch ersten Song abspielen (Standard)'
    )
    autoplay_group.add_argument(
        '--no-autoplay',
        action='store_false',
        dest='autoplay',
        help='Nicht automatisch starten'
    )
    
    args = parser.parse_args()
    
    root = tk.Tk()
    app = AudioPlayer(root, args)
    root.mainloop()
