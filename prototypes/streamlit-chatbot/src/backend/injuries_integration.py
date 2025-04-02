#src/backend/injuries_integration.py

import json
import requests
import traceback
from .predizioni import headers, API_HOST, get_team_id, find_fixture_id, extract_teams_from_query
from ..utils.team_aliases import TEAM_NAME_ALIASES
from datetime import datetime



def get_all_upcoming_fixtures(league_id=135, season=2024, n=50):
    """
    Returns a list of upcoming fixtures for the specified league & season.
    Example league_id=135 => Serie A. 
    'n' is how many upcoming matches you'd like (max).
    """
    try:
        url = f'https://{API_HOST}/v3/fixtures'
        params = {
            'league': league_id,
            'season': season,
            'next': n
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        fixtures = data.get('response', [])

        results = []
        for fx in fixtures:
            fixture_info = fx['fixture']
            home_team = fx['teams']['home']['name']
            away_team = fx['teams']['away']['name']
            home_id = fx['teams']['home']['id']
            away_id = fx['teams']['away']['id']
            fixture_id = fixture_info['id']
            date_utc = fixture_info['date']  # e.g. '2024-04-21T18:45:00+00:00'
            timestamp = fixture_info.get('timestamp', 0)
            
            results.append({
                'fixture_id': fixture_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_id': home_id,
                'away_id': away_id,
                'date_utc': date_utc,
                'timestamp': timestamp
            })
        return results
    except Exception as e:
        print(f"Error fetching upcoming fixtures: {str(e)}")
        return []


def get_raw_injuries_json(fixture_id):
    """
    Gets the raw JSON response for injuries data for a specific fixture.
    
    Args:
        fixture_id (int): The fixture ID to get injuries for
        
    Returns:
        str: The raw JSON response
    """
    try:
        url = f'https://{API_HOST}/v3/injuries'
        params = {'fixture': fixture_id}
        print(f"[DEBUG] Requesting injuries data for fixture: {fixture_id}")
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            injury_count = len(data.get('response', []))
            print(f"[DEBUG] Found {injury_count} injuries for fixture: {fixture_id}")
            # Return the raw JSON as a string
            return json.dumps(data, indent=2)
        
        print(f"No injuries data for fixture: {fixture_id}")
        return None
    except Exception as e:
        print(f"Error retrieving injuries data: {str(e)}")
        traceback.print_exc()
        return None

def get_team_injuries_json(team_id, season=2024):
    """
    Gets the raw JSON response for injuries data for a specific team in the current season.
    Prioritizes next fixture to avoid retrieving massive historical data.
    
    Args:
        team_id (int): The team ID to get injuries for
        season (int): The season year (default: 2024)
        
    Returns:
        str: The raw JSON response
    """
    try:
        print(f"[DEBUG] Getting injuries for team ID {team_id} in season {season}")
        
        # Get the next few fixtures for Serie A (league_id=135)
        upcoming_fixtures = get_all_upcoming_fixtures(league_id=135, season=season, n=10)
        
        # Find fixtures involving our team
        team_fixtures = []
        for fixture in upcoming_fixtures:
            # Since the team names in the fixture might not match our team ID exactly,
            # we'll rely on your existing functionality to map them
            fixture_id = fixture['fixture_id']
            
            # Using the fixture ID, get injury data
            injuries_json = get_raw_injuries_json(fixture_id)
            
            # Check if there's data and the team is mentioned
            if injuries_json:
                data = json.loads(injuries_json)
                
                # Check if our team is in the response
                for injury in data.get('response', []):
                    if injury.get('team', {}).get('id') == team_id:
                        print(f"[DEBUG] Found team {team_id} in fixture {fixture_id}")
                        return injuries_json
                
                print(f"[DEBUG] Team {team_id} not found in fixture {fixture_id}")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        print(f"[DEBUG] Trying injuries query with date filter: {today}")
        url = f'https://{API_HOST}/v3/injuries'
        params = {
            'team': team_id,
            'date': today
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('response') and len(data.get('response')) > 0:
                print(f"[DEBUG] Found {len(data.get('response'))} injuries for today")
                return json.dumps(data, indent=2)
        
        # Third approach: Try with league + season + team parameters
        league_id = 135  # Serie A
        print(f"[DEBUG] Trying with league={league_id}, season={season}, team={team_id}")
        url = f'https://{API_HOST}/v3/injuries'
        params = {
            'league': league_id,
            'season': season,
            'team': team_id
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            injuries_count = len(data.get('response', []))
            
            # If too many results, filter to most recent only
            if injuries_count > 15:
                print(f"[DEBUG] Found {injuries_count} injuries, filtering to most recent 10")
                filtered_response = sorted(
                    data.get('response', []),
                    key=lambda x: x.get('fixture', {}).get('timestamp', 0),
                    reverse=True
                )[:10]
                
                # Create new response with only the filtered data
                filtered_data = {
                    'get': data.get('get'),
                    'parameters': data.get('parameters'),
                    'errors': data.get('errors', []),
                    'results': len(filtered_response),
                    'paging': data.get('paging', {}),
                    'response': filtered_response
                }
                
                return json.dumps(filtered_data, indent=2)
            
            return json.dumps(data, indent=2)
        
        # If all else fails, fall back to basic team query but give a clear warning
        print(f"[DEBUG] WARNING: Using basic team query which may return too many results")
        url = f'https://{API_HOST}/v3/injuries'
        params = {'team': team_id}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                injuries_count = len(data.get('response', []))
                print(f"[DEBUG] Found {injuries_count} injuries with basic query")
                
                # Limit to 10 most recent injuries to avoid overwhelming display
                if injuries_count > 10:
                    print(f"[DEBUG] Limiting results from {injuries_count} to 10 most recent")
                    filtered_response = sorted(
                        data.get('response', []),
                        key=lambda x: x.get('fixture', {}).get('timestamp', 0) if x.get('fixture', {}).get('timestamp') else 0,
                        reverse=True
                    )[:10]
                    
                    # Create new response with only the filtered data
                    filtered_data = {
                        'get': data.get('get'),
                        'parameters': data.get('parameters'),
                        'errors': data.get('errors', []),
                        'results': len(filtered_response),
                        'paging': data.get('paging', {}),
                        'response': filtered_response
                    }
                    
                    return json.dumps(filtered_data, indent=2)
                
                return json.dumps(data, indent=2)
                
        print(f"No injuries data found for team: {team_id}")
        return None
    except Exception as e:
        print(f"Error retrieving team injuries data: {str(e)}")
        traceback.print_exc()
        return None

# Add this to injuries_integration.py

def find_next_match_for_team(team_id, season=2024, league_id=135):
    """
    Find the next match for a specific team.
    
    Args:
        team_id (int): The team ID to find next match for
        season (int): The season year
        league_id (int): The league ID (default: 135 for Serie A)
        
    Returns:
        dict: Information about the next match including fixture_id
    """
    try:

        
        # Get upcoming fixtures
        print(f"[DEBUG] Finding next match for team ID {team_id}")
        
        # Get all upcoming fixtures
        upcoming_fixtures = get_all_upcoming_fixtures(league_id=league_id, season=season, n=10)
        if not upcoming_fixtures:
            print(f"[DEBUG] No upcoming fixtures found for league {league_id}")
            return None
            
        # Get the team's name for better logging
        team_name = "Unknown"
        for fixture in upcoming_fixtures:
            if team_id in [fixture.get('home_id'), fixture.get('away_id')]:
                team_name = fixture['home_team'] if team_id == fixture.get('home_id') else fixture['away_team']
                break
        
        # Filter to find matches involving our team
        team_fixtures = []
        for fixture in upcoming_fixtures:
            # First check if we have team IDs in the fixture data
            home_id = fixture.get('home_id')
            away_id = fixture.get('away_id')
            
            # If we don't have IDs, we need to look up the team names
            if (home_id is None or away_id is None):
                # Get team IDs from names using your existing function
                
                home_team = fixture['home_team']
                away_team = fixture['away_team']
                
                # If neither match directly, try get_team_id
                if team_id != home_id and team_id != away_id:
                    home_id = get_team_id(home_team) if home_id is None else home_id
                    away_id = get_team_id(away_team) if away_id is None else away_id
            
            # Check if our team is playing in this fixture
            if team_id == home_id or team_id == away_id:
                team_fixtures.append(fixture)
                print(f"[DEBUG] Found fixture for {team_name}: {fixture['home_team']} vs {fixture['away_team']} on {fixture['date_utc']}")
        
        # Sort by date (although they should already be in order)
        if team_fixtures:

            
            # Convert date strings to datetime objects for sorting
            for fixture in team_fixtures:
                try:
                    fixture['datetime'] = datetime.fromisoformat(fixture['date_utc'].replace('Z', '+00:00'))
                except:
                    # If parsing fails, use a far future date
                    fixture['datetime'] = datetime.max
            
            # Sort by date
            team_fixtures.sort(key=lambda x: x['datetime'])
            
            # Return the next match (first in sorted list)
            next_match = team_fixtures[0]
            print(f"[DEBUG] Next match for {team_name} is {next_match['home_team']} vs {next_match['away_team']} (Fixture ID: {next_match['fixture_id']})")
            return next_match
    
    except Exception as e:
        import traceback
        print(f"[DEBUG] Error finding next match for team {team_id}: {str(e)}")
        traceback.print_exc()
    
    print(f"[DEBUG] No upcoming matches found for team ID {team_id}")
    return None

# Update get_injuries_for_query to handle single team + next match
def get_injuries_for_query(query):
    """
    Get injuries data based on user query.
    
    Args:
        query (str): The user's query
        
    Returns:
        str: The raw JSON injuries data
    """
    print(f"\n[DEBUG] get_injuries_for_query called with: '{query}'")
    
    # Check if this is a query about next match for a specific team
    is_next_match_query = any(term in query.lower() for term in [
        'prossima', 'prossimo', 'prossime', 'prossimi', 'next', 'upcoming',
        'giocherà', 'giocheranno', 'partita', 'incontro'
    ])
    
    # Try to extract team names from query
    home_team, away_team = extract_teams_from_query(query)
    
    # Log the teams found - important for debugging
    print(f"[DEBUG] Teams extracted: home={home_team}, away={away_team}")
    
    # Handle specific case: single team + next match query
    if is_next_match_query and ((home_team and not away_team) or (away_team and not home_team)):
    # Get the team we have
        team = home_team if home_team else away_team
        print(f"[DEBUG] Next match query for team: {team}")
        
        # Get team ID
        team_id = get_team_id(team)
        
        if team_id:
            print(f"[DEBUG] Finding next match for team: {team} (ID: {team_id})")
            
            # Find the next match for this team
            next_match = find_next_match_for_team(team_id)
            
            if next_match:
                fixture_id = next_match['fixture_id']
                print(f"[DEBUG] Found next match fixture ID: {fixture_id}")
                
                # Get injuries for this fixture
                injuries_data = get_raw_injuries_json(fixture_id)
                if injuries_data:
                    print(f"[DEBUG] Found injuries data for fixture ID: {fixture_id}")
                    return injuries_data
                else:
                    print(f"[DEBUG] No injuries data found for fixture ID: {fixture_id}")
                    # Return a simple JSON structure that indicates no injuries
                    return json.dumps({"response": [], "message": f"No injuries found for {team}'s next match"})
    
    # If we found two teams, try to get injuries for the fixture
    if home_team and away_team:
        print(f"[DEBUG] Two teams extracted: {home_team} vs {away_team}")
        
        # Get team IDs
        home_id = get_team_id(home_team)
        away_id = get_team_id(away_team)
        print(f"[DEBUG] Team IDs: {home_team}={home_id}, {away_team}={away_id}")
        
        if home_id and away_id:
            # Find fixture
            print(f"[DEBUG] Trying to find fixture with {home_team} as home team")
            fixture_id = find_fixture_id(home_id, away_id)
            if fixture_id:
                print(f"[DEBUG] Fixture found with ID: {fixture_id}")
                # Get injuries for this fixture
                injuries_data = get_raw_injuries_json(fixture_id)
                if injuries_data:
                    return injuries_data
                else:
                    print(f"[DEBUG] No injuries data found for fixture ID: {fixture_id}")
            
            # Try the reverse order (away might be home)
            print(f"[DEBUG] No fixture found with {home_team} as home. Trying with {away_team} as home team")
            fixture_id = find_fixture_id(away_id, home_id)
            if fixture_id:
                print(f"[DEBUG] Fixture found with reversed teams. ID: {fixture_id}")
                injuries_data = get_raw_injuries_json(fixture_id)
                if injuries_data:
                    return injuries_data
                else:
                    print(f"[DEBUG] No injuries data found for fixture ID: {fixture_id}")
    
    # If we're here, either we didn't find two teams or we couldn't find a fixture
    # Extract ANY team name from the query
    teams_to_check = []
    
    # Add explicitly mentioned teams first
    if home_team:
        teams_to_check.append(home_team)
    if away_team and away_team != home_team:
        teams_to_check.append(away_team)
    
    # If no teams were found using extract_teams_from_query, try another approach
    if not teams_to_check:
        
        query_lower = query.lower()
        for team_name, aliases in TEAM_NAME_ALIASES.items():
            # Check official team name
            if team_name.lower() in query_lower:
                teams_to_check.append(team_name)
                continue
                
            # Check aliases
            for alias in aliases:
                if alias.lower() in query_lower:
                    teams_to_check.append(team_name)
                    break
    
    print(f"[DEBUG] All teams to check for injuries: {teams_to_check}")
    
    # Try to get injuries for each team individually
    for team in teams_to_check:

        team_id = get_team_id(team)
        if team_id:
            # If this was a next match query and we found a team, try that approach first
            if is_next_match_query:
                print(f"[DEBUG] Trying next match approach for team: {team} (ID: {team_id})")
                next_match = find_next_match_for_team(team_id)
                if next_match:
                    fixture_id = next_match['fixture_id']
                    injuries_data = get_raw_injuries_json(fixture_id)
                    if injuries_data:
                        print(f"[DEBUG] Found injuries for next match (Fixture ID: {fixture_id})")
                        return injuries_data
            
            # Fall back to getting all team injuries
            print(f"[DEBUG] Getting all injuries for team: {team} (ID: {team_id})")
            team_injuries = get_team_injuries_json(team_id)
            if team_injuries:
                print(f"[DEBUG] Found injury data for {team}")
                return team_injuries
    
    print(f"[DEBUG] Could not find teams or fixtures for injuries query")
    return None


def is_injuries_query(query):
    """Check if query is related to player injuries or unavailability"""
    query_lower = query.lower().replace("'", "").replace("  ", " ")
    
    print(f"[DEBUG] Checking if query is injury-related: '{query_lower}'")
    # More specific primary injury keywords that take precedence
    primary_keywords = [
        'infortunat', 'infortunio', 'infortuni',  # injuries
        'nfortunat', 'nfortunio', 'nfortuni',     # common misspellings
        'squalificat', 'squalifica',              # suspensions
        'indisponibil', 'non disponibil', 'ammalati'
    ]
    
    # If any primary keyword is present, this is definitely an injuries query
    if any(keyword in query_lower for keyword in primary_keywords):
        print(f"[DEBUG] Primary injury keyword found in query: '{query}'")
        return True
    
    # Secondary keywords that might indicate injuries but could overlap with lineup queries
    secondary_keywords = [
        'non giocher', 'assent', 'assenz',  # won't play, absent
        'chi manca', 'mancheranno'  # who's missing
    ]
    
    # Check for more specific injury patterns that shouldn't be confused with lineup queries
    injury_patterns = [
        'non saranno disponibili',
        'giocatori che non',
        'chi sono gli indisponibili',
        'chi non giocherà',
        'giocatore fermo',
        'giocatori fermi',
        'non ci sarà',
        'non ci saranno'
    ]
    
    if any(pattern in query_lower for pattern in injury_patterns):
        print(f"[DEBUG] Injury pattern found in query: '{query}'")
        return True
    
    home_team, away_team = extract_teams_from_query(query)
    
    next_match_terms = [
        'prossima', 'prossimo', 'prossime', 'prossimi',
        'giocherà', 'giocheranno'
    ]
    
    has_team = bool(home_team or away_team)
    has_next_match_term = any(term in query_lower for term in next_match_terms)
    
    if has_team and has_next_match_term:
        if any(keyword in query_lower for keyword in secondary_keywords):
            print(f"[DEBUG] Team + next match + injury keyword found in query: '{query}'")
            return True
    
    # If we have secondary keywords AND specific clues that this is about player status not lineups
    if any(keyword in query_lower for keyword in secondary_keywords):
        # Look for specific clues that this is about availability status
        availability_clues = ['disponibil', 'partecip', 'presen', 'recup']
        if any(clue in query_lower for clue in availability_clues):
            print(f"[DEBUG] Secondary keyword + availability clue found in query: '{query}'")
            return True
            
        # If the query specifically asks about players not playing, but doesn't ask for formation
        formation_keywords = ['formazione', 'formazioni', 'titolar', 'scenderanno in campo', 'giocheranno']
        if not any(keyword in query_lower for keyword in formation_keywords):
            print(f"[DEBUG] Secondary keyword without formation terms found in query: '{query}'")
            return True
    
    print(f"[DEBUG] Query not detected as injury-related: '{query}'")
    return False


def process_injuries_json(raw_json):
    """
    Process the raw injuries JSON into a format suitable for the chat response.
    
    Args:
        raw_json (str): The raw JSON string from the API
        
    Returns:
        tuple: (flat_text_data, key_stats, team_names)
    """
    try:
        data = json.loads(raw_json)
        response_data = data.get('response', [])
        
        if not response_data:
            return "No injury data available.", "No injuries found.", []
        
        # Print the number of injuries found for debugging
        print(f"[DEBUG] Processing {len(response_data)} injury records")
        
        # Sort by fixture date - most recent/upcoming first
        response_data.sort(
            key=lambda x: x.get('fixture', {}).get('timestamp', 0) 
                if x.get('fixture', {}).get('timestamp') is not None else 0,
            reverse=True
        )
        
        # Extract teams involved
        teams = set()
        for item in response_data:
            team_name = item.get('team', {}).get('name', '')
            if team_name:
                teams.add(team_name)
        
        team_names = list(teams)
        print(f"[DEBUG] Teams with injuries: {team_names}")
        
        # Find unique fixtures and their details
        fixtures = {}
        for item in response_data:
            fixture = item.get('fixture', {})
            fixture_id = fixture.get('id')
            if fixture_id:
                timestamp = fixture.get('timestamp', 0)
                date = fixture.get('date', '')
                
                # Format the date nicely if available
                if date:
                    try:
                        from datetime import datetime
                        date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                    except:
                        formatted_date = date
                else:
                    formatted_date = "Data non disponibile"
                    
                if fixture_id not in fixtures:
                    fixtures[fixture_id] = {
                        'timestamp': timestamp,
                        'date': formatted_date,
                        'teams': set(),
                        'injuries': []
                    }
                
                fixtures[fixture_id]['teams'].add(item.get('team', {}).get('name', ''))
                fixtures[fixture_id]['injuries'].append(item)
        
        # For queries about next match, focus on the most imminent fixture
        latest_fixture = None
        latest_timestamp = 0
        for fixture_id, info in fixtures.items():
            if info['timestamp'] > latest_timestamp:
                latest_timestamp = info['timestamp']
                latest_fixture = fixture_id
        
        # If we have multiple fixtures, we'll focus on the most relevant one
        # This helps avoid showing hundreds of historical injuries
        if latest_fixture and len(fixtures) > 1:
            print(f"[DEBUG] Multiple fixtures found, focusing on fixture ID {latest_fixture} on {fixtures[latest_fixture]['date']}")
            
            # We'll use this fixture's data, but also count the total injuries
            total_injury_count = len(response_data)
            fixture_injury_count = len(fixtures[latest_fixture]['injuries'])
            
            # If there's a significant mismatch, we'll note it
            if total_injury_count > fixture_injury_count + 5:
                print(f"[DEBUG] Warning: Showing {fixture_injury_count} of {total_injury_count} total injuries")
            
            # Filter to just this fixture
            response_data = fixtures[latest_fixture]['injuries']
            
            # Add note about fixture date
            fixture_date = fixtures[latest_fixture]['date']
        else:
            # No need to filter, but still get the date of the most recent fixture
            fixture_date = fixtures[latest_fixture]['date'] if latest_fixture else None
            
        # Create a dictionary to organize injuries by team
        injuries_by_team = {}
        for item in response_data:
            team_name = item.get('team', {}).get('name', '')
            if team_name not in injuries_by_team:
                injuries_by_team[team_name] = []
            
            player_info = item.get('player', {})
            player_name = player_info.get('name', 'Unknown')
            player_type = player_info.get('type', 'Unknown')
            player_reason = player_info.get('reason', 'Unknown')
            
            injuries_by_team[team_name].append({
                'name': player_name,
                'type': player_type,
                'reason': player_reason
            })
        
        # Create flat text representation
        flat_text = []
        for team, players in injuries_by_team.items():
            flat_text.append(f"Team: {team}")
            for player in players:
                flat_text.append(f"  - {player['name']}: {player['type']} - {player['reason']}")
        
        flat_text_data = "\n".join(flat_text)
        
        # Create key stats (summary information)
        key_stats = []
        
        # Include fixture date if available
        if fixture_date:
            key_stats.append(f"Fixture date: {fixture_date}")
        
        total_players = sum(len(players) for players in injuries_by_team.values())
        key_stats.append(f"Total unavailable players: {total_players}")
        
        for team, players in injuries_by_team.items():
            missing_count = len([p for p in players if p['type'] == 'Missing Fixture'])
            questionable_count = len([p for p in players if p['type'] == 'Questionable'])
            key_stats.append(f"{team}: {len(players)} unavailable ({missing_count} confirmed, {questionable_count} questionable)")
        
        key_stats_str = "\n".join(key_stats)
        
        return flat_text_data, key_stats_str, team_names
        
    except Exception as e:
        import traceback
        print(f"Error processing injuries JSON: {str(e)}")
        traceback.print_exc()
        return f"Error processing data: {str(e)}", "No stats available", []
    
def generate_injuries_response(team_names, key_stats, flat_text_data, query=None):
    # Handle edge cases better
    if not team_names or len(team_names) == 0:
        return "Mi dispiace, non ho trovato dati sugli infortunati per le squadre richieste. Verifica i nomi delle squadre e riprova."
    
    if "No injury data available" in flat_text_data or "Error processing data" in flat_text_data:
        if len(team_names) == 1:
            return f"Mi dispiace, non ho trovato dati sugli infortunati per {team_names[0]}. I dati potrebbero non essere ancora disponibili o la squadra potrebbe non avere giocatori indisponibili segnalati."
        elif len(team_names) == 2:
            return f"Mi dispiace, non ho trovato dati sugli infortunati per la partita {team_names[0]} vs {team_names[1]}. I dati potrebbero non essere ancora disponibili o le squadre potrebbero non avere giocatori indisponibili segnalati."
        else:
            return "Mi dispiace, non ho trovato dati sugli infortunati per le squadre richieste. I dati potrebbero non essere ancora disponibili."
    
    # First try to extract the specific team from the query
    specific_team = None
    if query:
        # Try standard extraction first
        from .predizioni import extract_teams_from_query
        home_team, away_team = extract_teams_from_query(query)
        specific_team = home_team if home_team else away_team
        
        # If extraction failed but we know it's about a specific team,
        # try to find matches in the raw query text
        if not specific_team and len(team_names) > 0:
            query_lower = query.lower().replace("'", "").replace("dell ", "").replace("dell'", "")
            for team in team_names:
                if team.lower() in query_lower:
                    specific_team = team
                    break
                # Check for shortened team names too (e.g., "Milan" in "AC Milan")
                shortened = team.split()[-1]  # Get last word of team name
                if len(shortened) > 3 and shortened.lower() in query_lower:
                    specific_team = team
                    break
                    
    print(f"[DEBUG] Final specific team determined: {specific_team}")
    
    # If we have a specific team, filter team_names to only include that team
    teams_to_show = set()
    if specific_team:
        teams_to_show.add(specific_team)
    else:
        teams_to_show = set(team_names)
    
    print(f"[DEBUG] Teams to show in response: {teams_to_show}")
    

    
    response = []
    
    # Check if this is for a specific fixture
    fixture_date = None
    for line in key_stats.split('\n'):
        if line.startswith('Fixture date:'):
            fixture_date = line.replace('Fixture date:', '').strip()
            break
    
    # Add header with context about next match
    other_team = None
    if len(team_names) == 2 and len(teams_to_show) == 1:
        # If we're showing only one team from a two-team match
        specific_team_name = next(iter(teams_to_show))
        other_team = next(team for team in team_names if team != specific_team_name)
        
        if fixture_date:
            response.append(f"# Giocatori indisponibili per {specific_team_name}")
            response.append(f"**Prossima partita**: {specific_team_name} vs {other_team} - {fixture_date}")
        else:
            response.append(f"# Giocatori indisponibili per {specific_team_name}")
            response.append(f"**Prossima partita**: {specific_team_name} vs {other_team}")
    elif len(teams_to_show) == 1:
        team_name = next(iter(teams_to_show))
        if fixture_date:
            response.append(f"# Giocatori indisponibili per {team_name}")
            response.append(f"**Data partita**: {fixture_date}")
        else:
            response.append(f"# Giocatori indisponibili per {team_name}")
    else:
        # Multiple teams
        if fixture_date:
            response.append(f"# Giocatori indisponibili per {' vs '.join(teams_to_show)}")
            response.append(f"**Data partita**: {fixture_date}")
        else:
            response.append(f"# Giocatori indisponibili per {' vs '.join(teams_to_show)}")
    
    response.append("")
    
    # Translate injury types and reasons to Italian
    injury_translations = {
        "Muscle Injury": "Infortunio muscolare",
        "Thigh Injury": "Infortunio alla coscia",
        "Ankle Injury": "Infortunio alla caviglia",
        "Calf Injury": "Infortunio al polpaccio",
        "Knee Injury": "Infortunio al ginocchio",
        "Hamstring": "Infortunio ai muscoli posteriori della coscia",
        "Red Card": "Cartellino rosso",
        "Knock": "Contusione",
        "Leg Injury": "Infortunio alla gamba",
        "Foot Injury": "Infortunio al piede",
        "Back Injury": "Infortunio alla schiena",
        "Shoulder Injury": "Infortunio alla spalla",
        "Suspension": "Squalifica",
        "Groin Injury": "Infortunio all'inguine",
        "Illness": "Malattia",
        "Hip Injury": "Infortunio all'anca",
        "Head Injury": "Infortunio alla testa",
        "Not disclosed": "Non divulgato",
        "Unknown": "Sconosciuto",
        "Injury": "Infortunio",
        "Missing Fixture": "Non disponibile",
        "Questionable": "In dubbio"
        # Add more translations as needed
    }
    
    # Check for unreasonable numbers in the stats
    has_unreasonable_numbers = False
    total_players = 0
    
    for line in key_stats.split('\n'):
        if "Total unavailable players:" in line:
            parts = line.split(':')
            if len(parts) > 1:
                try:
                    total_count = int(parts[1].strip())
                    if total_count > 20:  # Unreasonable number for a single match
                        has_unreasonable_numbers = True
                        total_players = total_count
                except:
                    pass
    
    # If numbers are unreasonable, add a note about filtered data
    if has_unreasonable_numbers:
        response.append("**Nota**: Sono stati trovati numerosi giocatori indisponibili registrati. Mostro solo i dati più recenti e rilevanti.")
        response.append("")
    
    # Add key stats summary for the filtered teams only
    filtered_stats = []
    total_unavailable = 0
    
    for line in key_stats.split('\n'):
        if line.startswith('Fixture date:'):
            # Already handled above
            continue
            
        if "Total unavailable players" in line and len(teams_to_show) == len(team_names):
            if has_unreasonable_numbers:
                # Don't show unreasonable numbers
                continue
                
            total = line.split(": ")[1]
            total_unavailable = int(total)
            filtered_stats.append(f"In totale ci sono **{total}** giocatori indisponibili.")
            
        elif ":" in line and not line.startswith("Error"):
            team, count_info = line.split(":", 1)
            
            # Only include this team if it's in our filtered set
            show_this_team = False
            for team_to_show in teams_to_show:
                if team_to_show in team:
                    show_this_team = True
                    break
            
            if not show_this_team:
                continue
                
            # Check for unreasonable numbers in team stats
            if has_unreasonable_numbers and "unavailable" in count_info:
                # Try to extract the count
                import re
                count_match = re.search(r'(\d+) unavailable', count_info)
                if count_match and int(count_match.group(1)) > 10:
                    # Just show "Giocatori indisponibili" without the inflated number
                    filtered_stats.append(f"**{team}:** Giocatori indisponibili:")
                    continue
            
            # Translate to Italian
            count_info = count_info.replace("unavailable", "indisponibili")
            count_info = count_info.replace("confirmed", "confermati")
            count_info = count_info.replace("questionable", "in dubbio")
            filtered_stats.append(f"**{team}:** {count_info}")
    
    # If we're filtering to one team, don't show the total
    if len(teams_to_show) < len(team_names) and filtered_stats:
        # Remove the total line if it's the first item
        if filtered_stats and "In totale ci sono" in filtered_stats[0]:
            filtered_stats.pop(0)
    
    # Add filtered stats to response
    response.extend(filtered_stats)
    response.append("")
    
    # Process the detailed flat text data, but filter by team
    current_team = None
    has_players = False
    player_count = 0
    show_current_team = False
    
    for line in flat_text_data.split('\n'):
        if line.startswith("Team: "):
            current_team = line.replace("Team: ", "")
            
            # Reset show flag for new team
            show_current_team = False
            
            # Only show this team if it's in our filtered set
            for team_to_show in teams_to_show:
                if team_to_show in current_team:
                    show_current_team = True
                    break
            
            if show_current_team:
                response.append(f"## {current_team}")
                # Reset player count for new team
                player_count = 0
            
        elif line.strip().startswith("- ") and show_current_team:
            # Only show a reasonable number of players per team (max 10)
            player_count += 1
            if player_count > 10 and has_unreasonable_numbers:
                if player_count == 11:  # Only add this message once
                    response.append("_(Altri giocatori indisponibili non mostrati)_")
                continue
                
            has_players = True
            # Process player info line
            player_info = line.strip()[2:]
            if ":" in player_info:
                name, rest = player_info.split(":", 1)
                if " - " in rest:
                    status_type, reason = rest.strip().split(" - ", 1)
                    
                    # Translate status and reason
                    translated_reason = injury_translations.get(reason.strip(), reason)
                    
                    # Format based on the status type
                    if "Missing Fixture" in status_type:
                        status = "**Non disponibile**"
                    elif "Questionable" in status_type:
                        status = "**In dubbio**"
                    else:
                        status = f"**{status_type}**"
                    
                    response.append(f"- **{name}**: {status} - {translated_reason}")
                else:
                    # Translate the rest if possible
                    translated_rest = injury_translations.get(rest.strip(), rest)
                    response.append(f"- **{name}**: {translated_rest}")
            else:
                response.append(f"- {player_info}")
    
    # If we found team names but no players, add a message
    if not has_players and teams_to_show:
        if len(teams_to_show) == 1:
            team_name = next(iter(teams_to_show))
            response.append(f"Non ci sono giocatori indisponibili segnalati per {team_name} al momento.")
        else:
            team_names_str = " vs ".join(teams_to_show)
            response.append(f"Non ci sono giocatori indisponibili segnalati per questa partita ({team_names_str}) al momento.")
    
    # Add disclaimer
    response.append("")
    response.append("_Nota: I dati sugli infortunati vengono aggiornati ogni 4 ore dall'API fornitore. Le informazioni potrebbero non essere complete per tutte le squadre._")
    
    return "\n".join(response)

def find_next_match_for_team(team_id, season=2024, league_id=135):

    """
    Find the next match for a specific team.
    
    Args:
        team_id (int): The team ID to find next match for
        season (int): The season year
        league_id (int): The league ID (default: 135 for Serie A)
        
    Returns:
        dict: Information about the next match including fixture_id
    """
    try:
        
        # Get upcoming fixtures
        print(f"[DEBUG] Finding next match for team ID {team_id}")
        
        # Get all upcoming fixtures
        upcoming_fixtures = get_all_upcoming_fixtures(league_id=league_id, season=season, n=10)
        if not upcoming_fixtures:
            print(f"[DEBUG] No upcoming fixtures found for league {league_id}")
            return None
            
        # Get the team's name for better logging
        team_name = "Unknown"
        for fixture in upcoming_fixtures:
            if team_id in [fixture.get('home_id'), fixture.get('away_id')]:
                team_name = fixture['home_team'] if team_id == fixture.get('home_id') else fixture['away_team']
                break
        
        # Filter to find matches involving our team
        team_fixtures = []
        for fixture in upcoming_fixtures:
            # First check if we have team IDs in the fixture data
            home_id = fixture.get('home_id')
            away_id = fixture.get('away_id')
            
            # If we don't have IDs, we need to look up the team names
            if (home_id is None or away_id is None):
                # Get team IDs from names using your existing function
                
                home_team = fixture['home_team']
                away_team = fixture['away_team']
                
                # If neither match directly, try get_team_id
                if team_id != home_id and team_id != away_id:
                    home_id = get_team_id(home_team) if home_id is None else home_id
                    away_id = get_team_id(away_team) if away_id is None else away_id
            
            # Check if our team is playing in this fixture
            if team_id == home_id or team_id == away_id:
                team_fixtures.append(fixture)
                print(f"[DEBUG] Found fixture for {team_name}: {fixture['home_team']} vs {fixture['away_team']} on {fixture['date_utc']}")
        
        # Sort by date (although they should already be in order)
        if team_fixtures:

            
            # Convert date strings to datetime objects for sorting
            for fixture in team_fixtures:
                try:
                    fixture['datetime'] = datetime.fromisoformat(fixture['date_utc'].replace('Z', '+00:00'))
                except:
                    # If parsing fails, use a far future date
                    fixture['datetime'] = datetime.max
            
            # Sort by date
            team_fixtures.sort(key=lambda x: x['datetime'])
            
            # Return the next match (first in sorted list)
            next_match = team_fixtures[0]
            print(f"[DEBUG] Next match for {team_name} is {next_match['home_team']} vs {next_match['away_team']} (Fixture ID: {next_match['fixture_id']})")
            return next_match
    
    except Exception as e:
        import traceback
        print(f"[DEBUG] Error finding next match for team {team_id}: {str(e)}")
        traceback.print_exc()
    
    print(f"[DEBUG] No upcoming matches found for team ID {team_id}")
    return None


