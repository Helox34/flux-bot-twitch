import customtkinter as ctk
import main
import os
import subprocess
import sys

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class FluxApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.engine = main.FluxEngine()

        self.title("Flux - Autonomous AI Streaming Producer")
        self.geometry("1000x650")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.log_history = "" 

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="FLUX AI", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30,20))
        
        # Przyciski Menu
        ctk.CTkButton(self.sidebar, text="Dashboard", command=self.show_dashboard).pack(pady=10, padx=20)
        ctk.CTkButton(self.sidebar, text="Biblioteka Klipów", command=self.show_library, fg_color="#555").pack(pady=10, padx=20) # Wyróżniłem kolorem
        ctk.CTkButton(self.sidebar, text="Ustawienia", command=self.show_settings).pack(pady=10, padx=20)
        
        self.status_lbl = ctk.CTkLabel(self.sidebar, text="Silnik: OFF", text_color="gray", font=("Arial", 12, "bold"))
        self.status_lbl.pack(side="bottom", pady=20)

        # --- CONTENT ---
        self.content = ctk.CTkFrame(self, corner_radius=10)
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.lbl_audio = None; self.lbl_chat = None; self.lbl_clips = None; self.log_box = None; self.entry_nick = None

        self.show_dashboard()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_dashboard(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Live Monitoring", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)

        top_frame = ctk.CTkFrame(self.content)
        top_frame.pack(fill="x", padx=20, pady=10)
        
        if not self.engine.is_running:
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
        self.lbl_audio = self.create_stat(stats_frame, "Audio Level", "0", 0)
        self.lbl_chat = self.create_stat(stats_frame, "Czat (msg/s)", "0.0", 1)
        self.lbl_clips = self.create_stat(stats_frame, "Klipy", "0", 2)

        ctk.CTkLabel(self.content, text="Logi systemowe:", anchor="w").pack(fill="x", padx=20, pady=(10,0))
        self.log_box = ctk.CTkTextbox(self.content, height=250)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_box.insert("0.0", self.log_history)
        self.log_box.see("end")

    # --- NOWA FUNKCJA: BIBLIOTEKA ---
    def show_library(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Twoje Nagrania", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)

        # Kontener z paskiem przewijania
        scroll_frame = ctk.CTkScrollableFrame(self.content)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Szukamy plików .mp4 zaczynających się od "clip_"
        files = [f for f in os.listdir(".") if f.endswith(".mp4") and f.startswith("clip_")]
        
        # Sortujemy od najnowszych (według daty modyfikacji)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        if not files:
            ctk.CTkLabel(scroll_frame, text="Brak nagrań w folderze.", text_color="gray").pack(pady=20)
        else:
            for filename in files:
                self.create_clip_row(scroll_frame, filename)

    def create_clip_row(self, parent, filename):
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", pady=5, padx=5)
        
        # Ikona/Nazwa pliku
        ctk.CTkLabel(row, text="🎬 " + filename, font=("Arial", 12)).pack(side="left", padx=10, pady=10)
        
        # Rozmiar pliku w MB
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        ctk.CTkLabel(row, text=f"{size_mb:.1f} MB", text_color="gray").pack(side="left", padx=20)

        # Przycisk Otwórz
        # Używamy lambda z domyślnym argumentem (f=filename), żeby każdy przycisk pamiętał swój plik
        ctk.CTkButton(row, text="ODTWÓRZ ▶️", width=100, command=lambda f=filename: self.open_file(f)).pack(side="right", padx=10, pady=5)

    def open_file(self, filename):
        """Otwiera plik w domyślnym odtwarzaczu systemu Windows."""
        try:
            os.startfile(filename)
        except Exception as e:
            print(f"Błąd otwierania: {e}")

    def show_settings(self):
        self.clear_content()
        ctk.CTkLabel(self.content, text="Konfiguracja Czułości", font=("Arial", 20, "bold")).pack(pady=10, anchor="w", padx=20)
        self.create_slider("Próg Audio (Krzyk)", 500, 10000, self.engine.audio_threshold, lambda v: setattr(self.engine, 'audio_threshold', int(v)))
        self.create_slider("Próg Czat (Spam)", 1, 50, self.engine.chat_threshold, lambda v: setattr(self.engine, 'chat_threshold', float(v)))
        self.create_slider("Długość klipu (s)", 10, 120, self.engine.record_duration, lambda v: setattr(self.engine, 'record_duration', int(v)))

    def toggle_engine(self):
        if not self.engine.is_running:
            if self.entry_nick:
                nick = self.entry_nick.get()
                if not nick: return
                success = self.engine.start(nick, self.update_log, self.update_stats)
                if success:
                    self.status_lbl.configure(text="Łączenie...", text_color="yellow")
                    self.show_dashboard()
                else:
                    self.status_lbl.configure(text="NIE ZNALEZIONO", text_color="red")
        else:
            self.engine.stop()
            self.status_lbl.configure(text="Silnik: OFF", text_color="gray")
            self.show_dashboard()

    def update_log(self, msg):
        self.log_history += msg
        try:
            if self.log_box and self.log_box.winfo_exists():
                self.log_box.insert("end", msg); self.log_box.see("end")
        except: pass

    def update_stats(self, audio, chat, clips, is_live):
        try:
            if self.lbl_audio and self.lbl_audio.winfo_exists(): self.lbl_audio.configure(text=str(audio))
            if self.lbl_chat and self.lbl_chat.winfo_exists(): self.lbl_chat.configure(text=f"{chat:.1f}")
            if self.lbl_clips and self.lbl_clips.winfo_exists(): self.lbl_clips.configure(text=str(clips))
            if self.status_lbl and self.status_lbl.winfo_exists() and self.engine.is_running:
                nick = self.engine.target_channel
                if is_live: self.status_lbl.configure(text=f"LIVE: {nick}", text_color="#00FF00")
                else: self.status_lbl.configure(text=f"OFFLINE (Czuwanie)", text_color="orange")
        except Exception: pass

    def clear_content(self):
        for w in self.content.winfo_children(): w.destroy()
        self.lbl_audio = None; self.lbl_chat = None; self.lbl_clips = None; self.log_box = None; self.entry_nick = None

    def create_stat(self, parent, title, val, col):
        frame = ctk.CTkFrame(parent)
        frame.pack(side="left", expand=True, fill="both", padx=5, pady=5)
        ctk.CTkLabel(frame, text=title, font=("Arial", 12)).pack(pady=5)
        lbl = ctk.CTkLabel(frame, text=val, font=("Arial", 24, "bold"), text_color="#1f6aa5")
        lbl.pack(pady=5); return lbl

    def create_slider(self, title, min_v, max_v, default, cmd):
        frame = ctk.CTkFrame(self.content)
        frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame, text=title).pack(anchor="w", padx=10)
        slider = ctk.CTkSlider(frame, from_=min_v, to=max_v, command=cmd)
        slider.set(default); slider.pack(fill="x", padx=10, pady=10)

    def on_close(self):
        self.engine.stop(); self.destroy()

if __name__ == "__main__":
    app = FluxApp()
    app.mainloop()