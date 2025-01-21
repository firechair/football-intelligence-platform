# chalicelib/json_explorer.py (o semplicemente json_explorer.py se lo usi localmente)

import json
import os

def explore_json(data, prefix='root', depth=0, max_depth=5, key_counts=None):
    """
    Esplora ricorsivamente un oggetto JSON per comprenderne la struttura.

    Parameters:
    - data: Il dizionario o lista JSON da esplorare.
    - prefix: Il percorso corrente nella struttura JSON.
    - depth: Profondità corrente della ricorsione.
    - max_depth: Profondità massima da esplorare.
    - key_counts: Dizionario per contare le occorrenze delle chiavi.
    """
    if key_counts is None:
        key_counts = {}

    if depth > max_depth:
        print(f"{prefix}: ... (profondità massima raggiunta)")
        return key_counts

    if isinstance(data, dict):
        print(f"{'  ' * depth}[DICT] {prefix} -> {len(data)} chiavi")
        for key, value in data.items():
            full_key = prefix + '.' + key
            key_counts[full_key] = key_counts.get(full_key, 0) + 1
            explore_json(value, full_key, depth + 1, max_depth, key_counts)

    elif isinstance(data, list):
        print(f"{'  ' * depth}[LIST] {prefix} -> {len(data)} elementi")
        for i, item in enumerate(data[:3]):  # Mostra solo i primi 3 elementi
            explore_json(item, f"{prefix}[{i}]", depth + 1, max_depth, key_counts)
        if len(data) > 3:
            print(f"{'  ' * (depth + 1)}... ({len(data) - 3} altri elementi)")

    else:
        # È un valore semplice (stringa, int, float, bool, None)
        print(f"{'  ' * depth}[VALUE] {prefix} -> {type(data).__name__}: {repr(data)}")

    return key_counts

def save_structure_to_file(key_counts, output_filepath):
    """
    Salva la struttura esplorata del JSON in un file TXT.

    Parameters:
    - key_counts: Dizionario delle chiavi con le occorrenze.
    - output_filepath: Percorso del file di output (può essere in locale o /tmp).
    """
    with open(output_filepath, 'w', encoding='utf-8') as f:
        f.write("🔍 Struttura del file JSON\n\n")
        for key, count in key_counts.items():
            f.write(f"{key} -> Occorrenze: {count}\n")
    print(f"\n📄 Struttura salvata in: {output_filepath}")

def analyze_json_data(data, output_filepath=None, max_depth=5):
    """
    Esplora un JSON già caricato in memoria (dict o list) e,
    se specificato, salva la struttura in output_filepath.

    Parameters:
    - data: il contenuto JSON (dict/list) già in memoria.
    - output_filepath: se non è None, salva la struttura su file (locale o /tmp).
    - max_depth: profondità massima di esplorazione.
    """
    print("\n🔍 Esplorazione JSON in memoria\n")
    key_counts = explore_json(data, max_depth=max_depth)
    if output_filepath is not None:
        save_structure_to_file(key_counts, output_filepath)
    return key_counts

def analyze_json_file(filepath, output_filepath='json_structure.txt', max_depth=5):
    """
    Carica ed esplora un file JSON dal percorso specificato (filepath).
    Poi, salva il risultato nel file di output (output_filepath).

    Parameters:
    - filepath: Percorso del file JSON (locale o /tmp).
    - output_filepath: Percorso del file di output (locale o /tmp).
    - max_depth: Profondità massima da esplorare.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)

        print(f"\n🔍 Esplorazione del file JSON: {filepath}\n")
        key_counts = explore_json(data, max_depth=max_depth)
        # Salvataggio su file (se vuoi disabilitarlo, passa output_filepath=None)
        if output_filepath:
            save_structure_to_file(key_counts, output_filepath)

    except json.JSONDecodeError:
        print("❌ Errore nel parsing del file JSON.")
    except FileNotFoundError:
        print(f"❌ File non trovato: {filepath}")
    except Exception as e:
        print(f"❌ Errore inaspettato: {e}")

# ESECUZIONE DIRETTA DA TERMINALE
if __name__ == '__main__':
    # Qui mettiamo un esempio di utilizzo in locale (puoi cambiare i percorsi).
    # Se lo esegui in una lambda, userai i percorsi /tmp/ passandoli come parametri
    # dalla tua funzione app.py di Chalice (oppure con un if, etc.).

    # Percorsi di esempio in locale (cambia con i tuoi)
    filepath = '/Users/dev/Desktop/test/testapi/json_files/event_1602202357_details.json'
    output_filepath = '/Users/dev/Desktop/test/testapi/json_files/json_structure.txt'

    # Esempio di esecuzione
    analyze_json_file(filepath, output_filepath, max_depth=5)

    # Oppure, se volessi salvare/leggere in /tmp/ (solo come dimostrazione):
    # analyze_json_file("/tmp/event_1602202357_details.json", "/tmp/json_structure.txt")
