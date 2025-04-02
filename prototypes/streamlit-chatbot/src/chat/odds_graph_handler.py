import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
import plotly.express as px

class OddsGraphHandler:
    def __init__(self):
        """Initialize the OddsGraphHandler"""
        self.main_markets = {}
        self.secondary_markets = {}
        
        # Initialize session state
        if 'odds_graph_params' not in st.session_state:
            st.session_state.odds_graph_params = {}
        if 'show_odds_graph' not in st.session_state:
            st.session_state.show_odds_graph = False
    
    def set_market_dictionaries(self, main_markets, secondary_markets):
        """Set the market dictionaries for reference"""
        self.main_markets = main_markets
        self.secondary_markets = secondary_markets
    
    def is_graph_request(self, query):
        """Check if the query is asking for an odds graph visualization"""
        graph_keywords = [
            'grafico quote', 'andamento quota', 'andamento delle quote', 
            'trend quota', 'storico quote', 'mostra grafico',
            'visualizza quote', 'vedi quote', 'grafico', 'andamento'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in graph_keywords)
    
    def handle_graph_request(self, query):
        """Extract parameters from the query and prepare graph data"""
        # Extract market information
        market_id = self._extract_market_id(query)
        
        # Extract team information to get fixture ID
        fixture_id = self._extract_fixture_id(query)
        
        # Extract selection information
        selection = self._extract_selection(query)
        
        # Extract bookmaker information or use default
        bookmaker = self._extract_bookmaker(query) or "Bookmaker J"
        
        # Create parameters
        params = {
            'fixture_id': fixture_id,
            'market_id': market_id,
            'selection': selection,
            'bookmaker': bookmaker
        }
        
        # Store parameters in session state
        st.session_state.odds_graph_params = params
        st.session_state.show_odds_graph = True
        
        # Generate response text
        response = self._generate_graph_response(params)
        
        return params, response
    
    def _extract_market_id(self, query):
        """Extract market ID from the query"""
        query_lower = query.lower()
        
        # Check for market names in the query
        for market_id, market_name in {**self.main_markets, **self.secondary_markets}.items():
            if market_name.lower() in query_lower:
                return market_id
        
        # Check for common market keywords
        if '1x2' in query_lower or 'match winner' in query_lower or 'vincente' in query_lower:
            return '1'  # Match Winner market
        elif 'over/under' in query_lower or 'over under' in query_lower or 'over' in query_lower or 'under' in query_lower:
            return '5'  # Goals Over/Under market
        elif 'handicap' in query_lower:
            return '4'  # Asian Handicap market
        elif 'double chance' in query_lower or 'doppia chance' in query_lower:
            return '12'  # Double Chance market
        
        # Default to Match Winner if no match
        return '1'
    
    def _extract_fixture_id(self, query):
        """Extract fixture ID from the query based on team names"""
        # Simplified implementation - in a real app, you would search for team names
        # and find the corresponding fixture ID from your database
        
        # Try to extract team names from patterns like "Team1 vs Team2"
        team_pattern = r'([A-Za-z\s]+)\s+(?:vs|contro|vs\.|contro\.)\s+([A-Za-z\s]+)'
        match = re.search(team_pattern, query, re.IGNORECASE)
        
        if match:
            home_team = match.group(1).strip()
            away_team = match.group(2).strip()
            
            # Now search for this match in the odds data
            if 'odds_data' in st.session_state and st.session_state.odds_data is not None:
                df = st.session_state.odds_data
                
                # Try exact match first
                matches = df[(df['home_team'].str.lower() == home_team.lower()) & 
                              (df['away_team'].str.lower() == away_team.lower())]
                
                if not matches.empty:
                    return matches.iloc[0]['fixture_id']
                
                # Try partial match
                matches = df[df['home_team'].str.contains(home_team, case=False) & 
                              df['away_team'].str.contains(away_team, case=False)]
                
                if not matches.empty:
                    return matches.iloc[0]['fixture_id']
        
        # If no specific match is found or mentioned, use the first fixture_id in the data
        if 'odds_data' in st.session_state and st.session_state.odds_data is not None:
            df = st.session_state.odds_data
            if not df.empty and 'fixture_id' in df.columns:
                return df['fixture_id'].iloc[0]
        
        # Fallback to a dummy ID
        return 12345
    
    def _extract_selection(self, query):
        """Extract selection from the query"""
        query_lower = query.lower()
        
        # Common selections
        if 'home' in query_lower or 'casa' in query_lower or '1' in query_lower:
            return 'Home'
        elif 'draw' in query_lower or 'pareggio' in query_lower or 'x' in query_lower:
            return 'Draw'
        elif 'away' in query_lower or 'trasferta' in query_lower or '2' in query_lower:
            return 'Away'
        elif 'over' in query_lower:
            # Try to extract the over value
            over_pattern = r'over\s+(\d+(?:\.\d+)?)'
            match = re.search(over_pattern, query_lower)
            if match:
                return f"Over {match.group(1)}"
            return 'Over 2.5'
        elif 'under' in query_lower:
            # Try to extract the under value
            under_pattern = r'under\s+(\d+(?:\.\d+)?)'
            match = re.search(under_pattern, query_lower)
            if match:
                return f"Under {match.group(1)}"
            return 'Under 2.5'
        
        # Default selection based on extracted market
        market_id = self._extract_market_id(query)
        if market_id == '1':  # Match Winner
            return 'Home'  # Default to home team
        elif market_id == '5':  # Over/Under
            return 'Over 2.5'  # Default to over 2.5
        
        # Generic fallback
        return 'Home'
    
    def _extract_bookmaker(self, query):
        """Extract bookmaker from the query"""
        query_lower = query.lower()
        
        # List of common bookmakers
        bookmakers = ['Bookmaker A', 'Bookmaker J', 'Bookmaker B', 'Bookmaker C', 'Bookmaker G', 'Bookmaker F', 'Bookmaker D']
        
        for bookmaker in bookmakers:
            if bookmaker in query_lower:
                return bookmaker.title()
        
        # Default bookmaker
        return 'Bookmaker J'
    
    def _generate_graph_response(self, params):
        """Generate a response about the graph being shown"""
        market_name = self._get_market_name(params.get('market_id'))
        selection = params.get('selection')
        bookmaker = params.get('bookmaker')
        
        # Get match details if available
        match_str = "la partita selezionata"
        match_details = self._get_match_details(params.get('fixture_id'))
        if match_details:
            match_str = f"{match_details.get('home_team', '')} vs {match_details.get('away_team', '')}"
        
        return f"Ecco il grafico dell'andamento quote per '{selection}' nel mercato '{market_name}' offerto da {bookmaker} per {match_str}. Il grafico mostra l'evoluzione delle quote nelle ultime ore. Puoi vedere l'andamento e identificare eventuali variazioni significative."
    
    def render_odds_graph(self, params=None):
        """Render a graph of odds data based on provided parameters"""
        # If no params provided, use the ones in session state
        if params is None and 'odds_graph_params' in st.session_state:
            params = st.session_state.odds_graph_params
        
        if not params:
            st.info("No odds parameters provided for graphing.")
            return
        
        # Extract parameters
        fixture_id = params.get('fixture_id')
        market_id = params.get('market_id')
        selection = params.get('selection')
        bookmaker = params.get('bookmaker')
        
        # Ensure selection is string
        selection_str = str(selection) if selection is not None else "None"
        
        # Display basic information
        st.subheader("Odds Trend Visualization")
        
        # Get market name
        market_name = self._get_market_name(market_id)
        
        # Show selected parameters
        st.write(f"**Market:** {market_name}")
        st.write(f"**Selection:** {selection_str}")
        st.write(f"**Bookmaker:** {bookmaker}")
        
        # Get match details if available
        match_details = self._get_match_details(fixture_id)
        if match_details:
            st.write(f"**Match:** {match_details.get('home_team', '')} vs {match_details.get('away_team', '')}")
        
        # Generate and display mock trend data
        self._display_mock_trend(fixture_id, market_id, selection_str, bookmaker)
    
    def _get_market_name(self, market_id):
        """Get market name from market ID"""
        market_id_str = str(market_id) if market_id is not None else "None"
        
        if market_id_str in self.main_markets:
            return self.main_markets[market_id_str]
        elif market_id_str in self.secondary_markets:
            return self.secondary_markets[market_id_str]
        return f"Market {market_id_str}"
    
    def _get_match_details(self, fixture_id):
        """Get match details from fixture ID"""
        try:
            # Try to get match details from the session state
            if 'odds_data' in st.session_state and st.session_state.odds_data is not None:
                df = st.session_state.odds_data
                match_rows = df[df['fixture_id'] == fixture_id]
                
                if not match_rows.empty:
                    match_row = match_rows.iloc[0]
                    return {
                        'home_team': match_row['home_team'],
                        'away_team': match_row['away_team']
                    }
            
            return None
        except Exception as e:
            st.error(f"Error getting match details: {str(e)}")
            return None
    
    def _display_mock_trend(self, fixture_id, market_id, selection, bookmaker):
        """Generate and display mock trend data for visualization"""
        # Create a seed based on the inputs to get consistent mock data
        # Ensure selection is a string to avoid hash inconsistencies
        selection_str = str(selection) if selection is not None else "None"
        seed = hash(f"{fixture_id}_{market_id}_{selection_str}_{bookmaker}") % 10000
        np.random.seed(seed)
        
        # Generate timestamps for the last 24 hours
        now = datetime.now()
        timestamps = [now - timedelta(hours=i) for i in range(24, -1, -1)]
        
        # Starting odd value between 1.5 and 3.0
        base_value = np.random.uniform(1.5, 3.0)
        
        # Generate random movements with upward or downward trend
        trend_direction = np.random.choice([-1, 1])
        trend_strength = np.random.uniform(0.005, 0.015)  # Controls how strong the trend is
        random_changes = np.random.normal(trend_strength * trend_direction, 0.03, len(timestamps))
        cumulative_changes = np.cumsum(random_changes)
        
        # Ensure odds don't go below 1.01
        odds_values = [max(1.01, base_value + change) for change in cumulative_changes]
        
        # Create mock dataframe
        history_df = pd.DataFrame({
            'timestamp': timestamps,
            'odd': odds_values
        })
        
        # Create Plotly chart
        fig = px.line(
            history_df, 
            x='timestamp', 
            y='odd',
            markers=True,
            title=f"Odds Movement Over Time (Sample Data)"
        )
        
        # Calculate range for better visualization
        y_min = history_df['odd'].min() * 0.95  # 5% below min
        y_max = history_df['odd'].max() * 1.05  # 5% above max
        
        # Customize the chart for better appearance
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Odds Value",
            hovermode="x unified",
            yaxis=dict(
                tickformat=".2f",
                range=[y_min, y_max]
            ),
            height=400,
            title_font=dict(size=20),
            font=dict(family="Arial", size=14),
            margin=dict(l=40, r=40, t=60, b=40),
            plot_bgcolor='rgba(25,25,25,0.8)',
            paper_bgcolor='rgba(30,30,30,0)',
            xaxis=dict(
                gridcolor='rgba(80, 80, 80, 0.3)',
                showgrid=True,
            ),
            yaxis_gridcolor='rgba(80, 80, 80, 0.3)',
        )
        
        # Add specific styling to the line
        fig.update_traces(
            line=dict(width=3, color='#fbbf24'),
            marker=dict(size=8, color='#fb923c', line=dict(width=2, color='#fbbf24')),
            hovertemplate='<b>%{y:.2f}</b><br>%{x}<br>Bookmaker: ' + str(bookmaker)
        )
        
        # Add trend indicators
        if len(history_df) > 0:
            latest_value = history_df['odd'].iloc[-1]
            fig.add_hline(
                y=latest_value, 
                line_dash="dash", 
                line_color="#38bdf8",
                annotation_text=f"Current: {latest_value:.2f}", 
                annotation_position="top right"
            )
            
            # Average line
            avg_value = history_df['odd'].mean()
            fig.add_hline(
                y=avg_value, 
                line_dash="dot", 
                line_color="#4ade80",
                annotation_text=f"Avg: {avg_value:.2f}", 
                annotation_position="top left"
            )
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Add trend analysis
        if len(history_df) >= 2:
            first_value = history_df['odd'].iloc[0]
            last_value = history_df['odd'].iloc[-1]
            change = last_value - first_value
            pct_change = (change / first_value) * 100
            
            if pct_change > 0:
                st.success(f"The odds have increased by {pct_change:.1f}% from {first_value:.2f} to {last_value:.2f}.")
            elif pct_change < 0:
                st.error(f"The odds have decreased by {abs(pct_change):.1f}% from {first_value:.2f} to {last_value:.2f}.")
            else:
                st.info(f"The odds have remained stable at {last_value:.2f}.")