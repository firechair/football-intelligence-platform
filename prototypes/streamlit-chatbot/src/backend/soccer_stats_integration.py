# src/backend/soccer_stats_integration.py
"""
This module implements a comprehensive integration for soccer statistics parsing and analysis.
It provides functions to extract, parse, and present soccer match data in a format optimized
for LLM processing and user-friendly display.
"""

import json
import re

def process_soccer_json(json_data):
    """
    Process soccer JSON data for LLM consumption through a chain of specialized functions.
    
    Args:
        json_data (str/dict): Raw JSON data from the API
        
    Returns:
        tuple: (flat_text_data, key_stats, team_names) processed data
    """
    # 1. Preprocess the JSON to ensure consistent structure
    processed_json = preprocess_json_for_soccer_stats(json_data)
    
    # 2. Convert to flat text format
    flat_text_data = improved_parse_json_to_flat_text(processed_json)
    
    # 3. Extract key statistics
    key_stats = extract_soccer_statistics(flat_text_data)
    
    # 4. Extract team names for reference
    team_names = extract_team_names(flat_text_data)
    
    return flat_text_data, key_stats, team_names

def preprocess_json_for_soccer_stats(json_data):
    """
    Preprocess the JSON data to ensure it has the expected structure for soccer stats.
    
    Args:
        json_data (str): Raw JSON data
        
    Returns:
        dict: Processed JSON data ready for parsing
    """
    try:
        # Parse the JSON
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data
            
        # Check for the expected structure
        if 'response' in data and isinstance(data['response'], list) and len(data['response']) > 0:
            # The structure looks good
            return data
            
        # If we don't have the expected structure, try to restructure it
        response_data = {'response': []}
        
        if isinstance(data, dict):
            # Check if this is already a predictions object
            if 'predictions' in data:
                response_data['response'].append(data)
            elif 'response' in data and not isinstance(data['response'], list):
                # Convert non-list response to list
                response_data['response'].append(data['response'])
            else:
                # Last resort - just use the data as is
                response_data['response'].append(data)
                
        return response_data
        
    except Exception as e:
        print(f"Error preprocessing JSON: {str(e)}")
        # Return a minimal valid structure
        return {'response': [{'error': str(e)}]}

