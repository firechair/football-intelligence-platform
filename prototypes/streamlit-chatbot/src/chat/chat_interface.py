# src/chat/chat_interface.py
import streamlit as st
from ..backend.handler import LLMHandler
from ..backend.database import DatabaseHandler
from ..backend.web_langchain import get_serie_a_schedule_snippet, langchain_web_search, you_news
from ..backend.predizioni import get_prediction_for_query, get_raw_prediction_json
from .odds_graph_handler import OddsGraphHandler

from ..backend.soccer_stats_integration import process_soccer_json, build_soccer_stats_prompt
from ..backend.lineup_integration import is_lineup_query, get_lineup_for_query, process_lineup_json, generate_lineup_response
from ..backend.injuries_integration import is_injuries_query, get_injuries_for_query, process_injuries_json, generate_injuries_response
import time
import json
import traceback  # For detailed error logging

def build_conversation_prompt(messages, raw_json_data=None, form_query=False):
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
    
    # Add raw JSON data if available
    if raw_json_data:
        # Add this section to convert the raw JSON to a more specific instruction
        try:
            # Parse the JSON to extract team names
            import json
            data = json.loads(raw_json_data)
            response = data.get('response', [])
            if response and len(response) > 0:
                prediction_data = response[0]
                teams = prediction_data.get('teams', {})
                home_team = teams.get('home', {}).get('name', 'la squadra di casa')
                away_team = teams.get('away', {}).get('name', 'la squadra ospite')
                
                # Enhanced instruction for form queries
                if form_query:
                    specific_instruction = (
                        f"IMPORTANTE: L'utente ha chiesto informazioni sulle statistiche e curve di forma di {home_team} e {away_team}. "
                        f"Devi analizzare il JSON grezzo qui sotto per estrarre e presentare un'analisi dettagliata delle statistiche di forma. "
                        f"Concentrati in particolare su:\n\n"
                        f"1. La percentuale di forma per entrambe le squadre (`teams.home.last_5.form` e `teams.away.last_5.form`)\n"
                        f"2. Statistiche di attacco e difesa (`teams.*.last_5.att`, `teams.*.last_5.def`)\n"
                        f"3. Gol segnati e subiti negli ultimi 5 incontri (`teams.*.last_5.goals.*`)\n"
                        f"4. Le sequenze di partite recenti e serie di risultati (`teams.*.league.form`)\n"
                        f"5. Confronto diretto statistico tra le squadre (`comparison.*`)\n\n"
                        f"Interpreta le sequenze di forma come: W=vittoria, D=pareggio, L=sconfitta, leggendo da sinistra a destra (più recente a meno recente).\n"
                        f"Valuta e commenta lo stato di forma attuale, evidenziando punti di forza e debolezza di ciascuna squadra.\n"
                        f"Usa un tono esperto e analitico. NON INVENTARE statistiche non presenti nel JSON."
                    )
                else:
                    # Standard instruction for other football queries
                    specific_instruction = (
                        f"IMPORTANTE: L'utente ha chiesto informazioni sulla partita {home_team} vs {away_team}. "
                        f"Devi utilizzare SOLO i dati forniti nel JSON qui sotto. NON INVENTARE statistiche o informazioni. "
                        f"Quando l'utente chiede di statistiche e curve di forma, metti in evidenza: "
                        f"1. La percentuale di forma (`last_5.form`) e statistiche attacco/difesa (`last_5.att`, `last_5.def`) "
                        f"2. Le percentuali di confronto tra squadre (`comparison.*`) "
                        f"3. Tendenze di gol e prestazioni recenti (`last_5.goals.*`) "
                        f"NON parlare di quote o andamento quote a meno che non venga esplicitamente richiesto dall'utente."
                    )
            else:
                specific_instruction = (
                    "IMPORTANTE: Utilizza SOLO i dati forniti nel JSON qui sotto per rispondere all'utente. "
                    "NON INVENTARE statistiche o informazioni. Se un'informazione non è presente nei dati, "
                    "indica chiaramente che non è disponibile."
                )
        except Exception as e:
            print(f"[DEBUG] Error in build_conversation_prompt: {str(e)}")
            specific_instruction = (
                "IMPORTANTE: Utilizza SOLO i dati forniti nel JSON qui sotto per rispondere all'utente. "
                "NON INVENTARE statistiche o informazioni."
            )
        
        convo += (
            "<|im_start|>system\n"
            f"{specific_instruction}\n\n"
            "Ecco i dati delle previsioni calcistiche in formato JSON grezzo. "
            "Usa questi dati per rispondere accuratamente alle domande dell'utente:\n\n"
            f"```json\n{raw_json_data}\n```\n"
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
                "Ecco alcuni dati dal web che potrebbero essere incompleti o obsoleti:\n"
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

    # Finally, open an assistant block to prompt the model for a new reply
    convo += "<|im_start|>assistant\n"
    return convo

def is_football_query(query):
    """Check if query is related to football predictions or statistics"""
    # FIRST - Check if this is a graph request, if so it's NOT a football query
    graph_keywords = [
        'grafico quote', 'andamento quota', 'andamento delle quote', 
        'trend quota', 'storico quote', 'mostra grafico'
    ]

    if is_lineup_query(query):
        print(f"[DEBUG] Query is a lineup query - not treating as regular football query")
        return False
    
    query_lower = query.lower()
    
    # If it contains graph-related terms, don't handle as football query
    if any(keyword in query_lower for keyword in graph_keywords):
        print(f"[DEBUG] Query contains graph keywords - not treating as football query")
        return False
    
    # Only check for football keywords if it's not a graph request
    keywords = [
        'partita', 'squadra', 'calcio', 'serie a', 'pronostico', 'previsioni',
        'statistiche', 'forme', 'incontri', 'vittoria', 'sconfitta', 'pareggio',
        'gol', 'risultato', 'scommesse', 'vs', 'contro'
    ]
    
    return any(keyword in query_lower for keyword in keywords)

class ChatInterface:
    def __init__(self):
        if 'llm_handler' not in st.session_state:
            st.session_state.llm_handler = LLMHandler()
        self.llm_handler = st.session_state.llm_handler
        self.db = DatabaseHandler()
        self.graph_handler = OddsGraphHandler()
        
        # Always initialize a fresh cache for each new session
        # This ensures we don't use stale data between sessions
        if 'session_initialized' in st.session_state and st.session_state.session_initialized:
            st.session_state.json_data_cache = None
            st.session_state.json_timestamp = None
            st.session_state.json_query = None

    def get_prediction_json(self, query):
        print(f"\n[DEBUG] Processing query for prediction: '{query}'")        
        # Always get fresh data for each query to avoid cache issues
        with st.spinner("Recupero i dati delle previsioni calcistiche..."):
            print(f"[DEBUG] Calling get_prediction_for_query")
            json_data = get_prediction_for_query(query)
            # Add this to see if the data looks valid
            if json_data:
                print(f"[DEBUG] JSON data preview (first 200 chars): {json_data[:200]}...")
            else:
                print(f"[DEBUG] No JSON data returned!")
        
        return json_data

    def render(self):
        """Render the chat interface with improved layout and logical flow"""

        if 'MAIN_MARKETS' in st.session_state and 'SECONDARY_MARKETS' in st.session_state:
            print(f"[DEBUG] Setting market dictionaries on graph handler")
            self.graph_handler.set_market_dictionaries(
                st.session_state.MAIN_MARKETS,
                st.session_state.SECONDARY_MARKETS
            )
        if 'current_chat_id' not in st.session_state:
            st.info("Seleziona o crea una nuova chat")
            return

        # Ensure system message
        self.db.ensure_system_message(st.session_state.current_chat_id)
        
        # Create a container for the entire chat area to maintain structure
        chat_container = st.container()
        
        with chat_container:
            # 1) Display existing messages (user and assistant only)
            messages = self.db.get_chat_messages(st.session_state.current_chat_id)
            for role, content in messages:
                if role in ("user", "assistant"):
                    with st.chat_message(role):
                        st.write(content)
        
            # 2) ADD HELPER MESSAGE - consistently positioned after the messages
            st.markdown("""
            <div style="font-size: 0.9em; margin: 15px 0; padding: 8px; border-radius: 4px; 
                background-color: #1e293b; border: 1px solid #3a506b; color: #e2e8f0;">
            💡 <b>Tip:</b> Puoi chiedere "<span style="color: #fbbf24;">Mostrami il grafico delle quote per 1X2 in Inter vs Milan</span>" 
            per vedere l'andamento delle quote.
            </div>
            """, unsafe_allow_html=True)
            
            # 3) Checkboxes to choose online search and/or news retrieval (reduced to 2 columns)
            col1, col2 = st.columns(2)
            with col1:
                use_online_search = st.checkbox("Use online search for the next message")
            with col2:
                use_online_news = st.checkbox("Use online news for the next message")

        # 4) Chat input (outside the container to maintain sticky behavior)
        user_input = st.chat_input("What's on your mind?")

        if user_input:
            print(f"[DEBUG] Processing user input: '{user_input}'")

            # Clear any cached data to prevent hallucinations between queries
            if 'json_data_cache' in st.session_state:
                st.session_state.json_data_cache = None
            if 'json_timestamp' in st.session_state:
                st.session_state.json_timestamp = None
            if 'json_query' in st.session_state:
                st.session_state.json_query = None

            is_graph = self.graph_handler.is_graph_request(user_input)
            print(f"[DEBUG] Is graph request: {is_graph}")
            # Check if this is a graph request
            if is_graph:
                try:
                    print(f"[DEBUG] Processing as graph request: '{user_input}'")
                    params, response = self.graph_handler.handle_graph_request(user_input)
                    
                    # Add the user message to the database
                    self.db.add_message(st.session_state.current_chat_id, "user", user_input)
                    
                    # Display the user message in the UI
                    with st.chat_message("user"):
                        st.write(user_input)
                    
                    # Add the assistant's response to the database
                    self.db.add_message(st.session_state.current_chat_id, "assistant", response)
                    
                    # Display the assistant's response in the UI
                    with st.chat_message("assistant"):
                        st.write(response)
                    
                    if params and params['fixture_id']:
                        # Reset dialog_shown to ensure dialog appears
                        st.session_state.dialog_shown = False
                        
                        # Set required parameters
                        st.session_state.selected_fixture = params['fixture_id']
                        st.session_state.selected_market = params['market_id']
                        st.session_state.selected_selection = params['selection']
                        st.session_state.selected_bookmaker = params['bookmaker']
                        st.session_state.show_trend_popup = True
                        
                        # Trigger a rerun to show the dialog
                        time.sleep(0.5)  # Small delay to ensure UI updates
                        st.rerun()
                    
                    return  # Exit the method after processing
                except Exception as e:
                    print(f"[DEBUG] Error processing graph request: {str(e)}")
                    print(traceback.format_exc())
                    st.error(f"Error processing graph request: {str(e)}")
            
            # Regular message processing
            # (A) Save the user's message in the database
            self.db.add_message(st.session_state.current_chat_id, "user", user_input)

            # (B) Display the user's message in the UI
            with st.chat_message("user"):
                st.write(user_input)

            # (C) If online search/news is enabled, get a snippet
            if use_online_search or use_online_news:
                snippet = ""
                with st.spinner('Searching the web...'):
                    # Special handling for Serie A upcoming matches
                    if "prossime partite" in user_input.lower() and "serie a" in user_input.lower():
                        snippet = get_serie_a_schedule_snippet()
                    else:
                        # Depending on which checkbox is selected, call the appropriate function.
                        if use_online_news:
                            snippet = you_news(user_input, count=3)
                        elif use_online_search:
                            snippet = langchain_web_search(user_input, num_results=4)
                if snippet.strip():
                    self.db.add_message(
                        st.session_state.current_chat_id,
                        "snippet",
                        snippet
                    )
                    self.db.increment_api_usage()

            # (D) Re-fetch messages (including the new user message and snippet)
            updated_messages = self.db.get_chat_messages(st.session_state.current_chat_id)

            raw_json = None
            flat_text_data = None
            key_stats = None
            team_names = None
            full_prompt = None
            
            
            # 1. FIRST CHECK: Injury queries - process before lineup queries
            if is_injuries_query(user_input):
                print(f"[DEBUG] Processing as injuries query: '{user_input}'")
                from ..backend.predizioni import extract_teams_from_query
                home_team, away_team = extract_teams_from_query(user_input)
                team_str = f"{home_team} e {away_team}" if home_team and away_team else "le squadre richieste"
                
                # We've already saved and displayed the user message above, no need to do it again
                
                with st.spinner("Recupero i dati sugli infortunati..."):
                    raw_json = get_injuries_for_query(user_input)
                print(f"[DEBUG] Raw injuries JSON obtained: {'Yes' if raw_json else 'No'}")
                
                if raw_json:
                    try:
                        # Process the injuries JSON data
                        flat_text_data, key_stats, team_names = process_injuries_json(raw_json)
                        print(f"[DEBUG] Processed injuries data. Team names: {team_names}")
                        print(f"[DEBUG] Key info preview: {key_stats[:200]}...")
                        
                        # Generate templated response for injuries data
                        response = generate_injuries_response(team_names, key_stats, flat_text_data, query=user_input)
                        
                        # Add the generated response to the database and display it
                        self.db.add_message(st.session_state.current_chat_id, "assistant", response)
                        
                        # Display the response in the UI
                        with st.chat_message("assistant"):
                            st.write(response)
                            
                            # Display debug info if needed
                            with st.expander("Injuries Data (Debug)", expanded=False):
                                st.subheader("Injuries Data")
                                
                                if st.button("Show Exact Data Used", key="show_injuries_data"):
                                    st.subheader("Team Names")
                                    st.text(f"{', '.join(team_names)}")
                                    
                                    st.subheader("Generated Response")
                                    st.text(response)
                                    
                                    st.subheader("Extracted Key Information")
                                    st.text(key_stats)
                                    
                                    st.subheader("Full Flat Text Data")
                                    st.text(flat_text_data[:2000] + "..." if len(flat_text_data) > 2000 else flat_text_data)
                                    
                                    st.subheader("Raw Data Sample")
                                    try:
                                        sample_json = json.loads(raw_json)
                                        if 'response' in sample_json and len(sample_json['response']) > 0:
                                            sample = sample_json['response'][0]
                                            st.json(sample, expanded=False)
                                    except:
                                        st.text("Could not parse JSON for preview")
                        
                        # Clean any cached data to avoid leakage between queries
                        if 'json_data_cache' in st.session_state:
                            st.session_state.json_data_cache = None
                        if 'json_timestamp' in st.session_state:
                            st.session_state.json_timestamp = None
                        if 'json_query' in st.session_state:
                            st.session_state.json_query = None
                        
                        # EXIT EARLY - skip the rest of the method since we've handled the response
                        return
                        
                    except Exception as e:
                        print(f"[DEBUG] Error in injuries data processing: {str(e)}")
                        print(traceback.format_exc())
                        # Continue with normal flow but add a warning message
                        full_prompt = build_conversation_prompt(updated_messages, None)
                        full_prompt = full_prompt.replace("<|im_start|>assistant\n", 
                            f"<|im_start|>system\nNon ho potuto elaborare correttamente i dati degli infortunati a causa di un errore: {str(e)}. Non inventare dettagli.\n<|im_end|>\n<|im_start|>assistant\n")
                else:
                    # No JSON data available - special no-data instruction for injuries queries
                    print(f"[DEBUG] No injuries data found - using direct template response")
                    
                    # Create a simple "no data" response
                    response = f"Mi dispiace, non ho trovato dati sugli infortunati per {team_str}. Potrebbe essere che non ci siano infortunati segnalati o che i dati non siano disponibili per queste squadre."
                    
                    # Add the generated response to the database (user message already added above)
                    self.db.add_message(st.session_state.current_chat_id, "assistant", response)
                    
                    # Display the response in the UI
                    with st.chat_message("assistant"):
                        st.write(response)
                    
                    # EXIT EARLY - skip the rest of the method since we've handled the response
                    return
            
            # 2. SECOND CHECK: Lineup queries (only if not an injury query)
            elif is_lineup_query(user_input):
                print(f"[DEBUG] Processing as lineup query: '{user_input}'")
                from ..backend.predizioni import extract_teams_from_query
                home_team, away_team = extract_teams_from_query(user_input)
                team_str = f"{home_team} e {away_team}" if home_team and away_team else "le squadre richieste"
                
                # We've already saved and displayed the user message above, no need to do it again
                
                with st.spinner("Recupero i dati delle formazioni..."):
                    raw_json = get_lineup_for_query(user_input)
                print(f"[DEBUG] Raw lineup JSON obtained: {'Yes' if raw_json else 'No'}")
                
                if raw_json:
                    try:
                        # Process the lineup JSON data
                        flat_text_data, key_stats, team_names = process_lineup_json(raw_json)
                        print(f"[DEBUG] Processed lineup data. Team names: {team_names}")
                        print(f"[DEBUG] Key info preview: {key_stats[:200]}...")
                        
                        # CHANGE: Skip LLM completely and use our template generator
                        print(f"[DEBUG] Generating templated response for lineup data")
                        
                        # Add note about substitution data limitations
                        response = generate_lineup_response(team_names, key_stats, flat_text_data)
                        
                        # Add clarification about substitutions if query asks about them
                        if any(term in user_input.lower() for term in ["sostitu", "cambi", "entrati", "usciti", "subentra", "in panchina"]):
                            response += "\n\n**Nota:** Non ho informazioni sulle sostituzioni effettuate durante la partita. Questi dati mostrano solo la formazione iniziale e i giocatori in panchina, non i cambi avvenuti durante l'incontro."
                        
                        # Add the generated response to the database and display it
                        # (no need to add the user message again)
                        self.db.add_message(st.session_state.current_chat_id, "assistant", response)
                        
                        # Display the response in the UI
                        with st.chat_message("assistant"):
                            st.write(response)
                            
                            # Display debug info
                            with st.expander("Soccer Data (Debug)", expanded=False):
                                st.subheader("Lineup Data")
                                
                                # Add a button to show the exact data we used
                                if st.button("Show Exact Data Used", key="show_data"):
                                    st.subheader("Team Names")
                                    st.text(f"{', '.join(team_names)}")
                                    
                                    st.subheader("Generated Response")
                                    st.text(response)
                                    
                                    st.subheader("Extracted Key Information")
                                    st.text(key_stats)
                                    
                                    st.subheader("Full Flat Text Data")
                                    st.text(flat_text_data[:2000] + "..." if len(flat_text_data) > 2000 else flat_text_data)
                        
                        # Store data in session state for debugging
                        st.session_state.lineup_data = {
                            'team_names': team_names,
                            'key_stats': key_stats,
                            'flat_text_data': flat_text_data,
                            'generated_response': response
                        }
                        
                        # EXIT EARLY - skip the rest of the method since we've handled the response
                        return
                        
                    except Exception as e:
                        print(f"[DEBUG] Error in lineup data processing: {str(e)}")
                        print(traceback.format_exc())
                        # Continue with normal flow but add a warning message
                        full_prompt = build_conversation_prompt(updated_messages, None)
                        full_prompt = full_prompt.replace("<|im_start|>assistant\n", 
                            f"<|im_start|>system\nNon ho potuto elaborare correttamente i dati delle formazioni a causa di un errore: {str(e)}. Non inventare dettagli.\n<|im_end|>\n<|im_start|>assistant\n")
                else:
                    # No JSON data available - special no-data instruction for lineup queries
                    print(f"[DEBUG] No lineup data found - using direct template response")
                    
                    # Create a simple "no data" response
                    response = f"Mi dispiace, non ho trovato dati sulle formazioni per la partita tra {team_str}. Verifica che le squadre abbiano effettivamente giocato tra loro nelle stagioni recenti."
                    
                    # Add the generated response to the database (user message already added above)
                    self.db.add_message(st.session_state.current_chat_id, "assistant", response)
                    
                    # Display the response in the UI
                    with st.chat_message("assistant"):
                        st.write(response)
                    
                    # EXIT EARLY - skip the rest of the method since we've handled the response
                    return
            
            # 3. THIRD CHECK: Other football queries
            elif is_football_query(user_input):
                print(f"[DEBUG] Processing as football query: '{user_input}'")
                raw_json = self.get_prediction_json(user_input)
                print(f"[DEBUG] Raw JSON obtained: {'Yes' if raw_json else 'No'}")
                
                # Simple form query detection
                is_form = "statistiche" in user_input.lower() or "forma" in user_input.lower() or "curve" in user_input.lower()
                
                # Always try to use the soccer stats parser for football queries
                if raw_json:
                    print(f"[DEBUG] Using soccer stats parser automatically")
                    try:
                        # Process the JSON data through our specialized pipeline
                        flat_text_data, key_stats, team_names = process_soccer_json(raw_json)
                        print(f"[DEBUG] Processed soccer data. Team names: {team_names}")
                        
                        # Build enhanced prompt with flat text and key stats
                        full_prompt = build_soccer_stats_prompt(
                            updated_messages, 
                            flat_text_data,
                            key_stats,
                            form_query=is_form
                        )
                    except Exception as e:
                        print(f"[DEBUG] Error in soccer stats processing: {str(e)}")
                        print(traceback.format_exc())
                        # Fallback to regular JSON processing
                        full_prompt = build_conversation_prompt(updated_messages, raw_json, form_query=is_form)
                else:
                    # No JSON data available
                    full_prompt = build_conversation_prompt(updated_messages, None)
            else:
                print(f"[DEBUG] Processing as regular message: '{user_input}'")
                # Not a football query
                full_prompt = build_conversation_prompt(updated_messages, None)

            # (F) Get the LLM response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = self.llm_handler.get_response(full_prompt, is_full_prompt=True)
                st.write(response)

                # Display debug info for soccer stats if it was processed
                if flat_text_data and (is_football_query(user_input) or is_lineup_query(user_input)):
                    with st.expander("Soccer Data (Debug)", expanded=False):
                        if is_lineup_query(user_input):
                            st.subheader("Lineup Data")
                            
                            # Add a button to show prompt details
                            if st.button("Show Full Prompt (Debug)", key="show_prompt"):
                                st.text_area("Full Prompt to LLM", full_prompt, height=400)
                                
                            # Add before/after verification
                            if 'lineup_response' not in st.session_state:
                                st.session_state.lineup_response = response
                            
                            if st.button("Verify Lineup Response", key="verify_lineup"):
                                st.subheader("VERIFICATION RESULTS")
                                
                                # Check for specific hallucination patterns
                                hallucination_indicators = [
                                    "sostituito da", "subentrato", "terminata", "risultato", 
                                    "è finita", "finita", "score", "cartellino", "gol", "goal",
                                    "11/03/2024", "marzo 2024", "Sarri", "Cioffi", "Martusciello"
                                ]
                                
                                detected_hallucinations = []
                                for indicator in hallucination_indicators:
                                    if indicator.lower() in response.lower():
                                        detected_hallucinations.append(indicator)
                                
                                if detected_hallucinations:
                                    st.error(f"HALLUCINATION DETECTED! Response contains invented details: {', '.join(detected_hallucinations)}")
                                else:
                                    st.success("No obvious hallucination patterns detected")
                                
                                # Compare coaches in response vs data
                                if "Baroni" not in response and "M. Baroni" in key_stats:
                                    st.warning("COACH MISMATCH: Response doesn't mention coach Baroni who is in the data")
                                if "Runjaić" not in response and "K. Runjaić" in key_stats:
                                    st.warning("COACH MISMATCH: Response doesn't mention coach Runjaić who is in the data")
                                
                                # Check key players
                                if "Provedel" not in response and "Provedel" in flat_text_data:
                                    st.warning("PLAYER MISSING: Response doesn't mention Provedel who is in the data")
                                if "Okoye" not in response and "Okoye" in flat_text_data:
                                    st.warning("PLAYER MISSING: Response doesn't mention Okoye who is in the data")
                        else:
                            st.subheader("Match Data")
                            
                        if team_names:
                            st.subheader("Team Names")
                            if isinstance(team_names, tuple) or isinstance(team_names, list):
                                if len(team_names) >= 2:
                                    st.text(f"Home: {team_names[0]}, Away: {team_names[1]}")
                                else:
                                    st.text(str(team_names))
                            else:
                                st.text(str(team_names))
                        
                        st.subheader("Extracted Key Information")
                        st.text(key_stats)
                        
                        st.subheader("Raw Data Sample")
                        try:
                            sample_json = json.loads(raw_json)
                            if 'response' in sample_json and len(sample_json['response']) > 0:
                                sample = sample_json['response'][0]
                                st.json(sample, expanded=False)
                        except:
                            st.text("Could not parse JSON for preview")
                        
                        st.subheader("Full Flat Text Data")
                        st.text(flat_text_data[:2000] + "..." if len(flat_text_data) > 2000 else flat_text_data)

            # (G) Save the assistant response in the database
            self.db.add_message(st.session_state.current_chat_id, "assistant", response)

