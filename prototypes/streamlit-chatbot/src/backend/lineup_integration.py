# src/backend/lineup_integration.py
"""
This module implements integration for soccer team lineup retrieval and analysis.
It provides functions to extract, parse, and present lineup data in a format optimized
for LLM processing and user-friendly display.
"""

import json
import re
from .predizioni import headers, API_HOST, get_team_id, find_fixture_id, extract_teams_from_query

def is_lineup_query(query):
    query_lower = query.lower()
    
    # First check if it might be an injury query - if so, return False immediately
    injury_keywords = [
        'infortunat', 'infortunio', 'infortuni',  # injuries
        'squalificat', 'squalifica',  # suspensions
        'chi non', 'indisponibil', 'non disponibil'  # unavailable
    ]
    if any(keyword in query_lower for keyword in injury_keywords):
        print(f"[DEBUG] Injury keyword found in query - not a lineup query")
        return False
    
    # Check for keywords that would indicate this is NOT a lineup query
    negative_keywords = ['grafico', 'quote', 'andamento', 'scommesse', 'pronostico']
    if any(keyword in query_lower for keyword in negative_keywords):
        return False
    
    # Primary lineup keywords (strong indicators)
    primary_lineup_keywords = [
        'formazione', 'formazioni', 'titolari', 'titolare', 'undici iniziale',
        'starting xi', 'lineup', 'schieramento', 'hanno giocato', 'hanno schierato'
    ]
    
    # Strong indicators
    if any(keyword in query_lower for keyword in primary_lineup_keywords):
        print(f"[DEBUG] Primary lineup keyword found in query")
        return True
    
    # If asking about "chi gioca" (who plays), it's likely a lineup query
    # but only if it doesn't contain unavailability words
    if ("chi gioca" in query_lower or "chi ha giocato" in query_lower) and not any(kw in query_lower for kw in ['non gioca', 'non ha giocato']):
        print(f"[DEBUG] 'Chi gioca' pattern found - treating as lineup query")
        return True
    
    # Context checks requiring at least one team name
    from ..backend.predizioni import extract_teams_from_query
    home_team, away_team = extract_teams_from_query(query)
    if home_team or away_team:
        # Check for context that strongly suggests this is about lineups
        context_indicators = [
            'quali giocatori', 'con quali', 'in campo', 'ha schierato', 'hanno utilizzato'
        ]
        
        if any(indicator in query_lower for indicator in context_indicators):
            print(f"[DEBUG] Team name + lineup context found in query")
            return True
    
    # Default to false if no strong patterns are found
    return False

