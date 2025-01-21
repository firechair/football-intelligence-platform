# chalicelib/organizzazione_evento.py
import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import poisson
import os

# -------------------
#  Funzioni helper
# -------------------

def safe_get(d, *keys, default=None):
    """
    Estrae in modo sicuro valori annidati da un dizionario.
    Esempio: safe_get(event, 'periods', 'num_0', 'team_total', 'home', 'points').
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d

def identifica_value_bets(df, verbose=False, threshold=0.7):
    """
    Identifica le value bets in un DataFrame di quote.
    threshold = soglia di Probabilità Stimata sopra la quale considerare la scommessa.
    """
    # Calcolo delle probabilità implicite
    df['Probabilità Implicita'] = 1 / df['Odds']
    
    # Rimuove eventuali righe con Odds = 0 o negative
    df = df[df['Probabilità Implicita'] > 0]
    
    if verbose:
        print("\n[DEBUG] Probabilità Implicita Originali (prime righe):")
        print(df[['Match ID', 'Bet Type', 'Outcome', 'Probabilità Implicita']].head())
    
    # Calcolo delle probabilità stimate usando Poisson
    def compute_prob(row):
        from math import isfinite
        bet_type = row['Bet Type']
        outcome = row['Outcome']
        hc_points = row.get('Points', 0)
        goals_home = row.get('Gol Previsti Casa', 0)
        goals_away = row.get('Gol Previsti Ospite', 0)

        # Se i gol non sono numerici o sono None, restituisci 0.
        if not (isfinite(goals_home) and isfinite(goals_away)):
            return 0

        if bet_type == 'handicap':
            if outcome == 'Casa':
                # Prob(Casa + Handicap > Ospite)
                prob = 0
                for i in range(0, 10):
                    for j in range(0, 10):
                        if (i + hc_points) > j:
                            prob += poisson.pmf(i, goals_home) * poisson.pmf(j, goals_away)
                if verbose:
                    print(f"[DEBUG] Handicap Casa: Handicap={hc_points}, Prob Stimata={prob:.6f}")
                return prob

            elif outcome == 'Ospite':
                # Prob(Casa + Handicap < Ospite)
                prob = 0
                for i in range(0, 10):
                    for j in range(0, 10):
                        if (i + hc_points) < j:
                            prob += poisson.pmf(i, goals_home) * poisson.pmf(j, goals_away)
                if verbose:
                    print(f"[DEBUG] Handicap Ospite: Handicap={hc_points}, Prob Stimata={prob:.6f}")
                return prob

        elif bet_type in ['total_over', 'total_under']:
            total_goals = goals_home + goals_away
            try:
                points_f = float(hc_points)
            except (TypeError, ValueError):
                return 0

            if bet_type == 'total_over':
                prob_over = 1 - poisson.cdf(points_f + 0.5, total_goals)
                if verbose:
                    print(f"[DEBUG] Total Over: total_goals={total_goals}, prob_over={prob_over:.6f}")
                return prob_over
            else:  # total_under
                prob_under = poisson.cdf(points_f + 0.5, total_goals)
                if verbose:
                    print(f"[DEBUG] Total Under: total_goals={total_goals}, prob_under={prob_under:.6f}")
                return prob_under

        elif bet_type in ['team_total_over', 'team_total_under']:
            team = row.get('Team', 'Home')  # 'Home' o 'Away'
            team_goals = goals_home if team.lower() == 'home' else goals_away

            try:
                points_f = float(hc_points)
            except (TypeError, ValueError):
                return 0

            if bet_type == 'team_total_over':
                prob_over = 1 - poisson.cdf(points_f + 0.5, team_goals)
                if verbose:
                    print(f"[DEBUG] Team Total Over: team_goals={team_goals}, prob_over={prob_over:.6f}")
                return prob_over
            else:  # team_total_under
                prob_under = poisson.cdf(points_f + 0.5, team_goals)
                if verbose:
                    print(f"[DEBUG] Team Total Under: team_goals={team_goals}, prob_under={prob_under:.6f}")
                return prob_under

        return 0

    df['Probabilità Stimata'] = df.apply(compute_prob, axis=1)
    
    # Differenza tra Prob Stimata e Prob Implicita
    df['Differenza'] = df['Probabilità Stimata'] - df['Probabilità Implicita']
    
    # Expected Value
    df['Expected Value'] = (df['Probabilità Stimata'] * df['Odds']) - 1

    # Value Bet se differenza > 0, prob stimata > threshold e EV > 0
    df['Value Bet'] = (
        (df['Differenza'] > 0) &
        (df['Probabilità Stimata'] > threshold) &
        (df['Expected Value'] > 0)
    )
    
    value_bets = df[df['Value Bet']].copy()
    value_bets.sort_values(by='Differenza', ascending=False, inplace=True)
    
    if verbose and not value_bets.empty:
        print("\n[DEBUG] Righe con Differenza >0, Probabilità Stimata > Threshold e Expected Value >0:")
        print(value_bets[[
            'Match ID', 'Bet Type', 'Outcome',
            'Gol Previsti Casa', 'Gol Previsti Ospite',
            'Probabilità Implicita', 'Probabilità Stimata',
            'Differenza', 'Expected Value'
        ]])
    
    return value_bets

def process_single_json(
    filepath,
    verbose=False,
    save_csv=False,
    csv_output_path=None,
    threshold=0.7
):
    """
    Esegue tutta la pipeline di analisi su un singolo file JSON:
    1. Carica il JSON.
    2. Crea un DataFrame con le quote.
    3. Identifica eventuali value bets.
    4. (Opzionale) Salva un CSV con i risultati.

    Parametri:
      - filepath: Percorso del file JSON (può essere locale o in /tmp).
      - verbose: Se True, mostra maggiori dettagli di debug.
      - save_csv: Se True, salva i risultati delle value bets in un CSV.
      - csv_output_path: Path del CSV di output (se None e save_csv=True, genera un nome di default).
      - threshold: soglia di 'Probabilità Stimata' sopra cui considerare "value bet".
    """
    print(f"\n[DEBUG] Carico il file JSON: {filepath}")
    if not os.path.isfile(filepath):
        print(f"Errore: Il file '{filepath}' non esiste.")
        return

    # Caricamento del file
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)
        if verbose:
            # Stampiamo un'anteprima di 1000 caratteri
            json_preview = json.dumps(data, indent=2)[:1000]
            print(f"[DEBUG] Anteprima del JSON:\n{json_preview}...\n")
    except json.JSONDecodeError:
        print(f"Errore nel parsing del file: {filepath}")
        return

    events = data.get('events', [])
    if not events:
        print("[DEBUG] Nessun evento trovato nel JSON.")
        return

    # Creiamo una lista di dizionari (una riga per ciascuna quota)
    data_list = []
    for event in events:
        match_id = safe_get(event, 'event_id')
        data_partita = safe_get(event, 'starts')
        squadra_casa = safe_get(event, 'home')
        squadra_trasferta = safe_get(event, 'away')

        if verbose:
            print(f"\n[DEBUG] ----------\n[DEBUG] Elaboro evento ID: {match_id}")
            print(f"[DEBUG] Data Partita: {data_partita}")
            print(f"[DEBUG] Squadre: {squadra_casa} vs {squadra_trasferta}")

        gol_previsti_casa = safe_get(event, 'periods', 'num_0', 'team_total', 'home', 'points')
        gol_previsti_ospite = safe_get(event, 'periods', 'num_0', 'team_total', 'away', 'points')

        if verbose:
            print(f"[DEBUG] Gol Previsti (Casa={gol_previsti_casa}, Ospite={gol_previsti_ospite})")

        # Se mancano i gol previsti, salto
        if gol_previsti_casa is None or gol_previsti_ospite is None:
            print("[DEBUG] I gol previsti sono None (o mancanti). Salto l'evento.")
            continue

        periods = safe_get(event, 'periods', default={})
        if not periods:
            print("[DEBUG] Nessun periodo trovato per questo evento. Salto l'evento.")
            continue

        # Estrai le varie quote (spreads, totals, team_total) da 'periods'
        for period_key, period_value in periods.items():
            spreads = safe_get(period_value, 'spreads', default={})
            totals = safe_get(period_value, 'totals', default={})
            team_totals = safe_get(period_value, 'team_total', default={})

            # Handicap
            for spread_key, spread_value in spreads.items():
                try:
                    handicap = float(spread_key)
                except ValueError:
                    continue
                quota_casa = spread_value.get('home')
                quota_ospite = spread_value.get('away')

                if quota_casa:
                    try:
                        quota_casa = float(quota_casa)
                        data_list.append({
                            'Match ID': match_id,
                            'Data Partita': data_partita,
                            'Squadra Casa': squadra_casa,
                            'Squadra Trasferta': squadra_trasferta,
                            'Period': period_key,
                            'Bet Type': 'handicap',
                            'Handicap Type': 'Pos/Neg',
                            'Points': handicap,
                            'Team': None,
                            'Odds': quota_casa,
                            'Outcome': 'Casa',
                            'Gol Previsti Casa': gol_previsti_casa,
                            'Gol Previsti Ospite': gol_previsti_ospite
                        })
                    except (TypeError, ValueError):
                        pass

                if quota_ospite:
                    try:
                        quota_ospite = float(quota_ospite)
                        data_list.append({
                            'Match ID': match_id,
                            'Data Partita': data_partita,
                            'Squadra Casa': squadra_casa,
                            'Squadra Trasferta': squadra_trasferta,
                            'Period': period_key,
                            'Bet Type': 'handicap',
                            'Handicap Type': 'Pos/Neg',
                            'Points': handicap,
                            'Team': None,
                            'Odds': quota_ospite,
                            'Outcome': 'Ospite',
                            'Gol Previsti Casa': gol_previsti_casa,
                            'Gol Previsti Ospite': gol_previsti_ospite
                        })
                    except (TypeError, ValueError):
                        pass

            # Totals (Over/Under)
            for points_key, totals_value in totals.items():
                over = totals_value.get('over')
                under = totals_value.get('under')

                if over:
                    try:
                        over_f = float(over)
                        data_list.append({
                            'Match ID': match_id,
                            'Data Partita': data_partita,
                            'Squadra Casa': squadra_casa,
                            'Squadra Trasferta': squadra_trasferta,
                            'Period': period_key,
                            'Bet Type': 'total_over',
                            'Handicap Type': None,
                            'Points': points_key,  # stringa, magari da convertire
                            'Team': None,
                            'Odds': over_f,
                            'Outcome': 'Over',
                            'Gol Previsti Casa': gol_previsti_casa,
                            'Gol Previsti Ospite': gol_previsti_ospite
                        })
                    except (TypeError, ValueError):
                        pass

                if under:
                    try:
                        under_f = float(under)
                        data_list.append({
                            'Match ID': match_id,
                            'Data Partita': data_partita,
                            'Squadra Casa': squadra_casa,
                            'Squadra Trasferta': squadra_trasferta,
                            'Period': period_key,
                            'Bet Type': 'total_under',
                            'Handicap Type': None,
                            'Points': points_key,
                            'Team': None,
                            'Odds': under_f,
                            'Outcome': 'Under',
                            'Gol Previsti Casa': gol_previsti_casa,
                            'Gol Previsti Ospite': gol_previsti_ospite
                        })
                    except (TypeError, ValueError):
                        pass

            # Team Totals
            for team, team_total in team_totals.items():
                team_points = safe_get(team_total, 'points')
                over_tt = team_total.get('over')
                under_tt = team_total.get('under')

                if over_tt:
                    try:
                        over_tt = float(over_tt)
                        data_list.append({
                            'Match ID': match_id,
                            'Data Partita': data_partita,
                            'Squadra Casa': squadra_casa,
                            'Squadra Trasferta': squadra_trasferta,
                            'Period': period_key,
                            'Bet Type': 'team_total_over',
                            'Handicap Type': None,
                            'Points': team_points,
                            'Team': team.capitalize(),  # 'Home' o 'Away'
                            'Odds': over_tt,
                            'Outcome': 'Over',
                            'Gol Previsti Casa': gol_previsti_casa,
                            'Gol Previsti Ospite': gol_previsti_ospite
                        })
                    except (TypeError, ValueError):
                        pass

                if under_tt:
                    try:
                        under_tt = float(under_tt)
                        data_list.append({
                            'Match ID': match_id,
                            'Data Partita': data_partita,
                            'Squadra Casa': squadra_casa,
                            'Squadra Trasferta': squadra_trasferta,
                            'Period': period_key,
                            'Bet Type': 'team_total_under',
                            'Handicap Type': None,
                            'Points': team_points,
                            'Team': team.capitalize(),
                            'Odds': under_tt,
                            'Outcome': 'Under',
                            'Gol Previsti Casa': gol_previsti_casa,
                            'Gol Previsti Ospite': gol_previsti_ospite
                        })
                    except (TypeError, ValueError):
                        pass

    # Creazione DataFrame
    df = pd.DataFrame(data_list)

    if verbose:
        print("\n[DEBUG] Prime righe del DataFrame creato:")
        print(df.head(10).to_string(index=False))

    # Pulizia rapida
    df.dropna(subset=['Odds'], inplace=True)
    df['Odds'] = pd.to_numeric(df['Odds'], errors='coerce')
    df.dropna(subset=['Odds'], inplace=True)

    # Identificazione value bets
    value_bets = identifica_value_bets(df, verbose=verbose, threshold=threshold)

    print("\n💡 Value Bets Identificate:")
    if not value_bets.empty:
        display_columns = [
            'Match ID', 'Squadra Casa', 'Squadra Trasferta',
            'Period', 'Bet Type', 'Handicap Type', 'Points', 'Team',
            'Odds', 'Outcome', 'Probabilità Implicita',
            'Probabilità Stimata', 'Differenza', 'Expected Value'
        ]
        print(value_bets[display_columns].to_string(index=False, float_format=lambda x: f"{x:.6f}"))

        # Se vogliamo salvare un CSV
        if save_csv:
            if csv_output_path is None:
                # default
                csv_output_path = "value_bets.csv"  # in locale
            value_bets[display_columns].to_csv(csv_output_path, index=False, float_format='%.6f')
            print(f"\nLe value bets sono state salvate in '{csv_output_path}'.")
    else:
        print("Nessuna value bet identificata.")

    # Se vuoi stampare un report differenze
    if not value_bets.empty:
        diff_df = value_bets.copy()
        diff_df['Tipo di Scommessa'] = diff_df['Bet Type'] + "_" + diff_df['Outcome']
        diff_df = diff_df[['Tipo di Scommessa', 'Differenza']]
        diff_df.sort_values(by='Differenza', ascending=False, inplace=True)
    
        print("\n📋 Differenze nelle probabilità (top):")
        print(diff_df.head(20).to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    else:
        print("Nessun grafico o differenze da mostrare, nessuna value bet.")

    if verbose:
        print("\n[DEBUG] Elaborazione completata.")

# ---------------
# Esecuzione locale
# ---------------
if __name__ == "__main__":
    # Esempio di percorso locale
    filepath = '/Users/dev/Desktop/test/testapi/json_files/event_1602899962_details.json'
    process_single_json(
        filepath=filepath,
        verbose=True,
        save_csv=True,
        csv_output_path='/Users/dev/Desktop/test/testapi/csv_risultati/value_betsnew6.csv',
        threshold=0.7
    )
