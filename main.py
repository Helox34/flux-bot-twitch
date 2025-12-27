import requests
import sys
import subprocess
import time
import os

# --- TWOJE DANE ---
CLIENT_ID = '4uv95tg4zx45b0c98x3amhpr13fng3'       
CLIENT_SECRET = 'o65r6v3s29akfpijrc75drcukfkwv7' 

def get_twitch_access_token():
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'client_credentials'
    }
    try:
        response = requests.post(url, params=params)
        return response.json().get('access_token')
    except:
        return None

def get_user_id(nickname, token):
    headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.twitch.tv/helix/users', headers=headers, params={'login': nickname})
    data = response.json()
    return data['data'][0]['id'] if data['data'] else None

def check_stream_status(user_id, token):
    headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.twitch.tv/helix/streams', headers=headers, params={'user_id': user_id})
    data = response.json()
    if data['data']:
        return True, data['data'][0]
    return False, None

def record_stream_sample(streamer_nick, duration=30):
    """Nagrywa stream przez określoną liczbę sekund."""
    print(f"\n🎥 Flux: Rozpoczynam nagrywanie {streamer_nick} na {duration} sekund...")
    
    filename = f"{streamer_nick}_test.mp4"
    twitch_url = f"twitch.tv/{streamer_nick}"
    
    # Komenda uruchamiająca streamlink
    # To tak, jakbyś wpisał w konsoli: streamlink twitch.tv/nick best -o plik.mp4
    command = [
        "streamlink",
        twitch_url,
        "best",             # Najlepsza jakość
        "-o", filename,     # Nazwa pliku wyjściowego
        "--force"           # Nadpisz plik, jeśli istnieje
    ]
    
    try:
        # Uruchamiamy proces w tle
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Czekamy (nagrywamy)
        time.sleep(duration)
        
        # Kończymy nagrywanie
        print("🛑 Flux: Koniec czasu! Zatrzymywanie nagrywania...")
        process.terminate()
        
        print(f"✅ Gotowe! Sprawdź plik: {filename} w folderze projektu.")
        
    except FileNotFoundError:
        print("❌ Błąd: Nie znaleziono programu 'streamlink'. Upewnij się, że zainstalowałeś go przez pip.")

# --- START ---
if __name__ == "__main__":
    print("🤖 Flux: System gotowy.")
    token = get_twitch_access_token()
    
    target = input("\nPodaj nick do nagrania (np. MelaPustelnik): ")
    user_id = get_user_id(target, token)
    
    if user_id:
        is_live, info = check_stream_status(user_id, token)
        if is_live:
            print(f"🔴 {target} jest LIVE! (Widzów: {info['viewer_count']})")
            # Uruchamiamy nagrywanie próbne
            record_stream_sample(target)
        else:
            print(f"⚪ {target} jest offline.")
    else:
        print("❌ Nie znaleziono streamera.")