import socket
import threading
import time
import numpy as np
import sys
import subprocess
import streamlink
import os
import datetime

# --- KONFIGURACJA ---
NICKNAME = 'justinfan12345'
# CHANNEL - o to zapyta program przy starcie

# --- PROGI I USTAWIENIA ---
CHAT_THRESHOLD = 3.0       # Msg/s
AUDIO_THRESHOLD = 2000     # Audio RMS
RECORD_DURATION = 30       # Długość klipu w sekundach
COOLDOWN_TIME = 60         # Ile sekund przerwy po nagraniu klipu?

# Zmienne globalne
current_chat_velocity = 0.0
current_audio_level = 0.0
is_stream_live = False
last_clip_time = 0         # Kiedy ostatnio nagrywaliśmy?

class ChatMonitor(threading.Thread):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.messages_window = []

    def run(self):
        global current_chat_velocity
        server = 'irc.chat.twitch.tv'
        sock = socket.socket()
        try:
            sock.connect((server, 6667))
            sock.send(f"NICK {NICKNAME}\n".encode('utf-8'))
            sock.send(f"JOIN #{self.channel}\n".encode('utf-8'))
            
            while True:
                resp = sock.recv(2048).decode('utf-8', 'ignore')
                if resp.startswith('PING'):
                    sock.send("PONG\n".encode('utf-8'))
                elif "PRIVMSG" in resp:
                    now = time.time()
                    self.messages_window.append(now)
                    self.messages_window = [t for t in self.messages_window if now - t <= 10.0]
                    if len(self.messages_window) > 0:
                        current_chat_velocity = len(self.messages_window) / 10.0
                    else:
                        current_chat_velocity = 0
        except:
            pass

class StreamAudioMonitor(threading.Thread):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    def get_stream_url(self):
        try:
            streams = streamlink.streams(f"https://twitch.tv/{self.channel}")
            if not streams: return None
            return streams['audio_only'].url if 'audio_only' in streams else streams['best'].url
        except:
            return None

    def run(self):
        global current_audio_level, is_stream_live
        
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"

        while True:
            stream_url = self.get_stream_url()
            
            if stream_url:
                is_stream_live = True
                
                command = [
                    ffmpeg_cmd, "-i", stream_url, "-f", "s16le", 
                    "-ac", "1", "-ar", "16000", "-vn", "-"
                ]
                
                try:
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    while True:
                        raw_audio = process.stdout.read(4096)
                        if not raw_audio: break
                        
                        audio_data = np.frombuffer(raw_audio, dtype=np.int16)
                        if len(audio_data) > 0:
                            audio_data_safe = audio_data.astype(np.float64)
                            rms = np.sqrt(np.mean(audio_data_safe**2))
                            if not np.isnan(rms):
                                current_audio_level = int(rms)
                except:
                    is_stream_live = False
                    time.sleep(5)
            else:
                is_stream_live = False
                current_audio_level = 0
                time.sleep(10)