def get_fixture_lineup(fixture_id, team_id=None):
    """
    Get lineup data for a specific fixture from the API
    
    Args:
        fixture_id (int): The fixture ID
        team_id (int, optional): Team ID to filter results for just one team
        
    Returns:
        str: The raw JSON lineup data as a string
    """
    import requests
    
    try:
        url = f'https://{API_HOST}/v3/fixtures/lineups'
        params = {'fixture': fixture_id}
        
        # Add team filter if provided
        if team_id:
            params['team'] = team_id
            print(f"[DEBUG] Requesting lineup data for fixture: {fixture_id} filtered for team: {team_id}")
        else:
            print(f"[DEBUG] Requesting lineup data for fixture: {fixture_id} (both teams)")
            
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] Params: {params}")
        
        response = requests.get(url, headers=headers, params=params)
        
        print(f"[DEBUG] API status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                print(f"[DEBUG] Successfully retrieved lineup data")
                # Return the full, unprocessed JSON as a string
                return json.dumps(data, indent=2)
            else:
                print(f"[DEBUG] API response contains no lineup data")
        else:
            print(f"[DEBUG] API error: {response.text[:200]}")
        
        print(f"[DEBUG] No lineup data for fixture: {fixture_id}")
        return None
    except Exception as e:
        print(f"[DEBUG] Error retrieving lineup data: {str(e)}")
        return None

def find_fixtures_multiple_seasons(home_team_id, away_team_id, league_id=135, seasons=None):
    """
    Find fixture IDs across multiple seasons
    
    Args:
        home_team_id (int): Home team ID
        away_team_id (int): Away team ID
        league_id (int): League ID (default: 135 for Serie A)
        seasons (list): List of seasons to check (default: current and previous season)
        
    Returns:
        list: List of fixture IDs sorted by date (most recent first)
    """
    import requests
    
    if seasons is None:
        # Current season and previous season
        import datetime
        current_year = datetime.datetime.now().year
        seasons = [current_year, current_year-1]
    
    all_fixtures = []
    
    try:
        for season in seasons:
            print(f"[DEBUG] Looking for fixtures in season {season}")
            url = f'https://{API_HOST}/v3/fixtures'
            
            # Check with home_team_id as the home team
            params = {
                'league': league_id,
                'season': season,
                'team': home_team_id
            }
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get('response', [])
                
                for fixture in fixtures:
                    teams = fixture['teams']
                    if (teams['home']['id'] == home_team_id and 
                        teams['away']['id'] == away_team_id):
                        all_fixtures.append({
                            'fixture_id': fixture['fixture']['id'],
                            'date': fixture['fixture']['date'],
                            'season': season
                        })
            
            # Check with away_team_id as the home team
            params = {
                'league': league_id,
                'season': season,
                'team': away_team_id
            }
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get('response', [])
                
                for fixture in fixtures:
                    teams = fixture['teams']
                    if (teams['home']['id'] == away_team_id and 
                        teams['away']['id'] == home_team_id):
                        all_fixtures.append({
                            'fixture_id': fixture['fixture']['id'],
                            'date': fixture['fixture']['date'],
                            'season': season
                        })
        
        # Sort fixtures by date, most recent first
        all_fixtures.sort(key=lambda x: x['date'], reverse=True)
        
        print(f"[DEBUG] Found {len(all_fixtures)} fixtures across seasons {seasons}")
        for f in all_fixtures:
            print(f"[DEBUG] Fixture ID: {f['fixture_id']}, Date: {f['date']}, Season: {f['season']}")
        
        return all_fixtures
    
    except Exception as e:
        print(f"[DEBUG] Error finding fixtures across seasons: {str(e)}")
        return []

def get_lineup_for_query(query):
    """
    Get lineup data based on user query
    
    Args:
        query (str): The user's query
        
    Returns:
        str: The raw JSON lineup data
    """
    print(f"\n[DEBUG] Getting lineup for query: '{query}'")
    
    # Extract team names from query
    home_team, away_team = extract_teams_from_query(query)
    
    if home_team and away_team:
        print(f"[DEBUG] Teams extracted: {home_team} vs {away_team}")
        
        # Get team IDs
        home_id = get_team_id(home_team)
        away_id = get_team_id(away_team)
        print(f"[DEBUG] Team IDs: {home_team}={home_id}, {away_team}={away_id}")
        
        if home_id and away_id:
            # Check if query is asking about a specific team's lineup
            query_lower = query.lower()
            is_home_team_specific = False
            is_away_team_specific = False
            
            # Look for patterns that indicate interest in a specific team
            if home_team.lower() in query_lower and away_team.lower() not in query_lower:
                is_home_team_specific = True
                print(f"[DEBUG] Query appears to be specifically about {home_team}'s lineup")
            elif away_team.lower() in query_lower and home_team.lower() not in query_lower:
                is_away_team_specific = True
                print(f"[DEBUG] Query appears to be specifically about {away_team}'s lineup")
            
            # Find fixtures across multiple seasons
            import datetime
            current_year = datetime.datetime.now().year
            # Look in current and past 2 seasons
            seasons = [current_year, current_year-1, current_year-2]
            fixtures = find_fixtures_multiple_seasons(home_id, away_id, seasons=seasons)
            
            if fixtures:
                # Try each fixture, starting with the most recent
                for fixture_info in fixtures:
                    fixture_id = fixture_info['fixture_id']
                    fixture_date = fixture_info['date']
                    fixture_season = fixture_info['season']
                    
                    print(f"[DEBUG] Trying to get lineup for fixture ID {fixture_id} from {fixture_date} (season {fixture_season})")
                    
                    # If query is about a specific team, filter the API call
                    if is_home_team_specific:
                        lineup_data = get_fixture_lineup(fixture_id, home_id)
                    elif is_away_team_specific:
                        lineup_data = get_fixture_lineup(fixture_id, away_id)
                    else:
                        # Get data for both teams
                        lineup_data = get_fixture_lineup(fixture_id)
                    
                    if lineup_data:
                        print(f"[DEBUG] Found lineup data for fixture ID {fixture_id}")
                        return lineup_data
                    else:
                        print(f"[DEBUG] No lineup data available for fixture ID {fixture_id}")
            
            # Try the reverse team order (in case we missed anything)
            fixtures = find_fixtures_multiple_seasons(away_id, home_id, seasons=seasons)
            
            if fixtures:
                # Try each fixture, starting with the most recent
                for fixture_info in fixtures:
                    fixture_id = fixture_info['fixture_id']
                    fixture_date = fixture_info['date']
                    fixture_season = fixture_info['season']
                    
                    print(f"[DEBUG] Trying to get lineup for fixture ID {fixture_id} from {fixture_date} (season {fixture_season}) with reversed teams")
                    
                    # If query is about a specific team, filter the API call
                    if is_home_team_specific:
                        lineup_data = get_fixture_lineup(fixture_id, home_id)
                    elif is_away_team_specific:
                        lineup_data = get_fixture_lineup(fixture_id, away_id)
                    else:
                        # Get data for both teams
                        lineup_data = get_fixture_lineup(fixture_id)
                    
                    if lineup_data:
                        print(f"[DEBUG] Found lineup data for fixture ID {fixture_id}")
                        return lineup_data
                    else:
                        print(f"[DEBUG] No lineup data available for fixture ID {fixture_id}")
            
            print(f"[DEBUG] No fixtures found with lineup data available")
    else:
        print(f"[DEBUG] Could not extract two teams from query")
    
    print(f"[DEBUG] No lineup data found for query")
    return None

def process_lineup_json(json_data):
    """
    Process lineup JSON data for LLM consumption
    
    Args:
        json_data (str): Raw JSON data from the API
        
    Returns:
        tuple: (flat_text_data, key_info, team_names) processed data
    """
    # Parse the JSON
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except Exception as e:
            print(f"Error parsing JSON: {str(e)}")
            return "Errore nell'elaborazione dei dati delle formazioni.", None, None
    else:
        data = json_data
    
    # Check for valid response structure
    if not data.get('response') or not isinstance(data['response'], list):
        return "Nessun dato valido sulle formazioni trovato.", None, None
    
    # Create flat text representation
    flat_text_data = "INFORMAZIONI SULLE FORMAZIONI\n" + "=" * 30 + "\n\n"
    
    team_names = []
    fixture_id = None
    fixture_date = None
    
    # Extract fixture info if available
    if 'parameters' in data and 'fixture' in data['parameters']:
        fixture_id = data['parameters']['fixture']
        flat_text_data += f"Fixture ID: {fixture_id}\n\n"
    
    # Process each team's lineup
    for team_index, team_data in enumerate(data['response']):
        team_info = team_data.get('team', {})
        team_name = team_info.get('name', f"Squadra {team_index+1}")
        team_names.append(team_name)
        
        # Team header
        flat_text_data += f"SQUADRA: {team_name}\n"
        flat_text_data += "-" * 30 + "\n"
        
        # Formation
        formation = team_data.get('formation', 'Non disponibile')
        flat_text_data += f"Modulo: {formation}\n\n"
        
        # Coach
        coach = team_data.get('coach', {})
        coach_name = coach.get('name', 'Non disponibile')
        flat_text_data += f"Allenatore: {coach_name}\n\n"
        
        # Starting XI
        flat_text_data += "FORMAZIONE TITOLARE:\n"
        starting_xi = team_data.get('startXI', [])
        for player_data in starting_xi:
            player = player_data.get('player', {})
            player_name = player.get('name', 'Sconosciuto')
            player_number = player.get('number', 'N/A')
            player_pos = player.get('pos', 'N/A')
            player_grid = player.get('grid', 'N/A')
            
            position_full = translate_position(player_pos)
            
            flat_text_data += f"- {player_name} (#{player_number}, {position_full}, Posizione: {player_grid})\n"
        
        flat_text_data += "\n"
        
        # Substitutes
        flat_text_data += "PANCHINA:\n"
        substitutes = team_data.get('substitutes', [])
        for player_data in substitutes:
            player = player_data.get('player', {})
            player_name = player.get('name', 'Sconosciuto')
            player_number = player.get('number', 'N/A')
            player_pos = player.get('pos', 'N/A')
            
            position_full = translate_position(player_pos)
            
            flat_text_data += f"- {player_name} (#{player_number}, {position_full})\n"
        
        flat_text_data += "\n" + "=" * 30 + "\n\n"
    
    # Extract key information
    key_info = extract_lineup_key_info(data, team_names)
    
    return flat_text_data, key_info, team_names

def translate_position(pos_code):
    """Translate position code to full Italian position name"""
    position_map = {
        'G': 'Portiere',
        'D': 'Difensore',
        'M': 'Centrocampista',
        'F': 'Attaccante'
    }
    return position_map.get(pos_code, pos_code)

def extract_lineup_key_info(data, team_names):
    """
    Extract key information from lineup data
    
    Args:
        data (dict): The parsed JSON data
        team_names (list): The team names
        
    Returns:
        str: A structured summary of key lineup information
    """
    info_lines = []
    
    try:
        response = data.get('response', [])
        if not response:
            return "Nessuna informazione sulla formazione disponibile"
        
        # Get information for each team
        for i, team_data in enumerate(response):
            team_name = team_data.get('team', {}).get('name', 'Squadra sconosciuta')
            formation = team_data.get('formation', 'Non disponibile')
            coach = team_data.get('coach', {}).get('name', 'Non disponibile')
            
            info_lines.append(f"SQUADRA: {team_name}")
            info_lines.append(f"Modulo: {formation}")
            info_lines.append(f"Allenatore: {coach}")
            
            # Count players by position for starting XI
            positions = {'G': 0, 'D': 0, 'M': 0, 'F': 0}
            starting_xi = team_data.get('startXI', [])
            for player_data in starting_xi:
                pos = player_data.get('player', {}).get('pos', '')
                if pos in positions:
                    positions[pos] += 1
            
            # Format position summary in Italian
            pos_summary_parts = []
            for pos, count in positions.items():
                if count > 0:
                    pos_full = translate_position(pos)
                    pos_summary_parts.append(f"{count} {pos_full}{'' if count == 1 else 'i'}")
            
            pos_summary = ", ".join(pos_summary_parts)
            info_lines.append(f"Giocatori per ruolo: {pos_summary}")
            
            # Extract starting players by position for a structured player list
            starting_players = {'G': [], 'D': [], 'M': [], 'F': []}
            for player_data in starting_xi:
                player = player_data.get('player', {})
                pos = player.get('pos', '')
                player_name = player.get('name', 'Sconosciuto')
                player_number = player.get('number', '')
                if pos in starting_players:
                    starting_players[pos].append(f"{player_name} (#{player_number})")
            
            # Add structured player list to make it more obvious to LLM
            info_lines.append("\nGIOCATORI TITOLARI:")
            for pos, label in [('G', 'Portiere'), ('D', 'Difensori'), ('M', 'Centrocampisti'), ('F', 'Attaccanti')]:
                if starting_players[pos]:
                    info_lines.append(f"- {label}: {', '.join(starting_players[pos])}")
            
            # Key players (one from each position for quick reference)
            key_players = []
            for pos in ['G', 'D', 'M', 'F']:
                for player_data in starting_xi:
                    player = player_data.get('player', {})
                    if player.get('pos') == pos:
                        pos_full = translate_position(pos)
                        key_players.append(f"{player.get('name', 'Sconosciuto')} ({pos_full})")
                        break
            
            if key_players:
                info_lines.append(f"\nGiocatori chiave: {', '.join(key_players)}")
            
            info_lines.append("-" * 30)
        
        return "\n".join(info_lines)
    
    except Exception as e:
        print(f"Error extracting lineup key info: {str(e)}")
        return "Errore nell'elaborazione delle informazioni sulle formazioni"

def build_lineup_prompt(messages, flat_text_data, key_info, team_names):
    """
    Build a lineup-specific conversation prompt with instructions
    to use only provided data
    
    Args:
        messages: List of (role, content) tuples representing the conversation
        flat_text_data: Flat text representation of the lineup data
        key_info: Extracted key information
        team_names: List of team names
        
    Returns:
        str: Formatted conversation prompt
    """
    convo = ""
    
    # Create team names string
    team_names_str = " e ".join(team_names) if team_names else "le squadre"
    
    # START WITH A SUPER CRITICAL SAFETY INSTRUCTION - This must come first
    convo += (
        "<|im_start|>system\n"
        f"ISTRUZIONI DI SICUREZZA CRITICHE E VINCOLANTI:\n"
        f"===================================================\n"
        f"L'utente ha chiesto le formazioni della partita tra {team_names_str}.\n\n"
        f"1. ASSOLUTAMENTE NO INVENZIONI - Non inventare giocatori, allenatori, moduli, sostituzioni, risultati, date!\n"
        f"2. UTILIZZA SOLO I DATI FORNITI - Usa esclusivamente le informazioni nelle sezioni 'DATI VERIFICATI' e 'INFORMAZIONI SULLE FORMAZIONI'\n"
        f"3. NESSUN DETTAGLIO INVENTATO - Non menzionare minuti di gioco, sostituzioni, eventi della partita o risultati\n"
        f"4. VERIFICA OGNI NOME - Menziona solo giocatori e allenatori presenti nei dati, non aggiungere nomi non presenti\n"
        f"5. NIENTE EVENTI DEL MATCH - Non commentare su gol, cartellini, sostituzioni o altri eventi a meno che non siano esplicitamente nei dati\n\n"
        f"Violazioni di queste istruzioni sono gravi errori di sicurezza. Se un dato non è fornito, indicalo chiaramente.\n"
        f"===================================================\n"
        f"DATI VERIFICATI - UTILIZZARE SOLO QUESTI:\n\n{key_info}\n"
        "<|im_end|>\n"
    )
    
    # Add system message if present (lower priority than our critical instructions)
    for role, content in messages:
        if role == "system":
            convo += (
                "<|im_start|>system\n"
                f"{content}\n"
                "<|im_end|>\n"
            )
            break
    
    # Create detailed system instructions with the data to use
    system_instruction = (
        f"STRUTTURA DELLA RISPOSTA:\n"
        f"1. Titolo con nome delle squadre e formazione\n"
        f"2. Allenatore\n"
        f"3. Giocatori titolari raggruppati per ruolo\n"
        f"4. OPZIONALE: Solo se richiesto, elenco panchina\n\n"
        
        f"ISTRUZIONI TECNICHE PER L'ELABORAZIONE:\n"
        f"- Le posizioni dei giocatori sono codificate come: G = Portiere, D = Difensore, M = Centrocampista, F = Attaccante\n"
        f"- La posizione sul campo è in formato \"X:Y\" dove X = linea (1=porta), Y = colonna (da sinistra a destra)\n"
        f"- NON SPECULARE su formazioni o dati mancanti\n"
        f"- NON MENZIONARE date, risultati, o eventi della partita, limitati solo alle formazioni\n\n"
        
        f"INFORMAZIONI SULLE FORMAZIONI - DATI COMPLETI DA UTILIZZARE:\n"
        f"{flat_text_data}\n"
    )
    
    convo += (
        "<|im_start|>system\n"
        f"{system_instruction}\n"
        "<|im_end|>\n"
    )
    
    # Add regular messages (user and assistant history)
    for role, content in messages:
        if role == "system":
            continue  # Skip as already handled
            
        elif role == "snippet":
            # Additional data from web search (low priority)
            convo += (
                "<|im_start|>system\n"
                "NOTA: I dati web seguenti sono a bassa priorità e potrebbero essere obsoleti. "
                "In caso di conflitto, usa SOLO i dati delle formazioni forniti sopra.\n"
                f"{content}\n"
                "<|im_end|>\n"
            )
        elif role in ("user", "assistant"):
            convo += (
                f"<|im_start|>{role}\n"
                f"{content}\n"
                "<|im_end|>\n"
            )
        else:
            convo += (
                f"<|im_start|>{role}\n"
                f"{content}\n"
                "<|im_end|>\n"
            )

    # FINAL safety check before generating response
    convo += (
        "<|im_start|>system\n"
        "CONTROLLO FINALE DI SICUREZZA:\n"
        "1. Verifica che stai usando SOLO i giocatori nei dati verificati\n"
        "2. NON menzionare sostituzioni, minuti di gioco o eventi non presenti nei dati\n"
        "3. NON citare date, risultati o punteggi\n"
        "4. Se l'utente chiede specificamente della Lazio, concentra la risposta sulla Lazio\n"
        "5. Fornisci una risposta strutturata, chiara e basata UNICAMENTE sui dati forniti\n"
        "<|im_end|>\n"
    )
    
    # Open assistant block for response
    convo += "<|im_start|>assistant\n"
    return convo


def generate_lineup_response(team_names, key_stats, flat_text_data):
    """
    Generate a pre-written response for lineup queries that the model cannot hallucinate.
    
    This function completely bypasses the LLM for lineup queries, eliminating hallucination risks.
    
    Args:
        team_names: List of team names
        key_stats: Structured key stats
        flat_text_data: Full flat text data
        
    Returns:
        str: The formatted response with actual lineup data
    """
    if not team_names or not key_stats:
        return "Mi dispiace, non ho trovato dati sulle formazioni per questa partita. Verifica che le squadre abbiano realmente giocato tra loro nelle stagioni recenti."
    
    # Extract formations and coaches directly from key_stats
    formations = {}
    coaches = {}
    player_sections = {}
    
    # Initialize data structures
    for team in team_names:
        formations[team] = "Non disponibile"
        coaches[team] = "Non disponibile"
        player_sections[team] = {
            "G": [],  # Goalkeepers
            "D": [],  # Defenders
            "M": [],  # Midfielders
            "F": []   # Forwards
        }
    
    # Parse key_stats to extract the exact team data
    current_team = None
    for line in key_stats.split('\n'):
        if line.startswith('SQUADRA: '):
            current_team = line.replace('SQUADRA: ', '').strip()
        
        elif current_team and line.startswith('Modulo: '):
            formations[current_team] = line.replace('Modulo: ', '').strip()
            
        elif current_team and line.startswith('Allenatore: '):
            coaches[current_team] = line.replace('Allenatore: ', '').strip()
            
        # Extract player lists from GIOCATORI TITOLARI section
        elif line.startswith('- Portiere: ') and current_team:
            players = line.replace('- Portiere: ', '').strip()
            player_sections[current_team]['G'] = [p.strip() for p in players.split(',')]
            
        elif line.startswith('- Difensori: ') and current_team:
            players = line.replace('- Difensori: ', '').strip()
            player_sections[current_team]['D'] = [p.strip() for p in players.split(',')]
            
        elif line.startswith('- Centrocampisti: ') and current_team:
            players = line.replace('- Centrocampisti: ', '').strip()
            player_sections[current_team]['M'] = [p.strip() for p in players.split(',')]
            
        elif line.startswith('- Attaccanti: ') and current_team:
            players = line.replace('- Attaccanti: ', '').strip()
            player_sections[current_team]['F'] = [p.strip() for p in players.split(',')]
    
    # If we couldn't find structured player lists, extract them from flat_text
    if not any(player_sections[team]['G'] for team in team_names):
        # Parse flat text to extract player info
        current_team = None
        current_section = None
        for line in flat_text_data.split('\n'):
            if line.startswith('SQUADRA: '):
                current_team = line.replace('SQUADRA: ', '').strip()
                current_section = None
            elif line.startswith('Modulo: ') and current_team and not formations[current_team]:
                formations[current_team] = line.replace('Modulo: ', '').strip()
            elif line.startswith('Allenatore: ') and current_team and not coaches[current_team]:
                coaches[current_team] = line.replace('Allenatore: ', '').strip()
            elif line == 'FORMAZIONE TITOLARE:' and current_team:
                current_section = 'titolari'
            elif line == 'PANCHINA:' and current_team:
                current_section = 'panchina'
            elif line.startswith('- ') and current_team and current_section == 'titolari':
                # Extract player info from line like "- I. Provedel (#94, Portiere, Posizione: 1:1)"
                player_info = line[2:].strip()
                if '(' in player_info and ',' in player_info:
                    player_name = player_info.split('(')[0].strip()
                    position_info = player_info.split(',')[1].strip() if len(player_info.split(',')) > 1 else ""
                    
                    # Determine position category
                    if 'Portiere' in position_info:
                        player_sections[current_team]['G'].append(player_name)
                    elif 'Difensore' in position_info:
                        player_sections[current_team]['D'].append(player_name)
                    elif 'Centrocampista' in position_info:
                        player_sections[current_team]['M'].append(player_name)
                    elif 'Attaccante' in position_info:
                        player_sections[current_team]['F'].append(player_name)
    
    # Build the response for each team
    team_responses = []
    for team in team_names:
        # Get match date if available
        match_date = ""
        for line in flat_text_data.split('\n'):
            if line.startswith("Fixture ID:"):
                fixture_id = line.replace("Fixture ID:", "").strip()
                match_date = f" (Fixture ID: {fixture_id})"
                break
                
        team_response = f"**{team} ({formations[team]}):**{match_date}\n"
        team_response += f"* **Allenatore:** {coaches[team]}\n"
        
        # Add goalkeeper(s)
        if player_sections[team]['G']:
            team_response += f"* **Portiere:** {', '.join(player_sections[team]['G'])}\n"
        else:
            team_response += f"* **Portiere:** Dato non disponibile\n"
            
        # Add defenders
        if player_sections[team]['D']:
            team_response += f"* **Difensori:** {', '.join(player_sections[team]['D'])}\n"
        else:
            team_response += f"* **Difensori:** Dati non disponibili\n"
            
        # Add midfielders
        if player_sections[team]['M']:
            team_response += f"* **Centrocampisti:** {', '.join(player_sections[team]['M'])}\n"
        else:
            team_response += f"* **Centrocampisti:** Dati non disponibili\n"
            
        # Add forwards
        if player_sections[team]['F']:
            team_response += f"* **Attaccanti:** {', '.join(player_sections[team]['F'])}\n"
        else:
            team_response += f"* **Attaccanti:** Dati non disponibili\n"
        
        team_responses.append(team_response)
    
    # Combine all team responses
    response = f"Ecco le formazioni titolari:\n\n"
    response += "\n\n".join(team_responses)
    
    # Add note about data source and limitations
    response += "\n\n**Nota:** Queste sono le formazioni iniziali ufficiali. Non ho informazioni su eventuali sostituzioni avvenute durante la partita."
    
    return response