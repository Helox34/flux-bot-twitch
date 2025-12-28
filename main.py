import socket
import threading
import time
import numpy as np
import subprocess
import streamlink
import os
import datetime
import sys
import requests
import shutil
import json
import re 
import wave
import io
import speech_recognition as sr
import cv2 # Biblioteka do wideo (OpenCV)
import pytesseract # Biblioteka do czytania tekstu (Tesseract)

# --- IMPORTY DLA MINERA ---
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Settings import Priority, FollowersOrder

# --- KONFIGURACJA ŚCIEŻKI DO TESSERACT OCR (SPRAWDŹ CZY MASZ TU PROGRAM!) ---
# Jeśli zainstalowałeś w innym miejscu, zmień tę ścieżkę:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- TWOJE DANE ---
CLIENT_ID = '4uv95tg4zx45b0c98x3amhpr13fng3'       
CLIENT_SECRET = 'o65r6v3s29akfpijrc75drcukfkwv7' 

USER_NICK = 'helox343' 
USER_TOKEN = 'oauth:34hx48t13eomojbosd757cj4h5gfer'

STREAMERS_FILE = "streamers_list.json"
DEFAULT_STREAMERS = ["MrDzinold", "MelaPustelnik", "Diables", "Kasix", "Fernatka", "PAGO3", "IzakOOO"]

# --- SŁOWNIKI TRIGGERÓW ---
HYPE_KEYWORDS = {
    "clip": 10, "klip": 10, "ale urwał": 8, "o chuj": 8, "wtf": 7, "omg": 7,
    "pog": 6, "win": 8, "xd": 3, "lol": 2, "kurwa": 3, "ez": 4, "szef": 4, "!!!": 5
}

AUDIO_TRIGGERS = [
    "o mój boże", "o kurwa", "ja pierdolę", "ale fart", "wygrałem", 
    "nie wierzę", "co jest", "ale urwał", "szef", "ez", "łatwo", "clip"
]

# Nowe: Słowa, których szukamy NA EKRANIE (nieczułe na wielkość liter)
VISUAL_TRIGGERS = [
    "victory", "defeat", "winner", "zwycięstwo", "porażka", 
    "#1", "wygrał", "eliminacja", "knocked", "killed"
]

# --- OBSŁUGA PLIKÓW ---
def load_streamers():
    try:
        with open(STREAMERS_FILE, 'r') as f: return json.load(f)
    except: return DEFAULT_STREAMERS

def save_streamers(lista):
    with open(STREAMERS_FILE, 'w') as f: json.dump(lista, f)

def add_streamer_to_file(nick):
    current = load_streamers(); 
    if nick not in current: current.append(nick); save_streamers(current); return True
    return False

def remove_streamer_from_file(nick):
    current = load_streamers(); 
    if nick in current: current.remove(nick); save_streamers(current); return True
    return False

def get_temp_token():
    try:
        url = "https://id.twitch.tv/oauth2/token"
        params = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'client_credentials'}
        r = requests.post(url, params=params)
        return r.json().get('access_token')
    except: return None

def check_stream_status(user_login):
    token = get_temp_token()
    if not token: return False
    try:
        url = "https://api.twitch.tv/helix/streams"
        headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {token}'}
        params = {'user_login': user_login}
        r = requests.get(url, headers=headers, params=params)
        data = r.json().get('data')
        return True if data and len(data) > 0 else False
    except: return False

