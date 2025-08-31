# services/news.py
import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
NEWS_API_BASE_URL = "https://newsapi.org/v2"

def get_news_response(query: str, news_api_key: str) -> str:
    if not news_api_key:
        return "I can't fetch the news without a valid API key."

    # On free plan, /top-headlines gives 401 → use /everything
    is_general_query = any(k in query.lower() for k in ["news", "latest", "headlines", "current events", "what's happening"])
    
    params = {"apiKey": news_api_key, "pageSize": 5, "language": "en"}
    
    if is_general_query:
        url = f"{NEWS_API_BASE_URL}/everything"
        params["q"] = "latest"
    else:
        url = f"{NEWS_API_BASE_URL}/everything"
        params["q"] = query

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "ok" and data.get("articles"):
            return format_articles_for_llm(data["articles"])
        else:
            return "Looks like I couldn't find any news on that topic."
    except requests.exceptions.HTTPError as e:
        logger.error(f"NewsAPI error: {e}")
        return "⚠️ My NewsAPI key may not support this request."
    except Exception as e:
        logger.error(f"Unexpected news error: {e}")
        return "Something went wrong while fetching the news."

def format_articles_for_llm(articles: List[Dict[str, Any]], max_count: int = 3) -> str:
    if not articles:
        return "No articles available."
    out = "Here are some headlines:\n\n"
    for i, art in enumerate(articles[:max_count]):
        title = art.get("title", "No title")
        desc = art.get("description", "No description")
        src = art.get("source", {}).get("name", "Unknown")
        out += f"{i+1}. {title}\n    Source: {src}\n    Summary: {desc}\n\n"
    return out
