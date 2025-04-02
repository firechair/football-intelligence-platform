# web_langchain.py
import os
import requests
from langchain_community.tools.you import YouSearchTool
from langchain_community.utilities.you import YouSearchAPIWrapper


# Ensure your You.com API key is set; this will use the value from your environment if available
os.environ["YDC_API_KEY"] = os.getenv("YDC_API_KEY", "REDACTED")

def langchain_web_search(query, num_results=1):
    """
    Uses the LangChain You.com search tool to retrieve web results.
    """
    # Initialize the API wrapper with desired settings
    api_wrapper = YouSearchAPIWrapper(num_web_results=num_results)
    search_tool = YouSearchTool(api_wrapper=api_wrapper)
    
    # Invoke the tool; this returns a list of Document objects
    documents = search_tool.invoke(query)
    
    # Combine the results into a snippet for your prompt.
    combined_snippet = ""
    for doc in documents:
        title = doc.metadata.get("title", "No Title")
        url = doc.metadata.get("url", "")
        snippet = doc.page_content[:500]  # Adjust the snippet length as needed
        combined_snippet += f"Title: {title}\nSnippet: {snippet}\nURL: {url}\n\n"
    
    return combined_snippet if combined_snippet.strip() else "No search results found."

def you_news(query, count=5, offset=0, country="US", search_lang="en", ui_lang="en-US",
             safesearch="moderate", spellcheck=True, recency="day"):
    """
    Calls the You.com News API to retrieve news results.
    """
    api_key = os.environ.get("YDC_API_KEY")
    if not api_key:
        raise ValueError("YDC_API_KEY not set in environment variables")
    
    url = "https://chat-api.you.com/news"
    headers = {"X-API-Key": api_key}
    params = {
        "query": query,
        "count": count,
        "offset": offset,
        "country": country,
        "search_lang": search_lang,
        "ui_lang": ui_lang,
        "safesearch": safesearch,
        "spellcheck": spellcheck,
        "recency": recency
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    
    news_results = data.get("news", {}).get("results", [])
    if not news_results:
        return "No news results found."
    
    combined_news = ""
    for result in news_results:
        title = result.get("title", "No Title")
        description = result.get("description", "")
        url_result = result.get("url", "")
        combined_news += f"Title: {title}\nDescription: {description}\nURL: {url_result}\n\n"
    
    return combined_news


def get_serie_a_schedule_snippet():
    """
    Fetch upcoming Serie A fixtures from the aggregator (league_id=135, season=2024).
    Return a textual snippet listing them.
    """
    from .predizioni import get_all_upcoming_fixtures  # adjust import path as needed
    
    fixtures = get_all_upcoming_fixtures(league_id=135, season=2024, n=10)
    if not fixtures:
        return "Non sono disponibili informazioni sulle prossime partite di Serie A."
    
    lines = ["Ecco le prossime partite di Serie A:"]
    for fx in fixtures:
        # Example date: '2025-02-14T19:45:00+00:00'. We can format it:
        date_str = fx['date_utc'].split('T')[0]  # '2025-02-14'
        lines.append(f"- {date_str}: {fx['home_team']} vs {fx['away_team']}")
    return "\n".join(lines)