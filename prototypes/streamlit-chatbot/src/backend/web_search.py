# src/backend/web_search.py

import requests
from googlesearch import search
import trafilatura
from bs4 import BeautifulSoup  # only needed if you want to keep google_search as well

def generic_web_search(query, num_results=5):
    """
    1) Perform a Google search for `query`
    2) Fetch each result's HTML
    3) Use Trafilatura to extract main text
    4) Return a combined snippet
    """

    results = []
    # Perform Google search
    for link in search(query, num=num_results, stop=num_results, pause=4):
        results.append(link)

    # Collect text from each link
    extracts = []
    for link in results:
        try:
            # Fetch the page
            response = requests.get(link, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()

            # Extract main content with trafilatura
            extracted_text = trafilatura.extract(response.text, url=link)
            if extracted_text:
                # Optionally limit size to avoid huge prompts
                snippet = extracted_text[:1000]  # e.g., keep first 1000 chars
                # You might want to add link info
                combined_snippet = f"URL: {link}\nContent:\n{snippet}"
                extracts.append(combined_snippet)

        except Exception:
            pass

    if not extracts:
        return "No meaningful text found."

    # Combine everything into one big snippet
    result_text = "\n\n---\n\n".join(extracts)
    return result_text


# OPTIONAL: Keep your old google_search for meta tags
def google_search(query, num_results=5):
    """
    Perform a Google search for `query`.
    Return a short summary of the top results (title, snippet, url).
    """
    results = []
    for link in search(query, num=num_results, stop=num_results, pause=2):
        results.append(link)

    summaries = []
    for link in results:
        try:
            response = requests.get(link, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "No title"
            
            desc_tag = soup.find("meta", attrs={"name": "description"})
            snippet = desc_tag["content"].strip() if desc_tag else ""
            
            summary = f"Title: {title}\nSnippet: {snippet}\nURL: {link}"
            summaries.append(summary)
        except:
            pass

    combined = "\n\n".join(summaries)
    return combined

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
