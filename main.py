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
import json  # Potrzebne do zapisywania listy

# --- IMPORTY DLA MINERA ---
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Settings import Priority, FollowersOrder

# --- TWOJE DANE ---
CLIENT_ID = '4uv95tg4zx45b0c98x3amhpr13fng3'       
CLIENT_SECRET = 'o65r6v3s29akfpijrc75drcukfkwv7' 

USER_NICK = 'helox343' 
USER_TOKEN = 'oauth:34hx48t13eomojbosd757cj4h5gfer'

# Plik, w którym zapisujemy listę streamerów
STREAMERS_FILE = "streamers_list.json"
# Domyślna lista (jeśli plik nie istnieje)
DEFAULT_STREAMERS = ["MrDzinold", "MelaPustelnik", "Diables", "Kasix", "Fernatka", "PAGO3", "IzakOOO"]

# --- FUNKCJE OBSŁUGI LISTY STREAMERÓW ---
def load_streamers():
    """Wczytuje listę z pliku JSON. Jeśli brak pliku, tworzy go."""
    if not os.path.exists(STREAMERS_FILE):
        save_streamers(DEFAULT_STREAMERS)
        return DEFAULT_STREAMERS
    try:
        with open(STREAMERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return DEFAULT_STREAMERS

def save_streamers(lista):
    """Zapisuje listę do pliku JSON."""
    with open(STREAMERS_FILE, 'w') as f:
        json.dump(lista, f)

def add_streamer_to_file(nick):
    current = load_streamers()
    if nick not in current:
        current.append(nick)
        save_streamers(current)
        return True
    return False

def remove_streamer_from_file(nick):
    current = load_streamers()
    if nick in current:
        current.remove(nick)
        save_streamers(current)
        return True
    return False

# --- SILNIK FLUX ---
class FluxEngine:
    def __init__(self):
        self.is_running = False
        self.target_channel = ""
        self.log_callback = None
        self.stats_callback = None
        
        self.current_chat_velocity = 0.0
        self.current_audio_level = 0.0
        self.is_stream_live = False
        self.session_clips = []
        
        self.chat_threshold = 3.0
        self.audio_threshold = 2000
        self.cooldown_time = 60
        self.record_duration = 60 
        
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
        server = 'irc.chat.twitch.tv'
        sock = socket.socket()
        msgs = []
        try:
            sock.connect((server, 6667))
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

                if not self.dvr_process:
                    self._start_dvr_recording(streams)

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
        stream_url = streams['best'].url
        self.stream_start_time = time.time()
        self.log("📼 DVR: Buforowanie wideo...")
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        cmd = [ffmpeg_cmd, "-i", stream_url, "-c", "copy", "-f", "mpegts", "-y", self.dvr_filename]
        self.dvr_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _cut_clip_from_dvr(self, reason):
        if not os.path.exists(self.dvr_filename): return
        now = time.time()
        offset_end = now - self.stream_start_time + 10 
        offset_start = max(0, offset_end - 40)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_name = f"clip_{self.target_channel}_{timestamp}.mp4"
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        cmd = [ffmpeg_cmd, "-i", self.dvr_filename, "-ss", str(offset_start), "-to", str(offset_end), "-c", "copy", "-y", out_name]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_name

    def _handle_trigger(self, reason):
        self.log(f"🎬 WYKRYTO: {reason} -> Zapis klipu...")
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
            if self.is_stream_live and self.dvr_process:
                time_since_last = time.time() - self.last_trigger_time
                triggered = False
                reason = ""
                if time_since_last > self.cooldown_time:
                    if (time.time() - self.stream_start_time) > 30:
                        if self.current_chat_velocity > self.chat_threshold:
                            triggered = True; reason = f"CHAT ({self.current_chat_velocity:.1f}/s)"
                        elif self.current_audio_level > self.audio_threshold:
                            triggered = True; reason = f"AUDIO ({self.current_audio_level})"
                if triggered:
                    threading.Thread(target=self._handle_trigger, args=(reason,)).start()
                    self.last_trigger_time = time.time()
            time.sleep(0.5)
        if self.dvr_process: self.dvr_process.terminate()
        if os.path.exists(self.dvr_filename):
            try: os.remove(self.dvr_filename)
            except: pass

# --- KLASA MINERA ---
class PointMiner:
    def __init__(self):
        self.is_mining = False
        clean_token = USER_TOKEN.replace("oauth:", "")
        
        # Inicjalizujemy bibliotekę
        self.miner = TwitchChannelPointsMiner(
            username=USER_NICK,
            password=clean_token,
            claim_drops_startup=True,
            priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER]
        )

    def start(self):
        if self.is_mining: return
        self.is_mining = True
        
        # Ładujemy aktualną listę z pliku przed startem
        targets = load_streamers()
        
        t = threading.Thread(target=self._mine_process, args=(targets,))
        t.daemon = True
        t.start()

    def _mine_process(self, targets):
        print(f"⛏️ [MINER] Start dla: {USER_NICK}")
        print(f"🎯 [MINER] Cele (z pliku): {targets}")
        try:
            self.miner.mine(
                targets,
                followers=False,
                followers_order=FollowersOrder.ASC
            )
        except Exception as e:
            print(f"❌ [MINER] Błąd: {e}")