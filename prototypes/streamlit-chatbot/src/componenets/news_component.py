# src/components/news_component.py
import streamlit as st
from datetime import datetime, timedelta

class NewsComponent:
    def __init__(self):
        # Initialize session state for news
        if 'news_items' not in st.session_state:
            st.session_state.news_items = [
                {"title": "Match Preview", "content": "Inter Milan vs Juventus: Key players to watch", "timestamp": datetime.now()},
                {"title": "Odds Movement", "content": "Significant shift in Champions League betting odds", "timestamp": datetime.now()},
                {"title": "Betting Insights", "content": "Serie A: Under 2.5 goals market showing value", "timestamp": datetime.now()},
                {"title": "Injury Update", "content": "Star striker doubtful for upcoming fixture", "timestamp": datetime.now()},
            ]
        if 'last_news_fetch' not in st.session_state:
            st.session_state.last_news_fetch = datetime.now()
        
    def fetch_news(self):
        """
        Fetch news from API provider
        Replace this with your actual API call
        """
        # Check if we should fetch new data (e.g., every 2 minutes)
        if (datetime.now() - st.session_state.last_news_fetch).seconds > 120:
            print("[DEBUG] Fetching new news items")
            
            # TODO: Replace this with your actual API call
            # Example of API integration:
            # response = requests.get("https://your-news-api.com/endpoint", headers={"Authorization": "Bearer YOUR_API_KEY"})
            # data = response.json()
            
            # This is a placeholder with dummy data
            dummy_news = [
                {"title": "Match Preview", "content": "Inter Milan vs Juventus: Key players to watch", "timestamp": datetime.now()},
                {"title": "Odds Movement", "content": "Significant shift in Champions League betting odds", "timestamp": datetime.now()},
                {"title": "Betting Insights", "content": "Serie A: Under 2.5 goals market showing value", "timestamp": datetime.now()},
                {"title": "Injury Update", "content": "Star striker doubtful for upcoming fixture", "timestamp": datetime.now()},
            ]
            
            # Update session state
            st.session_state.news_items = dummy_news
            st.session_state.last_news_fetch = datetime.now()
        
        return st.session_state.news_items
    
    def display_news_window(self):
        """Display news using Streamlit native components"""
        # Simple header
        st.subheader("📰 Latest News")
        
        # Create a container with fixed height for scrolling
        news_container = st.container(height=300)
        
        # Fetch news
        news_items = self.fetch_news()
        
        # Display news items in the container
        with news_container:
            if not news_items:
                st.info("No news available at the moment.")
            else:
                for news in news_items:
                    # Create a container for each news item
                    with st.container():
                        # Format time
                        time_str = news["timestamp"].strftime("%H:%M")
                        
                        # Title with bold
                        st.markdown(f"**{news['title']}**")
                        
                        # Content
                        st.write(news["content"])
                        
                        # Time with small font
                        st.markdown(f"<small style='text-align: right; display: block; color: #888;'>{time_str}</small>", unsafe_allow_html=True)
                        
                        # Add a separator
                        st.divider()
        
        # Add a refresh button
        if st.button("Refresh News", use_container_width=True):
            # Force immediate refresh
            st.session_state.last_news_fetch = datetime.now() - timedelta(minutes=10)
            st.rerun()

# Function to be called from main app
def display_news():
    news_component = NewsComponent()
    news_component.display_news_window()