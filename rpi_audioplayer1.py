#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Touchscreen Audioplayer für Raspberry Pi mit erweiterten Features
Benötigt: pygame für Audio-Wiedergabe
Installation: sudo apt-get install python3-pygame python3-mutagen

Startparameter:
    --repeat [off|all|one]  : Repeat-Modus beim Start (Standard: all)
    --folder PATH           : Startordner festlegen
    --volume 0-100          : Start-Lautstärke (Standard: 70)
    --autoplay              : Automatisch ersten Song abspielen
    --no-autoplay           : Nicht automatisch starten
    --crossfade SECONDS     : Crossfade-Dauer in Sekunden (Standard: 3)

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
    python3 audioplayer.py --repeat one --folder /media/usb/music --crossfade 5
    python3 audioplayer.py --volume 50 --no-autoplay
"""

import tkinter as tk
from tkinter import ttk
import pygame
import os
from pathlib import Path
from mutagen import File as MutagenFile
import time
import math
import argparse
import threading

class AudioPlayer:
    def __init__(self, root, args=None):
        self.root = root
        self.root.title("Touchscreen Audioplayer")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#2c3e50')
        
        # Pygame Mixer initialisieren
        pygame.mixer.init()
        
        # Startparameter verarbeiten
        if args is None:
            args = type('obj', (object,), {
                'repeat': 'all',  # HARDCODED: Standard Repeat-Modus ('off', 'all', 'one')
                'folder': None,
                'volume': 70,
                'autoplay': True,
                'crossfade': 3  # Crossfade-Dauer in Sekunden
            })
        
        # Variablen
        self.playlist = []
        self.current_index = 0
        self.is_playing = False
        self.volume = args.volume / 100.0
        self.music_folder = args.folder if args.folder else str(Path.home() / "Music")
        self.song_length = 0
        self.is_seeking = False
        self.animation_offset = 0
        self.start_time = 0
        self.start_position = 0
        self.autoplay = args.autoplay
        self.crossfade_duration = args.crossfade
        self.is_fading = False
        self.fullscreen = True
        
        # Equalizer-Werte (0-100, 50 = neutral)
        self.eq_bass = 50
        self.eq_mid = 50
        self.eq_treble = 50
        
        # Repeat-Modus aus args setzen
        repeat_modes = {'off': 0, 'all': 1, 'one': 2}
        self.repeat_mode = repeat_modes.get(args.repeat.lower(), 1)  # Standard: 'all'
        
        # Vordefinierte Ordner (kannst du anpassen!)
        self.preset_folders = [
            str(Path.home() / "Music"),
            str(Path.home() / "Music" / "Rock"),
            str(Path.home() / "Music" / "Jazz"),
            str(Path.home() / "Music" / "Classical"),
            str(Path.home() / "Downloads"),
            "/media/usb/music"  # USB-Stick Beispiel
        ]
        
        # GUI erstellen
        self.create_widgets()
        
        # Tastatur-Shortcuts binden
        self.setup_keyboard_shortcuts()
        
        # Lautstärke initial setzen
        self.volume_scale.set(args.volume)
        
        # Repeat-Button initial richtig setzen
        self.update_repeat_button()
        
        # Ordner laden
        self.load_folder(self.music_folder)
        
        # Loops starten
        self.check_music_end()
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
        
        # Repeat Button (darunter zentriert)
        self.repeat_btn = tk.Button(
            main_control_frame,
            text="🔁 AUS",
            command=self.toggle_repeat,
            font=('Arial', 14, 'bold'),
            bg='#95a5a6',
            fg='white',
            activebackground='#7f8c8d',
            width=12,
            height=2
        )
        self.repeat_btn.grid(row=1, column=1, columnspan=3, pady=10)
        
        # Lautstärke Frame mit +/- Buttons
        volume_frame = tk.Frame(main_frame, bg='#2c3e50')
        volume_frame.pack(pady=10)
        
        tk.Label(
            volume_frame,
            text="🔊",
            font=('Arial', 20),
            bg='#2c3e50',
            fg='white'
        ).pack(side=tk.LEFT, padx=5)
        
        # Volume - Button
        self.vol_down_btn = tk.Button(
            volume_frame,
            text="−",
            command=lambda: self.adjust_volume(-10),
            font=('Arial', 20, 'bold'),
            bg='#e67e22',
            fg='white',
            activebackground='#d35400',
            width=3,
            height=1
        )
        self.vol_down_btn.pack(side=tk.LEFT, padx=5)
        
        self.volume_scale = tk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.change_volume,
            bg='#34495e',
            fg='white',
            highlightthickness=0,
            troughcolor='#2c3e50',
            font=('Arial', 11)
        )
        self.volume_scale.set(70)
        self.volume_scale.pack(side=tk.LEFT, padx=5)
        
        # Volume + Button
        self.vol_up_btn = tk.Button(
            volume_frame,
            text="+",
            command=lambda: self.adjust_volume(10),
            font=('Arial', 20, 'bold'),
            bg='#e67e22',
            fg='white',
            activebackground='#d35400',
            width=3,
            height=1
        )
        self.vol_up_btn.pack(side=tk.LEFT, padx=5)
        
        # Playlist Anzeige
        playlist_frame = tk.Frame(main_frame, bg='#2c3e50')
        playlist_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        tk.Label(
            playlist_frame,
            text="Playlist:",
            font=('Arial', 14, 'bold'),
            bg='#2c3e50',
            fg='white'
        ).pack(anchor=tk.W)
        
        # Scrollbare Listbox
        scrollbar = tk.Scrollbar(playlist_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.playlist_box = tk.Listbox(
            playlist_frame,
            font=('Arial', 11),
            bg='#34495e',
            fg='white',
            selectbackground='#3498db',
            yscrollcommand=scrollbar.set,
            height=4
        )
        self.playlist_box.pack(fill=tk.BOTH, expand=True)
        self.playlist_box.bind('<<ListboxSelect>>', self.on_playlist_select)
        scrollbar.config(command=self.playlist_box.yview)
        
        # Equalizer Frame (Hinweis: Pygame unterstützt keinen echten EQ)
        eq_frame = tk.Frame(main_frame, bg='#2c3e50')
        eq_frame.pack(pady=10, fill=tk.X)
        
        # Crossfade Anzeige
        crossfade_info = tk.Label(
            eq_frame,
            text=f"🎚️ Crossfade: {self.crossfade_duration}s",
            font=('Arial', 11),
            bg='#2c3e50',
            fg='#95a5a6'
        )
        crossfade_info.pack()
        
        # Info-Label für Equalizer
        eq_info = tk.Label(
            eq_frame,
            text="⚠️ EQ: Nur Visualisierung (Pygame-Limitierung)",
            font=('Arial', 9),
            bg='#2c3e50',
            fg='#7f8c8d'
        )
        eq_info.pack()
        
        # Equalizer Sliders
        eq_sliders = tk.Frame(eq_frame, bg='#2c3e50')
        eq_sliders.pack(pady=5)
        
        for i, (label, var_name) in enumerate([("Bass", "eq_bass"), ("Mid", "eq_mid"), ("Treble", "eq_treble")]):
            col_frame = tk.Frame(eq_sliders, bg='#2c3e50')
            col_frame.grid(row=0, column=i, padx=15)
            
            tk.Label(
                col_frame,
                text=label,
                font=('Arial', 10),
                bg='#2c3e50',
                fg='white'
            ).pack()
            
            slider = tk.Scale(
                col_frame,
                from_=0,
                to=100,
                orient=tk.VERTICAL,
                length=100,
                bg='#34495e',
                fg='white',
                highlightthickness=0,
                troughcolor='#2c3e50',
                showvalue=False,
                width=15
            )
            slider.set(50)
            slider.pack()
            setattr(self, f"{var_name}_slider", slider)
        
        # Exit Button
        exit_btn = tk.Button(
            main_frame,
            text="BEENDEN",
            command=self.root.quit,
            font=('Arial', 12, 'bold'),
            bg='#e74c3c',
            fg='white',
            activebackground='#c0392b',
            width=12,
            height=1
        )
        exit_btn.pack(pady=8)
    
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
        self.root.bind('q', lambda e: self.root.quit())
        self.root.bind('Q', lambda e: self.root.quit())
        self.root.bind('<Escape>', lambda e: self.root.quit())
    
    def toggle_fullscreen(self):
        """Wechselt zwischen Fullscreen und Fenster-Modus"""
        self.fullscreen = not self.fullscreen
        self.root.attributes('-fullscreen', self.fullscreen)
    
    def crossfade_to_next(self):
        """Crossfade zum nächsten Song (Fade-Out + Fade-In)"""
        if self.is_fading or not self.is_playing:
            return
        
        self.is_fading = True
        
        def fade():
            # Fade-Out
            steps = 20
            fade_step = self.crossfade_duration / steps
            
            for i in range(steps, 0, -1):
                if not self.is_fading:
                    return
                vol = self.volume * (i / steps)
                pygame.mixer.music.set_volume(vol)
                time.sleep(fade_step)
            
            # Nächsten Song laden
            if self.repeat_mode == 2:
                self.load_song(self.current_index)
            else:
                self.current_index = (self.current_index + 1) % len(self.playlist)
                self.load_song(self.current_index)
            
            # Song starten und Fade-In
            pygame.mixer.music.play()
            
            for i in range(1, steps + 1):
                if not self.is_fading:
                    return
                vol = self.volume * (i / steps)
                pygame.mixer.music.set_volume(vol)
                time.sleep(fade_step)
            
            # Finale Lautstärke setzen
            pygame.mixer.music.set_volume(self.volume)
            self.is_fading = False
        
        # Fade in separatem Thread ausführen
        fade_thread = threading.Thread(target=fade, daemon=True)
        fade_thread.start()
    
    def skip_seconds(self, seconds):
        """Springt X Sekunden vor oder zurück"""
        if self.song_length > 0:
            # Berechne neue Position
            elapsed = time.time() - self.start_time
            current_pos = self.start_position + elapsed
            new_pos = max(0, min(current_pos + seconds, self.song_length))
            
            # Springe zur neuen Position
            try:
                pygame.mixer.music.play(start=new_pos)
                self.start_time = time.time()
                self.start_position = new_pos
                
                # Aktualisiere UI
                progress = (new_pos / self.song_length) * 100
                self.progress_var.set(progress)
                self.current_time_label.config(text=self.format_time(new_pos))
                
                if not self.is_playing:
                    pygame.mixer.music.pause()
            except Exception as e:
                print(f"Skip-Fehler: {e}")
    
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
            try:
                pygame.mixer.music.play(start=position)
                # Zeit-Tracking nach Seek aktualisieren
                self.start_time = time.time()
                self.start_position = position
                if not self.is_playing:
                    pygame.mixer.music.pause()
            except:
                pass
    
    def on_progress_change(self, val):
        """Wird aufgerufen wenn der Progress-Slider bewegt wird"""
        if self.is_seeking and self.song_length > 0:
            current = (float(val) / 100) * self.song_length
            self.current_time_label.config(text=self.format_time(current))
    
    def update_progress(self):
        """Aktualisiert die Fortschrittsanzeige"""
        if self.is_playing and not self.is_seeking and self.song_length > 0:
            try:
                # Berechne Position basierend auf verstrichener Zeit seit Start
                elapsed = time.time() - self.start_time
                pos = self.start_position + elapsed
                
                if pos >= 0 and pos <= self.song_length:
                    progress = (pos / self.song_length) * 100
                    self.progress_var.set(progress)
                    self.current_time_label.config(text=self.format_time(pos))
            except:
                pass
        
        self.root.after(500, self.update_progress)
    
    def load_folder(self, folder_path):
        """Lädt alle Audio-Dateien aus dem Ordner"""
        if not os.path.exists(folder_path):
            self.title_label.config(text=f"Ordner nicht gefunden: {folder_path}")
            return
        
        self.playlist = []
        audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
        
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
                pygame.mixer.music.load(filepath)
                filename = os.path.basename(filepath)
                self.title_label.config(text=filename)
                self.current_index = index
                self.update_playlist_display()
                
                # Song-Länge ermitteln
                self.song_length = self.get_song_length(filepath)
                self.total_time_label.config(text=self.format_time(self.song_length))
                self.current_time_label.config(text="0:00")
                self.progress_var.set(0)
                
                # Position zurücksetzen
                self.start_position = 0
                self.start_time = time.time()
                
            except Exception as e:
                self.title_label.config(text=f"Fehler: {str(e)}")
    
    def play_song(self):
        """Startet die Wiedergabe"""
        try:
            pygame.mixer.music.play()
            self.is_playing = True
            self.play_btn.config(text="⏸ PAUSE", bg='#e67e22')
            self.start_time = time.time()
            self.start_position = 0
        except Exception as e:
            self.title_label.config(text=f"Wiedergabefehler: {str(e)}")
    
    def pause_song(self):
        """Pausiert die Wiedergabe"""
        pygame.mixer.music.pause()
        self.is_playing = False
        self.play_btn.config(text="▶ PLAY", bg='#27ae60')
        # Position beim Pausieren speichern
        if hasattr(self, 'start_time'):
            elapsed = time.time() - self.start_time
            self.start_position = self.start_position + elapsed
    
    def toggle_play(self):
        """Wechselt zwischen Play und Pause"""
        if self.is_playing:
            self.pause_song()
        else:
            # Wenn pausiert, von aktueller Position weiterspielen
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
                self.is_playing = True
                self.play_btn.config(text="⏸ PAUSE", bg='#e67e22')
                # Zeit beim Unpause neu setzen
                self.start_time = time.time()
            else:
                # Song von gespeicherter Position starten
                if hasattr(self, 'start_position') and self.start_position > 0:
                    try:
                        pygame.mixer.music.play(start=self.start_position)
                        self.is_playing = True
                        self.play_btn.config(text="⏸ PAUSE", bg='#e67e22')
                        self.start_time = time.time()
                    except:
                        self.play_song()
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
        self.volume = float(val) / 100
        pygame.mixer.music.set_volume(self.volume)
    
    def on_playlist_select(self, event):
        """Song aus Playlist auswählen"""
        selection = self.playlist_box.curselection()
        if selection:
            index = selection[0]
            self.load_song(index)
            if self.is_playing:
                self.play_song()
    
    def check_music_end(self):
        """Prüft ob Song zu Ende ist"""
        if not pygame.mixer.music.get_busy() and self.is_playing and not self.is_fading:
            if self.repeat_mode == 2:  # Repeat One
                self.load_song(self.current_index)
                self.play_song()
            elif self.repeat_mode == 1:  # Repeat All
                self.next_song()
            elif self.repeat_mode == 0:  # Kein Repeat
                # Nur weiterspielen wenn nicht letzter Song
                if self.current_index < len(self.playlist) - 1:
                    self.next_song()
                else:
                    self.is_playing = False
                    self.play_btn.config(text="▶ PLAY", bg='#27ae60')
        
        # Crossfade früh starten (X Sekunden vor Ende)
        if self.is_playing and not self.is_fading and self.song_length > 0 and self.crossfade_duration > 0:
            elapsed = time.time() - self.start_time
            pos = self.start_position + elapsed
            
            # Starte Crossfade wenn nur noch crossfade_duration Sekunden übrig
            if pos >= (self.song_length - self.crossfade_duration):
                if (self.repeat_mode == 1 or 
                    (self.repeat_mode == 0 and self.current_index < len(self.playlist) - 1)):
                    self.crossfade_to_next()
        
        self.root.after(1000, self.check_music_end)


if __name__ == "__main__":
    # Kommandozeilen-Argumente parsen
    parser = argparse.ArgumentParser(
        description='Touchscreen Audioplayer für Raspberry Pi',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s --repeat all
  %(prog)s --repeat one --folder /media/usb/music
  %(prog)s --volume 50 --no-autoplay
  %(prog)s --crossfade 5 --volume 80
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
    
    parser.add_argument(
        '--crossfade',
        type=float,
        default=3.0,
        metavar='SECONDS',
        help='Crossfade-Dauer in Sekunden (Standard: 3.0, 0 = aus)'
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
