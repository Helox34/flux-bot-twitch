import requests
import sys

# --- KONFIGURACJA ---
# Wklej tutaj ponownie swoje dane (chyba że już je masz w pliku)
CLIENT_ID = '4uv95tg4zx45b0c98x3amhpr13fng3'       
CLIENT_SECRET = 'o65r6v3s29akfpijrc75drcukfkwv7' 

def get_twitch_access_token():
    """Loguje się i pobiera token (przepustkę)."""
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    try:
        response = requests.post(url, params=params)
        data = response.json()
        return data.get('access_token')
    except Exception as e:
        print(f"❌ Błąd logowania: {e}")
        return None

def get_user_id(nickname, token):
    """Zamienia nick streamera (np. 'shroud') na jego ID liczbowe."""
    url = 'https://api.twitch.tv/helix/users'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {token}'
    }
    params = {'login': nickname}
    
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    
    if data['data']:
        return data['data'][0]['id'] # Zwracamy ID znalezionego użytkownika
    else:
        return None

def check_stream_status(user_id, token):
    """Sprawdza, czy dany numer ID prowadzi teraz transmisję."""
    url = 'https://api.twitch.tv/helix/streams'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {token}'
    }
    params = {'user_id': user_id}
    
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    
    # Jeśli lista 'data' nie jest pusta, to znaczy, że stream trwa
    if data['data']:
        stream_info = data['data'][0]
        return True, stream_info
    else:
        return False, None

# --- GŁÓWNA PĘTLA PROGRAMU ---
if __name__ == "__main__":
    print("🤖 Flux: Uruchamianie systemu...")
    
    # 1. Logowanie
    token = get_twitch_access_token()
    if not token:
        sys.exit() # Koniec programu, jeśli brak tokena

    # 2. Pytamy użytkownika, kogo sprawdzić
    target_streamer = input("\nPodaj nick streamera do sprawdzenia (np. xayoo_, izakooo): ")
    
    # 3. Szukamy ID tego streamera
    print(f"🔍 Szukam ID dla użytkownika {target_streamer}...")
    user_id = get_user_id(target_streamer, token)
    
    if user_id:
        print(f"✅ Znaleziono ID: {user_id}")
        
        # 4. Sprawdzamy status
        is_live, info = check_stream_status(user_id, token)
        
        if is_live:
            print(f"\n🔴 {target_streamer} JEST ONLINE!")
            print(f"Tytuł: {info['title']}")
            print(f"Gra/Kategoria: {info['game_name']}")
            print(f"Widzów: {info['viewer_count']}")
            print("--- Tutaj w przyszłości Flux zacznie nagrywać ---")
        else:
            print(f"\n⚪ {target_streamer} jest offline.")
            print("Flux przechodzi w stan czuwania (na razie kończy pracę).")
            
    else:
        print(f"❌ Nie znaleziono użytkownika o nicku '{target_streamer}'. Sprawdź pisownię.")