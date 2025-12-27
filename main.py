import socket
import threading
import time
import numpy as np
import sys
import subprocess
import streamlink

# --- KONFIGURACJA ---
NICKNAME = 'justinfan12345' 
CHANNEL = 'mrzdinold'   # Nick streamera (małe litery!)
# TOKEN nie jest potrzebny do samego czytania czatu w trybie anonimowym

# --- PROGI CZUŁOŚCI ---
CHAT_THRESHOLD = 3.0       # Wiadomości na sekundę
AUDIO_THRESHOLD = 2000     # Próg głośności cyfrowej (0-30000)

# Zmienne globalne
current_chat_velocity = 0.0
current_audio_level = 0.0
is_stream_live = False

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
                    # Liczymy średnią z ostatnich 10 sekund
                    self.messages_window = [t for t in self.messages_window if now - t <= 10.0]
                    if len(self.messages_window) > 0:
                        current_chat_velocity = len(self.messages_window) / 10.0
                    else:
                        current_chat_velocity = 0
        except Exception as e:
            print(f"Błąd czatu: {e}")

class StreamAudioMonitor(threading.Thread):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    def get_stream_url(self):
        try:
            streams = streamlink.streams(f"https://twitch.tv/{self.channel}")
            if not streams:
                return None
            return streams['audio_only'].url if 'audio_only' in streams else streams['best'].url
        except:
            return None

    def run(self):
        global current_audio_level, is_stream_live
        
        while True:
            # 1. Pobierz URL strumienia
            stream_url = self.get_stream_url()
            
            if stream_url:
                is_stream_live = True
                
                # 2. Uruchom FFmpeg, który wypluwa surowe audio (PCM 16-bit) na wyjście (pipe)
                command = [
                    "ffmpeg",
                    "-i", stream_url,
                    "-f", "s16le",       # Format: surowe 16-bitowe liczby
                    "-ac", "1",          # Mono (jeden kanał wystarczy)
                    "-ar", "16000",      # Próbkowanie 16kHz (oszczędność CPU)
                    "-vn",               # Bez wideo
                    "-"                  # Wyjście na standardowe wyjście (stdout)
                ]
                
                # Uruchamiamy proces
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL # Ukryj logi FFmpeg
                )
                
                # 3. Czytaj dane w pętli
                while True:
                    # Czytaj próbkę danych (np. 4096 bajtów)
                    raw_audio = process.stdout.read(4096)
                    
                    if not raw_audio:
                        break # Strumień się urwał
                        
                    # Zamiana bajtów na liczby
                    audio_data = np.frombuffer(raw_audio, dtype=np.int16)
                    
                    # Oblicz średnią głośność (RMS)
                    if len(audio_data) > 0:
                        rms = np.sqrt(np.mean(audio_data**2))
                        current_audio_level = int(rms)
                    
            else:
                is_stream_live = False
                current_audio_level = 0
                time.sleep(10) # Jak offline, to sprawdź znowu za 10s

# --- START ---
if __name__ == "__main__":
    target = input("Podaj nick streamera: ").lower()
    
    # Uruchamiamy wątki
    t_chat = ChatMonitor(target)
    t_chat.daemon = True
    t_chat.start()
    
    t_audio = StreamAudioMonitor(target)
    t_audio.daemon = True
    t_audio.start()
    
    print(f"🎧 Flux Server: Nasłuchuję kanału {target}...")
    print("Oczekuję na dane (może to potrwać kilka sekund)...")

    try:
        while True:
            status = "Cisza..."
            
            # Logika
            if current_chat_velocity > CHAT_THRESHOLD: status = "🔥 CHAT SPAM!"
            if current_audio_level > AUDIO_THRESHOLD:  status = "🔊 KRZYK!"
            if not is_stream_live: status = "OFFLINE"
            
            # Pasek stanu
            sys.stdout.write(f"\rStatus: [{status}] | Czat: {current_chat_velocity:.1f} m/s | Audio Level: {current_audio_level}   ")
            sys.stdout.flush()
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\nKoniec.")