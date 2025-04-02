import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
import html

def display_odds_table(df, market_dict, significant_changes=None):
    """
    Display odds in a table format with color-coded changes
    
    Args:
        df: DataFrame containing odds data
        market_dict: Dictionary mapping market IDs to market names
        significant_changes: Dictionary containing changes with percentage values
    """
    
    if df.empty:
        st.info("No odds data available for the selected markets.")
        return
    
    # Filter data to only include markets that exist in the market_dict
    df_filtered = df[df['market_id'].isin(market_dict.keys())].copy()
    
    if df_filtered.empty:
        st.info(f"No odds data available for the selected markets. Available markets: {df['market_id'].unique().tolist()}")
        return
    
    # Create an enhanced HTML table with modern styling
    html_table = """
    <style>
    .odds-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
        font-family: 'Arial', sans-serif;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        border-radius: 4px;
        overflow: hidden;
    }
    .odds-table th, .odds-table td {
        border: 1px solid #2c3e50;
        padding: 8px;
        text-align: center;
    }
    .odds-table th {
        background-color: #2c3e50;
        color: white !important;
        font-weight: bold;
        padding: 12px 8px;
    }
    .odds-table tr:nth-child(even) {
        background-color: #1a202c;
    }
    .odds-table tr:nth-child(odd) {
        background-color: #2d3748;
    }
    .odds-table td {
        color: #f8f9fa !important;
        font-weight: 500;
    }
    .event-header {
        text-align: left !important;
        background-color: #102a43 !important;
        color: white !important;
    }
    .market-header {
        background-color: #3a506b !important;
        color: white !important;
        font-weight: bold;
    }
    .event-cell {
        text-align: left !important;
        font-weight: bold;
        color: #e2e8f0 !important;
    }
    .odds-value {
        font-weight: bold;
        color: #fbbf24 !important;
    }
    /* Color classes for different change percentages */
    .change-small {
        background-color: rgba(52, 211, 153, 0.3) !important;
        color: #34d399 !important;
    }
    .change-medium {
        background-color: rgba(251, 191, 36, 0.3) !important;
        color: #fbbf24 !important;
    }
    .change-large {
        background-color: rgba(239, 68, 68, 0.3) !important;
        color: #ef4444 !important;
    }
    /* Legend styling */
    .legend-container {
        display: flex;
        justify-content: flex-end;
        margin-top: 10px;
        font-family: 'Arial', sans-serif;
        padding: 10px;
        background-color: #1e293b;
        border-radius: 4px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        margin-left: 15px;
    }
    .legend-color {
        width: 20px;
        height: 20px;
        margin-right: 5px;
        border-radius: 3px;
    }
    .legend-title {
        color: white;
        margin-right: 15px;
        font-weight: bold;
    }
    .legend-text {
        color: #f8f9fa;
        font-size: 14px;
    }
    </style>
    
    <div style="overflow-x: auto;">
    <table class="odds-table">
    """
    
    # Get unique matches
    matches = df_filtered.drop_duplicates(subset=['fixture_id', 'home_team', 'away_team'])
    matches_list = matches[['fixture_id', 'home_team', 'away_team']].to_dict('records')
    
    # Get unique markets and map them to readable names
    markets = {}
    for market_id in df_filtered['market_id'].unique():
        if market_id in market_dict:
            markets[market_id] = market_dict[market_id]
    
    # Create basic header row with event info and the first few markets
    html_table += "<tr>"
    html_table += "<th class='event-header' colspan='3'>Event</th>"
    
    # Determine priority markets based on what's available in the data
    available_market_ids = df_filtered['market_id'].unique().tolist()
    
    # Check if we're dealing with main or secondary markets
    if '1' in available_market_ids:  # Main markets
        priority_markets = [m for m in ["1", "4", "5"] if m in available_market_ids]
    else:  # Secondary markets
        # Just take the first 3 markets we find
        priority_markets = available_market_ids[:3] if len(available_market_ids) > 0 else []
    
    for market_id in priority_markets:
        if market_id in markets:
            market_name = markets[market_id]
            market_data = df_filtered[df_filtered['market_id'] == market_id]
            selections = market_data['selection'].unique()
            html_table += f"<th class='market-header' colspan='{len(selections)}'>{market_name}</th>"
    
    html_table += "</tr>"
    
    # Create header row with selection names
    html_table += "<tr>"
    html_table += "<th>Date</th><th>Home</th><th>Away</th>"
    
    # Add selection headers
    for market_id in priority_markets:
        if market_id in markets:
            market_data = df_filtered[df_filtered['market_id'] == market_id]
            selections = sorted(market_data['selection'].unique())
            
            for selection in selections:
                display_name = selection
                if selection == "Over" or selection.startswith("Over "):
                    display_name = "O" if selection == "Over" else f"O {selection.split(' ', 1)[1]}"
                elif selection == "Under" or selection.startswith("Under "):
                    display_name = "U" if selection == "Under" else f"U {selection.split(' ', 1)[1]}"
                html_table += f"<th>{display_name}</th>"
    
    html_table += "</tr>"
    
    # Add data rows - one for each match
    for match in matches_list:
        fixture_id = match['fixture_id']
        home_team = match['home_team']
        away_team = match['away_team']
        
        # Get date from match data
        match_data = df_filtered[df_filtered['fixture_id'] == fixture_id]
        fixture_date = match_data['fixture_date'].iloc[0] if 'fixture_date' in match_data.columns else ""
        
        # Format date if it exists
        try:
            date_str = datetime.fromisoformat(str(fixture_date).replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
        except:
            date_str = str(fixture_date)
        
        # Start row with event info
        html_table += "<tr>"
        html_table += f"<td class='event-cell'>{date_str}</td>"
        html_table += f"<td class='event-cell'>{home_team}</td>"
        html_table += f"<td class='event-cell'>{away_team}</td>"
        
        # Add odds data for each market and selection
        for market_id in priority_markets:
            if market_id in markets:
                market_data = df_filtered[df_filtered['market_id'] == market_id]
                market_match_data = market_data[market_data['fixture_id'] == fixture_id]
                selections = sorted(market_data['selection'].unique())
                
                for selection in selections:
                    # Find the odds for this selection
                    selection_data = market_match_data[market_match_data['selection'] == selection]
                    
                    if not selection_data.empty:
                        # Get the most recent odds
                        if 'fetch_timestamp' in selection_data.columns:
                            selection_data = selection_data.sort_values('fetch_timestamp', ascending=False)
                        
                        # Get the odds value
                        odds_value = selection_data['odd'].iloc[0] if 'odd' in selection_data.columns else ""
                        
                        # Format the odds value
                        if odds_value != "":
                            try:
                                formatted_odds = f"{float(odds_value):.2f}"
                                
                                # Check if this odd has a change to color-code
                                cell_class = 'odds-value'
                                if significant_changes:
                                    bookmaker = selection_data['bookmaker'].iloc[0] if 'bookmaker' in selection_data.columns else ""
                                    merge_key = f"{fixture_id}_{market_id}_{selection}_{bookmaker}"
                                    if merge_key in significant_changes:
                                        percent_change = significant_changes[merge_key]['percent_change']
                                        # Apply color based on percentage change ranges
                                        if 0 < percent_change <= 1:
                                            cell_class = 'odds-value change-small'
                                        elif 1 < percent_change <= 3:
                                            cell_class = 'odds-value change-medium'
                                        elif percent_change > 3:
                                            cell_class = 'odds-value change-large'
                                        
                                        # Add direction arrow
                                        direction = significant_changes[merge_key]['direction']
                                        arrow = "↑" if direction == "up" else "↓"
                                        formatted_odds = f"{formatted_odds} {arrow}"
                                
                                html_table += f"<td class='{cell_class}'>{formatted_odds}</td>"
                            except:
                                formatted_odds = str(odds_value)
                                html_table += f"<td class='odds-value'>{formatted_odds}</td>"
                        else:
                            html_table += "<td>-</td>"
                    else:
                        html_table += "<td>-</td>"
        
        html_table += "</tr>"
    
    html_table += "</table>"
    
    # Add legend
    html_table += """
    <div class="legend-container">
        <div class="legend-title">Odds Change:</div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgba(52, 211, 153, 0.3);"></div>
            <div class="legend-text">0-1% Change</div>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgba(251, 191, 36, 0.3);"></div>
            <div class="legend-text">1-3% Change</div>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgba(239, 68, 68, 0.3);"></div>
            <div class="legend-text">3%+ Change</div>
        </div>
    </div>
    """
    
    html_table += "</div>"
    
    # Display the HTML table
    st.markdown(html_table, unsafe_allow_html=True)
    
        

def display_odds_in_app(df, market_dict, significant_changes=None):
    """
    Display odds in a format similar to the image
    
    Args:
        df: DataFrame containing odds data
        market_dict: Dictionary mapping market IDs to market names (MAIN_MARKETS or SECONDARY_MARKETS)
        significant_changes: Dictionary of significant changes to highlight
    """
    if df.empty:
        st.info("No odds data available.")
        return
    
    # Get unique matches
    unique_matches = df.drop_duplicates(subset=['home_team', 'away_team', 'fixture_id'])
    
    if unique_matches.empty:
        st.info("No matches available.")
        return
    
    # Create an expandable section for each match
    for _, match in unique_matches.iterrows():
        fixture_id = match['fixture_id']
        home_team = match['home_team']
        away_team = match['away_team']
        
        # Get fixture date
        fixture_date = match.get('fixture_date', '')
        try:
            # Try to parse and format the date
            date_obj = datetime.fromisoformat(fixture_date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
        except (ValueError, AttributeError, TypeError):
            formatted_date = fixture_date
        
        # Create expandable section for this match
        with st.expander(f"{home_team} vs {away_team} - {formatted_date}"):
            # Filter data for this match
            match_data = df[df['fixture_id'] == fixture_id]
            
            # Group markets into a table similar to the screenshot
            market_rows = []
            
            # Process each market
            for market_id, market_name in market_dict.items():
                # Filter for this market
                market_data = match_data[match_data['market_id'] == market_id]
                
                if market_data.empty:
                    continue
                
                # Create a row for this market
                market_row = {
                    'Market': f"{market_name} ({market_id})"
                }
                
                # Get all bookmakers
                bookmakers = market_data['bookmaker'].unique()
                
                # For each bookmaker, add columns for different selections
                for bookmaker in bookmakers:
                    # Filter for this bookmaker
                    bookmaker_data = market_data[market_data['bookmaker'] == bookmaker]
                    
                    # Get all selections for this market/bookmaker
                    for _, selection_row in bookmaker_data.iterrows():
                        selection = selection_row['selection']
                        odd_value = selection_row['odd']
                        
                        # Check if this odd has a significant change
                        if significant_changes:
                            merge_key = f"{fixture_id}_{market_id}_{selection}_{bookmaker}"
                            if merge_key in significant_changes:
                                direction = significant_changes[merge_key]['direction']
                                arrow = "↑" if direction == "up" else "↓"
                                odd_value = f"{odd_value} {arrow}"
                        
                        # Clean selection name for column
                        column_name = f"{selection} ({bookmaker})"
                        market_row[column_name] = odd_value
                
                # Add to market rows
                market_rows.append(market_row)
            
            # Create DataFrame for this match's markets
            market_df = pd.DataFrame(market_rows)
            
            if not market_df.empty:
                # Get all columns (market + all selections)
                all_columns = ['Market'] + [col for col in market_df.columns if col != 'Market']
                
                # Configure number formatting for selections
                column_config = {
                    'Market': st.column_config.TextColumn("Market")
                }
                
                # Add formatting for each selection column
                for col in market_df.columns:
                    if col != 'Market':
                        column_config[col] = st.column_config.NumberColumn(
                            col,
                            format="%.2f"
                        )
                
                # Display the dataframe
                st.dataframe(
                    market_df[all_columns],
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config
                )
            else:
                st.info(f"No odds data available for {market_name}.")

