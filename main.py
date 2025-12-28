import socket
import threading
import time
import numpy as np
import subprocess
import streamlink
import os
import datetime
import sys
import urllib.request
import urllib.error

# --- KONFIGURACJA ---
NICKNAME = 'justinfan12345'

class FluxEngine:
    def __init__(self):
        self.is_running = False
        self.target_channel = ""
        self.log_callback = None
        self.stats_callback = None
        
        # Zmienne stanu
        self.current_chat_velocity = 0.0
        self.current_audio_level = 0.0
        self.is_stream_live = False
        self.last_clip_time = 0
        self.session_clips = []
        
        # Ustawienia
        self.chat_threshold = 3.0
        self.audio_threshold = 2000
        self.cooldown_time = 60
        self.record_duration = 30

    def log(self, message):
        if self.log_callback:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            self.log_callback(f"[{timestamp}] {message}\n")
        else:
            print(message)

    def _verify_channel_exists(self, channel):
        """Sprawdza, czy kanał istnieje na Twitchu (nie czy jest live, tylko czy istnieje)."""
        url = f"https://www.twitch.tv/{channel}"
        try:
            # Udajemy przeglądarkę (User-Agent), żeby Twitch nas nie zablokował
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False # Strona nie istnieje (zły nick)
            return True # Inny błąd (np. serwery padły), pozwalamy spróbować
        except Exception:
            return True # Brak internetu lub inny błąd, pozwalamy spróbować

    def start(self, channel, log_cb, stats_cb):
        """Startuje silnik z weryfikacją."""
        if self.is_running: return False

        # Czyścimy nick z linków itp.
        clean_channel = channel.lower().replace("twitch.tv/", "").replace("https://", "").strip()
        
        # Podpinamy logowanie, żeby móc zgłosić błąd
        self.log_callback = log_cb
        self.stats_callback = stats_cb

        self.log(f"🔍 Weryfikacja kanału: {clean_channel}...")

        # --- NOWOŚĆ: Sprawdzamy czy istnieje ---
        if not self._verify_channel_exists(clean_channel):
            self.log(f"❌ BŁĄD: Nie znaleziono streamera '{clean_channel}'!")
            self.log("   Sprawdź, czy nie zrobiłeś literówki.")
            return False # Zwracamy Fałsz - start się nie udał
        # ---------------------------------------

        self.target_channel = clean_channel
        self.is_running = True
        self.session_clips = []
        
        self.main_loop_thread = threading.Thread(target=self._main_loop)
        self.main_loop_thread.daemon = True
        self.main_loop_thread.start()
        
        self.log(f"🟢 Flux Engine: Start dla kanału {self.target_channel}")
        return True # Sukces

    def stop(self):
        self.is_running = False
        self.log("🛑 Zatrzymywanie procesów...")

    def _monitor_chat(self):
        server = 'irc.chat.twitch.tv'
        sock = socket.socket()
        messages_window = []
        try:
            sock.connect((server, 6667))
            sock.send(f"NICK {NICKNAME}\n".encode('utf-8'))
            sock.send(f"JOIN #{self.target_channel}\n".encode('utf-8'))
            sock.settimeout(2.0)
            while self.is_running:
                try:
                    resp = sock.recv(2048).decode('utf-8', 'ignore')
                    if resp.startswith('PING'): sock.send("PONG\n".encode('utf-8'))
                    elif "PRIVMSG" in resp:
                        now = time.time()
                        messages_window.append(now)
                        messages_window = [t for t in messages_window if now - t <= 10.0]
                        self.current_chat_velocity = len(messages_window) / 10.0 if messages_window else 0
                except socket.timeout: continue
                except: pass
        except Exception as e: self.log(f"Błąd czatu: {e}")
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

                stream_url = streams['audio_only'].url if 'audio_only' in streams else streams['best'].url
                self.is_stream_live = True
                
                command = [ffmpeg_cmd, "-i", stream_url, "-f", "s16le", "-ac", "1", "-ar", "16000", "-vn", "-"]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                
                while self.is_running:
                    raw_audio = process.stdout.read(4096)
                    if not raw_audio: break
                    audio_data = np.frombuffer(raw_audio, dtype=np.int16)
                    if len(audio_data) > 0:
                        audio_data_safe = audio_data.astype(np.float64)
                        rms = np.sqrt(np.mean(audio_data_safe**2))
                        if not np.isnan(rms): self.current_audio_level = int(rms)
                process.terminate()
            except:
                self.is_stream_live = False
                time.sleep(5)

    def _record_clip_process(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"clip_{self.target_channel}_{timestamp}.mp4"
        cmd = ["streamlink", f"twitch.tv/{self.target_channel}", "best", "-o", filename, "--force"]
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(self.record_duration)
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill()
        return filename

    def _handle_recording(self, reason):
        self.log(f"🎥 Start nagrywania ({self.record_duration}s)... Powód: {reason}")
        filename = self._record_clip_process()
        if os.path.exists(filename):
            self.log(f"✅ Zapisano klip: {filename}")
            self.session_clips.append((filename, reason))
        else:
            self.log("❌ Błąd: Plik nie powstał (może brak streamu?).")

    def _main_loop(self):
        t1 = threading.Thread(target=self._monitor_chat); t1.daemon=True; t1.start()
        t2 = threading.Thread(target=self._monitor_audio); t2.daemon=True; t2.start()
        self.log("Systemy monitorowania aktywne.")

        while self.is_running:
            if self.stats_callback:
                self.stats_callback(self.current_audio_level, self.current_chat_velocity, len(self.session_clips), self.is_stream_live)

            if self.is_stream_live:
                time_since_last = time.time() - self.last_clip_time
                triggered = False
                reason = ""
                if time_since_last > self.cooldown_time:
                    if self.current_chat_velocity > self.chat_threshold:
                        triggered = True; reason = f"CHAT ({self.current_chat_velocity:.1f}/s)"
                    elif self.current_audio_level > self.audio_threshold:
                        triggered = True; reason = f"AUDIO ({self.current_audio_level})"
                if triggered:
                    self.log(f"🎬 WYKRYTO: {reason}")
                    threading.Thread(target=self._handle_recording, args=(reason,)).start()
                    self.last_clip_time = time.time()
            time.sleep(0.5)
        self.log("Silnik zatrzymany.")