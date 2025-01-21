# partite.py (Versione Modificata per Lambda/Chalice)
import requests
import json

# Configurazione API (potresti recuperare la key da variabile d'ambiente se preferisci)
URL = "https://Bookmaker H-odds.p.rapidapi.com/kit/v1/markets"
PARAMS = {
    "sport_id": 1,    # ID Sport (Calcio)
    "is_have_odds": "true"
}
HEADERS = {
    "x-rapidapi-key": "REDACTED",
    "x-rapidapi-host": "Bookmaker H-odds.p.rapidapi.com"
}

def scarica_partite_serie_a():
    """
    Scarica i dati delle partite di Serie A (league_id=2436) dall'API 
    e ritorna la lista di eventi come Python dict (list of dict).
    """
    try:
        print("🌐 Richiesta dati delle partite di Serie A...")
        response = requests.get(URL, headers=HEADERS, params=PARAMS)
        print(f"🔄 Stato della risposta: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            # Filtra solo le partite con league_id == 2436 (Serie A)
            serie_a_events = [event for event in events if event.get('league_id') == 2436]

            if not serie_a_events:
                print("❌ Nessuna partita di Serie A trovata nei dati ricevuti.")
            else:
                print(f"✅ Trovate {len(serie_a_events)} partite di Serie A.")
            
            return serie_a_events

        else:
            print(f"❌ Errore: {response.status_code} - {response.text}")
            return []

    except requests.exceptions.RequestException as e:
        print(f"❌ Errore nella richiesta API: {e}")
        return []

def salva_partite_in_locale(partite, filename="partite_serie_a.json"):
    """
    Salva la lista di partite in un file locale (in JSON).
    """
    with open(filename, "w") as file:
        json.dump(partite, file, indent=4)
    print(f"✅ Dati delle partite di Serie A salvati in '{filename}'.")

def stampa_riassunto_partite(partite):
    """
    Stampa un riassunto in console.
    """
    for event in partite:
        print(f"⚽ Partita: {event.get('home')} vs {event.get('away')}")
        print(f"📅 Data: {event.get('starts')}")
        print(f"🆔 ID Evento: {event.get('event_id')}")
        print("-" * 20)

# Esempio: se vuoi ancora poterlo eseguire a riga di comando:
if __name__ == "__main__":
    serie_a_events = scarica_partite_serie_a()
    if serie_a_events:
        salva_partite_in_locale(serie_a_events)
        stampa_riassunto_partite(serie_a_events)