# --- SILNIK FLUX ---
class FluxEngine:
    def __init__(self):
        self.is_running = False
        self.target_channel = ""
        self.log_callback = None
        self.stats_callback = None
        
        self.current_hype_score = 0.0
        self.current_audio_level = 0.0
        self.last_heard_text = "..."
        self.last_seen_text = "..." # Nowe pole do GUI
        self.is_stream_live = False
        self.session_clips = []
        
        self.hype_threshold = 20.0
        self.audio_threshold = 2000
        self.cooldown_time = 45
        self.record_duration = 60 
        
        self.dvr_process = None
        self.dvr_filename = "flux_buffer_temp.ts"
        self.stream_start_time = 0
        self.last_trigger_time = 0
        
        self.recognizer = sr.Recognizer()

    def log(self, message):
        if self.log_callback:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            self.log_callback(f"[{timestamp}] {message}\n")
        else: print(message)

    def start(self, channel, log_cb, stats_cb):
        if self.is_running: return False
        clean_channel = channel.lower().replace("twitch.tv/", "").replace("https://", "").strip()
        self.log_callback = log_cb; self.stats_callback = stats_cb

        self.log(f"🔍 Weryfikacja: {clean_channel}...")
        if not check_stream_status(clean_channel) and not self._verify_channel_exists(clean_channel):
             self.log(f"⚠️ Kanał może być offline lub nie istnieć."); 
        
        self.target_channel = clean_channel
        self.is_running = True
        self.session_clips = []
        
        if os.path.exists(self.dvr_filename): 
            try: os.remove(self.dvr_filename)
            except: pass

        threading.Thread(target=self._main_loop, daemon=True).start()
        self.log(f"🟢 Flux Engine: START (Vision + Audio + Chat)")
        return True

    def _verify_channel_exists(self, channel):
        return True # Uproszczone dla szybkości

    def stop(self):
        self.is_running = False
        if self.dvr_process: self.dvr_process.terminate()
        self.log("🛑 Zatrzymywanie...")

    # --- VISION AI: OKO FLUXA ---
    def _monitor_video(self):
        """Pobiera klatki ze streama i szuka napisów."""
        self.log("👁️ Vision AI: Uruchamianie analizy obrazu...")
        
        while self.is_running:
            if not self.is_stream_live:
                time.sleep(5); continue

            try:
                # Pobieramy URL strumienia
                streams = streamlink.streams(f"https://twitch.tv/{self.target_channel}")
                if not streams: time.sleep(5); continue
                stream_url = streams['best'].url
                
                # Otwieramy strumień w OpenCV
                cap = cv2.VideoCapture(stream_url)
                
                while self.is_running and self.is_stream_live and cap.isOpened():
                    ret, frame = cap.read()
                    if not ret: break
                    
                    # --- OPTYMALIZACJA ---
                    # Nie analizujemy każdej klatki (bo PC wybuchnie). 
                    # Robimy to raz na 3 sekundy.
                    
                    # Konwersja na szarość (łatwiej czytać tekst)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # OCR - Czytanie tekstu (może zająć chwilę)
                    try:
                        text = pytesseract.image_to_string(gray)
                        clean_text = " ".join(text.split()).lower() # Usuń znaki nowej linii
                        
                        # Wyświetl w GUI (tylko pierwsze 50 znaków żeby nie śmiecić)
                        if len(clean_text) > 2:
                            self.last_seen_text = clean_text[:60] + "..."
                        
                        # Sprawdź triggery
                        for trigger in VISUAL_TRIGGERS:
                            if trigger in clean_text:
                                self.log(f"👁️ ZOBACZONO: '{trigger.upper()}' -> Wyzwalanie klipu!")
                                threading.Thread(target=self._trigger_clip, args=(f"VIDEO: {trigger.upper()}",)).start()
                                # Pauza po znalezieniu, żeby nie spamować klipami z tej samej klatki
                                time.sleep(10) 
                                break
                                
                    except Exception as e:
                        # Często rzuca błąd jak nie znajdzie tekstu, to normalne
                        pass
                    
                    # Czyścimy bufor OpenCV (żeby nie czytał starych klatek)
                    for _ in range(60): # Pomiń następne ~2 sekundy klatek (przy 30fps)
                        cap.grab()
                        
                    time.sleep(2.0) # Dodatkowe odciążenie procesora
                    
                cap.release()
            except Exception as e:
                # self.log(f"Błąd Vision: {e}") 
                time.sleep(5)

    # --- POZOSTAŁE MODUŁY (Audio, Chat, DVR) ---
    def _transcribe_worker(self, audio_data):
        try:
            with io.BytesIO() as wav_file:
                with wave.open(wav_file, 'wb') as wf:
                    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000); wf.writeframes(audio_data)
                wav_file.seek(0)
                with sr.AudioFile(wav_file) as source:
                    audio = self.recognizer.record(source)
                try:
                    text = self.recognizer.recognize_google(audio, language="pl-PL")
                    self.last_heard_text = text.lower()
                    for trigger in AUDIO_TRIGGERS:
                        if trigger in self.last_heard_text:
                            self.log(f"🗣️ USŁYSZANO: '{trigger}' -> Wyzwalanie klipu!")
                            threading.Thread(target=self._trigger_clip, args=(f"GŁOS: {trigger}",)).start()
                            break
                except: pass
        except: pass

    def _monitor_audio_loop(self):
        # To ta sama funkcja co wcześniej, tylko zmieniłem nazwę dla porządku
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        audio_buffer = bytearray(); buffer_limit = 16000 * 2 * 5
        while self.is_running:
            try:
                streams = streamlink.streams(f"https://twitch.tv/{self.target_channel}")
                if not streams:
                    self.is_stream_live = False; self.current_audio_level = 0; time.sleep(5); continue

                if not self.dvr_process: self._start_dvr_recording(streams)
                audio_url = streams['audio_only'].url if 'audio_only' in streams else streams['best'].url
                cmd = [ffmpeg_cmd, "-i", audio_url, "-f", "s16le", "-ac", "1", "-ar", "16000", "-vn", "-"]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                self.is_stream_live = True
                while self.is_running and self.is_stream_live:
                    raw = process.stdout.read(4096)
                    if not raw: break
                    data = np.frombuffer(raw, dtype=np.int16)
                    if len(data) > 0:
                        rms = np.sqrt(np.mean(data.astype(np.float64)**2))
                        if not np.isnan(rms): self.current_audio_level = int(rms)
                    audio_buffer.extend(raw)
                    if len(audio_buffer) >= buffer_limit:
                        chunk = bytes(audio_buffer); audio_buffer = bytearray()
                        threading.Thread(target=self._transcribe_worker, args=(chunk,)).start()
                process.terminate()
            except: self.is_stream_live = False; time.sleep(5)

    def _monitor_chat(self):
        server = 'irc.chat.twitch.tv'; sock = socket.socket(); hype_events = [] 
        try:
            sock.connect((server, 6667))
            sock.send(f"PASS {USER_TOKEN}\n".encode('utf-8')); sock.send(f"NICK {USER_NICK}\n".encode('utf-8')); sock.send(f"JOIN #{self.target_channel}\n".encode('utf-8')); sock.settimeout(2.0)
            while self.is_running:
                try:
                    resp = sock.recv(2048).decode('utf-8', 'ignore')
                    if resp.startswith('PING'): sock.send("PONG\n".encode('utf-8'))
                    elif "PRIVMSG" in resp:
                        try:
                            content = resp.split("PRIVMSG #" + self.target_channel + " :")[1].strip()
                            points = 1.0
                            for w, v in HYPE_KEYWORDS.items(): 
                                if w in content.lower(): points += v
                            if len(content) > 4 and content.isupper(): points += 2.0
                            hype_events.append((time.time(), points))
                        except: pass
                        now = time.time(); hype_events = [t for t in hype_events if now - t[0] <= 10.0]
                        self.current_hype_score = sum(p[1] for p in hype_events)
                except socket.timeout: continue
                except: pass
        except: pass; sock.close()

    def _start_dvr_recording(self, streams):
        stream_url = streams['best'].url
        self.stream_start_time = time.time()
        self.log("📼 DVR: Buforowanie wideo...")
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        cmd = [ffmpeg_cmd, "-i", stream_url, "-c", "copy", "-f", "mpegts", "-y", self.dvr_filename]
        self.dvr_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _cut_clip_from_dvr(self, reason):
        if not os.path.exists(self.dvr_filename): return
        now = time.time(); duration = 60; post_event_buffer = 15 
        offset_end = now - self.stream_start_time + post_event_buffer
        offset_start = max(0, offset_end - duration)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_name = f"clip_{self.target_channel}_{timestamp}.mp4"
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        cmd = [ffmpeg_cmd, "-i", self.dvr_filename, "-ss", str(offset_start), "-to", str(offset_end), "-c", "copy", "-y", out_name]
        threading.Timer(post_event_buffer, lambda: subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)).start()
        return out_name

    def _trigger_clip(self, reason):
        if time.time() - self.last_trigger_time < self.cooldown_time: return
        self.log(f"⚡ AKCJA: {reason} -> Wycinanie..."); self.last_trigger_time = time.time()
        out_name = self._cut_clip_from_dvr(reason)
        if out_name: self.session_clips.append((out_name, reason))

    def _main_loop(self):
        t1 = threading.Thread(target=self._monitor_chat); t1.daemon=True; t1.start()
        t2 = threading.Thread(target=self._monitor_audio_loop); t2.daemon=True; t2.start()
        t3 = threading.Thread(target=self._monitor_video); t3.daemon=True; t3.start() # Nowy wątek VIDEO
        
        while self.is_running:
            if self.stats_callback:
                self.stats_callback(self.current_audio_level, self.current_hype_score, len(self.session_clips), self.is_stream_live, self.last_heard_text, self.last_seen_text)
            
            if self.is_stream_live and self.dvr_process:
                time_since_last = time.time() - self.last_trigger_time
                if time_since_last > self.cooldown_time and (time.time() - self.stream_start_time) > 30:
                    if self.current_hype_score > self.hype_threshold: self._trigger_clip(f"HYPE ({self.current_hype_score:.1f})")
                    elif self.current_audio_level > self.audio_threshold: self._trigger_clip(f"AUDIO ({self.current_audio_level})")
            time.sleep(0.5)
            
        if self.dvr_process: self.dvr_process.terminate()
        if os.path.exists(self.dvr_filename): 
            try: os.remove(self.dvr_filename)
            except: pass

class PointMiner:
    def __init__(self):
        self.is_mining = False
        self.miner = TwitchChannelPointsMiner(username=USER_NICK, password=USER_TOKEN.replace("oauth:",""), claim_drops_startup=True, priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER])
    def start(self):
        if self.is_mining: return
        self.is_mining = True; targets = load_streamers()
        threading.Thread(target=self._mine_process, args=(targets,), daemon=True).start()
    def _mine_process(self, targets):
        print(f"⛏️ [MINER] Start: {USER_NICK}"); 
        try: self.miner.mine(targets, followers=False, followers_order=FollowersOrder.ASC)
        except: pass