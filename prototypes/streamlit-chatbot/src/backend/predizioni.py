#bettingbot/src/backend/predizioni.py
from flask import Flask, request, jsonify
import requests
from collections import OrderedDict
from datetime import datetime
import json
from src.utils.team_aliases import TEAM_NAME_ALIASES
import numpy as np
from datetime import datetime, timedelta
API_KEY = 'REDACTED'
API_HOST = 'api-football-v1.p.rapidapi.com'

headers = {
    'X-RapidAPI-Key': API_KEY,
    'X-RapidAPI-Host': API_HOST
}


def get_team_id(team_name, country='Italy'):
    try:
        print(f"[DEBUG] Getting ID for team: {team_name}, country: {country}")
        
        # Check if this team name is in our aliases
        team_name_lower = team_name.lower()
        official_name = None
        
        # Look for the team in our aliases
        for official, aliases in TEAM_NAME_ALIASES.items():
            if team_name_lower in aliases:
                official_name = official
                print(f"[DEBUG] Team name matched to alias: {team_name} -> {official_name}")
                break
        
        # If we found an official name in our aliases, use that instead
        if official_name:
            search_name = official_name
        else:
            search_name = team_name
        
        url = f'https://{API_HOST}/v3/teams'
        params = {'search': search_name}
        response = requests.get(url, headers=headers, params=params)
        print(f"[DEBUG] API status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            for team in data.get('response', []):
                team_info = team['team']
                print(f"[DEBUG] Found team: {team_info['name']} (ID: {team_info['id']}, Country: {team_info['country']})")
                
                # For Italian teams, handle special cases like "AS Roma" vs "Roma"
                if country.lower() == 'italy':
                    # Check if this is the team we're looking for
                    team_found = False
                    
                    # Direct match on name
                    if team_info['name'].lower() == search_name.lower():
                        team_found = True
                    
                    # Check against our aliases
                    for official, aliases in TEAM_NAME_ALIASES.items():
                        if (team_info['name'].lower() in [a.lower() for a in aliases] or 
                            team_info['name'].lower() == official.lower()):
                            if search_name.lower() == official.lower() or search_name.lower() in aliases:
                                team_found = True
                                break
                    
                    if team_found and team_info['country'].lower() == country.lower():
                        print(f"[DEBUG] Team matched: {search_name} = {team_info['id']} ({team_info['name']})")
                        return team_info['id']
                
                # Standard exact match for non-Italian teams
                elif (team_info['name'].lower() == search_name.lower() and
                    team_info['country'].lower() == country.lower()):
                    print(f"[DEBUG] Team matched: {search_name} = {team_info['id']}")
                    return team_info['id']
        
        # Special hardcoded fixes for common Serie A teams that might cause issues
        if country.lower() == 'italy':
            if search_name.lower() == "roma" or search_name.lower() == "as roma":
                print(f"[DEBUG] Using hardcoded ID for Roma: 497")
                return 497
            elif search_name.lower() == "inter" or search_name.lower() == "internazionale":
                print(f"[DEBUG] Using hardcoded ID for Inter: 505")
                return 505
            elif search_name.lower() == "milan" or search_name.lower() == "ac milan":
                print(f"[DEBUG] Using hardcoded ID for Milan: 489")
                return 489
        
        print(f"[DEBUG] Team not found: {search_name}")
        return None
    except Exception as e:
        print(f"[DEBUG] Error getting team ID: {str(e)}")
        return None
    
def find_fixture_id(home_team_id, away_team_id, league_id=135, season=2024):
    try:
        print(f"\n[DEBUG] Finding fixture for: Home ID={home_team_id}, Away ID={away_team_id}, League={league_id}, Season={season}")  # Add this
        url = f'https://{API_HOST}/v3/fixtures'
        params = {
            'league': league_id,
            'season': season,
            'team': home_team_id,
            'next': 50
        }
        print(f"[DEBUG] API Request params: {params}")  # Add this line
        response = requests.get(url, headers=headers, params=params)
        print(f"[DEBUG] API status code: {response.status_code}")  # Add this line
        
        if response.status_code == 200:
            data = response.json()
            fixtures = data.get('response', [])
            print(f"[DEBUG] Found {len(fixtures)} fixtures for team ID {home_team_id}")  # Add this line
            
            for fixture in fixtures:
                teams = fixture['teams']
                print(f"[DEBUG] Checking fixture: {teams['home']['name']} (ID: {teams['home']['id']}) vs "
                     f"{teams['away']['name']} (ID: {teams['away']['id']})")  # Add this line
                
                if (teams['home']['id'] == home_team_id and 
                    teams['away']['id'] == away_team_id):
                    print(f"[DEBUG] MATCH FOUND! Fixture ID: {fixture['fixture']['id']}")  # Add this line
                    return fixture['fixture']['id']
            
            # Try to print actual teams matching our IDs from all fixtures
            home_team_found = False
            away_team_found = False
            for fixture in fixtures:
                teams = fixture['teams']
                if teams['home']['id'] == home_team_id or teams['away']['id'] == home_team_id:
                    home_team_found = True
                    print(f"[DEBUG] Home team found in another match: {teams['home']['name']} vs {teams['away']['name']}")
                
                if teams['home']['id'] == away_team_id or teams['away']['id'] == away_team_id:
                    away_team_found = True
                    print(f"[DEBUG] Away team found in another match: {teams['home']['name']} vs {teams['away']['name']}")
            
            if not home_team_found:
                print(f"[DEBUG] No matches found containing team ID {home_team_id} at all!")
            if not away_team_found:
                print(f"[DEBUG] No matches found containing team ID {away_team_id} at all!")
                
        else:
            print(f"[DEBUG] API error response: {response.text}")  # Add this line
            
        print(f"[DEBUG] No fixture found for teams: {home_team_id} vs {away_team_id}")
        return None
    except Exception as e:
        print(f"[DEBUG] Error finding fixture: {str(e)}")
        return None


def get_raw_prediction_json(fixture_id):
    """
    Gets the full, unformatted JSON response from the predictions API.
    
    Args:
        fixture_id (int): The fixture ID to get predictions for
        
    Returns:
        str: The complete JSON response as a string
    """
    try:
        url = f'https://{API_HOST}/v3/predictions'
        params = {'fixture': fixture_id}
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                # Return the full, unprocessed JSON as a string
                return json.dumps(data, indent=2)
        
        print(f"No prediction data for fixture: {fixture_id}")
        return None
    except Exception as e:
        print(f"Error retrieving raw prediction data: {str(e)}")
        return None

def extract_teams_from_query(query):

    print(f"\n[DEBUG] Extracting teams from query: '{query}'")
    
    # Convert query to lowercase for matching
    query_lower = query.lower()
    
    # Find all possible teams mentioned in the query
    found_teams = []
    
    # Try to match each team's aliases against the query
    for official_name, aliases in TEAM_NAME_ALIASES.items():
        # Check if the official name is in the query
        if official_name.lower() in query_lower:
            print(f"[DEBUG] Found team by official name: {official_name}")
            found_teams.append(official_name)
            continue
            
        # Check if any alias is in the query
        for alias in aliases:
            if alias in query_lower:
                print(f"[DEBUG] Found team by alias: {alias} -> {official_name}")
                found_teams.append(official_name)
                break
    
    # Remove duplicates while preserving order
    found_teams = list(dict.fromkeys(found_teams))
    
    # If we found exactly 2 teams, return them
    if len(found_teams) == 2:
        print(f"[DEBUG] Returning teams: {found_teams[0]} and {found_teams[1]}")
        return found_teams[0], found_teams[1]
    else:
        print(f"[DEBUG] Could not identify exactly 2 teams. Found: {found_teams}")
        return None, None

def get_prediction_for_query(query):
    """
    Get prediction data based on user query.
    
    Args:
        query (str): The user's query
        
    Returns:
        str: The raw JSON prediction data
    """
    print(f"\n[DEBUG] get_prediction_for_query called with: '{query}'")  # Add this line
    
    # Try to extract team names from query
    home_team, away_team = extract_teams_from_query(query)
    
    if home_team and away_team:
        print(f"[DEBUG] Teams extracted: {home_team} vs {away_team}")  # Add this line
        
        # Get team IDs
        home_id = get_team_id(home_team)
        away_id = get_team_id(away_team)
        print(f"[DEBUG] Team IDs: {home_team}={home_id}, {away_team}={away_id}")  # Add this line
        
        if home_id and away_id:
            # Find fixture
            print(f"[DEBUG] Trying to find fixture with {home_team} as home team")  # Add this line
            fixture_id = find_fixture_id(home_id, away_id)
            if fixture_id:
                print(f"[DEBUG] Fixture found with ID: {fixture_id}")  # Add this line
                # Get raw prediction data
                return get_raw_prediction_json(fixture_id)
            
            # Try the reverse order (away might be home)
            print(f"[DEBUG] No fixture found with {home_team} as home. Trying with {away_team} as home team")  # Add this line
            fixture_id = find_fixture_id(away_id, home_id)
            if fixture_id:
                print(f"[DEBUG] Fixture found with reversed teams. ID: {fixture_id}")  # Add this line
                return get_raw_prediction_json(fixture_id)
            
            print(f"[DEBUG] No fixture found with either team order")  # Add this line
    else:
        print(f"[DEBUG] Could not extract two teams from query")  # Add this line
    
    # If we couldn't find specific teams or fixture, get the next upcoming match
    print(f"[DEBUG] Falling back to next upcoming fixture")  # Add this line
    upcoming = get_all_upcoming_fixtures(n=1)
    if upcoming:
        fixture_id = upcoming[0]['fixture_id']
        print(f"[DEBUG] Using next upcoming fixture: {fixture_id}")  # Add this line
        return get_raw_prediction_json(fixture_id)
    
    print(f"[DEBUG] No prediction data found for query")  # Add this line
    return None

def get_all_leagues():
    """
    Return a list of leagues from the API, e.g. [ {league_id, name, country}, ... ]
    Filter out if you only want certain countries or league types.
    """
    import requests

    try:
        url = f'https://{API_HOST}/v3/leagues'
        # Possibly add filters, e.g. 'type': 'league', 'country': 'Italy' if you only want certain countries
        params = {}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            results = []
            for entry in data.get('response', []):
                league_info = entry.get('league', {})
                country_info = entry.get('country', {})
                # For example:
                results.append({
                    'league_id': league_info.get('id'),
                    'league_name': league_info.get('name'),
                    'country': country_info.get('name'),
                    'season': league_info.get('season', 2024)  # might be missing
                })
            return results
        return []
    except Exception as e:
        print(f"Error fetching leagues: {e}")
        return []

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
            fixture_id = fixture_info['id']
            date_utc = fixture_info['date']  # e.g. '2024-04-21T18:45:00+00:00'
            
            results.append({
                'fixture_id': fixture_id,
                'home_team': home_team,
                'away_team': away_team,
                'date_utc': date_utc
            })
        return results
    except Exception as e:
        print(f"Error fetching upcoming fixtures: {str(e)}")
        return []


def format_prediction_data(prediction_data):
    """Format the prediction data - returns OrderedDict for API and formatted string for Gradio"""
    try:
        # Extract data
        predictions = prediction_data.get('predictions', {})
        teams = prediction_data.get('teams', {})
        comparison = prediction_data.get('comparison', {})
        h2h = prediction_data.get('h2h', [])
        fixture = prediction_data.get('fixture', {})
        
        # Teams Information
        home_team = teams.get('home', {}).get('name', 'Unknown')
        away_team = teams.get('away', {}).get('name', 'Unknown')
        
        # Prediction Details
        winner_info = predictions.get('winner', {})
        winner = winner_info.get('name', 'No Prediction')
        advice = predictions.get('advice', 'No advice available')
        win_percent = predictions.get('percent', {})
        
        # Goals Predictions
        goals_predictions = predictions.get('goals', {})
        home_goals_prediction = goals_predictions.get('home', 'N/A')
        away_goals_prediction = goals_predictions.get('away', 'N/A')
        
        # Prepare the OrderedDict for API response
        result = OrderedDict()
        result['match'] = f"{home_team} vs {away_team}"
        result['predicted_winner'] = winner
        result['win_probabilities'] = {
            'home': win_percent.get('home', 'N/A'),
            'draw': win_percent.get('draw', 'N/A'),
            'away': win_percent.get('away', 'N/A')
        }
        result['betting_advice'] = advice
        result['goals_predictions'] = {
            home_team: home_goals_prediction,
            away_team: away_goals_prediction
        }
        
        # Statistical comparison (excluding poisson distribution)
        statistical_comparison = {
            key: {
                'home': value.get('home', 'N/A'),
                'away': value.get('away', 'N/A')
            }
            for key, value in comparison.items()
            if 'poisson' not in key.lower().replace(' ', '')
        }
        result['statistical_comparison'] = statistical_comparison
        
        # Head-to-head matches
        result['head_to_head'] = [
            {
                'date': match.get('fixture', {}).get('date', 'Unknown'),
                'home_team': match.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                'home_goals': match.get('goals', {}).get('home', 'N/A'),
                'away_goals': match.get('goals', {}).get('away', 'N/A'),
                'away_team': match.get('teams', {}).get('away', {}).get('name', 'Unknown'),
            }
            for match in h2h
        ]

        return result

    except Exception as e:
        print(f"Error formatting prediction data: {str(e)}")
        return None
    

def retrieve_prediction(fixture_id):
    try:
        url = f'https://{API_HOST}/v3/predictions'
        params = {'fixture': fixture_id}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['response']:
                prediction_data = data['response'][0]
                # Return the raw prediction data for the Flask API
                return format_prediction_data(prediction_data)
        print(f"No prediction data for fixture: {fixture_id}")
        return None
    except Exception as e:
        print(f"Error retrieving prediction: {str(e)}")
        return None

def fetch_odds_history_for_graph(fixture_id, market_id, selection, bookmaker=None):

        seed = hash(f"{fixture_id}_{market_id}_{selection}_{bookmaker}") % 10000
        np.random.seed(seed)
        
        # Generate a base odd value between 1.5 and 3.5
        base_odd = np.random.uniform(1.5, 3.5)
        
        # Create timestamps for last 7 days with 6-hour intervals
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        timestamps = []
        current = start_time
        while current <= end_time:
            timestamps.append(current)
            current += timedelta(hours=6)
        
        # Add some randomness to timestamps to make it more realistic
        timestamps = [t + timedelta(minutes=np.random.randint(-30, 30)) for t in timestamps]
        
        # Generate odds with some random variation and trend
        trend_direction = np.random.choice([-1, 1])  # Upward or downward trend
        trend_magnitude = np.random.uniform(0.05, 0.15)  # How strong the trend is
        
        # Create data points
        data = []
        for i, ts in enumerate(timestamps):
            # Calculate trend effect
            trend_effect = trend_direction * trend_magnitude * (i / len(timestamps))
            
            # Random noise
            noise = np.random.normal(0, 0.03)
            
            # Calculate odd value with trend and noise
            odd_value = max(1.01, base_odd + trend_effect + noise)
            odd_value = round(odd_value, 2)  # Round to 2 decimal places
            
            data.append({
                "fixture_id": fixture_id,
                "market_id": market_id,
                "selection": selection,
                "bookmaker": bookmaker,
                "odd": odd_value,
                "timestamp": ts
            })
        
        return data

def format_prediction_for_chat(prediction_data):
    """Format the prediction data into a readable string"""
    try:
        if not prediction_data:
            return "Nessuna predizione disponibile"

        formatted_lines = []
        
        # Match info
        match = prediction_data.get('match', '')
        formatted_lines.extend([
            f"🏟️ {match}",
            ""
        ])
        
        # Win probabilities
        win_prob = prediction_data.get('win_probabilities', {})
        formatted_lines.extend([
            "📊 Probabilità:",
            f"• Vittoria {match.split(' vs ')[0]}: {win_prob.get('home', 'N/A')}",
            f"• Pareggio: {win_prob.get('draw', 'N/A')}",
            f"• Vittoria {match.split(' vs ')[1]}: {win_prob.get('away', 'N/A')}",
            ""
        ])
        
        # Goals predictions
        goals = prediction_data.get('goals_predictions', {})
        formatted_lines.extend([
            "⚽ Goals previsti:",
            f"• {list(goals.keys())[0]}: {list(goals.values())[0]}",
            f"• {list(goals.keys())[1]}: {list(goals.values())[1]}",
            ""
        ])
        
        # Statistical comparison
        stats = prediction_data.get('statistical_comparison', {})
        if stats:
            formatted_lines.extend(["📈 Statistiche comparative:"])
            for key, value in stats.items():
                formatted_lines.append(f"• {key}:")
                formatted_lines.append(f"  - Casa: {value['home']}")
                formatted_lines.append(f"  - Trasferta: {value['away']}")
            formatted_lines.append("")
        
        # Head to head
        h2h = prediction_data.get('head_to_head', [])
        if h2h:
            formatted_lines.extend(["🤼 Precedenti scontri diretti:"])
            for match in h2h[:5]:  # Show last 5 matches
                date = datetime.fromisoformat(match['date'].replace('Z', '+00:00')).strftime("%d/%m/%Y")
                formatted_lines.append(
                    f"• {date}: {match['home_team']} {match['home_goals']}-{match['away_goals']} {match['away_team']}"
                )
            formatted_lines.append("")
        
        # Betting advice
        advice = prediction_data.get('betting_advice', '')
        if advice:
            formatted_lines.extend([
                "💡 Suggerimento:",
                advice
            ])
        
        return "\n".join(formatted_lines)
        
    except Exception as e:
        print(f"Error formatting prediction data: {str(e)}")
        return "Errore nel formato della predizione"



# Add these functions to your predizioni.py file

def get_all_bookmakers():
    """
    Get a list of all available bookmakers from the API.
    
    Returns:
        list: A list of dictionaries with bookmaker IDs and names.
    """
    try:
        url = f'https://{API_HOST}/v3/odds/bookmakers'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', [])
        else:
            print(f"Failed to get bookmakers: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting bookmakers: {str(e)}")
        return []

def get_all_betting_markets():
    """
    Get a list of all available betting markets from the API.
    
    Returns:
        list: A list of dictionaries with market IDs and names.
    """
    try:
        url = f'https://{API_HOST}/v3/odds/bets'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', [])
        else:
            print(f"Failed to get betting markets: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting betting markets: {str(e)}")
        return []

def get_match_odds(fixture_id, bookmaker_id=None, bet_id=None):
    """
    Get odds for a specific match, optionally filtered by bookmaker and/or bet type.
    
    Args:
        fixture_id (int): ID of the fixture
        bookmaker_id (int, optional): ID of the bookmaker to filter by
        bet_id (int, optional): ID of the bet type to filter by
        
    Returns:
        dict: The odds data structure from the API
    """
    try:
        url = f'https://{API_HOST}/v3/odds'
        params = {'fixture': fixture_id}
        
        # Add optional filters
        if bookmaker_id:
            params['bookmaker'] = bookmaker_id
        if bet_id:
            params['bet'] = bet_id
            
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', [])
        else:
            print(f"Failed to get odds for fixture {fixture_id}: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting odds for fixture {fixture_id}: {str(e)}")
        return []

def get_all_serie_a_odds(season=2024, bookmaker_id=None, bet_id=None):
    """
    Get odds for all upcoming Serie A matches, optionally filtered by bookmaker and/or bet type.
    
    Args:
        season (int): Season year, defaults to 2024
        bookmaker_id (int, optional): ID of the bookmaker to filter by
        bet_id (int, optional): ID of the bet type to filter by
        
    Returns:
        list: A list of odds data for all upcoming Serie A matches
    """
    try:
        # First get all upcoming Serie A fixtures
        fixtures = get_all_upcoming_fixtures(league_id=135, season=season)
        
        if not fixtures:
            print("No upcoming Serie A fixtures found")
            return []
            
        # Now get odds for each fixture
        all_odds = []
        for fixture in fixtures:
            fixture_id = fixture['fixture_id']
            odds = get_match_odds(fixture_id, bookmaker_id, bet_id)
            
            if odds:
                # Add fixture info to odds data for easier access later
                for odd in odds:
                    odd['home_team'] = fixture['home_team']
                    odd['away_team'] = fixture['away_team']
                    odd['date_utc'] = fixture['date_utc']
                all_odds.extend(odds)
                
        return all_odds
    except Exception as e:
        print(f"Error getting all Serie A odds: {str(e)}")
        return []

def format_odds_for_display(odds_data):
    """
    Format odds data from the API into a flat structure for easy display in a table.
    
    Args:
        odds_data (list): Raw odds data from the API
        
    Returns:
        list: Formatted odds data for display as a list of dictionaries
    """
    formatted_odds = []
    
    try:
        for fixture_odds in odds_data:
            fixture = fixture_odds.get('fixture', {})
            league = fixture_odds.get('league', {})
            
            # Extract fixture details
            fixture_id = fixture.get('id')
            fixture_date = fixture.get('date')
            home_team = fixture_odds.get('home_team', '')
            away_team = fixture_odds.get('away_team', '')
            
            if not home_team or not away_team:
                # Try to extract from teams if available
                teams = fixture_odds.get('teams', {})
                home_team = teams.get('home', {}).get('name', '')
                away_team = teams.get('away', {}).get('name', '')
            
            # Process bookmakers
            bookmakers = fixture_odds.get('bookmakers', [])
            for bookmaker in bookmakers:
                bookmaker_id = bookmaker.get('id')
                bookmaker_name = bookmaker.get('name')
                
                # Process bets/markets
                bets = bookmaker.get('bets', [])
                for bet in bets:
                    bet_id = bet.get('id')
                    bet_name = bet.get('name')
                    
                    # Process values/selections
                    values = bet.get('values', [])
                    for value in values:
                        selection = value.get('value')
                        odd = value.get('odd')
                        handicap = value.get('handicap', '')
                        main = value.get('main', False)
                        suspended = value.get('suspended', False)
                        
                        # Add entry to formatted odds
                        formatted_odds.append({
                            'fixture_id': fixture_id,
                            'date_utc': fixture_date,
                            'home_team': home_team,
                            'away_team': away_team,
                            'league_id': league.get('id'),
                            'league_name': league.get('name'),
                            'bookmaker_id': bookmaker_id,
                            'bookmaker': bookmaker_name,
                            'market_id': str(bet_id),  # Convert to string to match your existing code
                            'market_name': bet_name,
                            'selection': selection,
                            'handicap': handicap,
                            'odd': odd,
                            'main_selection': main,
                            'suspended': suspended,
                            'update_time': fixture_odds.get('update')
                        })
            
        return formatted_odds
    except Exception as e:
        print(f"Error formatting odds for display: {str(e)}")
        return []

def get_filtered_odds_data(fixtures=None, bookmakers=None, markets=None, selections=None, teams=None, league_id=135, season=2024):
    """
    Get odds data filtered by various criteria for UI display.
    
    Args:
        fixtures (list, optional): List of fixture IDs to filter by
        bookmakers (list, optional): List of bookmaker IDs or names to filter by
        markets (list, optional): List of market IDs to filter by
        selections (list, optional): List of selection values to filter by
        teams (list, optional): List of team names to filter by
        league_id (int): League ID, defaults to 135 (Serie A)
        season (int): Season year, defaults to 2024
        
    Returns:
        list: Filtered odds data formatted for display
    """
    try:
        # Get all fixtures for the specified league and season
        if not fixtures:
            all_fixtures = get_all_upcoming_fixtures(league_id=league_id, season=season)
            fixture_ids = [f['fixture_id'] for f in all_fixtures]
        else:
            fixture_ids = fixtures
            
        if not fixture_ids:
            print(f"No fixtures found for league {league_id}, season {season}")
            return []
        
        # Filter fixtures by team if specified
        if teams:
            team_fixtures = []
            for fixture_id in fixture_ids:
                # Find the fixture info
                fixture_info = next((f for f in all_fixtures if f['fixture_id'] == fixture_id), None)
                if fixture_info and (fixture_info['home_team'] in teams or fixture_info['away_team'] in teams):
                    team_fixtures.append(fixture_id)
            fixture_ids = team_fixtures
        
        # Get all bookmakers if needed
        if bookmakers is None:
            all_bookmakers = get_all_bookmakers()
            bookmaker_ids = [b['id'] for b in all_bookmakers]
        else:
            bookmaker_ids = bookmakers
        
        # Get all markets if needed
        if markets is None:
            all_markets = get_all_betting_markets()
            market_ids = [m['id'] for m in all_markets]
        else:
            market_ids = markets
        
        # Get odds for each fixture
        all_odds_data = []
        for fixture_id in fixture_ids:
            # Get odds with the specified filters
            odds = get_match_odds(fixture_id)
            if odds:
                all_odds_data.extend(odds)
        
        # Format the odds data
        formatted_odds = format_odds_for_display(all_odds_data)
        
        # Apply additional filters
        filtered_odds = formatted_odds
        
        # Filter by bookmaker
        if bookmakers:
            filtered_odds = [odd for odd in filtered_odds if str(odd['bookmaker_id']) in [str(b) for b in bookmaker_ids] 
                            or odd['bookmaker'] in bookmaker_ids]
        
        # Filter by market
        if markets:
            filtered_odds = [odd for odd in filtered_odds if str(odd['market_id']) in [str(m) for m in market_ids]]
        
        # Filter by selection
        if selections:
            filtered_odds = [odd for odd in filtered_odds if odd['selection'] in selections]
        
        return filtered_odds
    except Exception as e:
        print(f"Error getting filtered odds data: {str(e)}")
        return []

def track_odds_changes(current_odds, previous_odds=None):
    """
    Track changes in odds values between current and previous odds data.
    
    Args:
        current_odds (list): Current formatted odds data
        previous_odds (list, optional): Previous formatted odds data to compare with
        
    Returns:
        dict: A dictionary of odds changes with their percentage changes
    """
    if not previous_odds:
        return {}
    
    changes = {}
    
    try:
        # Create a unique key for each odd
        for current in current_odds:
            key = f"{current['fixture_id']}_{current['market_id']}_{current['selection']}_{current['bookmaker']}"
            
            # Find the corresponding previous odd
            previous = next((p for p in previous_odds if 
                         f"{p['fixture_id']}_{p['market_id']}_{p['selection']}_{p['bookmaker']}" == key), None)
            
            if previous:
                try:
                    current_value = float(current['odd'])
                    previous_value = float(previous['odd'])
                    
                    if previous_value > 0:  # Avoid division by zero
                        percent_change = abs((current_value - previous_value) / previous_value * 100)
                        
                        changes[key] = {
                            'direction': 'up' if current_value > previous_value else 'down',
                            'percent_change': percent_change,
                            'old_value': previous_value,
                            'new_value': current_value,
                            'fixture_id': current['fixture_id'],
                            'market_id': current['market_id'],
                            'selection': current['selection'],
                            'bookmaker': current['bookmaker']
                        }
                except (ValueError, TypeError):
                    # Skip if we can't convert to float
                    pass
                    
        return changes
    except Exception as e:
        print(f"Error tracking odds changes: {str(e)}")
        return {}

def get_odds_history(fixture_id, bookmaker_id, market_id, selection=None):
    """
    Attempt to get historical odds data for a specific fixture, bookmaker, and market.
    
    Note: Based on the API documentation, it's not clear if historical odds data is directly available.
    The documentation mentions "We keep a 7-days history" but doesn't specify a dedicated endpoint.
    This is a best effort to retrieve such data if available.
    
    Args:
        fixture_id (int): ID of the fixture
        bookmaker_id (int): ID of the bookmaker
        market_id (int): ID of the market/bet type
        selection (str, optional): Specific selection value to filter by
        
    Returns:
        list: Historical odds data if available, otherwise an empty list
    """
    try:
        # Try to use the regular odds endpoint to see if it returns any historical data
        url = f'https://{API_HOST}/v3/odds'
        params = {
            'fixture': fixture_id,
            'bookmaker': bookmaker_id,
            'bet': market_id
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            odds_data = data.get('response', [])
            
            # Extract historical data if available
            history = []
            
            if odds_data:
                for odds in odds_data:
                    bookmakers = odds.get('bookmakers', [])
                    for bookmaker in bookmakers:
                        if bookmaker.get('id') == bookmaker_id:
                            bets = bookmaker.get('bets', [])
                            for bet in bets:
                                if bet.get('id') == market_id:
                                    values = bet.get('values', [])
                                    if selection:
                                        values = [v for v in values if v.get('value') == selection]
                                    
                                    # Add values to history with update timestamp
                                    for value in values:
                                        history.append({
                                            'timestamp': odds.get('update', ''),
                                            'value': value.get('value', ''),
                                            'odd': value.get('odd', ''),
                                            'handicap': value.get('handicap', '')
                                        })
            
            return history
        else:
            print(f"Failed to get odds history: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting odds history: {str(e)}")
        return []