import customtkinter as ctk
import main
import os
import subprocess
import sys
import threading
import re 
import tkinter as tk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- KLASA PRZECHWYTUJĄCA KONSOLĘ (ULEPSZONA O BUFOROWANIE) ---
class IORedirector(object):
    """Ta klasa skleja kawałki tekstu w pełne linie, żeby Regex zawsze działał"""
    def __init__(self, text_widget, original_stream, parser_callback):
        self.text_widget = text_widget
        self.original_stream = original_stream 
        self.parser_callback = parser_callback
        self.line_buffer = "" # Tu magazynujemy kawałki tekstu

    def write(self, string):
        # 1. Wypisz w czarnej konsoli (natychmiast)
        try:
            if self.original_stream:
                self.original_stream.write(string)
                self.original_stream.flush()
        except: pass

        # 2. Wypisz w aplikacji (natychmiast)
        try:
            self.text_widget.insert("end", string)
            self.text_widget.see("end")
        except: pass
        
        # 3. SKLEJANIE I ANALIZA (To naprawia błąd "Total: ?")
        self.line_buffer += string
        while "\n" in self.line_buffer:
            # Odcinamy jedną pełną linię
            line, self.line_buffer = self.line_buffer.split("\n", 1)
            # Wysyłamy PEŁNĄ linię do analizy
            if line.strip():
                self.parser_callback(line)

    def flush(self):
        try:
            if self.original_stream:
                self.original_stream.flush()
        except: pass

class FluxApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Flux - Autonomous AI Streaming Producer")
        self.geometry("1100x750") 
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # DANE
        self.global_session_points = 0
        self.streamer_stats = {} 
        self.log_history = ""
        self.status_labels = {} 
        self.points_labels = {}
        self.refresh_timer = None

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="FLUX AI", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30,20))
        
        ctk.CTkButton(self.sidebar, text="Dashboard", command=self.show_dashboard).pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar, text="Biblioteka Klipów", command=self.show_library, fg_color="#555").pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar, text="Lista Streamerów", command=self.show_streamer_list, fg_color="#444").pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar, text="Ustawienia", command=self.show_settings).pack(pady=10, padx=20)
        
        self.btn_miner = ctk.CTkButton(self.sidebar, text="URUCHOM KOPARKĘ ⛏️", command=self.start_miner, fg_color="#6A0DAD", hover_color="#4B0082")
        self.btn_miner.pack(pady=(30, 10), padx=20)
        
        self.status_lbl = ctk.CTkLabel(self.sidebar, text="Silnik: OFF", text_color="gray", font=("Arial", 12, "bold"))
        self.status_lbl.pack(side="bottom", pady=20)

        # --- CONTENT ---
        self.content = ctk.CTkFrame(self, corner_radius=10)
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Inicjalizacja zmiennych UI
        self.lbl_audio = None; self.lbl_chat = None; self.lbl_clips = None; self.lbl_points = None
        self.log_box = None; self.entry_nick = None; self.lbl_speech = None; self.lbl_vision = None
        self.scroll_list = None
        
        # Pokaż Dashboard na start
        self.show_dashboard()
        
        # --- PRZEKIEROWANIE KONSOLI ---
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        sys.stdout = IORedirector(self.log_box, self.original_stdout, self.parse_points_from_log)
        sys.stderr = IORedirector(self.log_box, self.original_stderr, self.parse_points_from_log)

        # Inicjalizacja silników
        self.engine = main.FluxEngine()
        self.miner = main.PointMiner()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(2000, self.start_miner) 

    def start_miner(self):
        if self.btn_miner.cget("state") == "disabled": return
        print("⛏️ AUTOSTART: Uruchomiono kopanie w tle.") 
        self.miner.start()
        self.btn_miner.configure(text="KOPARKA DZIAŁA ✅", state="disabled", fg_color="green")

    # --- PARSOWANIE PUNKTÓW ---
    def parse_points_from_log(self, msg):
        self.log_history += msg
        
        # 1. TOTALNE PUNKTY
        # Szukamy: Streamer(username=X, ..., channel_points=10.66k)
        if "channel_points=" in msg:
            try:
                user_match = re.search(r"username=([a-zA-Z0-9_]+)", msg, re.IGNORECASE)
                pts_match = re.search(r"channel_points=([0-9\.kKmM]+)", msg)
                
                if user_match and pts_match:
                    user = user_match.group(1).lower()
                    pts = pts_match.group(1)
                    
                    if user not in self.streamer_stats: 
                        self.streamer_stats[user] = {'total': pts, 'session': 0}
                    else:
                        self.streamer_stats[user]['total'] = pts
                    
                    # Od razu próbujemy zaktualizować widok (jeśli jest otwarty)
                    self.update_list_label(user)
            except: pass

        # 2. SESJA (BONUS)
        if "Claiming the bonus" in msg:
            try:
                user_match = re.search(r"username=([a-zA-Z0-9_]+)", msg, re.IGNORECASE)
                if user_match:
                    user = user_match.group(1).lower()
                    self.global_session_points += 50
                    
                    if user not in self.streamer_stats: 
                        self.streamer_stats[user] = {'total': '?', 'session': 0}
                    self.streamer_stats[user]['session'] += 50
                    
                    self.update_list_label(user)
                    if self.lbl_points: self.lbl_points.configure(text=str(self.global_session_points))
            except: pass

    def update_list_label(self, user):
        """Aktualizuje tekst na liście"""
        # Sprawdzamy czy mamy etykietę dla tego usera
        # Musimy szukać po kluczach słownika, bo user w stats jest lowercase, a w liście może być różnie
        
        target_label = None
        # Znajdź właściwą etykietę (ignorując wielkość liter)
        for label_name, label_obj in self.points_labels.items():
            if label_name.lower() == user:
                target_label = label_obj
                break
        
        if target_label and user in self.streamer_stats:
            stats = self.streamer_stats[user]
            txt = f"Total: {stats['total']}"
            if stats['session'] > 0:
                txt += f" | Sesja: +{stats['session']}"
            try:
                target_label.configure(text=txt)
            except: pass

    # --- DASHBOARD ---
    def show_dashboard(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Live Monitoring (Full AI)", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)
        
        top_frame = ctk.CTkFrame(self.content)
        top_frame.pack(fill="x", padx=20, pady=10)
        
        if not hasattr(self, 'engine') or not self.engine.is_running:
            self.entry_nick = ctk.CTkEntry(top_frame, placeholder_text="Nick Streamera", width=300)
            self.entry_nick.pack(side="left", padx=10, pady=10)
            self.btn_start = ctk.CTkButton(top_frame, text="START", fg_color="green", command=self.toggle_engine)
            self.btn_start.pack(side="left", padx=10)
        else:
            current_nick = self.engine.target_channel.upper()
            lbl = ctk.CTkLabel(top_frame, text=f"Monitorowany kanał: {current_nick}", font=("Arial", 16, "bold"), text_color="#3B8ED0")
            lbl.pack(side="left", padx=20, pady=10)
            self.btn_start = ctk.CTkButton(top_frame, text="ZAKOŃCZ", fg_color="red", command=self.toggle_engine)
            self.btn_start.pack(side="right", padx=20)

        stats_frame = ctk.CTkFrame(self.content)
        stats_frame.pack(fill="x", padx=20, pady=10)
        
        self.lbl_audio = self.create_stat(stats_frame, "Audio Level", "0")
        self.lbl_chat = self.create_stat(stats_frame, "Hype Score", "0.0")
        self.lbl_clips = self.create_stat(stats_frame, "Klipy", "0")
        self.lbl_points = self.create_stat(stats_frame, "Punkty (Sesja)", str(self.global_session_points))

        ai_frame = ctk.CTkFrame(self.content, fg_color="#2B2B2B")
        ai_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(ai_frame, text="Słuch (Audio):", font=("Arial", 12, "bold"), text_color="gray").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.lbl_speech = ctk.CTkLabel(ai_frame, text="...", font=("Arial", 13, "italic"), text_color="#00E5FF", wraplength=600, justify="left")
        self.lbl_speech.grid(row=0, column=1, sticky="w", padx=10)
        
        ctk.CTkLabel(ai_frame, text="Wzrok (Vision):", font=("Arial", 12, "bold"), text_color="gray").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.lbl_vision = ctk.CTkLabel(ai_frame, text="...", font=("Arial", 13, "italic"), text_color="#FFD700", wraplength=600, justify="left")
        self.lbl_vision.grid(row=1, column=1, sticky="w", padx=10)

        ctk.CTkLabel(self.content, text="Logi systemowe:", anchor="w").pack(fill="x", padx=20, pady=(10,0))
        self.log_box = ctk.CTkTextbox(self.content, height=200)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_box.insert("0.0", self.log_history)
        self.log_box.see("end")
        
        # Przywracamy przekierowanie po odświeżeniu
        if hasattr(self, 'original_stdout'):
            sys.stdout = IORedirector(self.log_box, self.original_stdout, self.parse_points_from_log)
            sys.stderr = IORedirector(self.log_box, self.original_stderr, self.parse_points_from_log)

    # --- LISTA STREAMERÓW ---
    def show_streamer_list(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Zarządzanie Minerem", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)
        
        add_frame = ctk.CTkFrame(self.content)
        add_frame.pack(fill="x", padx=20, pady=10)
        self.entry_streamer = ctk.CTkEntry(add_frame, placeholder_text="Nick np. Xayoo_", width=300)
        self.entry_streamer.pack(side="left", padx=10, pady=10)
        ctk.CTkButton(add_frame, text="DODAJ +", command=self.add_streamer_click, fg_color="green", width=100).pack(side="left", padx=10)

        ctk.CTkLabel(self.content, text="Aktualnie farmieni (Auto-odświeżanie):", anchor="w").pack(fill="x", padx=20, pady=(10,0))
        
        self.scroll_list = ctk.CTkScrollableFrame(self.content)
        self.scroll_list.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.refresh_streamer_list_ui()

    def refresh_streamer_list_ui(self):
        if not hasattr(self, 'scroll_list') or not self.scroll_list.winfo_exists(): return
        if self.refresh_timer: self.after_cancel(self.refresh_timer)
        
        for w in self.scroll_list.winfo_children(): w.destroy()
        self.status_labels = {}
        self.points_labels = {}

        streamers = main.load_streamers()
        
        for name in streamers:
            row = ctk.CTkFrame(self.scroll_list)
            row.pack(fill="x", pady=2, padx=5)
            
            ctk.CTkLabel(row, text=name, font=("Arial", 14, "bold"), width=150, anchor="w").pack(side="left", padx=10, pady=5)
            
            lbl_status = ctk.CTkLabel(row, text="Sprawdzam...", text_color="gray", font=("Arial", 12, "bold"), width=80)
            lbl_status.pack(side="left", padx=5)
            self.status_labels[name] = lbl_status

            # PUNKTY
            stats = self.streamer_stats.get(name.lower(), {'total': '?', 'session': 0})
            points_text = f"Total: {stats['total']}"
            if stats['session'] > 0:
                points_text += f" | Sesja: +{stats['session']}"
            
            lbl_points = ctk.CTkLabel(row, text=points_text, text_color="#AACCFF", font=("Arial", 12))
            lbl_points.pack(side="left", padx=20)
            self.points_labels[name] = lbl_points

            ctk.CTkButton(row, text="USUŃ ❌", width=60, fg_color="#AA0000", hover_color="#FF0000", 
                          command=lambda n=name: self.remove_streamer_click(n)).pack(side="right", padx=10, pady=5)

        threading.Thread(target=self._check_statuses_in_background, args=(streamers,), daemon=True).start()
        self.refresh_timer = self.after(300000, self.refresh_streamer_list_ui)

    def _check_statuses_in_background(self, streamers):
        for name in streamers:
            is_live = main.check_stream_status(name)
            try:
                if name in self.status_labels:
                    lbl = self.status_labels[name]
                    if is_live:
                        lbl.configure(text="🟢 ONLINE", text_color="#00FF00")
                    else:
                        lbl.configure(text="🔴 OFFLINE", text_color="#FF3333")
            except: pass

    # --- POZOSTAŁE FUNKCJE ---
    def show_library(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Twoje Nagrania", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)
        scroll_frame = ctk.CTkScrollableFrame(self.content)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        files = [f for f in os.listdir(".") if f.endswith(".mp4") and f.startswith("clip_")]
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        if not files: ctk.CTkLabel(scroll_frame, text="Brak nagrań w folderze.", text_color="gray").pack(pady=20)
        else:
            for filename in files: self.create_clip_row(scroll_frame, filename)

    def create_clip_row(self, parent, filename):
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", pady=5, padx=5)
        ctk.CTkLabel(row, text="🎬 " + filename, font=("Arial", 12)).pack(side="left", padx=10, pady=10)
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        ctk.CTkLabel(row, text=f"{size_mb:.1f} MB", text_color="gray").pack(side="left", padx=20)
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)
        ctk.CTkButton(btn_frame, text="▶️", width=40, command=lambda f=filename: self.open_file(f)).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🗑️", width=40, fg_color="#AA0000", hover_color="red", command=lambda f=filename: self.delete_file(f)).pack(side="left", padx=5)

    def delete_file(self, filename):
        try: os.remove(filename); self.show_library()
        except Exception as e: print(f"Błąd: {e}")

    def update_engine_log(self, msg): 
        print(msg) 

    def update_stats(self, audio, hype, clips, is_live, speech="", vision=""):
        try:
            if self.lbl_audio: self.lbl_audio.configure(text=str(audio))
            if self.lbl_chat: self.lbl_chat.configure(text=f"{hype:.1f}")
            if self.lbl_clips: self.lbl_clips.configure(text=str(clips))
            if self.lbl_points: self.lbl_points.configure(text=str(self.global_session_points))
            if self.lbl_speech and speech: self.lbl_speech.configure(text=speech)
            if self.lbl_vision and vision: self.lbl_vision.configure(text=vision)
            if self.status_lbl and self.engine.is_running:
                nick = self.engine.target_channel
                if is_live: self.status_lbl.configure(text=f"LIVE: {nick}", text_color="#00FF00")
                else: self.status_lbl.configure(text=f"OFFLINE (Czuwanie)", text_color="orange")
        except: pass

    def add_streamer_click(self):
        nick = self.entry_streamer.get().strip()
        if nick: main.add_streamer_to_file(nick); self.refresh_streamer_list_ui()
    def remove_streamer_click(self, nick):
        main.remove_streamer_from_file(nick); self.refresh_streamer_list_ui()
    def open_file(self, filename):
        try: os.startfile(filename)
        except Exception as e: print(f"Błąd: {e}")
    def show_settings(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Konfiguracja Czułości AI", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)
        self.create_slider("Audio Threshold", 500, 10000, self.engine.audio_threshold, lambda v: setattr(self.engine, 'audio_threshold', int(v)))
        self.create_slider("Hype Threshold", 10, 200, self.engine.hype_threshold, lambda v: setattr(self.engine, 'hype_threshold', float(v)))
        ctk.CTkLabel(self.content, text="* 1 pkt = zwykła wiadomość, 5-10 pkt = XD, CLIP, URWAŁ itp.", text_color="gray").pack(pady=5)
    def create_stat(self, parent, title, val):
        frame = ctk.CTkFrame(parent); frame.pack(side="left", expand=True, fill="both", padx=5, pady=5)
        ctk.CTkLabel(frame, text=title, font=("Arial", 12)).pack(pady=5)
        lbl = ctk.CTkLabel(frame, text=val, font=("Arial", 24, "bold"), text_color="#1f6aa5"); lbl.pack(pady=5); return lbl
    def create_slider(self, t, min_v, max_v, d, c):
        f=ctk.CTkFrame(self.content); f.pack(fill="x", padx=20, pady=5); ctk.CTkLabel(f, text=t).pack(anchor="w", padx=10); s=ctk.CTkSlider(f, from_=min_v, to=max_v, command=c); s.set(d); s.pack(fill="x", padx=10, pady=5)
    def clear_content(self):
        if self.refresh_timer: self.after_cancel(self.refresh_timer); self.refresh_timer = None
        for w in self.content.winfo_children(): w.destroy()
        self.lbl_audio = None; self.lbl_chat = None; self.lbl_clips = None; self.log_box = None; self.lbl_points = None
        self.entry_nick = None; self.scroll_list = None; self.lbl_speech = None; self.lbl_vision = None; self.points_labels = {}
    def toggle_engine(self):
        if not self.engine.is_running:
            if self.entry_nick.get(): self.engine.start(self.entry_nick.get(), self.update_engine_log, self.update_stats); self.show_dashboard()
        else: self.engine.stop(); self.show_dashboard()
    def on_close(self):
        self.engine.stop(); self.destroy()

if __name__ == "__main__":
    app = FluxApp()
    app.mainloop()