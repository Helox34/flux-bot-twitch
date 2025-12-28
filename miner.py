from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import Chat
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings

# --- TWOJA KONFIGURACJA ---
USERNAME = "helox343"
# Token bez "oauth:" (biblioteka sama to ogarnia lub przyjmuje czysty)
TOKEN = "34hx48t13eomojbosd757cj4h5gfer" 

# Lista streamerów, u których chcesz zbierać punkty
# Możesz dodać więcej po przecinku, np. ["MrDzinold", "Xayoo_", "MelaPustelnik"]
TARGET_STREAMERS = ["MrDzinold", "MelaPustelnik"] 

# --- KONFIGURACJA STRATEGII ---
miner = TwitchChannelPointsMiner(
    username=USERNAME,
    password=TOKEN,      # Twój token OAuth
    claim_drops_startup=True, # Zbieraj dropy (np. do gier)
    priority=[           # Co jest najważniejsze?
        Priority.STREAK, # Ciągłość oglądania
        Priority.DROPS,  # Dropy
        Priority.ORDER   # Kolejność z listy
    ],
    logger_settings=None, # Domyślne logi w konsoli
    streamer_settings=None
)

# --- START KOPANIA ---
print(f"⛏️ Uruchamiam Minera dla: {USERNAME}")
print(f"🎯 Cele: {TARGET_STREAMERS}")

miner.mine(
    TARGET_STREAMERS,
    followers=False,        # Nie kop u wszystkich, których obserwujesz (tylko z listy wyżej)
    chat_presence=True,     # Bądź widoczny na czacie (ważne dla Watchtime!)
    followers_order=FollowersOrder.ASC,
    
    # --- OBSTAWIANIE ZAKŁADÓW (PREDICTIONS) ---
    # Ustawione na bezpieczną strategię: 
    # Bot patrzy na co głosuje większość ludzi i obstawia to samo, ale małą kwotą.
    bet_settings=BetSettings(
        strategy=Strategy.SMART, # Analizuje szanse
        percentage=5,            # Stawia 5% posiadanych punktów (bezpiecznie)
        max_points=500,          # Maksymalnie 500 pkt na jeden zakład
        filter_condition=None
    )
)