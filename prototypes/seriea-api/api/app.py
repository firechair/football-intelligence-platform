# api/app.py
from flask import Flask, request, jsonify
import os

# Importa le tue funzioni dai moduli nella cartella api/
from partite import (
    scarica_partite_serie_a,
    salva_partite_in_locale,
    stampa_riassunto_partite
)
from raccolta import (
    fetch_event_data,
    raccogli_dettagli_eventi,
    raccogli_dettagli_eventi_da_lista
)
from organizzazione_evento import process_single_json

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    """
    Endpoint di base, per testare se l'app funziona.
    """
    return jsonify({"hello": "world"})

@app.route("/partite", methods=["GET"])
def get_partite():
    """
    1) Scarica le partite di Serie A da Bookmaker H (via RapidAPI).
    2) Restituisce la lista di partite in formato JSON.

    Opzionalmente, salva il file su /tmp/partite_serie_a.json se vuoi riutilizzarlo.
    """
    # 1. Scarica in memoria
    partite = scarica_partite_serie_a()
    
    # 2. (Opzionale) Salva su /tmp per riuso successivo
    #    Se preferisci tenerlo in locale in environment di test, modifica il path
    path_local = "/tmp/partite_serie_a.json"
    salva_partite_in_locale(partite, path_local)  # funzione del tuo file partite.py

    # 3. (Opzionale) stampa un riassunto sul log
    stampa_riassunto_partite(partite)

    # 4. Restituisce in JSON
    return jsonify({
        "numero_di_partite": len(partite),
        "partite": partite
    })

@app.route("/raccolta", methods=["GET"])
def do_raccolta():
    """
    1) Legge /tmp/partite_serie_a.json creato da /partite
    2) Crea N file JSON (uno per match) contenenti tutti i dati delle quote
       (es. /tmp/json_files/event_{ID}_details.json per ogni match)
    """
    input_json_path = "/tmp/partite_serie_a.json"
    output_folder = "/tmp/json_files"

    # Se non esiste la cartella /tmp/json_files, la crea
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Usa la funzione di raccolta
    raccogli_dettagli_eventi(input_json_path, output_folder)

    # Potresti restituire la lista degli event_id raccolti o un semplice "OK"
    return jsonify({"status": "OK", "message": f"Dati salvati in {output_folder}"})

@app.route("/analizza", methods=["POST"])
def analizza_match():
    """
    1) Riceve in POST un body JSON con la chiave 'filename' o 'filepath',
       che indica quale file JSON del singolo match analizzare.
    2) Esegue process_single_json per calcolare value bets, pronostico, ecc.
    3) Restituisce i risultati o un messaggio di output.

    Esempio di body JSON:
    {
      "filename": "event_1602899962_details.json"
    }
    """
    data = request.get_json()
    if not data or "filename" not in data:
        return jsonify({"error": "Devi fornire 'filename' nel body JSON."}), 400

    # In questo esempio, i file si trovano in /tmp/json_files
    filename = data["filename"]
    filepath = f"/tmp/json_files/{filename}"

    if not os.path.exists(filepath):
        return jsonify({"error": f"File non trovato: {filepath}"}), 404

    # Esegui la funzione di analisi
    # Nota: puoi decidere se salvare un CSV in /tmp, se lo desideri
    process_single_json(
        filepath=filepath,
        verbose=True,
        save_csv=False,          # Metti True se vuoi salvare un CSV
        csv_output_path=None,    # Se True, potresti usare "/tmp/value_bets.csv"
        threshold=0.7
    )

    return jsonify({"status": "OK", "analizzato": filepath})

# Per debug locale
if __name__ == "__main__":
    app.run(debug=True)
