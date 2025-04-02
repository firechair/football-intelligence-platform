#bettingbot/src/backend/dynamodb/oddsdb.py
import streamlit as st
import boto3
import pandas as pd
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from datetime import datetime

@st.cache_data(ttl=5)  # 5 seconds cache time
def fetch_dynamodb_items():
    """
    Fetch all odds data from DynamoDB and return as formatted dataframe
    with improved performance and error handling
    """
    try:
        # Create a Session using credentials from Streamlit secrets
        session = boto3.Session(
            aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
            region_name=st.secrets["aws"]["region_name"]
        )
        dynamodb = session.resource("dynamodb")
        table = dynamodb.Table("SoccerOdds2")  # your table name
        
        # Use scan with pagination for better performance
        items = []
        last_evaluated_key = None
        
        while True:
            if last_evaluated_key:
                response = table.scan(ExclusiveStartKey=last_evaluated_key)
            else:
                response = table.scan()
                
            items.extend(response.get("Items", []))
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(items)
        
        # If the DataFrame is empty, return empty DataFrame
        if df.empty:
            return df
        
        # Ensure consistent column names (converting from DynamoDB to your app expectations)
        column_mapping = {
            'MatchId': 'fixture_id',
            'Timestamp': 'timestamp',
            'FixtureDate': 'fixture_date',
            'HomeTeam': 'home_team',
            'AwayTeam': 'away_team',
            'FetchTimestamp': 'fetch_timestamp',
            'Bookmaker': 'bookmaker',
            'MarketName': 'market_name',
            'MarketId': 'market_id',
            'Selection': 'selection',
            'Odd': 'odd',
            'LeagueId': 'league_id'
        }
        
        # Rename columns to match your application's expectations
        for db_col, app_col in column_mapping.items():
            if db_col in df.columns and app_col not in df.columns:
                df.rename(columns={db_col: app_col}, inplace=True)
        
        # Convert numeric types
        if 'odd' in df.columns:
            df['odd'] = pd.to_numeric(df['odd'], errors='coerce')
            
        return df
        
    except Exception as e:
        st.error(f"Error fetching data from DynamoDB: {str(e)}")
        return pd.DataFrame()  # Return empty DataFrame on error

def fetch_odds_for_matches(match_ids=None):
    """
    Fetch odds for specific matches with better performance
    
    Args:
        match_ids: List of fixture IDs to fetch, or None for all matches
    
    Returns:
        DataFrame containing the odds data
    """
    try:
        # Create a Session using credentials from Streamlit secrets
        session = boto3.Session(
            aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
            region_name=st.secrets["aws"]["region_name"]
        )
        dynamodb = session.resource("dynamodb")
        table = dynamodb.Table("SoccerOdds2")
        
        all_items = []
        
        # If specific match IDs are provided, query for each one
        if match_ids:
            for match_id in match_ids:
                response = table.query(
                    KeyConditionExpression=Key('MatchId').eq(str(match_id))
                )
                all_items.extend(response.get('Items', []))
                
                # Handle pagination if needed
                while 'LastEvaluatedKey' in response:
                    response = table.query(
                        KeyConditionExpression=Key('MatchId').eq(str(match_id)),
                        ExclusiveStartKey=response['LastEvaluatedKey']
                    )
                    all_items.extend(response.get('Items', []))
        else:
            # If no match IDs provided, use scan (less efficient but gets all data)
            response = table.scan()
            all_items = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                all_items.extend(response.get('Items', []))
        
        # Convert to DataFrame
        df = pd.DataFrame(all_items)
        
        if df.empty:
            return df
            
        # Ensure consistent column names (converting from DynamoDB to your app expectations)
        column_mapping = {
            'MatchId': 'fixture_id',
            'Timestamp': 'timestamp',
            'FixtureDate': 'fixture_date',
            'HomeTeam': 'home_team',
            'AwayTeam': 'away_team',
            'FetchTimestamp': 'fetch_timestamp',
            'Bookmaker': 'bookmaker',
            'MarketName': 'market_name',
            'MarketId': 'market_id',
            'Selection': 'selection',
            'Odd': 'odd',
            'LeagueId': 'league_id'
        }
        
        # Rename columns to match your application's expectations
        for db_col, app_col in column_mapping.items():
            if db_col in df.columns and app_col not in df.columns:
                df.rename(columns={db_col: app_col}, inplace=True)
        
        # Convert numeric types
        if 'odd' in df.columns:
            df['odd'] = pd.to_numeric(df['odd'], errors='coerce')
            
        return df
        
    except Exception as e:
        st.error(f"Error fetching match odds from DynamoDB: {str(e)}")
        return pd.DataFrame()

