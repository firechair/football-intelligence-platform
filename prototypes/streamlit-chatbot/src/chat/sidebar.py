# src/chat/sidebar.py
import streamlit as st
from ..backend.database import DatabaseHandler

class Sidebar:
    def __init__(self):
        self.db = DatabaseHandler()

    def render(self):
        st.header("Gestisci le tue conversazioni")

        # New chat button
        if st.button("➕ New Chat"):
            new_chat_id = self.db.create_new_chat()
            st.session_state.current_chat_id = new_chat_id
            system_prompt = (
                "Sei un esperto di calcio"
                "Rispondi sempre in modo cordiale e professionale, utilizza il linguaggio Italiano"
                "Analizza sempre i dati che ti vengono forniti per rispondere sempre in maniera accurata"
            )
            self.db.add_message(new_chat_id, "system", system_prompt)
            # === end system message insertion ===

            st.rerun()

        st.markdown("---")

        # List existing chats
        try:
            chats = self.db.get_all_chats()
            if not chats:
                st.info("Non ci sono chat. Creane una per iniziare!")
                return

            for chat in chats:
                chat_id, chat_name = chat
                msg_count = self.db.get_chat_message_count(chat_id)

                col1, col2, col3 = st.columns([4, 1, 1])

                with col1:
                    if st.button(f"{chat_name} (📝 {msg_count})", key=f"chat_{chat_id}"):
                        st.session_state.current_chat_id = chat_id
                        st.rerun()

                # Rename button
                with col2:
                    if st.button("✏️", key=f"rename_{chat_id}"):
                        # Store which chat we want to rename
                        st.session_state.rename_chat_id = chat_id
                        st.session_state.rename_chat_name = chat_name
                        st.rerun()

                # Delete button
                with col3:
                    if st.button("🗑️", key=f"delete_{chat_id}"):
                        self.db.delete_chat(chat_id)
                        # If we just deleted the current_chat_id, clear it
                        if "current_chat_id" in st.session_state and st.session_state.current_chat_id == chat_id:
                            del st.session_state.current_chat_id
                        st.rerun()

            # After listing all chats, check if we are in "rename mode"
            if "rename_chat_id" in st.session_state:
                st.markdown("---")
                st.subheader("Rename Chat")

                # Text input for the new name
                new_name = st.text_input(
                    "Enter new name:",
                    value=st.session_state.rename_chat_name,  # default old name
                    key="rename_input"  # a stable key
                )

                # "Save" button
                if st.button("Save", key="save_rename"):
                    self.db.rename_chat(
                        st.session_state.rename_chat_id,
                        new_name
                    )
                    # Clear rename state
                    del st.session_state.rename_chat_id
                    del st.session_state.rename_chat_name
                    st.rerun()

                # Optional: "Cancel" button
                if st.button("Cancel", key="cancel_rename"):
                    del st.session_state.rename_chat_id
                    del st.session_state.rename_chat_name
                    st.rerun()

        except Exception as e:
            st.error(f"Error loading chats: {str(e)}")