def record_clip(channel_name):
    """Nagrywa klip i konwertuje na pion."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename_base = f"clip_{channel_name}_{timestamp}"
    filename_mp4 = f"{filename_base}.mp4"
    
    # 1. Nagrywanie
    cmd_record = [
        "streamlink", f"twitch.tv/{channel_name}", "best", 
        "-o", filename_mp4, "--force"
    ]
    
    # Uruchamiamy nagrywanie w tle (nie blokujemy całego bota, ale czekamy na wynik)
    # W wersji pro: używamy bufora, tu dla prostoty nagrywamy 30s OD MOMENTU wykrycia
    proc = subprocess.Popen(cmd_record, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(RECORD_DURATION)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        
    # 2. Konwersja na pion (TikTok)
    if os.path.exists(filename_mp4):
        ffmpeg_cmd = "./ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
        filename_vertical = f"{filename_base}_vertical.mp4"
        
        cmd_convert = [
            ffmpeg_cmd, "-i", filename_mp4, "-vf", "crop=ih*(9/16):ih", 
            "-c:a", "copy", filename_vertical, "-y"
        ]
        subprocess.run(cmd_convert, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return filename_vertical, timestamp
    return None, None

def generate_summary(channel, session_clips):
    """Tworzy plik tekstowy z podsumowaniem."""
    if not session_clips:
        return
        
    summary_filename = f"SUMMARY_{channel}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
    
    with open(summary_filename, "w", encoding="utf-8") as f:
        f.write(f"RAPORT Z TRANSMISJI: {channel}\n")
        f.write("="*30 + "\n")
        f.write(f"Liczba nagranych klipów: {len(session_clips)}\n\n")
        
        for i, (clip_name, time_taken, trigger_type) in enumerate(session_clips):
            f.write(f"{i+1}. [{time_taken}] - {trigger_type}\n")
            f.write(f"   Plik: {clip_name}\n")
            
    print(f"\n📝 Wygenerowano podsumowanie: {summary_filename}")

# --- START ---
if __name__ == "__main__":
    target = input("Podaj nick streamera: ").lower()
    
    t_chat = ChatMonitor(target)
    t_chat.daemon = True
    t_chat.start()
    
    t_audio = StreamAudioMonitor(target)
    t_audio.daemon = True
    t_audio.start()
    
    print(f"🤖 Flux v0.7: Uruchomiony dla {target}. Czekam na stream...")
    
    # Stan sesji
    was_live_previously = False
    session_clips = [] # Lista tupli: (nazwa_pliku, czas, powod)

    try:
        while True:
            # 1. Obsługa końca streama (Online -> Offline)
            if was_live_previously and not is_stream_live:
                print(f"\n🏁 Stream {target} zakończony (lub przerwa).")
                generate_summary(target, session_clips)
                session_clips = [] # Resetujemy listę na następny stream
                was_live_previously = False
                print("💤 Przechodzę w stan czuwania...")

            # 2. Obsługa początku streama (Offline -> Online)
            if not was_live_previously and is_stream_live:
                print(f"\n🟢 STREAM ONLINE! Rozpoczynam monitoring...")
                was_live_previously = True

            # 3. Główna pętla monitorująca (tylko gdy Online)
            if is_stream_live:
                status = "Monitorowanie..."
                triggered = False
                trigger_reason = ""
                
                # Sprawdzamy cooldowna
                time_since_last = time.time() - last_clip_time
                
                if time_since_last > COOLDOWN_TIME:
                    if current_chat_velocity > CHAT_THRESHOLD:
                        triggered = True
                        trigger_reason = f"CHAT SPAM ({current_chat_velocity:.1f} m/s)"
                    elif current_audio_level > AUDIO_THRESHOLD:
                        triggered = True
                        trigger_reason = f"AUDIO SPIKE ({current_audio_level})"
                
                if triggered:
                    print(f"\n🎬 WYKRYTO MOMENT: {trigger_reason} -> NAGRYWAM!")
                    # Zatrzymujemy na chwilę wypisywanie statusu
                    clip_name, clip_time = record_clip(target)
                    
                    if clip_name:
                        print(f"✅ Zapisano klip: {clip_name}")
                        session_clips.append((clip_name, clip_time, trigger_reason))
                        last_clip_time = time.time()
                    else:
                        print("❌ Błąd nagrywania.")

                # Pasek statusu
                sys.stdout.write(f"\r[{status}] Czat: {current_chat_velocity:.1f} | Audio: {current_audio_level} | Klipy w sesji: {len(session_clips)}   ")
                sys.stdout.flush()
            else:
                # Tryb oszczędzania energii (gdy offline)
                sys.stdout.write(f"\r💤 Czuwanie (Offline)... Sprawdzam za 10s...        ")
                sys.stdout.flush()
                time.sleep(10)

            time.sleep(0.2)

    except KeyboardInterrupt:
        if session_clips:
            generate_summary(target, session_clips)
        print("\n🛑 Flux zatrzymany.")