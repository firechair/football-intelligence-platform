#bettingbot/src/backend/api/odds_api.py
import numpy as np
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import os
import urllib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Base URL
API_BASE_URL = "http://example.invalid:8081"

# Target bookmakers (from the documentation)
TARGET_BOOKMAKERS = ["23", "124", "379", "455"]  # Bookmaker A, Bookmaker D, Bookmaker E, Bookmaker G Sportsbook

# Market type mappings (based on documentation)
MARKET_TYPE_MAPPINGS = {
    "1": "1x2",              # 1X2 - 3Way - Home/Draw/Away
    "2": "12",               # 12 - 2Way - Home/Away
    "3": "oe",               # Odd/Even
    "4": "ou",               # Over/Under
    "5": "cs",               # Correct Score
    "6": "ah",               # Asian Handicap
    "7": "c_ah",             # Corner Asian Handicap
    "8": "1x2_hc",           # 3Way Handicap
    "9": "win",              # Winner
    "10": "dc",              # Double Chance
    "11": "gs",              # Goalscorer
    "12": "ht_ft",           # Half Time / Full Time
    "13": "ng",              # Number of Goals
    "14": "smg",             # Half with Most Goals
    "15": "tng",             # Time of Next Goal
    "16": "nc",              # Next Corner
    "17": "dnb",             # Draw No Bet
    "18": "bts",             # Both to Score
    "19": "wtn",             # Win to Nil
    "20": "g_ah",            # Game Handicap
    "21": "s_ah",            # Set Handicap
    "22": "p_ou",            # Points Over/Under
    "23": "yc_ou",           # Yellow Cards Over/Under
    "24": "b_first",         # First Team Booking
    "25": "b_most",          # Most Booking
    "26": "b_nb",            # Number of Cards
    "27": "c_oe",            # Corners Odd/Even
    "28": "c_hc",            # Corner Handicap
    "29": "c_ou",            # Corners Over/Under
    "30": "c_last",          # Last Corner
    "31": "c_most",          # Most Corners
    "32": "c_nb",            # Number of Corners
    "33": "c_sm",            # Half with Most Corners
    "34": "c_par_nb",        # Team Number of Corners
    "35": "par_ou",          # Team Score Over/Under
    "36": "par_oe",          # Team Odd/Even Goals
    "37": "par_ts",          # Team Total Score
    "38": "p_hc",            # Points Handicap
    "39": "ew",              # Each Way
    "40": "s_first",         # First Team To Score
    "41": "s_ou",            # Sets Over/Under
    "42": "tb",              # Tiebreak
    "43": "s_next",          # Next Team to Score
    "44": "toq",             # To Qualify
    "45": "car_ou",          # Total Cards Over/Under
}

