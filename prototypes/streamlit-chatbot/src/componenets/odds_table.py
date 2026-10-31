import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.backend.predizioni import fetch_odds_history_for_graph
import time
import random


class OddsTable:
    def __init__(self):
        """Initialize the OddsTable component."""
        if 'last_cell_interaction' not in st.session_state:
            st.session_state.last_cell_interaction = False
        if 'dialog_already_shown' not in st.session_state:
            st.session_state.dialog_already_shown = False
        if 'selected_fixture' not in st.session_state:
            st.session_state.selected_fixture = None
        if 'selected_market' not in st.session_state:
            st.session_state.selected_market = None
        if 'selected_selection' not in st.session_state:
            st.session_state.selected_selection = None
        if 'selected_bookmaker' not in st.session_state:
            st.session_state.selected_bookmaker = None
        if 'show_trend_popup' not in st.session_state:
            st.session_state.show_trend_popup = False
        if 'dialog_shown_for_selection' not in st.session_state:
            st.session_state.dialog_shown_for_selection = None


    def _prepare_data_for_aggrid(self, df, market_dict):
        """
        Prepare data for AgGrid display with proper match-based rows and market-based columns.
        This creates one row per match, with market data organized properly in columns.
        """
        if df.empty:
            return pd.DataFrame()
            
        # Filter data to markets in the dictionary
        df_filtered = df[df['market_id'].isin(market_dict.keys())].copy()
        
        if df_filtered.empty:
            return pd.DataFrame()
        
        # Get unique fixtures (matches)
        fixtures = df_filtered.drop_duplicates(subset=['fixture_id', 'home_team', 'away_team'])
        
        # Initialize the result data
        result_data = []
        
        # Debug columns if needed
        if st.session_state.get('debug_mode', False):
            print(f"DataFrame columns: {df_filtered.columns.tolist()}")
        
        # For each fixture, create ONE row
        for _, fixture in fixtures.iterrows():
            fixture_id = fixture['fixture_id']
            home_team = fixture['home_team'] 
            away_team = fixture['away_team']
            
            # PRIMARY IMPROVEMENT: Directly use date_utc field which exists in the data
            # Format date - Use date_utc which we know exists from the debug output
            date_str = "Date not available"
            
            # First, try date_utc field
            if 'date_utc' in fixture.index and fixture['date_utc']:
                fixture_date = fixture['date_utc']
                try:
                    # Handle different date formats
                    if isinstance(fixture_date, str):
                        # Remove Z or +00:00 to standardize format
                        cleaned_date = fixture_date.replace('Z', '').replace('+00:00', '')
                        # Try to parse as ISO format
                        date_obj = datetime.fromisoformat(cleaned_date)
                        # Format for display with day of week
                        date_str = date_obj.strftime('%Y-%m-%d %H:%M')
                    elif isinstance(fixture_date, (datetime, pd.Timestamp)):
                        # It's already a datetime object
                        date_str = fixture_date.strftime('%Y-%m-%d %H:%M')
                    else:
                        # Try to convert to string and parse
                        date_str = str(fixture_date)
                        
                except Exception as e:
                    if st.session_state.get('debug_mode', False):
                        print(f"Error parsing date_utc: {e} for value: {fixture_date}")
                    date_str = str(fixture_date)
            # Fall back to fixture_date if available
            elif 'fixture_date' in fixture.index and fixture['fixture_date']:
                date_str = str(fixture['fixture_date'])
                
            # Create base row for this fixture
            row = {
                'fixture_id': fixture_id,
                'date': date_str,
                'home_team': home_team,
                'away_team': away_team,
                'match': f"{home_team} vs {away_team}",
                # Add columns for tracking clicks
                '_clicked_column': None,
                '_clicked_fixture_id': None,
                '_clicked_market_id': None,
                '_clicked_bookmaker': None,
                '_clicked_selection': None
            }
            
            # Get all data for this fixture
            fixture_data = df_filtered[df_filtered['fixture_id'] == fixture_id]
            
            # Group by market, selection, and bookmaker
            for market_id, market_name in market_dict.items():
                market_data = fixture_data[fixture_data['market_id'] == market_id]
                
                if market_data.empty:
                    continue
                
                # Get unique bookmakers for this market
                bookmakers = market_data['bookmaker'].unique()
                
                # For each bookmaker, add the selections as columns
                for bookmaker in bookmakers:
                    bookmaker_data = market_data[market_data['bookmaker'] == bookmaker]
                    
                    # Add each selection as a column in the row
                    for _, odd_row in bookmaker_data.iterrows():
                        selection = odd_row['selection']
                        odd_value = odd_row['odd']
                        
                        # Create hierarchical column name: market_id|bookmaker|selection
                        column_name = f"{market_id}|{bookmaker}|{selection}"
                        row[column_name] = odd_value
            
            # Add this row to results
            result_data.append(row)
        
        # Convert to DataFrame
        result_df = pd.DataFrame(result_data)
        return result_df



    def _prepare_dialog_state(self):
        """Initialize all session state variables related to dialog display"""
        if 'dialog_trigger_source' not in st.session_state:
            st.session_state.dialog_trigger_source = None
        if 'dialog_should_show' not in st.session_state:
            st.session_state.dialog_should_show = False
        if 'current_dialog_id' not in st.session_state:
            st.session_state.current_dialog_id = None
        if 'selected_fixture' not in st.session_state:
            st.session_state.selected_fixture = None
        if 'selected_market' not in st.session_state:
            st.session_state.selected_market = None
        if 'selected_selection' not in st.session_state:
            st.session_state.selected_selection = None
        if 'selected_bookmaker' not in st.session_state:
            st.session_state.selected_bookmaker = None

    def _cell_click_callback(self, selection_id, fixture_id, market_id, selection, bookmaker):
        """Callback for handling cell clicks in the table"""
        # Update all relevant session state
        st.session_state.dialog_trigger_source = "cell_click"
        st.session_state.dialog_should_show = True
        st.session_state.current_dialog_id = selection_id
        
        # Store the selected data
        st.session_state.selected_fixture = fixture_id
        st.session_state.selected_market = market_id
        st.session_state.selected_selection = selection
        st.session_state.selected_bookmaker = bookmaker
        
        # This will cause a rerun with the updated session state

    def _close_dialog_callback(self):
        """Callback for the close button in the dialog"""
        # Update session state to indicate dialog should be closed
        st.session_state.dialog_should_show = False
        st.session_state.dialog_trigger_source = None
        # No need to reset other values as they don't affect dialog display

    def _build_hierarchical_columns(self, df, market_dict, changes=None):
            """Build hierarchical column definitions with proper grouping and animation for changes"""
            # Base columns that should always be visible
            base_columns = [
                {"headerName": "Date", "field": "date", "width": 150, "pinned": "left"},
                {"headerName": "Match", "field": "match", "width": 200, "pinned": "left"}
            ]
            
            # Hidden columns 
            hidden_columns = [
                {"headerName": "Fixture ID", "field": "fixture_id", "hide": True},
                {"headerName": "Home Team", "field": "home_team", "hide": True},
                {"headerName": "Away Team", "field": "away_team", "hide": True},
                {"headerName": "_clicked_column", "field": "_clicked_column", "hide": True},
                {"headerName": "_clicked_fixture_id", "field": "_clicked_fixture_id", "hide": True},
                {"headerName": "_clicked_market_id", "field": "_clicked_market_id", "hide": True},
                {"headerName": "_clicked_bookmaker", "field": "_clicked_bookmaker", "hide": True},
                {"headerName": "_clicked_selection", "field": "_clicked_selection", "hide": True}
            ]
            
            # Group columns by market and bookmaker
            market_columns = {}
            
            # Get all hierarchical columns
            hierarchical_columns = [col for col in df.columns if '|' in col]
            
            for col in hierarchical_columns:
                # Parse the hierarchical column name: market_id|bookmaker|selection
                parts = col.split('|')
                if len(parts) != 3:
                    continue
                    
                market_id, bookmaker, selection = parts
                
                # Get market name from the dictionary
                market_name = market_dict.get(market_id, f"Market {market_id}")
                
                # Create unique keys for the hierarchy
                market_key = f"Market: {market_name}"
                bookmaker_key = f"{market_key}|{bookmaker}"
                
                # Initialize the hierarchies if needed
                if market_key not in market_columns:
                    market_columns[market_key] = {}
                
                if bookmaker_key not in market_columns[market_key]:
                    market_columns[market_key][bookmaker_key] = []
                        
                # Format selection display name
                display_name = selection
                if selection == "Over" or selection.startswith("Over "):
                    display_name = "O" if selection == "Over" else f"O {selection.split(' ', 1)[1]}"
                elif selection == "Under" or selection.startswith("Under "):
                    display_name = "U" if selection == "Under" else f"U {selection.split(' ', 1)[1]}"
                
                # Create column definition with the agAnimateShowChangeCellRenderer
                # This renderer shows flashing animations on value changes
                column_def = {
                    "headerName": display_name,
                    "field": col,
                    "width": 80,
                    "type": ["numericColumn"],
                    "cellRenderer": "agAnimateShowChangeCellRenderer",  # Key for animations
                    "valueFormatter": JsCode("""
                        function(params) {
                            if (params.value === null || params.value === undefined) return '-';
                            return parseFloat(params.value).toFixed(2);
                        }
                    """),
                    "cellStyle": JsCode("""
                        function(params) {
                            if (params.value === null || params.value === undefined) return null;
                            
                            try {
                                // Check for changes with more robust approach
                                let fixtureId = params.data.fixture_id;
                                let columnParts = params.column.colId.split('|');
                                
                                if (columnParts.length === 3) {
                                    let marketId = columnParts[0];
                                    let bookmaker = columnParts[1];
                                    let selection = columnParts[2];
                                    
                                    // Build the key exactly as stored in changes
                                    let changeKey = fixtureId + '|' + marketId + '|' + bookmaker + '|' + selection;
                                    
                                    // Get changes from context, with fallback
                                    let changes = {};
                                    if (params.context && params.context.changes) {
                                        changes = params.context.changes;
                                    }
                                    
                                    // Check if this odd has a change
                                    if (changes[changeKey]) {
                                        console.log("Found change for: " + changeKey);
                                        
                                        // Extract change info safely
                                        let change = changes[changeKey];
                                        if (Array.isArray(change) && change.length >= 3) {
                                            let originalValue = change[0];
                                            let currentValue = change[1];
                                            let recentChange = change[2];
                                            
                                            let isIncrease = recentChange > 0;
                                            
                                            // Apply more visible styling
                                            return {
                                                'color': isIncrease ? '#4ade80' : '#ef4444',
                                                'font-weight': 'bold',
                                                'text-align': 'center',
                                                'background-color': isIncrease ? 'rgba(74, 222, 128, 0.3)' : 'rgba(239, 68, 68, 0.3)',
                                                'border-left': isIncrease ? '3px solid #4ade80' : '3px solid #ef4444',
                                                'cursor': 'pointer'
                                            };
                                        }
                                    }
                                }
                                
                                // Default styling (no change)
                                return {
                                    'color': '#fbbf24',
                                    'font-weight': 'bold',
                                    'text-align': 'center',
                                    'cursor': 'pointer'
                                };
                            } catch (error) {
                                console.error("Error in cellStyle:", error);
                                return {
                                    'color': '#fbbf24',
                                    'font-weight': 'bold', 
                                    'text-align': 'center',
                                    'cursor': 'pointer'
                                };
                            }
                        }
                    """)
                }
                
                # Add to the hierarchy
                market_columns[market_key][bookmaker_key].append(column_def)
            
            # Build the final column definitions
            column_defs = base_columns.copy()
            
            # Add market groups with bookmaker subgroups
            for market_key, bookmakers in market_columns.items():
                bookmaker_children = []
                
                for bookmaker_key, columns in bookmakers.items():
                    # Skip empty bookmakers
                    if not columns:
                        continue
                        
                    # Get bookmaker name from the key
                    bookmaker_name = bookmaker_key.split('|')[1]
                    
                    # Add bookmaker group
                    bookmaker_children.append({
                        "headerName": bookmaker_name,
                        "children": sorted(columns, key=lambda x: x["headerName"])
                    })
                
                # Skip empty markets
                if not bookmaker_children:
                    continue
                    
                # Add market group with bookmaker children
                column_defs.append({
                    "headerName": market_key.replace("Market: ", ""),
                    "children": bookmaker_children
                })
            
            # Add hidden columns
            column_defs.extend(hidden_columns)
            
            return column_defs

    def display_odds_table(self, df, market_dict, all_changes=None, fixture_filter=None, market_filter=None, table_id="default"):
        """Display the odds table with multi-level headers and enhanced change animations."""
        # Initialize dialog-related state
        self._prepare_dialog_state()
        
        if df.empty:
            st.info("No odds data available for the selected markets.")
            return
                
        # Prepare data for AgGrid
        prepared_data = self._prepare_data_for_aggrid(df, market_dict)
        
        if prepared_data.empty:
            st.info("No odds data available for display.")
            return
        
        # Ensure all_changes is a dictionary
        if all_changes is None:
            all_changes = {}

        # if st.session_state.get('debug_mode', False):
        #     st.write(f"Number of changes to apply: {len(all_changes)}")
        #     if all_changes:
        #         sample_key = list(all_changes.keys())[0]
        #         st.write(f"Sample change key: {sample_key}")
        #         st.write(f"Sample change value: {all_changes[sample_key]}")
                    
        # Build grid options with animation settings
        grid_options = self._build_aggrid_options(prepared_data, market_dict, all_changes)
        
        # Add enhanced CSS for cell flashing and animations
        st.markdown("""
        <style>
        /* Cell change animation - more pronounced */
        .ag-value-change-value-highlight {
            animation: ag-value-change-value-highlight 2s ease-out;
        }

        @keyframes ag-value-change-value-highlight {
            0% {
                background-color: rgba(22, 160, 133, 0.8);
                color: white;
                font-weight: bold;
                transform: scale(1.1);
            }
            50% {
                background-color: rgba(22, 160, 133, 0.4);
            }
            100% {
                background-color: transparent;
            }
        }

        /* Custom classes for changed cells */
        .cell-increase {
            color: #4ade80 !important;
            font-weight: bold;
            background-color: rgba(74, 222, 128, 0.3);
            border-left: 3px solid #4ade80;
            transition: all 0.5s ease-in-out;
        }

        .cell-decrease {
            color: #ef4444 !important;
            font-weight: bold;
            background-color: rgba(239, 68, 68, 0.3);
            border-left: 3px solid #ef4444;
            transition: all 0.5s ease-in-out;
        }

        /* Make table more responsive and interactive */
        .ag-theme-streamlit .ag-cell {
            transition: all 0.3s ease;
        }

        .ag-theme-streamlit .ag-cell:hover {
            background-color: rgba(0, 0, 0, 0.1);
            cursor: pointer;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display debug information if in debug mode
        if st.session_state.get('debug_mode', False) and all_changes:
            st.write(f"Number of changes to display: {len(all_changes)}")
            # Show a sample of changes
            sample_key = list(all_changes.keys())[0] if all_changes else None
            if sample_key:
                st.write(f"Sample change key: {sample_key}")
                st.write(f"Sample change value: {all_changes[sample_key]}")
        
        # Display AgGrid with enhanced settings
        grid_response = AgGrid(
            prepared_data,
            gridOptions=grid_options,
            enable_enterprise_modules=False,
            update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.VALUE_CHANGED,  # Changed to ensure updates are detected
            fit_columns_on_grid_load=False,
            theme='alpine',  # Try a different theme for better visualization
            height=500,
            width='100%',
            reload_data=True,  # Set to True to force refresh on data changes
            allow_unsafe_jscode=True,
            key=f"grid_{table_id}"
        )
        
        # Display changes in a separate table for better visibility
        if all_changes:
            with st.expander("Recent Odds Changes", expanded=True):
                changes_data = []
                for key, change_data in all_changes.items():
                    parts = key.split('|')
                    if len(parts) == 4:
                        fixture_id, market_id, bookmaker, selection = parts
                        original_value, current_value, recent_change, total_change = change_data
                        
                        # Find match name
                        match_name = "Unknown match"
                        for _, row in df.iterrows():
                            if str(row.get('fixture_id')) == fixture_id:
                                home = row.get('home_team', '')
                                away = row.get('away_team', '')
                                match_name = f"{home} vs {away}"
                                break
                        
                        try:
                            changes_data.append({
                                "Match": match_name,
                                "Market": market_dict.get(market_id, f"Market {market_id}"),
                                "Bookmaker": bookmaker,
                                "Selection": selection,
                                "Old Value": round(float(original_value), 2),
                                "New Value": round(float(current_value), 2),
                                "Change": round(float(recent_change), 2),
                                "Direction": "▲" if float(recent_change) > 0 else "▼"
                            })
                        except Exception as e:
                            if st.session_state.get('debug_mode', False):
                                st.error(f"Error adding change to table: {str(e)}")
                
                # Show changes in a dataframe
                if changes_data:
                    changes_df = pd.DataFrame(changes_data)
                    st.dataframe(changes_df, use_container_width=True)
                else:
                    st.info("No changes detected yet.")
        
        # Cell click detection - with improved error handling
        try:
            # Check if there are any selected rows
            if hasattr(grid_response, 'selected_rows') and grid_response.selected_rows is not None:
                # Handle different types of return values
                if isinstance(grid_response.selected_rows, pd.DataFrame) and not grid_response.selected_rows.empty:
                    selected_row = grid_response.selected_rows.iloc[0]
                elif isinstance(grid_response.selected_rows, list) and len(grid_response.selected_rows) > 0:
                    selected_row = grid_response.selected_rows[0]
                else:
                    # No valid selection
                    return
                    
                # Check if this is a new cell click with the clicked cell information
                if all(k in selected_row for k in ['_clicked_fixture_id', '_clicked_market_id', '_clicked_bookmaker', '_clicked_selection']) and \
                selected_row['_clicked_fixture_id'] is not None:
                    
                    # Get cell data
                    fixture_id = selected_row['_clicked_fixture_id']
                    market_id = selected_row['_clicked_market_id']
                    selection = selected_row['_clicked_selection']
                    bookmaker = selected_row['_clicked_bookmaker']
                    
                    # Create a unique ID for this selection
                    selection_id = f"{fixture_id}_{market_id}_{selection}_{bookmaker}"
                    
                    # Only trigger callback if this is a new selection
                    if st.session_state.current_dialog_id != selection_id:
                        self._cell_click_callback(selection_id, fixture_id, market_id, selection, bookmaker)
        except Exception as e:
            if st.session_state.get('debug_mode', False):
                with st.expander("Debug Changes Information", expanded=False):
                    st.write("### Changes Dictionary Structure")
                    st.json({
                        "number_of_changes": len(all_changes) if all_changes else 0,
                        "sample_key": list(all_changes.keys())[0] if all_changes and len(all_changes) > 0 else "None",
                        "sample_value": all_changes.get(list(all_changes.keys())[0]) if all_changes and len(all_changes) > 0 else "None"
                    })
                    
                    # Show grid options context
                    st.write("### Grid Options Context")
                    st.json({
                        "context_exists": "context" in grid_options,
                        "changes_in_context": "changes" in grid_options.get("context", {})
                    })
    

    def _build_aggrid_options(self, df, market_dict, changes=None):
        """Build AgGrid options with properly grouped headers and animation settings"""
        if df.empty:
            return None
            
        # Get column definitions with hierarchical structure
        column_defs = self._build_hierarchical_columns(df, market_dict, changes)

        if st.session_state.get('debug_mode', False) and changes:
            print(f"Passing {len(changes)} changes to AgGrid")
            if changes:
                first_key = list(changes.keys())[0]
                print(f"Sample change key: {first_key}")
                print(f"Sample change value: {changes[first_key]}")
        
        # Enhanced cell click handler with better parsing and tracking
        cell_clicked_jscode = JsCode("""
            function(params) {
                // Only handle clicks on odd cells (with market|bookmaker|selection format)
                const colId = params.column.colId;
                if (!colId.includes('|')) return;
                
                // Extract the components from the column ID
                const parts = colId.split('|');
                if (parts.length !== 3) return;
                
                const [market_id, bookmaker, selection] = parts;
                
                // Get fixture_id from the row data
                const fixture_id = params.data.fixture_id;
                
                // Log for debugging
                console.log("Cell clicked:", colId, params.value);
                
                // Store the clicked information in the row data
                params.node.setDataValue('_clicked_column', colId);
                params.node.setDataValue('_clicked_fixture_id', fixture_id);
                params.node.setDataValue('_clicked_market_id', market_id);
                params.node.setDataValue('_clicked_bookmaker', bookmaker);
                params.node.setDataValue('_clicked_selection', selection);
                
                // IMPORTANT: Explicitly select the row to ensure it appears in selected_rows
                params.node.setSelected(true);
                
                // Force refresh the UI to update the data
                params.api.refreshCells({ force: true });
            }
        """)
        
        # Create grid options with explicit animation settings
        grid_options = {
            "columnDefs": column_defs,
            "defaultColDef": {
                "resizable": True,
                "sortable": True,
                "filter": True,
                "minWidth": 80,
                "enableCellChangeFlash": True,  # Enable cell flashing on value changes
                "animateRows": True  # Enable row animations
            },
            "onCellClicked": cell_clicked_jscode,
            "rowSelection": "single",
            "suppressMenuHide": True,
            "suppressMovableColumns": False,
            "suppressClickEdit": True,
            # Very important - Pass changes to the grid context for the cellStyle function
            "context": {
                "changes": changes if changes else {}
            },
            # Configure value change animation settings
            "getRowId": JsCode("""
                function(params) {
                    // Use fixture_id as the unique key for rows
                    return params.data.fixture_id;
                }
            """),
            # Enhanced animation settings
            "valueChangeAnimation": True,  # Enable value change animations
            "animateRows": True,  # Animate rows when their position changes (sorting)
            "columnState": [
                {"colId": "date", "width": 150, "pinned": "left", "hide": False},
                {"colId": "match", "width": 200, "pinned": "left", "hide": False}
            ],
            "sideBar": {
                "toolPanels": [
                    {
                        "id": "columns",
                        "labelDefault": "Columns",
                        "labelKey": "columns",
                        "iconKey": "columns",
                        "toolPanel": "agColumnsToolPanel",
                        "toolPanelParams": {
                            "suppressRowGroups": True,
                            "suppressValues": True,
                            "suppressPivots": True,
                            "suppressPivotMode": True
                        }
                    }
                ],
                "defaultToolPanel": ""
            }
        }
        
        return grid_options

    @st.dialog("Odds Trend Visualization", width="large")
    def show_trend_dialog(self):
        """Show a modal dialog with the trend chart."""
        if not st.session_state.dialog_should_show:
            # Early exit if dialog shouldn't be shown
            return
            
        if not st.session_state.selected_fixture:
            st.error("No selection data available")
            st.session_state.dialog_should_show = False
            return
                
        fixture_id = st.session_state.selected_fixture
        market_id = st.session_state.selected_market
        selection = st.session_state.selected_selection
        bookmaker = st.session_state.selected_bookmaker
        
        # Get market name
        market_name = self._get_market_name(market_id)
        
        # Add header with information
        st.header(f"{market_name}: {selection}")
        st.subheader(f"Bookmaker: {bookmaker}")
        
        # Create the trend chart
        self._create_trend_chart(fixture_id, market_id, selection, bookmaker)
        
        # Show match details if available
        match_details = self._get_match_details(fixture_id)
        if match_details:
            st.markdown(f"**Match:** {match_details.get('home_team', '')} vs {match_details.get('away_team', '')}")
            st.markdown(f"**Date:** {match_details.get('date', '')}")
            
        # Raw data in expander
        with st.expander("View Data"):
            history_df = self._get_odds_history(fixture_id, market_id, selection, bookmaker)
            if not history_df.empty:
                # Format the timestamp
                display_df = history_df.copy()
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(display_df)
                
                # Summary stats
                if len(display_df) >= 2:
                    st.markdown("### Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Average", f"{display_df['odd'].mean():.2f}")
                    with col2:
                        st.metric("Min", f"{display_df['odd'].min():.2f}")
                    with col3:
                        st.metric("Max", f"{display_df['odd'].max():.2f}")
                    with col4:
                        # Calculate change
                        first_value = display_df.iloc[0]['odd']
                        last_value = display_df.iloc[-1]['odd']
                        change = last_value - first_value
                        st.metric("Change", f"{change:.2f}")
        
        # Add a close button with callback
        st.button("Close", key="dialog_close_btn", on_click=self._close_dialog_callback)




    def _create_trend_chart(self, fixture_id, market_id, selection, bookmaker=None):
        """Create and display trend chart for odds movement."""
        # Get historical data
        history_df = self._get_odds_history(fixture_id, market_id, selection, bookmaker)
        
        if history_df.empty:
            st.info("No historical odds data available for this selection.")
            return
            
        # Create Plotly chart
        fig = px.line(
            history_df, 
            x='timestamp', 
            y='odd',
            markers=True,
            title=f"Odds Movement Over Time"
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
            hovertemplate='<b>%{y:.2f}</b><br>%{x}<br>Bookmaker: ' + bookmaker
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

    def _get_match_details(self, fixture_id):
        """Get match details for the given fixture ID."""
        try:
            from src.backend.dynamodb.oddsdb import fetch_odds_for_matches
            
            # Get data for this fixture
            df = fetch_odds_for_matches([fixture_id])
            
            if df.empty:
                return None
                
            # Extract match details
            match_row = df.iloc[0]
            match_details = {
                'home_team': match_row.get('home_team', 'Unknown'),
                'away_team': match_row.get('away_team', 'Unknown'),
                'date': match_row.get('fixture_date', '')
            }
            
            # Format date if needed
            if match_details['date']:
                try:
                    date_str = datetime.fromisoformat(str(match_details['date']).replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                    match_details['date'] = date_str
                except (ValueError, TypeError):
                    pass
                    
            return match_details
        except Exception as e:
            st.error(f"Error fetching match details: {str(e)}")
            return None
        




    def _get_market_name(self, market_id):
        """Get the market name from the market ID."""
        if 'MAIN_MARKETS' in st.session_state and market_id in st.session_state.MAIN_MARKETS:
            return st.session_state.MAIN_MARKETS[market_id]
        elif 'SECONDARY_MARKETS' in st.session_state and market_id in st.session_state.SECONDARY_MARKETS:
            return st.session_state.SECONDARY_MARKETS[market_id]
        return f"Market {market_id}"

    def _get_odds_history(self, fixture_id, market_id, selection, bookmaker=None):
        """Fetch odds history from DynamoDB for trend visualization."""
        try:
            # Get historical data using our dummy data generator function
            history_data = fetch_odds_history_for_graph(
                fixture_id=fixture_id,
                market_id=market_id, 
                selection=selection,
                bookmaker=bookmaker
            )
            
            # Convert to DataFrame for plotting
            if history_data:
                df = pd.DataFrame(history_data)
                # Ensure timestamp is datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                return df
            
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error fetching odds history: {str(e)}")
            return pd.DataFrame()