def improved_parse_json_to_flat_text(json_data):
    """
    Parse a JSON structure into a flat text format with improved structure
    specifically designed for soccer match data.
    
    Args:
        json_data (dict/str): The JSON data to parse
        
    Returns:
        str: Enhanced flat text representation of the JSON data
    """
    # First parse JSON if it's a string
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except Exception as e:
            print(f"Error parsing JSON: {str(e)}")
            return f"Error parsing JSON: {str(e)}"
    else:
        data = json_data
    
    # Create full flat representation
    flat_data = {}
    
    def _flatten_json(obj, prefix=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                _flatten_json(value, new_prefix)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_prefix = f"{prefix}[{i}]"
                _flatten_json(item, new_prefix)
        else:
            flat_data[prefix] = obj
    
    # Start the flattening process
    _flatten_json(data)
    
    # Find the actual data paths in this specific API response
    # API responses can vary so we need to be flexible
    home_path_prefix = ""
    away_path_prefix = ""
    
    # First look for main team data outside h2h
    for key in flat_data.keys():
        if re.search(r'teams\.home\.name', key) and 'h2h' not in key:
            home_path_prefix = key.split('.teams.home.name')[0]
            break
    
    for key in flat_data.keys():
        if re.search(r'teams\.away\.name', key) and 'h2h' not in key:
            away_path_prefix = key.split('.teams.away.name')[0]
            break
    
    # If we found a prefix, use it - otherwise look in response
    if not home_path_prefix or not away_path_prefix:
        for key in flat_data.keys():
            if 'response' in key and '.teams.home.name' in key and 'h2h' not in key:
                home_path_prefix = key.split('.teams.home.name')[0]
                break
        
        for key in flat_data.keys():
            if 'response' in key and '.teams.away.name' in key and 'h2h' not in key:
                away_path_prefix = key.split('.teams.away.name')[0]
                break
    
    # Extract team names
    home_team_name = "Home Team"
    away_team_name = "Away Team"
    
    # Home team name - first try direct path
    home_name_key = f"{home_path_prefix}.teams.home.name" if home_path_prefix else None
    if home_name_key and home_name_key in flat_data:
        home_team_name = flat_data[home_name_key]
    else:
        # Try to find it anywhere in the flat data
        for key, value in flat_data.items():
            if key.endswith('teams.home.name') and 'h2h' not in key:
                home_team_name = value
                break
    
    # Away team name - first try direct path
    away_name_key = f"{away_path_prefix}.teams.away.name" if away_path_prefix else None
    if away_name_key and away_name_key in flat_data:
        away_team_name = flat_data[away_name_key]
    else:
        # Try to find it anywhere in the flat data
        for key, value in flat_data.items():
            if key.endswith('teams.away.name') and 'h2h' not in key:
                away_team_name = value
                break
    
    # Still no teams? Look in head-to-head data
    if home_team_name == "Home Team" or away_team_name == "Away Team":
        for key, value in flat_data.items():
            if 'h2h[0].teams.home.name' in key:
                home_team_name = value
            if 'h2h[0].teams.away.name' in key:
                away_team_name = value
    
    # Now build structured output
    sections = {
        "MATCH_INFO": [f"Match: {home_team_name} vs {away_team_name}"],
        "HOME_STATS": [f"{home_team_name} (Home Team) Statistics:"],
        "AWAY_STATS": [f"{away_team_name} (Away Team) Statistics:"],
        "FORM": ["Form Statistics:"],
        "GOALS": ["Goal Statistics:"],
        "COMPARISON": ["Team Comparison:"],
        "H2H": ["Head-to-Head History:"],
        "PREDICTIONS": ["Match Predictions:"],
    }
    
    # Process form data specifically
    for key, value in flat_data.items():
        # Home team form data
        if '.teams.home.last_5.form' in key:
            sections["FORM"].append(f"form.home = {value}")
        if '.teams.home.last_5.att' in key:
            sections["FORM"].append(f"att.home = {value}")
        if '.teams.home.last_5.def' in key:
            sections["FORM"].append(f"def.home = {value}")
        if '.teams.home.league.form' in key:
            sections["FORM"].append(f"form_sequence.home = {value}")
        
        # Away team form data
        if '.teams.away.last_5.form' in key:
            sections["FORM"].append(f"form.away = {value}")
        if '.teams.away.last_5.att' in key:
            sections["FORM"].append(f"att.away = {value}")
        if '.teams.away.last_5.def' in key:
            sections["FORM"].append(f"def.away = {value}")  
        if '.teams.away.league.form' in key:
            sections["FORM"].append(f"form_sequence.away = {value}")
    
    # Process goals data
    for key, value in flat_data.items():
        # Home team goals
        if '.teams.home.last_5.goals.for.total' in key:
            sections["GOALS"].append(f"goals_scored.home = {value}")
        if '.teams.home.last_5.goals.against.total' in key:
            sections["GOALS"].append(f"goals_conceded.home = {value}")
        if '.teams.home.last_5.goals.for.average' in key:
            sections["GOALS"].append(f"average_goals_scored.home = {value}")
        if '.teams.home.last_5.goals.against.average' in key:
            sections["GOALS"].append(f"average_goals_conceded.home = {value}")
        
        # Away team goals
        if '.teams.away.last_5.goals.for.total' in key:
            sections["GOALS"].append(f"goals_scored.away = {value}")
        if '.teams.away.last_5.goals.against.total' in key:
            sections["GOALS"].append(f"goals_conceded.away = {value}")
        if '.teams.away.last_5.goals.for.average' in key:
            sections["GOALS"].append(f"average_goals_scored.away = {value}")
        if '.teams.away.last_5.goals.against.average' in key:
            sections["GOALS"].append(f"average_goals_conceded.away = {value}")
    
    # Process comparison data
    for key, value in flat_data.items():
        if 'comparison.form.home' in key:
            sections["COMPARISON"].append(f"form.home = {value}")
        if 'comparison.form.away' in key:
            sections["COMPARISON"].append(f"form.away = {value}")
        if 'comparison.att.home' in key:
            sections["COMPARISON"].append(f"att.home = {value}")
        if 'comparison.att.away' in key:
            sections["COMPARISON"].append(f"att.away = {value}")
        if 'comparison.def.home' in key:
            sections["COMPARISON"].append(f"def.home = {value}")
        if 'comparison.def.away' in key:
            sections["COMPARISON"].append(f"def.away = {value}")
        if 'comparison.total.home' in key:
            sections["COMPARISON"].append(f"total.home = {value}")
        if 'comparison.total.away' in key:
            sections["COMPARISON"].append(f"total.away = {value}")
    
    # Process prediction data
    for key, value in flat_data.items():
        if 'predictions.winner.name' in key:
            sections["PREDICTIONS"].append(f"winner = {value}")
        if 'predictions.advice' in key:
            sections["PREDICTIONS"].append(f"advice = {value}")
        if 'predictions.percent.home' in key:
            sections["PREDICTIONS"].append(f"percent.home = {value}")
        if 'predictions.percent.draw' in key:
            sections["PREDICTIONS"].append(f"percent.draw = {value}")
        if 'predictions.percent.away' in key:
            sections["PREDICTIONS"].append(f"percent.away = {value}")
    
    # Process head-to-head data (only most recent matches)
    h2h_count = 0
    for i in range(5):  # Only include up to 5 most recent matches
        match_data = []
        for key, value in flat_data.items():
            if f'h2h[{i}].goals.home' in key:
                home_goals = value
                match_data.append(f"home_goals = {home_goals}")
            if f'h2h[{i}].goals.away' in key:
                away_goals = value
                match_data.append(f"away_goals = {away_goals}")
            if f'h2h[{i}].fixture.date' in key:
                date = value
                match_data.append(f"date = {date}")
            if f'h2h[{i}].teams.home.name' in key:
                match_home = value
                match_data.append(f"home_team = {match_home}")
            if f'h2h[{i}].teams.away.name' in key:
                match_away = value
                match_data.append(f"away_team = {match_away}")
        
        if match_data:
            h2h_count += 1
            sections["H2H"].append(f"--- Match {h2h_count} ---")
            sections["H2H"].extend(match_data)
    
    # Build the final output with the most important data first
    output_lines = []
    
    # Match Info
    output_lines.append("===== MATCH INFORMATION =====")
    output_lines.extend(sections["MATCH_INFO"])
    output_lines.append("")
    
    # Form - Most important for form queries
    output_lines.append("===== FORM STATISTICS =====")
    output_lines.extend(sections["FORM"])
    output_lines.append("")
    
    # Goals - Second most important
    output_lines.append("===== GOAL STATISTICS =====")
    output_lines.extend(sections["GOALS"])
    output_lines.append("")
    
    # Comparison - Third most important
    output_lines.append("===== TEAM COMPARISON =====")
    output_lines.extend(sections["COMPARISON"])
    output_lines.append("")
    
    # Predictions
    output_lines.append("===== PREDICTIONS =====")
    output_lines.extend(sections["PREDICTIONS"])
    output_lines.append("")
    
    # Head to Head - Less relevant for form
    output_lines.append("===== HEAD TO HEAD HISTORY =====")
    output_lines.extend(sections["H2H"])
    
    # Add original team data paths for debugging
    output_lines.append("")
    output_lines.append("===== DATA PATHS =====")
    output_lines.append(f"Home Team Data Path: {home_path_prefix}")
    output_lines.append(f"Away Team Data Path: {away_path_prefix}")
    
    return "\n".join(output_lines)

def extract_soccer_statistics(flat_text):
    """
    Extract and structure key soccer statistics from flat text data
    for easy LLM comprehension.
    
    Args:
        flat_text (str): The flat text data
        
    Returns:
        str: A clear, structured summary of key statistics
    """
    # Extract team names
    match_line = re.search(r'Match: (.*?) vs (.*?)$', flat_text, re.MULTILINE)
    if match_line:
        home_team = match_line.group(1)
        away_team = match_line.group(2)
    else:
        # Fallback to generic names
        home_team = "Home Team"
        away_team = "Away Team"
    
    # Create the output structure
    stats = []
    stats.append(f"MATCH: {home_team} vs {away_team}")
    stats.append("")
    
    # FORM STATISTICS
    stats.append("FORM STATISTICS:")
    
    # Home team form
    home_form = re.search(r'form\.home = (\d+%)', flat_text)
    home_att = re.search(r'att\.home = (\d+%)', flat_text)
    home_def = re.search(r'def\.home = (\d+%)', flat_text)
    
    if any([home_form, home_att, home_def]):
        stats.append(f"{home_team} Form:")
        if home_form:
            stats.append(f"- Recent Form: {home_form.group(1)}")
        else:
            stats.append("- Recent Form: Dato non disponibile")
            
        if home_att:
            stats.append(f"- Attack Rating: {home_att.group(1)}")
        else:
            stats.append("- Attack Rating: Dato non disponibile")
            
        if home_def:
            stats.append(f"- Defense Rating: {home_def.group(1)}")
        else:
            stats.append("- Defense Rating: Dato non disponibile")
    else:
        stats.append(f"{home_team} Form: Dati non disponibili")
    
    # Away team form
    away_form = re.search(r'form\.away = (\d+%)', flat_text)
    away_att = re.search(r'att\.away = (\d+%)', flat_text)
    away_def = re.search(r'def\.away = (\d+%)', flat_text)
    
    if any([away_form, away_att, away_def]):
        stats.append(f"{away_team} Form:")
        if away_form:
            stats.append(f"- Recent Form: {away_form.group(1)}")
        else:
            stats.append("- Recent Form: Dato non disponibile")
            
        if away_att:
            stats.append(f"- Attack Rating: {away_att.group(1)}")
        else:
            stats.append("- Attack Rating: Dato non disponibile")
            
        if away_def:
            stats.append(f"- Defense Rating: {away_def.group(1)}")
        else:
            stats.append("- Defense Rating: Dato non disponibile")
    else:
        stats.append(f"{away_team} Form: Dati non disponibili")
    
    stats.append("")
    stats.append("GOALS STATISTICS:")
    
    # Home team goals
    home_goals_scored = re.search(r'goals_scored\.home = (\d+)', flat_text)
    home_goals_conceded = re.search(r'goals_conceded\.home = (\d+)', flat_text)
    
    if any([home_goals_scored, home_goals_conceded]):
        stats.append(f"{home_team} Goals (Last 5 Matches):")
        if home_goals_scored:
            stats.append(f"- Goals Scored: {home_goals_scored.group(1)}")
        else:
            stats.append("- Goals Scored: Dato non disponibile")
            
        if home_goals_conceded:
            stats.append(f"- Goals Conceded: {home_goals_conceded.group(1)}")
        else:
            stats.append("- Goals Conceded: Dato non disponibile")
    else:
        stats.append(f"{home_team} Goals: Dati non disponibili")
    
    # Away team goals
    away_goals_scored = re.search(r'goals_scored\.away = (\d+)', flat_text)
    away_goals_conceded = re.search(r'goals_conceded\.away = (\d+)', flat_text)
    
    if any([away_goals_scored, away_goals_conceded]):
        stats.append(f"{away_team} Goals (Last 5 Matches):")
        if away_goals_scored:
            stats.append(f"- Goals Scored: {away_goals_scored.group(1)}")
        else:
            stats.append("- Goals Scored: Dato non disponibile")
            
        if away_goals_conceded:
            stats.append(f"- Goals Conceded: {away_goals_conceded.group(1)}")
        else:
            stats.append("- Goals Conceded: Dato non disponibile")
    else:
        stats.append(f"{away_team} Goals: Dati non disponibili")
    
    stats.append("")
    stats.append("RECENT FORM SEQUENCES:")
    
    # Team form sequences
    home_form_seq = re.search(r'form_sequence\.home = ([WDLS]+)', flat_text)
    away_form_seq = re.search(r'form_sequence\.away = ([WDLS]+)', flat_text)
    
    if home_form_seq:
        stats.append(f"{home_team} Form Sequence: {home_form_seq.group(1)}")
    else:
        stats.append(f"{home_team} Form Sequence: Dato non disponibile")
        
    if away_form_seq:
        stats.append(f"{away_team} Form Sequence: {away_form_seq.group(1)}")
    else:
        stats.append(f"{away_team} Form Sequence: Dato non disponibile")
    
    # Add comparison data - very important!
    stats.append("")
    stats.append("TEAM COMPARISON:")
    
    # Check for any comparison data
    comp_pattern = re.compile(r'(form|att|def|total)\.(home|away) = (\d+%)')
    comp_matches = comp_pattern.findall(flat_text)
    
    if comp_matches:
        comp_data = {}
        for stat_type, team, value in comp_matches:
            key = f"{stat_type}.{team}"
            comp_data[key] = value
        
        # Form comparison
        if 'form.home' in comp_data and 'form.away' in comp_data:
            stats.append(f"Form: {home_team} {comp_data['form.home']} vs {away_team} {comp_data['form.away']}")
        else:
            stats.append(f"Form Comparison: Dati non disponibili")
        
        # Attack comparison
        if 'att.home' in comp_data and 'att.away' in comp_data:
            stats.append(f"Attack: {home_team} {comp_data['att.home']} vs {away_team} {comp_data['att.away']}")
        else:
            stats.append(f"Attack Comparison: Dati non disponibili")
        
        # Defense comparison
        if 'def.home' in comp_data and 'def.away' in comp_data:
            stats.append(f"Defense: {home_team} {comp_data['def.home']} vs {away_team} {comp_data['def.away']}")
        else:
            stats.append(f"Defense Comparison: Dati non disponibili")
        
        # Overall comparison
        if 'total.home' in comp_data and 'total.away' in comp_data:
            stats.append(f"Overall: {home_team} {comp_data['total.home']} vs {away_team} {comp_data['total.away']}")
        else:
            stats.append(f"Overall Comparison: Dati non disponibili")
    else:
        stats.append("No comparison data available")
    
    # Add predictions if available
    stats.append("")
    stats.append("PREDICTIONS:")
    
    winner = re.search(r'winner = (.*?)$', flat_text, re.MULTILINE)
    home_percent = re.search(r'percent\.home = (\d+%)', flat_text)
    draw_percent = re.search(r'percent\.draw = (\d+%)', flat_text)
    away_percent = re.search(r'percent\.away = (\d+%)', flat_text)
    
    if winner:
        winner_team = winner.group(1)
        if winner_team == "None" or "null" in winner_team.lower():
            stats.append("- No clear winner predicted")
        else:
            stats.append(f"- Predicted Winner: {winner_team}")
    else:
        stats.append("- Winner Prediction: Dato non disponibile")
    
    if all([home_percent, draw_percent, away_percent]):
        stats.append(f"- Win Probability: {home_team} {home_percent.group(1)} | Draw {draw_percent.group(1)} | {away_team} {away_percent.group(1)}")
    else:
        stats.append("- Win Probability: Dati non disponibili")
    
    return "\n".join(stats)

def extract_team_names(flat_text):
    """
    Extract team names from flat text data.
    
    Args:
        flat_text (str): The flat text data
        
    Returns:
        tuple: (home_team, away_team) the extracted team names
    """
    match_line = re.search(r'Match: (.*?) vs (.*?)$', flat_text, re.MULTILINE)
    if match_line:
        home_team = match_line.group(1)
        away_team = match_line.group(2)
        return home_team, away_team
    else:
        # Fallback search
        home_team = "Home Team"
        away_team = "Away Team"
        
        home_match = re.search(r'home_team = "(.*?)"', flat_text)
        if home_match:
            home_team = home_match.group(1)
            
        away_match = re.search(r'away_team = "(.*?)"', flat_text)
        if away_match:
            away_team = away_match.group(1)
            
        return home_team, away_team

def build_soccer_stats_prompt(messages, flat_text_data, key_stats, form_query=False):
    """
    Build a soccer-specific conversation prompt with strict instructions
    to use only provided data.
    
    Args:
        messages: List of (role, content) tuples representing the conversation
        flat_text_data: Flat text representation of the data
        key_stats: Extracted key statistics
        form_query: Whether this is a form query
        
    Returns:
        str: Formatted conversation prompt
    """
    convo = ""
    
    # Add system message first
    for role, content in messages:
        if role == "system":
            convo += (
                "<|im_start|>system\n"
                f"{content}\n"
                "<|im_end|>\n"
            )
            break
    
    # Extract team names
    home_team, away_team = extract_team_names(flat_text_data)
    
    # Create very strict instructions
    system_instruction = (
        f"ATTENZIONE: L'utente ha chiesto informazioni sulle statistiche e curve di forma delle squadre {home_team} e {away_team}.\n\n"
        f"ISTRUZIONI OBBLIGATORIE DA SEGUIRE RIGOROSAMENTE:\n"
        f"1. Devi utilizzare ESCLUSIVAMENTE i dati statistici forniti qui sotto. NON inventare, stimare o inserire statistiche non presenti nei dati.\n"
        f"2. Se un dato specifico non è presente nelle statistiche fornite, indica chiaramente \"Dato non disponibile\".\n"
        f"3. Non usare assolutamente conoscenze generali sulle squadre o il campionato italiano.\n"
        f"4. Le tue risposte devono essere basate UNICAMENTE sui valori numerici e sulle statistiche presenti nei dati forniti.\n"
        f"5. Se i dati sembrano contraddittori o incompleti, segnalalo senza inventare informazioni aggiuntive.\n\n"
        
        f"STATISTICHE CHIAVE ESTRATTE:\n"
        f"----------------------------------------\n"
        f"{key_stats}\n"
        f"----------------------------------------\n\n"
        
        f"Quando fai riferimento alle sequenze di forma (come WDLW...), ricorda che:\n"
        f"- W = Vittoria\n"
        f"- D = Pareggio\n"
        f"- L = Sconfitta\n"
        f"Le sequenze si leggono da sinistra a destra (dalla partita più recente alla meno recente).\n\n"
        
        f"Le percentuali di forma, attacco e difesa sono dati chiave che indicano le prestazioni recenti delle squadre.\n"
        f"I dati sui gol segnati e subiti negli ultimi 5 incontri sono fondamentali per valutare l'efficacia offensiva e difensiva.\n\n"
        
        f"RICORDA: Una risposta accurata basata sui dati reali è sempre preferibile a una risposta completa ma inventata.\n"
        f"I dati completi in formato testo piatto sono forniti di seguito per tua referenza."
    )
    
    convo += (
        "<|im_start|>system\n"
        f"{system_instruction}\n\n"
        "DATI COMPLETI IN FORMATO TESTO PIATTO:\n"
        f"{flat_text_data}\n"
        "<|im_end|>\n"
    )
    
    # Add all regular messages in order (except system which we already handled)
    for role, content in messages:
        if role == "system":
            continue  # Skip as we already processed it
            
        elif role == "snippet":
            # Additional data from aggregator or web search
            convo += (
                "<|im_start|>system\n"
                "Ecco alcuni dati dal web che potrebbero essere incompleti o obsoleti. "
                "NOTA: Questi dati hanno priorità inferiore rispetto ai dati principali forniti sopra. "
                "In caso di conflitto, usa sempre i dati principali.\n"
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
            # If you have any other custom roles, handle them similarly
            convo += (
                f"<|im_start|>{role}\n"
                f"{content}\n"
                "<|im_end|>\n"
            )

    # Add explicit reminder before the assistant's reply
    convo += (
        "<|im_start|>system\n"
        "RICORDA: Rispondi solo con le informazioni presenti nei dati forniti. "
        "Non inventare statistiche o informazioni aggiuntive. "
        "Se un dato non è disponibile, indicalo chiaramente.\n"
        "<|im_end|>\n"
    )
    
    # Finally, open an assistant block to prompt the model for a new reply
    convo += "<|im_start|>assistant\n"
    return convo