def fetch_odds_history_for_graph(fixture_id, market_id, selection, bookmaker=None):
    """
    Fetch historical odds data for a specific selection to display in a graph
    
    Args:
        fixture_id: The ID of the match
        market_id: The market ID (e.g., "1" for 1X2)
        selection: The selection (e.g., "1", "X", "2")
        bookmaker: Optional bookmaker to filter by
        
    Returns:
        List of dictionaries with timestamp and odd values
    """
    try:
        # Create a Session using credentials from Streamlit secrets
        session = boto3.Session(
            aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
            region_name=st.secrets["aws"]["region_name"]
        )
        dynamodb = session.resource("dynamodb")
        table = dynamodb.Table("SoccerOdds2")
        
        # Query parameters - first get all items for this fixture
        response = table.query(
            KeyConditionExpression=Key('MatchId').eq(str(fixture_id))
        )
        
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression=Key('MatchId').eq(str(fixture_id)),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        # Filter the items in memory for better performance than using FilterExpression
        filtered_items = []
        for item in items:
            # Check if the item matches our criteria
            if (item.get('MarketId', '') == market_id or item.get('market_id', '') == market_id) and \
               (item.get('Selection', '') == selection or item.get('selection', '') == selection) and \
               (bookmaker is None or 
                item.get('Bookmaker', '') == bookmaker or 
                item.get('bookmaker', '') == bookmaker):
                filtered_items.append(item)
        
        # Format the data for graphing
        history = []
        for item in filtered_items:
            # Get timestamp from FetchTimestamp or timestamp
            ts = item.get('FetchTimestamp', item.get('fetch_timestamp', ''))
            
            # Parse timestamp if it's a string
            if isinstance(ts, str):
                try:
                    # Try to parse it as an ISO format timestamp
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    ts = dt.isoformat()
                except (ValueError, TypeError):
                    # If parsing fails, just use the string
                    pass
            
            # Get odd value
            odd_value = item.get('Odd', item.get('odd', 0))
            
            # Convert to float if it's a Decimal
            if isinstance(odd_value, Decimal):
                odd_value = float(odd_value)
            
            history.append({
                'timestamp': ts,
                'odd': odd_value,
                'bookmaker': item.get('Bookmaker', item.get('bookmaker', ''))
            })
        
        # Sort by timestamp
        history.sort(key=lambda x: x['timestamp'])
        return history
        
    except Exception as e:
        st.error(f"Error fetching odds history: {str(e)}")
        return []


def get_all_matches():
    """
    Get a list of all available matches
    
    Returns:
        List of dictionaries with match details
    """
    try:
        # Get all data
        df = fetch_dynamodb_items()
        
        if df.empty:
            return []
        
        # Get unique matches by fixture_id
        if 'fixture_id' in df.columns:
            match_ids = df['fixture_id'].unique()
        else:
            return []
        
        matches = []
        for match_id in match_ids:
            match_rows = df[df['fixture_id'] == match_id]
            if not match_rows.empty:
                # Get first row for match details
                row = match_rows.iloc[0]
                
                # Create a match object
                match = {
                    'fixture_id': match_id,
                    'home_team': row.get('home_team', ''),
                    'away_team': row.get('away_team', ''),
                    'fixture_date': row.get('fixture_date', ''),
                    'display_name': f"{row.get('home_team', '')} vs {row.get('away_team', '')}"
                }
                matches.append(match)
        
        return matches
    
    except Exception as e:
        st.error(f"Error getting matches: {str(e)}")
        return []

def get_selections_for_market(fixture_id, market_id):
    """
    Get available selections for a specific market
    
    Args:
        fixture_id: The ID of the match
        market_id: The market ID (e.g., "1" for 1X2)
        
    Returns:
        List of available selections
    """
    try:
        # Create a Session using credentials from Streamlit secrets
        session = boto3.Session(
            aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
            region_name=st.secrets["aws"]["region_name"]
        )
        dynamodb = session.resource("dynamodb")
        table = dynamodb.Table("SoccerOdds2")
        
        # Query for this match
        response = table.query(
            KeyConditionExpression=Key('MatchId').eq(str(fixture_id))
        )
        
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression=Key('MatchId').eq(str(fixture_id)),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        # Filter for the specified market and extract unique selections
        selections = set()
        for item in items:
            if (item.get('MarketId', '') == market_id or item.get('market_id', '') == market_id) and \
               ('Selection' in item or 'selection' in item):
                selections.add(item.get('Selection', item.get('selection', '')))
        
        return sorted(list(selections))
        
    except Exception as e:
        st.error(f"Error getting selections: {str(e)}")
        return []

def get_bookmakers():
    """
    Get a list of all bookmakers in the data
    
    Returns:
        List of bookmaker names
    """
    try:
        # Get all data
        df = fetch_dynamodb_items()
        
        if df.empty:
            return []
        
        # Get unique bookmakers
        if 'bookmaker' in df.columns:
            return sorted(df['bookmaker'].unique().tolist())
        elif 'Bookmaker' in df.columns:
            return sorted(df['Bookmaker'].unique().tolist())
        else:
            return []
    
    except Exception as e:
        st.error(f"Error getting bookmakers: {str(e)}")
        return []