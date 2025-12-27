import customtkinter as ctk
import tkinter as tk
from datetime import datetime

# Konfiguracja wstępna wyglądu
ctk.set_appearance_mode("Dark")  # Tryb ciemny
ctk.set_default_color_theme("dark-blue")  # Motyw kolorystyczny

class FluxApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Konfiguracja głównego okna
        self.title("Flux - Autonomous AI Streaming Producer")
        self.geometry("1100x700")
        
        # Grid layout 1x2 (Sidebar + Main Content)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 1. SIDEBAR (Nawigacja) ===
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        # Logo / Tytuł
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="FLUX AI", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Przyciski nawigacyjne
        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", command=self.show_dashboard)
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_library = ctk.CTkButton(self.sidebar_frame, text="Biblioteka Klipów", command=self.show_library)
        self.btn_library.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="Konfiguracja AI", command=self.show_settings)
        self.btn_settings.grid(row=3, column=0, padx=20, pady=10)

        # Status u dołu sidebara
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Silnik: OFF", text_color="gray")
        self.status_label.grid(row=6, column=0, padx=20, pady=20)

        # === 2. GŁÓWNY OBSZAR (Zmienna zawartość) ===
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Inicjalizacja widoku Dashboard
        self.show_dashboard()

    def show_dashboard(self):
        self.clear_frame()
        
        # Nagłówek
        lbl = ctk.CTkLabel(self.main_frame, text="Live Monitoring", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=10, anchor="w", padx=20)

        # Input URL
        url_frame = ctk.CTkFrame(self.main_frame)
        url_frame.pack(fill="x", padx=20, pady=10)
        
        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="Wklej link do Twitch (np. twitch.tv/shroud)", width=400)
        self.url_entry.pack(side="left", padx=10, pady=10)
        
        self.start_btn = ctk.CTkButton(url_frame, text="START MONITORING", fg_color="green", hover_color="darkgreen", command=self.toggle_engine)
        self.start_btn.pack(side="left", padx=10)

        # Sekcja statystyk na żywo (Symulacja wykresów)
        stats_frame = ctk.CTkFrame(self.main_frame)
        stats_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Wskaźniki
        self.create_metric_card(stats_frame, "Audio Level (dB)", "-45 dB", 0, 0)
        self.create_metric_card(stats_frame, "Chat Velocity", "12 msg/s", 0, 1)
        self.create_metric_card(stats_frame, "Loyalty Points", "1,250 mined", 0, 2)

        # Konsola logów
        log_lbl = ctk.CTkLabel(self.main_frame, text="System Logs:", anchor="w")
        log_lbl.pack(fill="x", padx=20, pady=(10,0))
        
        self.log_box = ctk.CTkTextbox(self.main_frame, height=150)
        self.log_box.pack(fill="x", padx=20, pady=10)
        self.log_box.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] System gotowy. Oczekiwanie na link...\n")

    def show_settings(self):
        self.clear_frame()
        lbl = ctk.CTkLabel(self.main_frame, text="Konfiguracja AI & Triggerów", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=10, anchor="w", padx=20)

        # Ustawienia Audio
        self.create_slider_setting("Audio Spike Threshold (dB)", -20, -60, -35)
        
        # Ustawienia Czat
        self.create_slider_setting("Chat Spam Sensitivity (msg/s)", 5, 100, 30)

        # Przełączniki
        switch_frame = ctk.CTkFrame(self.main_frame)
        switch_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkSwitch(switch_frame, text="Auto-Convert to 9:16 (TikTok Mode)").pack(anchor="w", padx=20, pady=10)
        ctk.CTkSwitch(switch_frame, text="Generate Summaries (GPT-4)").pack(anchor="w", padx=20, pady=10)
        ctk.CTkSwitch(switch_frame, text="Loyalty Mining (Auto-Click Bonus)").pack(anchor="w", padx=20, pady=10)

    def show_library(self):
        self.clear_frame()
        lbl = ctk.CTkLabel(self.main_frame, text="Wygenerowane Klipy i Shorty", font=ctk.CTkFont(size=20, weight="bold"))
        lbl.pack(pady=10, anchor="w", padx=20)
        
        # Lista (Placeholder)
        scroll = ctk.CTkScrollableFrame(self.main_frame)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        for i in range(5):
            clip_frame = ctk.CTkFrame(scroll)
            clip_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(clip_frame, text=f"Clip_2023-10-12_hero_play_{i}.mp4").pack(side="left", padx=10)
            ctk.CTkButton(clip_frame, text="Otwórz", width=80).pack(side="right", padx=10, pady=5)
            ctk.CTkButton(clip_frame, text="Upload TikTok", width=100, fg_color="purple").pack(side="right", padx=5, pady=5)

    # Funkcje pomocnicze
    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def create_metric_card(self, parent, title, value, row, col):
        card = ctk.CTkFrame(parent)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        
        ctk.CTkLabel(card, text=title, font=("Arial", 12)).pack(pady=(10,0))
        ctk.CTkLabel(card, text=value, font=("Arial", 24, "bold"), text_color="#3B8ED0").pack(pady=(5,10))

    def create_slider_setting(self, title, min_val, max_val, default):
        frame = ctk.CTkFrame(self.main_frame)
        frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(frame, text=title).pack(anchor="w", padx=10, pady=5)
        slider = ctk.CTkSlider(frame, from_=min_val, to=max_val)
        slider.set(default)
        slider.pack(fill="x", padx=10, pady=(0, 10))

    def toggle_engine(self):
        current_text = self.start_btn.cget("text")
        if "START" in current_text:
            self.start_btn.configure(text="STOP MONITORING", fg_color="red", hover_color="darkred")
            self.status_label.configure(text="Silnik: ONLINE (Listening)", text_color="green")
            self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Połączono z czatem. Analiza audio aktywna.\n")
        else:
            self.start_btn.configure(text="START MONITORING", fg_color="green", hover_color="darkgreen")
            self.status_label.configure(text="Silnik: OFF", text_color="gray")
            self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Zatrzymano monitoring.\n")

if __name__ == "__main__":
    app = FluxApp()
    app.mainloop()