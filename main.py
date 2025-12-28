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

# --- TWOJE DANE API (Do sprawdzania czy kanał istnieje - zostawiamy te robocze) ---
CLIENT_ID = '4uv95tg4zx45b0c98x3amhpr13fng3'       
CLIENT_SECRET = 'o65r6v3s29akfpijrc75drcukfkwv7' 

# --- TWOJE DANE DO LOGOWANIA NA CZAT (Aby być widocznym i zbierać watchtime) ---
USER_NICK = 'helox343' 
USER_TOKEN = 'oauth:34hx48t13eomojbosd757cj4h5gfer'  # Dodałem 'oauth:' automatycznie

class FluxEngine:
    def __init__(self):
        self.is_running = False
        self.target_channel = ""
        self.log_callback = None
        self.stats_callback = None
        
        # Stan
        self.current_chat_velocity = 0.0
        self.current_audio_level = 0.0
        self.is_stream_live = False
        self.session_clips = []
        
        # Ustawienia
        self.chat_threshold = 3.0
        self.audio_threshold = 2000
        self.cooldown_time = 60
        self.record_duration = 60 # Nagrywamy 60s (z przeszłości)
        
        # DVR (Time Machine - naprawia klipy)
        self.dvr_process = None
        self.dvr_filename = "flux_buffer_temp.ts"
        self.stream_start_time = 0
        self.last_trigger_time = 0

    def log(self, message):
        if self.log_callback:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            self.log_callback(f"[{timestamp}] {message}\n")
        else:
            print(message)

    def _get_api_token(self):
        try:
            url = "https://id.twitch.tv/oauth2/token"
            params = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'client_credentials'}
            r = requests.post(url, params=params)
            return r.json().get('access_token')
        except: return None

    def _verify_channel_exists(self, channel):
        token = self._get_api_token()
        if not token: return True
        try:
            url = "https://api.twitch.tv/helix/users"
            headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {token}'}
            r = requests.get(url, headers=headers, params={'login': channel})
            if not r.json().get('data'): return False
            return True
        except: return True

    def start(self, channel, log_cb, stats_cb):
        if self.is_running: return False
        clean_channel = channel.lower().replace("twitch.tv/", "").replace("https://", "").strip()
        self.log_callback = log_cb
        self.stats_callback = stats_cb

        self.log(f"🔍 Weryfikacja: {clean_channel}...")
        if not self._verify_channel_exists(clean_channel):
            self.log(f"❌ BŁĄD: Kanał '{clean_channel}' nie istnieje!")
            return False
        
        self.target_channel = clean_channel
        self.is_running = True
        self.session_clips = []
        
        # Czyścimy stary bufor jeśli istnieje
        if os.path.exists(self.dvr_filename):
            try: os.remove(self.dvr_filename)
            except: pass

        threading.Thread(target=self._main_loop, daemon=True).start()
        self.log(f"🟢 Flux Engine: Zalogowano jako {USER_NICK}")
        return True

    def stop(self):
        self.is_running = False
        if self.dvr_process:
            self.dvr_process.terminate()
        self.log("🛑 Zatrzymywanie...")

    def _monitor_chat(self):
        """Łączy się z czatem używając Twojego konta helox343."""
        server = 'irc.chat.twitch.tv'
        sock = socket.socket()
        msgs = []
        try:
            sock.connect((server, 6667))
            
            # --- LOGOWANIE UŻYTKOWNIKA ---
            sock.send(f"PASS {USER_TOKEN}\n".encode('utf-8'))
            sock.send(f"NICK {USER_NICK}\n".encode('utf-8'))
            sock.send(f"JOIN #{self.target_channel}\n".encode('utf-8'))
            
            sock.settimeout(2.0)
            while self.is_running:
                try:
                    resp = sock.recv(2048).decode('utf-8', 'ignore')
                    if resp.startswith('PING'): 
                        sock.send("PONG\n".encode('utf-8'))
                    elif "PRIVMSG" in resp:
                        now = time.time()
                        msgs.append(now)
                        msgs = [t for t in msgs if now - t <= 10.0]
                        self.current_chat_velocity = len(msgs) / 10.0 if msgs else 0
                except socket.timeout: continue
                except: pass
        except Exception as e:
            self.log(f"⚠️ Błąd połączenia z czatem: {e}")
        finally: sock.close()

    def _monitor_audio(self):
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        while self.is_running:
            try:
                streams = streamlink.streams(f"https://twitch.tv/{self.target_channel}")
                if not streams:
                    self.is_stream_live = False
                    self.current_audio_level = 0
                    time.sleep(5)
                    continue

                # Jeśli jesteśmy LIVE, odpalamy DVR (Buforowanie)
                if not self.dvr_process:
                    self._start_dvr_recording(streams)

                # Osobny proces do analizy audio
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
                process.terminate()
            except:
                self.is_stream_live = False
                time.sleep(5)

    def _start_dvr_recording(self, streams):
        """Nagrywa cały stream do pliku tymczasowego."""
        stream_url = streams['best'].url
        self.stream_start_time = time.time()
        self.log("📼 DVR: Buforowanie wideo (Time Machine)...")
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        # Używamy formatu MPEGTS bo jest odporny na błędy przy ciągłym zapisie
        cmd = [ffmpeg_cmd, "-i", stream_url, "-c", "copy", "-f", "mpegts", "-y", self.dvr_filename]
        self.dvr_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _cut_clip_from_dvr(self, reason):
        """Wycina klip z przeszłości (30s przed zdarzeniem)."""
        if not os.path.exists(self.dvr_filename): return
        
        now = time.time()
        # Logika czasu: Chcemy nagrać 40 sekund, kończąc 10 sekund PO triggerze
        # Czyli startujemy 30 sekund PRZED triggerem.
        offset_end = now - self.stream_start_time + 10 
        offset_start = max(0, offset_end - 40)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_name = f"clip_{self.target_channel}_{timestamp}.mp4"
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        
        # Wycinanie bez ponownego kodowania (bardzo szybkie)
        cmd = [ffmpeg_cmd, "-i", self.dvr_filename, "-ss", str(offset_start), "-to", str(offset_end), "-c", "copy", "-y", out_name]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_name

    def _handle_trigger(self, reason):
        self.log(f"🎬 WYKRYTO: {reason} -> Zapis klipu z przeszłości...")
        filename = self._cut_clip_from_dvr(reason)
        if filename and os.path.exists(filename):
            self.log(f"✅ Zapisano: {filename}")
            self.session_clips.append((filename, reason))

    def _main_loop(self):
        t1 = threading.Thread(target=self._monitor_chat); t1.daemon=True; t1.start()
        t2 = threading.Thread(target=self._monitor_audio); t2.daemon=True; t2.start()
        
        while self.is_running:
            if self.stats_callback:
                self.stats_callback(self.current_audio_level, self.current_chat_velocity, len(self.session_clips), self.is_stream_live)
            
            # Tylko jeśli DVR działa (mamy co wycinać)
            if self.is_stream_live and self.dvr_process:
                time_since_last = time.time() - self.last_trigger_time
                triggered = False
                reason = ""
                
                if time_since_last > self.cooldown_time:
                    # Czekamy aż uzbiera się min 30s bufora
                    if (time.time() - self.stream_start_time) > 30:
                        if self.current_chat_velocity > self.chat_threshold:
                            triggered = True; reason = f"CHAT ({self.current_chat_velocity:.1f}/s)"
                        elif self.current_audio_level > self.audio_threshold:
                            triggered = True; reason = f"AUDIO ({self.current_audio_level})"
                
                if triggered:
                    threading.Thread(target=self._handle_trigger, args=(reason,)).start()
                    self.last_trigger_time = time.time()
            
            time.sleep(0.5)
            
        # Sprzątanie
        if self.dvr_process: self.dvr_process.terminate()
        if os.path.exists(self.dvr_filename):
            try: os.remove(self.dvr_filename)
            except: pass