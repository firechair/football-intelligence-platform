# chalicelib/raccolta.py (o semplicemente raccolta.py)
import os
import json
import requests
import time

# Configurazione API per Dettagli Evento
URL_DETAILS = "https://Bookmaker H-odds.p.rapidapi.com/kit/v1/details"
HEADERS = {
    "x-rapidapi-key": "REDACTED",
    "x-rapidapi-host": "Bookmaker H-odds.p.rapidapi.com"
}

def fetch_event_data(event_id, max_attempts=5):
    """
    Effettua la richiesta API per un singolo evento, ritentando in caso di errore 429 (rate limit).
    Ritorna il dizionario JSON con i dettagli dell'evento, oppure None in caso di fallimento.
    """
    for attempt in range(max_attempts):
        response = requests.get(URL_DETAILS, headers=HEADERS, params={"event_id": event_id})
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            wait_time = 2 ** attempt  # Tempo di attesa crescente: 1s, 2s, 4s, ...
            print(f"⏳ Errore 429 (rate limit), attendo {wait_time} secondi prima di riprovare...")
            time.sleep(wait_time)
        else:
            print(f"❌ Errore con evento {event_id}: {response.status_code} - {response.text}")
            return None

    print(f"❌ Errore persistente con evento {event_id}. Superato il numero massimo di tentativi.")
    return None

def raccogli_dettagli_eventi(
        input_json_path="partite_serie_a.json", 
        output_folder="json_files"
    ):
    """
    1. Legge la lista di eventi da 'input_json_path' (file JSON).
    2. Estrae gli 'event_id' da ogni evento.
    3. Per ogni 'event_id' effettua una chiamata API per i dettagli dell'evento.
    4. Salva un file JSON per ogni evento in 'output_folder'.

    Parametri:
      - input_json_path: percorso del file JSON di input (es: 'partite_serie_a.json')
      - output_folder: cartella di output per i file JSON (es: 'json_files' o '/tmp' su Lambda)
    """
    # Verifica che la cartella di output esista (in locale o /tmp)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"📂 Cartella '{output_folder}' creata.")

    # Carica la lista di eventi
    try:
        with open(input_json_path, "r") as f:
            events = json.load(f)
        print(f"✅ File '{input_json_path}' caricato correttamente.")
    except FileNotFoundError:
        print(f"❌ Errore: il file '{input_json_path}' non è stato trovato.")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Errore durante la decodifica del JSON: {e}")
        return

    # Estrai gli 'event_id'
    event_ids = [event["event_id"] for event in events if "event_id" in event]
    if not event_ids:
        print("❌ Nessun 'event_id' trovato nel file JSON.")
        return
    
    print(f"🔄 Lista degli 'event_id' estratti: {event_ids}")

    # Richiama l'API per ogni evento e salva i dettagli
    for event_id in event_ids:
        print(f"🔄 Richiesta per evento ID: {event_id}")
        data = fetch_event_data(event_id)
        
        if data:
            file_path = os.path.join(output_folder, f"event_{event_id}_details.json")
            with open(file_path, "w") as file:
                json.dump(data, file, indent=4)
            print(f"📊 Dati evento {event_id} salvati in '{file_path}'")

def raccogli_dettagli_eventi_da_lista(
        events, 
        output_folder="json_files"
    ):
    """
    Variante di 'raccogli_dettagli_eventi' che riceve la lista 'events' già in memoria
    anziché un file JSON.
    
    1. Estrae gli 'event_id' da 'events'.
    2. Per ogni 'event_id' effettua la chiamata API.
    3. Salva i singoli file in 'output_folder'.

    Parametri:
      - events: lista di dict (gli eventi da processare).
      - output_folder: cartella di output per i file JSON.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"📂 Cartella '{output_folder}' creata.")

    event_ids = [event["event_id"] for event in events if "event_id" in event]
    if not event_ids:
        print("❌ Nessun 'event_id' trovato nella lista di eventi.")
        return

    print(f"🔄 Lista degli 'event_id' estratti: {event_ids}")

    for event_id in event_ids:
        print(f"🔄 Richiesta per evento ID: {event_id}")
        data = fetch_event_data(event_id)
        
        if data:
            file_path = os.path.join(output_folder, f"event_{event_id}_details.json")
            with open(file_path, "w") as file:
                json.dump(data, file, indent=4)
            print(f"📊 Dati evento {event_id} salvati in '{file_path}'")

# ESECUZIONE LOCALE (riga di comando)
if __name__ == '__main__':
    """
    Esempio di esecuzione in LOCALE.
    Leggerà 'partite_serie_a.json' e scriverà i file dei match in 'json_files'.
    Cambia i percorsi se vuoi.
    """
    local_input = "partite_serie_a.json"
    local_output = "json_files"  # In locale
    raccogli_dettagli_eventi(local_input, local_output)