def get_all_events():
    """
    Get a list of all available events
    
    Returns:
        List of dictionaries with event details
    """
    try:
        endpoint = f"{API_BASE_URL}/api/events"
        
        response = requests.get(endpoint, timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # Handle different response formats
            if isinstance(raw_data, dict) and "data" in raw_data:
                events = raw_data["data"]
            elif isinstance(raw_data, dict) and "status" in raw_data and raw_data.get("status") == "success":
                events = raw_data.get("data", [])
            else:
                events = raw_data  # Assume it's already the event list
            
            formatted_events = []
            for event in events:
                # Format the event data for our application
                # From the PHP code, we expect: id, name, startdate, status_type, tournament, sport
                event_id = event.get('id', '')
                event_name = event.get('name', '')
                
                # Parse home/away teams from name if it contains a delimiter
                home_team = ""
                away_team = ""
                if "-" in event_name:
                    parts = event_name.split("-")
                    home_team = parts[0].strip()
                    away_team = parts[1].strip() if len(parts) > 1 else ""
                
                # Get start date
                start_date = event.get('startdate', '')
                
                # Get tournament/sport info
                tournament = event.get('tournament', '')
                sport = event.get('sport', '')
                
                formatted_event = {
                    'fixture_id': str(event_id),
                    'name': event_name,
                    'home_team': home_team,
                    'away_team': away_team,
                    'fixture_date': start_date,
                    'tournament': tournament,
                    'sport': sport,
                    'status': event.get('status_type', ''),
                    'display_name': f"{home_team} vs {away_team}" if home_team and away_team else event_name
                }
                formatted_events.append(formatted_event)
            
            logger.info(f"Retrieved {len(formatted_events)} events")
            return formatted_events
        else:
            logger.warning(f"Failed to get events: {response.status_code}")
            return []
    
    except Exception as e:
        logger.error(f"Error getting events from API: {str(e)}")
        return []

def get_betting_providers():
    """
    Get a list of all available betting providers/bookmakers
    
    Returns:
        List of dictionaries with provider details
    """
    try:
        endpoint = f"{API_BASE_URL}/api/betting/providers"
        
        response = requests.get(endpoint, timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # Handle different response formats
            if isinstance(raw_data, dict) and "data" in raw_data:
                providers = raw_data["data"]
            elif isinstance(raw_data, dict) and "status" in raw_data and raw_data.get("status") == "success":
                providers = raw_data.get("data", [])
            else:
                providers = raw_data  # Assume it's already the provider list
            
            formatted_providers = []
            for provider in providers:
                # Format the provider data
                # From the PHP code, we expect: id, name, url, bookmaker, active
                formatted_provider = {
                    'id': provider.get('id', ''),
                    'name': provider.get('name', ''),
                    'url': provider.get('url', ''),
                    'bookmaker': provider.get('bookmaker', ''),
                    'active': provider.get('active', '')
                }
                formatted_providers.append(formatted_provider)
            
            logger.info(f"Retrieved {len(formatted_providers)} betting providers")
            return formatted_providers
        else:
            logger.warning(f"Failed to get providers: {response.status_code}")
            return []
    
    except Exception as e:
        logger.error(f"Error getting providers from API: {str(e)}")
        return []

def fetch_odds_for_event(event_id):
    """
    Fetch odds for a specific event
    
    Args:
        event_id: The ID of the event
    
    Returns:
        DataFrame containing the odds data
    """
    try:
        # Use the proper endpoint to get odds for this event
        endpoint = f"{API_BASE_URL}/api/betting/odds/{event_id}"
        
        logger.info(f"Fetching odds for event ID {event_id} from {endpoint}")
        
        response = requests.get(endpoint, timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # Handle different response formats
            if isinstance(raw_data, dict) and "data" in raw_data:
                odds_data = raw_data["data"]
            elif isinstance(raw_data, dict) and "status" in raw_data and raw_data.get("status") == "success":
                # Check if the data is in the expected format
                if "event" in raw_data.get("data", {}) and "odds" in raw_data.get("data", {}):
                    odds_data = raw_data["data"]
                else:
                    odds_data = raw_data.get("data", {})
            else:
                odds_data = raw_data  # Assume it's already the odds data
            
            # Transform the data to the format our application expects
            df = _transform_odds_data_to_df(odds_data, event_id)
            logger.info(f"Transformed odds data for event {event_id} with shape {df.shape}")
            return df
        else:
            logger.warning(f"Failed to retrieve odds for event {event_id}: {response.status_code}")
            return pd.DataFrame()
    
    except Exception as e:
        logger.error(f"Error fetching odds for event {event_id}: {str(e)}")
        return pd.DataFrame()

def fetch_all_odds():
    """
    Fetch all odds data from the API and return as formatted dataframe
    First gets all events, then fetches odds for each event
    """
    try:
        logger.info("Fetching all available odds data using events approach")
        
        # Step 1: Get all events
        events = get_all_events()
        
        if not events:
            logger.warning("No events found, using mock data")
        
        # Step 2: For each event, get its odds data
        all_dfs = []
        
        # Limit to first 10 events if there are too many to avoid overloading
        sample_events = events[:10] if len(events) > 10 else events
        
        for event in sample_events:
            try:
                # Extract the event ID
                event_id = event.get("fixture_id", "")
                if not event_id:
                    logger.warning(f"Could not find ID in event: {event}")
                    continue
                
                # Fetch odds for this event
                event_df = fetch_odds_for_event(event_id)
                
                if not event_df.empty:
                    # Add event information if not already present
                    if 'home_team' not in event_df.columns or event_df['home_team'].iloc[0] == '':
                        event_df['home_team'] = event.get('home_team', '')
                    
                    if 'away_team' not in event_df.columns or event_df['away_team'].iloc[0] == '':
                        event_df['away_team'] = event.get('away_team', '')
                    
                    if 'fixture_date' not in event_df.columns or event_df['fixture_date'].iloc[0] == '':
                        event_df['fixture_date'] = event.get('fixture_date', '')
                    
                    all_dfs.append(event_df)
                    logger.info(f"Added odds data for event {event_id}")
                else:
                    logger.warning(f"No odds data found for event {event_id}")
            except Exception as e:
                logger.error(f"Error processing event {event.get('fixture_id', '')}: {str(e)}")
        
        # Combine all DataFrames
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            logger.info(f"Combined odds data with shape {combined_df.shape}")
            return combined_df
        else:
            logger.warning("No odds data found for any events, returning empty DataFrame")
            return pd.DataFrame()

    
    except Exception as e:
        logger.error(f"Error in fetch_all_odds: {str(e)}")
        return pd.DataFrame()

def fetch_odds_by_bookmaker(event_id, bookmaker_id):
    """
    Fetch odds for a specific event from a specific bookmaker
    
    Args:
        event_id: The ID of the event
        bookmaker_id: The ID of the bookmaker
    
    Returns:
        DataFrame containing the odds data
    """
    try:
        # Use the proper endpoint
        endpoint = f"{API_BASE_URL}/api/betting/bookmaker/{bookmaker_id}/event/{event_id}"
        
        logger.info(f"Fetching odds for event {event_id} from bookmaker {bookmaker_id}")
        
        response = requests.get(endpoint, timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # Handle different response formats
            if isinstance(raw_data, dict) and "data" in raw_data:
                odds_data = raw_data["data"]
            elif isinstance(raw_data, dict) and "status" in raw_data and raw_data.get("status") == "success":
                odds_data = raw_data.get("data", {})
            else:
                odds_data = raw_data  # Assume it's already the odds data
            
            # Transform the data to the format our application expects
            df = _transform_bookmaker_odds_to_df(odds_data, event_id, bookmaker_id)
            logger.info(f"Transformed bookmaker odds with shape {df.shape}")
            return df
        else:
            logger.warning(f"Failed to retrieve odds for event {event_id} from bookmaker {bookmaker_id}: {response.status_code}")
            return pd.DataFrame()
    
    except Exception as e:
        logger.error(f"Error fetching odds by bookmaker: {str(e)}")
        return pd.DataFrame()

def fetch_odds_history_for_graph(fixture_id, market_id, selection, bookmaker=None):
    """Fetch historical odds data for a specific selection to display in a graph"""
    try:
        logger.info(f"Fetching history for fixture={fixture_id}, market={market_id}, selection={selection}, bookmaker={bookmaker}")
        
        # If no bookmaker provided, use the first one found
        if not bookmaker:
            providers = get_betting_providers()
            if providers:
                bookmaker = providers[0].get('id', '')
                logger.info(f"No bookmaker specified, using {bookmaker}")
            else:
                logger.warning("No bookmakers found")
                return []
        
        # Convert market_id to general_market type if applicable
        general_market = None
        for db_market_type, app_market_id in [
            ('ah', '4'),       # Asian Handicap -> 4
            ('1x2', '1'),      # 1X2 -> 1
            ('ou', '5'),       # Over/Under -> 5
            ('bts', '8'),      # Both Teams Score -> 8
            ('dc', '12'),      # Double Chance -> 12
            ('cs', '10'),      # Correct Score -> 10
            ('win', '9')       # Win/Handicap -> 9
        ]:
            if market_id == app_market_id:
                general_market = db_market_type
                break
        
        # If we couldn't map, use the original market_id
        if not general_market:
            general_market = market_id
            
        logger.info(f"Mapped market_id '{market_id}' to general_market '{general_market}'")
        
        endpoint = f"{API_BASE_URL}/api/betting/history/event/{fixture_id}/bookmaker/{bookmaker}"
        
        logger.info(f"Fetching odds history from: {endpoint}")
        response = requests.get(endpoint, timeout=15)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # Extract and format history data
            history_data = []
            
            # Parse according to the database structure
            if isinstance(raw_data, dict) and "data" in raw_data:
                if "history" in raw_data["data"]:
                    history_data = raw_data["data"]["history"]
                else:
                    history_data = raw_data["data"]
            elif isinstance(raw_data, dict) and "status" in raw_data and raw_data.get("status") == "success":
                history_data = raw_data.get("data", {}).get("history", [])
            elif isinstance(raw_data, list):
                history_data = raw_data
            
            # Log what we received
            logger.info(f"Received {len(history_data)} history records")
            
            # Process history records - match DB field names to our expected names
            history = []
            
            # Log the first record structure to help debugging
            if history_data and len(history_data) > 0:
                logger.info(f"Sample record structure: {history_data[0]}")
            
            for item in history_data if isinstance(history_data, list) else []:
                # Get timestamp - handle both 'capture_time' (from DB) and 'timestamp'
                ts = item.get('capture_time', item.get('ut', item.get('timestamp', '')))
                
                # Get odds values - handle both 'odds'/'odds_old' (from DB) and 'odd'/'previous_odd'
                odd_value = float(item.get('odds', item.get('current_odds', item.get('odd', 0))))
                prev_value = float(item.get('odds_old', item.get('old_odds', item.get('previous_odd', odd_value))))
                
                # Get market information - handle both DB field names and API field names
                item_general_market = item.get('general_market', item.get('market_type', ''))
                item_specific_market = item.get('specific_market', item.get('market_subtype', ''))
                item_market_scope = item.get('market_scope', '')
                
                logger.debug(f"Processing item: market={item_general_market}, specific={item_specific_market}, scope={item_market_scope}")
                logger.debug(f"Comparing with: general_market={general_market}, selection={selection}")
                
                # Market matching based on the mapped general_market
                market_matches = False
                if general_market:
                    # First try exact match
                    if general_market.lower() == item_general_market.lower():
                        market_matches = True
                    # For special cases like Asian Handicap
                    elif general_market == '4' and item_general_market.lower() == 'ah':
                        market_matches = True
                    # For 1X2 markets
                    elif general_market == '1' and item_general_market.lower() == '1x2':
                        market_matches = True
                    # For Over/Under markets  
                    elif general_market == '5' and item_general_market.lower() == 'ou':
                        market_matches = True
                else:
                    # If we have no market filter, accept all
                    market_matches = True
                
                # Selection matching - needs to be flexible based on the database structure
                selection_matches = False
                
                # Check if the selection matches the specific market
                if selection and item_specific_market:
                    selection_lower = selection.lower()
                    specific_market_lower = item_specific_market.lower()
                    
                    # Try different matching strategies
                    if selection_lower == specific_market_lower:
                        # Exact match
                        selection_matches = True
                    elif selection_lower in specific_market_lower or specific_market_lower in selection_lower:
                        # Substring match
                        selection_matches = True
                    elif selection in ['1', 'X', '2'] and item_general_market.lower() == '1x2':
                        # Special case for 1X2 markets
                        # '1' = Home, 'X' = Draw, '2' = Away in 1X2 markets
                        if (selection == '1' and specific_market_lower == 'win' and 'home' in item.get('team_name', '').lower()) or \
                           (selection == 'X' and specific_market_lower == 'draw') or \
                           (selection == '2' and specific_market_lower == 'win' and 'away' in item.get('team_name', '').lower()):
                            selection_matches = True
                    elif 'over' in selection_lower and 'over' in specific_market_lower:
                        # Match "Over X.Y" with just "Over" plus params
                        selection_matches = True
                    elif 'under' in selection_lower and 'under' in specific_market_lower:
                        # Match "Under X.Y" with just "Under" plus params
                        selection_matches = True
                
                # For Asian Handicap, also check if we need to match the market scope (1h = First Half)
                scope_matches = True
                if market_id == '19' and item_general_market.lower() == 'ah':  # Asian Handicap First Half
                    scope_matches = (item_market_scope.lower() == '1h')
                elif market_id == '4' and item_general_market.lower() == 'ah':  # Regular Asian Handicap
                    scope_matches = (item_market_scope.lower() in ['ord', 'fe'])
                
                # Only include records matching our filter criteria
                if market_matches and (selection_matches or not selection) and scope_matches:
                    # Format the data point
                    history.append({
                        'timestamp': ts,
                        'odd': odd_value,
                        'previous_odd': prev_value,
                        'bookmaker': bookmaker,
                        'market_type': item_general_market,
                        'market_scope': item_market_scope,
                        'specific_market': item_specific_market
                    })
                    logger.debug(f"Added history point: {odd_value}")
            
            # Sort by timestamp
            history.sort(key=lambda x: x['timestamp'])
            logger.info(f"Retrieved {len(history)} historical data points after filtering")
            
            if history:
                return history
            
            # If no matching data found and debug mode is enabled, log complete market data
            logger.warning("No matching historical data found after filtering. Generating mock data.")
            logger.debug(f"Selection criteria: market_id={market_id}, general_market={general_market}, selection={selection}")
            
            # Generate mock data when real data isn't available
        else:
            logger.warning(f"Failed to fetch history: {response.status_code}")
            
            # Generate mock data for testing


    except Exception as e:
        logger.error(f"Error fetching odds history: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        

def _transform_odds_data_to_df(odds_data, event_id):
    """Transform odds data from the API response to a DataFrame"""
    try:
        items = []
        
        # Extract event info
        event_info = {}
        if isinstance(odds_data, dict):
            if "event" in odds_data:
                event_info = odds_data["event"]
            
            # Extract home/away from event name if needed
            event_name = event_info.get('name', '')
            home_team = event_info.get('home_team', '')
            away_team = event_info.get('away_team', '')
            
            if not home_team or not away_team:
                if "-" in event_name:
                    parts = event_name.split("-")
                    home_team = parts[0].strip()
                    away_team = parts[1].strip() if len(parts) > 1 else ""
            
            event_info['home_team'] = home_team
            event_info['away_team'] = away_team
            
            # Process odds by market
            odds_list = []
            
            # Handle different response structures
            if "odds" in odds_data and isinstance(odds_data["odds"], dict):
                # Format: {"market_type": {"market_scope": [odds]}}
                for market_type, market_scopes in odds_data["odds"].items():
                    if isinstance(market_scopes, dict):
                        for market_scope, market_odds in market_scopes.items():
                            if isinstance(market_odds, list):
                                for odd in market_odds:
                                    odds_list.append({
                                        **odd, 
                                        "general_market": market_type, 
                                        "market_scope": market_scope
                                    })
            elif "odds" in odds_data and isinstance(odds_data["odds"], list):
                # Format: [{"market_type": "...", "market_scope": "...", ...}]
                odds_list = odds_data["odds"]
            
            # Process each odd entry
            for odd in odds_list:
                # Get market fields from database structure
                general_market = odd.get('general_market', odd.get('market_type', ''))
                market_scope = odd.get('market_scope', '')
                specific_market = odd.get('specific_market', odd.get('market_subtype', ''))
                
                # Use the mapping function to get the market ID
                market_id = map_database_market_to_app_id(general_market, market_scope)
                
                # Create selection name from available fields
                selection = specific_market
                
                # Add parameters for better description
                iparam = odd.get('iparam', '')
                dparam = odd.get('dparam', '')
                sparam = odd.get('sparam', '')
                
                if iparam and 'team_name' in odd:
                    selection = f"{selection} {odd['team_name']}"
                elif dparam:
                    selection = f"{selection} {dparam}"
                elif sparam:
                    selection = f"{selection} {sparam}"
                
                # Create formatted item
                items.append({
                    'fixture_id': event_id,
                    'home_team': home_team,
                    'away_team': away_team,
                    'fixture_date': event_info.get('startdate', ''),
                    'league_id': '',  # Not available
                    'bookmaker': odd.get('provider_name', odd.get('provider', '')),
                    'bookmaker_id': odd.get('provider_id', ''),
                    'market_id': market_id,
                    'market_name': market_id,
                    'market_scope': market_scope,
                    'general_market': general_market,
                    'specific_market': specific_market,
                    'selection': selection.strip() if selection else specific_market,
                    'odd': float(odd.get('odds', odd.get('odd', 0))),
                    'fetch_timestamp': datetime.now().isoformat(),
                    'timestamp': odd.get('capture_timestamp', odd.get('timestamp', datetime.now().isoformat()))
                })
        
        # Convert to DataFrame
        if items:
            df = pd.DataFrame(items)
            
            # Convert numeric types
            if 'odd' in df.columns:
                df['odd'] = pd.to_numeric(df['odd'], errors='coerce')
            
            return df
        else:
            logger.warning("No items could be transformed from odds data")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error transforming odds data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()
    

def get_selections_for_market(fixture_id, market_id):
    """
    Get available selections for a specific market
    Replacement for get_selections_for_market()
    
    Args:
        fixture_id: The ID of the event
        market_id: The market ID
        
    Returns:
        List of available selections
    """
    try:
        # Get event odds
        df = fetch_odds_for_events([fixture_id])
        
        if df.empty:
            return []
        
        # Filter for the specified market and extract unique selections
        filtered_df = df[df['market_id'] == market_id]
        
        if filtered_df.empty:
            return []
            
        # Get unique selections
        selections = filtered_df['selection'].unique().tolist()
        
        return sorted(selections)
        
    except Exception as e:
        logger.error(f"Error getting selections from API: {str(e)}")
        st.error(f"Error getting selections: {str(e)}")
        return []

def get_bookmakers():
    """
    Get a list of all bookmakers in the data
    Replacement for get_bookmakers()
    
    Returns:
        List of bookmaker names
    """
    try:
        # Since we're targeting specific bookmakers, we can return them directly
        # For a more dynamic approach, we could fetch all odds and extract unique bookmakers
        
        # Get all odds data
        df = fetch_all_odds()
        
        if df.empty:
            return []
        
        # Get unique bookmakers
        if 'bookmaker' in df.columns:
            return sorted(df['bookmaker'].unique().tolist())
        else:
            # Return hardcoded bookmakers as fallback
            return ["Bookmaker A", "Bookmaker D", "Bookmaker E", "Bookmaker G Sportsbook"]
    
    except Exception as e:
        logger.error(f"Error getting bookmakers from API: {str(e)}")
        st.error(f"Error getting bookmakers: {str(e)}")
        return []

def get_market_name_from_id(market_id):
    """
    Get the user-friendly market name from market ID, using app's market dictionaries
    
    Args:
        market_id: The market ID (string)
        
    Returns:
        String with user-friendly market name
    """
    # Try to get market name from session state first
    if 'MAIN_MARKETS' in st.session_state and market_id in st.session_state.MAIN_MARKETS:
        return st.session_state.MAIN_MARKETS[market_id]
    
    if 'SECONDARY_MARKETS' in st.session_state and market_id in st.session_state.SECONDARY_MARKETS:
        return st.session_state.SECONDARY_MARKETS[market_id]
    
    # If not in session state, use market type mappings
    if market_id in MARKET_TYPE_MAPPINGS:
        return MARKET_TYPE_MAPPINGS[market_id]
    
    # Default fallback
    return f"Market {market_id}"


def map_database_market_to_app_id(general_market, market_scope):
    """Map database market names to app market IDs"""
    # First convert to lowercase for consistent matching
    general_market = general_market.lower() if general_market else ''
    market_scope = market_scope.lower() if market_scope else ''
    
    # Asian Handicap mapping - matches the DB structure
    if general_market == 'ah':
        if market_scope == '1h':
            return '19'  # Asian Handicap First Half
        return '4'  # Asian Handicap
    
    # Match Winner (1X2) mapping
    elif general_market == '1x2':
        if market_scope == '1h':
            return '13'  # First Half Winner
        elif market_scope == '2h':
            return '3'   # Second Half Winner
        return '1'  # Match Winner
    
    # Over/Under mapping
    elif general_market == 'ou':
        if market_scope == '1h':
            return '6'  # Goals Over/Under First Half
        elif market_scope == '2h':
            return '26'  # Goals Over/Under Second Half
        return '5'  # Goals Over/Under
    
    # Both Teams to Score mapping
    elif general_market == 'bts':
        if market_scope == '1h':
            return '34'  # Both Teams Score First Half
        elif market_scope == '2h':
            return '35'  # Both Teams Score Second Half
        return '8'  # Both Teams Score
    
    # Corners mapping
    elif 'corner' in general_market or general_market == 'c_ou':
        if market_scope == '1h':
            return '77'  # Corner First Half
        return '45'  # Corners Over/Under
    
    elif general_market == 'c_ah':
        return '56'  # Corners Asian Handicap
    
    elif general_market == 'c_par_nb':
        if 'home' in market_scope:
            return '57'  # Home Corners Over/Under
        elif 'away' in market_scope:
            return '58'  # Away Corners Over/Under
        return '45'  # Default to Corners Over/Under
    
    # Double Chance mapping
    elif general_market == 'dc':
        if market_scope == '1h':
            return '20'  # Double Chance First Half
        return '12'  # Double Chance
    
    # Exact Score mapping
    elif general_market == 'cs':
        if market_scope == '1h':
            return '31'  # Correct Score First Half
        return '10'  # Exact Score
    
    # Handicap Result mapping
    elif general_market == '1x2_hc':
        if market_scope == '1h':
            return '18'  # Handicap Result First Half
        return '9'  # Handicap Result
    
    # Team to Score mapping
    elif general_market == 's_first':
        return '14'  # Team To Score First
    
    elif general_market == 's_next':
        return '15'  # Team To Score Last
    
    # Odd/Even mapping
    elif general_market == 'oe':
        if market_scope == '1h':
            return '22'  # Odd/Even First Half
        elif market_scope == '2h':
            return '63'  # Odd/Even Second Half
        elif 'home' in market_scope:
            return '23'  # Home Odd/Even
        elif 'away' in market_scope:
            return '60'  # Away Odd/Even
        return '21'  # Odd/Even
    
    # Number of Goals mapping
    elif general_market == 'ng':
        if market_scope == '1h':
            return '46'  # Exact Goals Number First Half
        elif market_scope == '2h':
            return '42'  # Second Half Exact Goals Number
        elif 'home' in market_scope:
            return '40'  # Home Team Exact Goals Number
        elif 'away' in market_scope:
            return '41'  # Away Team Exact Goals Number
        return '38'  # Exact Goals Number
    
    # HT/FT Double mapping
    elif general_market == 'ht_ft':
        return '7'  # HT/FT Double
    
    # Win to Nil mapping
    elif general_market == 'wtn':
        return '36'  # Win To Nil
    
    # If general_market is a numeric ID, try to map it
    if general_market.isdigit():
        market_num = general_market
        if market_num in MARKET_TYPE_MAPPINGS:
            market_type = MARKET_TYPE_MAPPINGS[market_num]
            return map_database_market_to_app_id(market_type, market_scope)
    
    # Return original if no mapping found
    logger.debug(f"No mapping found for market: {general_market}, scope: {market_scope}")
    return general_market

def fetch_odds_for_events(event_ids=None):
    """
    Compatibility function to maintain the same API for OddsTable.
    Fetches odds for multiple events.
    
    Args:
        event_ids: List of event IDs to fetch, or None for all events
    
    Returns:
        DataFrame containing the odds data
    """
    # If no event IDs, fetch all odds
    if not event_ids or len(event_ids) == 0:
        return fetch_all_odds()
    
    # If only one event ID, use the singular function
    if len(event_ids) == 1:
        return fetch_odds_for_event(event_ids[0])
    
    # For multiple events, combine results
    all_dfs = []
    for event_id in event_ids:
        df = fetch_odds_for_event(event_id)
        if not df.empty:
            all_dfs.append(df)
    
    # Combine all DataFrames
    if all_dfs:
        import pandas as pd
        return pd.concat(all_dfs, ignore_index=True)
    else:
        import pandas as pd
        return pd.DataFrame()


def debug_api_connection():
    """
    Debug function to test API connectivity with detailed error information.
    This can be called from a separate page or debug section in the UI.
    
    Returns:
        dict: Information about API connectivity tests
    """
    import requests
    from requests.exceptions import RequestException
    import json
    import time
    import socket
    
    results = {
        "api_base_reachable": False,
        "endpoints_tested": [],
        "successful_endpoints": [],
        "error_details": {},
        "response_samples": {},
        "additional_info": {}
    }
    
    # Helper function to safely parse JSON response
    def safe_parse_json(text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Not valid JSON", "raw": text[:500] + "..." if len(text) > 500 else text}
    
    # Test basic connectivity to the server
    try:
        # First check if the server is reachable at all
        base_response = requests.get(API_BASE_URL, timeout=5)
        results["api_base_reachable"] = True
        results["base_status_code"] = base_response.status_code
        results["base_response"] = safe_parse_json(base_response.text) if base_response.text else None
    except RequestException as e:
        results["api_base_reachable"] = False
        results["base_error"] = str(e)
    
    # Test all main endpoints from the PHP file
    endpoints = [
        {"url": f"{API_BASE_URL}/api/events", "params": {}},
        {"url": f"{API_BASE_URL}/api/events/1", "params": {}},  # Test with a specific event ID
        {"url": f"{API_BASE_URL}/api/betting/odds", "params": {}},
        {"url": f"{API_BASE_URL}/api/betting/odds/1", "params": {}},  # Test with a specific event ID
        {"url": f"{API_BASE_URL}/api/betting/providers", "params": {}},
        # Add more endpoints as needed
    ]
    
    # Test all endpoints
    for endpoint in endpoints:
        endpoint_key = f"{endpoint['url']}"
        results["endpoints_tested"].append(endpoint_key)
        
        try:
            start_time = time.time()
            response = requests.get(
                endpoint["url"], 
                params=endpoint["params"],
                timeout=10
            )
            response_time = time.time() - start_time
            
            status = {
                "status_code": response.status_code,
                "response_time_ms": int(response_time * 1000),
                "content_type": response.headers.get("Content-Type", "unknown"),
                "content_length": len(response.content),
                "headers": dict(response.headers)
            }
            
            if response.status_code < 400:
                results["successful_endpoints"].append(endpoint_key)
                sample_data = safe_parse_json(response.text) if response.text else None
                results["response_samples"][endpoint_key] = sample_data
            else:
                results["error_details"][endpoint_key] = {
                    **status,
                    "error_content": response.text[:1000] if response.text else None
                }
                
        except RequestException as e:
            results["error_details"][endpoint_key] = {
                "exception": str(e),
                "exception_type": type(e).__name__
            }
    
    # Additional diagnostics
    try:
        # Get the hostname from the URL
        from urllib.parse import urlparse
        parsed_url = urlparse(API_BASE_URL)
        hostname = parsed_url.netloc.split(':')[0]
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        # Try to resolve the IP
        try:
            ip_address = socket.gethostbyname(hostname)
            results["additional_info"]["hostname"] = hostname
            results["additional_info"]["ip_address"] = ip_address
            
            # Try port connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip_address, port))
            results["additional_info"]["port_open"] = (result == 0)
            sock.close()
        except socket.gaierror:
            results["additional_info"]["dns_resolution"] = "Failed to resolve hostname"
    except Exception as e:
        results["additional_info"]["network_error"] = str(e)
    
    return results

def show_api_debugger():
    """
    Display API debugging interface in a Streamlit app
    """
    st.title("API Debugging Tool")
    st.write("Use this tool to diagnose connection issues with the betting odds API")
    
    if st.button("Run API Diagnostics"):
        with st.spinner("Testing API endpoints..."):
            results = debug_api_connection()
            
            # Display results
            st.subheader("API Base Connectivity")
            if results["api_base_reachable"]:
                st.success(f"✅ API base URL ({API_BASE_URL}) is reachable")
            else:
                st.error(f"❌ API base URL ({API_BASE_URL}) is not reachable")
                st.error(f"Error: {results.get('base_error', 'Unknown error')}")
            
            st.subheader("Endpoint Tests")
            successful = results["successful_endpoints"]
            
            if successful:
                st.success(f"✅ {len(successful)} endpoint(s) responded successfully:")
                for endpoint in successful:
                    st.write(f"- {endpoint}")
                    
                # Show a sample of successful data
                if results["response_samples"]:
                    st.subheader("Sample Response")
                    sample_key = list(results["response_samples"].keys())[0]
                    st.json(results["response_samples"][sample_key])
            else:
                st.error("❌ No endpoints responded successfully")
            
            # Show errors
            if results["error_details"]:
                st.subheader("Error Details")
                for endpoint, details in results["error_details"].items():
                    with st.expander(f"Error for {endpoint}"):
                        st.write(details)
            
            # Additional info
            st.subheader("Network Information")
            st.write(results["additional_info"])
                
        st.subheader("Next Steps")
        if not results["api_base_reachable"]:
            st.write("""
            - Check if the API server is running at the correct IP address
            - Verify network connectivity (firewalls, VPNs, etc.)
            - Confirm IP address is correct in your config
            """)
        elif not successful:
            st.write("""
            - The server is reachable but all endpoints are failing
            - Check if the API structure has changed
            - Verify authentication requirements
            - The server might be returning 500 errors, check server logs
            """)
        else:
            st.write("""
            - Some endpoints work - use these in your application
            - Update your code to use the successful endpoints
            """)