@echo off
:: Przejdź do folderu z projektem (ważne, żeby pliki zapisały się w dobrym miejscu)
cd /d "C:\Users\Bartek Piwowarczyk\Documents\GitHub\flux-bot-twitch"

:: Uruchom Fluxa używając Pythona z wirtualnego środowiska
".venv\Scripts\python.exe" flux_gui.py

:: Jeśli program się zamknie, nie zamykaj okna od razu (żebyś widział ewentualne błędy)
pause