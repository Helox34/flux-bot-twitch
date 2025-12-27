import socket
import threading
import time
import numpy as np
import sounddevice as sd
import sys

# --- KONFIGURACJA UŻYTKOWNIKA ---
NICKNAME = 'justinfan123' # Anonimowy nick (wystarczy do odczytu czatu)
TOKEN = 'oauth:twoj_token_tutaj' # Tu wpisz swój token, jeśli chcesz pisać (do odczytu czasem nie trzeba, ale warto dać)
CHANNEL = 'mrzdinold' # Nick streamera (małymi literami!)

# --- PROGI CZUŁOŚCI (Możesz zmieniać) ---
CHAT_THRESHOLD = 2.0     # Ile wiadomości na sekundę uznajemy za "dużo"?
AUDIO_THRESHOLD = 15.0   # Jak głośno musi być? (skala orientacyjna)

# Zmienne współdzielone (dostępne dla wszystkich wątków)
current_chat_velocity = 0.0
current_audio_level = 0.0
is_running = True

class ChatMonitor(threading.Thread):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.messages_window = [] # Lista czasów nadejścia wiadomości

    def run(self):
        global current_chat_velocity
        server = 'irc.chat.twitch.tv'
        port = 6667
        sock = socket.socket()
        
        try:
            sock.connect((server, port))
            sock.send(f"PASS {TOKEN}\n".encode('utf-8'))
            sock.send(f"NICK {NICKNAME}\n".encode('utf-8'))
            sock.send(f"JOIN #{self.channel}\n".encode('utf-8'))
            
            print(f"💬 Czat: Podłączono do #{self.channel}")

            while is_running:
                resp = sock.recv(2048).decode('utf-8')
                
                # Ping-Pong (żeby Twitch nas nie rozłączył)
                if resp.startswith('PING'):
                    sock.send("PONG\n".encode('utf-8'))
                
                elif "PRIVMSG" in resp:
                    # Każda nowa wiadomość to znacznik czasu
                    now = time.time()
                    self.messages_window.append(now)
                    
                    # Usuwamy wiadomości starsze niż 5 sekund (okno czasowe)
                    self.messages_window = [t for t in self.messages_window if now - t <= 5.0]
                    
                    # Obliczamy prędkość: liczba wiadomości / 5 sekund
                    if len(self.messages_window) > 0:
                        current_chat_velocity = len(self.messages_window) / 5.0
                    else:
                        current_chat_velocity = 0
                        
        except Exception as e:
            print(f"❌ Błąd czatu: {e}")

class AudioMonitor(threading.Thread):
    def run(self):
        global current_audio_level
        
        def callback(indata, frames, time, status):
            global current_audio_level
            if status:
                print(status)
            # Obliczamy głośność (RMS - Root Mean Square)
            volume_norm = np.linalg.norm(indata) * 10
            current_audio_level = int(volume_norm)

        # Nasłuchujemy domyślnego urządzenia wejściowego (Mikrofon lub Stereo Mix)
        try:
            with sd.InputStream(callback=callback, channels=1):
                while is_running:
                    sd.sleep(100)
        except Exception as e:
            print(f"❌ Błąd audio: {e}")
            print("Upewnij się, że masz podłączony mikrofon lub włączony Stereo Mix.")

# --- GŁÓWNA PĘTLA ---
if __name__ == "__main__":
    target_channel = input("Podaj nick streamera (np. mrzdinold): ").lower()
    
    # 1. Start wątku Audio
    audio_thread = AudioMonitor()
    audio_thread.daemon = True # Wątek zamknie się razem z programem
    audio_thread.start()
    
    # 2. Start wątku Czat
    chat_thread = ChatMonitor(target_channel)
    chat_thread.daemon = True
    chat_thread.start()

    print("\n🧠 Flux Brain: Analiza rozpoczęta. Wciśnij Ctrl+C aby przerwać.\n")
    print(f"Progi: Czat > {CHAT_THRESHOLD} msg/s | Audio > {AUDIO_THRESHOLD}")

    try:
        while True:
            # Formatowanie wyjścia w jednej linii (\r nadpisuje linię)
            status = "SPOKÓJ"
            
            # Logika decyzyjna
            triggered = False
            
            if current_chat_velocity > CHAT_THRESHOLD:
                status = "🔥 SZYBKI CZAT!"
                triggered = True
            
            if current_audio_level > AUDIO_THRESHOLD:
                status = "🔊 GŁOŚNO!"
                triggered = True
                
            if current_chat_velocity > CHAT_THRESHOLD and current_audio_level > AUDIO_THRESHOLD:
                 status = "🔥🔥🔥 OMEGA MOMENT!"
                 triggered = True

            # Wyświetlanie
            output = f"\rCzat: {current_chat_velocity:.1f} msg/s | Audio: {current_audio_level:.1f} | Status: {status}"
            
            if triggered:
                 # Tutaj w przyszłości będzie funkcja: save_buffer_to_disk()
                 output += " -> 🎬 NAGRYWAM TERAZ! "
            
            sys.stdout.write(f"{output:<80}") # <80 czyści resztę linii
            sys.stdout.flush()
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        is_running = False
        print("\n\n🛑 Zatrzymano.")