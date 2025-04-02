# src/backend/database.py
import sqlite3
from datetime import datetime

class DatabaseHandler:
    def __init__(self):
        self.conn = sqlite3.connect('chatbot.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Create chats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats (chat_id)
            )
        ''')

        # Create API usage table to track queries per month
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage (
                month TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        ''')

        self.conn.commit()

    def get_all_chats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT chat_id, chat_name FROM chats ORDER BY created_at DESC')
        return cursor.fetchall()

    def create_new_chat(self, chat_name="New Chat"):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO chats (chat_name) VALUES (?)', (chat_name,))
        chat_id = cursor.lastrowid
        
        # Add system message with betting and graph instructions
        system_message = """Sei un assistente esperto in scommesse sportive e analisi di calcio.

        Puoi aiutare l'utente con:
        1. Analisi dettagliate delle statistiche sulle partite
        2. Informazioni sulle forme attuali delle squadre e le loro prestazioni 
        3. Consigli sulle scommesse basati sui dati disponibili
        4. Previsioni sui risultati delle partite
        5. Informazioni su infortunati e giocatori non disponibili

        Esempi di richieste di grafico:
        - "Mostrami il grafico delle quote per l'1 di Inter vs Milan"
        - "Voglio vedere l'andamento delle quote per Over 2.5 in Juventus vs Roma"
        - "Fammi vedere come sono cambiate le quote del pareggio in Napoli vs Lazio"
        - "Ci sono infortunati per la partita Lazio Udinese?"
        - "Chi sono i giocatori indisponibili per la Roma?"

        Utilizza dati storici e recenti per fornire analisi accurate e utili per le scommesse."""
        
        # Add system message to the new chat
        self.add_message(chat_id, "system", system_message)
        
        self.conn.commit()
        return chat_id

    def delete_chat(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
        cursor.execute('DELETE FROM chats WHERE chat_id = ?', (chat_id,))
        self.conn.commit()

    def get_chat_messages(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT role, content FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp
        ''', (chat_id,))
        return cursor.fetchall()

    def add_message(self, chat_id, role, content):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO messages (chat_id, role, content)
            VALUES (?, ?, ?)
        ''', (chat_id, role, content))
        self.conn.commit()

    def get_chat_message_count(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
        return cursor.fetchone()[0]

    def get_last_message(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT content FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (chat_id,))
        result = cursor.fetchone()
        return result[0] if result else "No messages"

    # === NEW RENAME METHOD ===
    def rename_chat(self, chat_id, new_chat_name):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE chats
            SET chat_name = ?
            WHERE chat_id = ?
        ''', (new_chat_name, chat_id))
        self.conn.commit()

    def get_api_usage(self):
        """Returns the number of API queries made in the current month."""
        current_month = datetime.now().strftime("%Y-%m")
        cursor = self.conn.cursor()
        cursor.execute("SELECT count FROM api_usage WHERE month = ?", (current_month,))
        result = cursor.fetchone()
        if result is None:
            # Insert a new record if none exists for the current month
            cursor.execute("INSERT INTO api_usage (month, count) VALUES (?, ?)", (current_month, 0))
            self.conn.commit()
            return 0
        return result[0]

    def increment_api_usage(self, increment=1):
        """Increments the API usage counter by a given value."""
        current_month = datetime.now().strftime("%Y-%m")
        current_count = self.get_api_usage()
        new_count = current_count + increment
        cursor = self.conn.cursor()
        cursor.execute("UPDATE api_usage SET count = ? WHERE month = ?", (new_count, current_month))
        self.conn.commit()
    

    def ensure_system_message(self, chat_id):
        """Check if chat has a system message and add one if not"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = "system"', (chat_id,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            # No system message found, add one
            system_message = """Sei un assistente esperto in scommesse sportive e analisi di calcio.

            Puoi aiutare l'utente con:
            1. Analisi dettagliate delle statistiche sulle partite
            2. Informazioni sulle forme attuali delle squadre e le loro prestazioni 
            3. Consigli sulle scommesse basati sui dati disponibili
            4. Previsioni sui risultati delle partite

            Esempi di richieste di grafico:
            - "Mostrami il grafico delle quote per l'1 di Inter vs Milan"
            - "Voglio vedere l'andamento delle quote per Over 2.5 in Juventus vs Roma"
            - "Fammi vedere come sono cambiate le quote del pareggio in Napoli vs Lazio"

            Utilizza dati storici e recenti per fornire analisi accurate e utili per le scommesse."""
            
            self.add_message(chat_id, "system", system_message)
            return True
        
        return False

    def __del__(self):
        try:
            self.conn.close()
        except:
            pass
