from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os
import requests
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


class BraveSearchInput(BaseModel):
    """Input schema for CachedBraveSearchTool."""
    search_query: str = Field(..., description="The search query to search the internet with")


class CachedBraveSearchTool(BaseTool):
    """Cached Brave Search tool that stores results to minimize API calls."""
    name: str = "Brave Web Search the internet"
    description: str = "A tool that can be used to search the internet with a search_query. Results are cached to improve performance."
    args_schema: type[BaseModel] = BraveSearchInput
    n_results: int = 5
    cache_dir: Path = Field(default_factory=lambda: Path("cache/search_results"))
    cache_expiry_hours: int = 24  # Cache expires after 24 hours

    def __init__(self, **data):
        super().__init__(**data)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, query: str) -> str:
        """Generate a cache key from the query."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> str | None:
        """Retrieve cached result if it exists and is not expired."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if cache is expired
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            if datetime.now() - cached_time > timedelta(hours=self.cache_expiry_hours):
                cache_file.unlink()  # Delete expired cache
                return None
            
            return cached_data['result']
        except Exception:
            return None

    def _save_to_cache(self, cache_key: str, result: str):
        """Save search result to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'result': result
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to cache result: {e}")

    def _run(self, search_query: str) -> str:
        """Search the internet using Brave Search API with caching."""
        # Check cache first
        cache_key = self._get_cache_key(search_query)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            print(f"[Cache Hit] Using cached results for: {search_query[:50]}...")
            return cached_result
        
        print(f"[Cache Miss] Fetching new results for: {search_query[:50]}...")
        
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return "Error: BRAVE_API_KEY not found in environment variables"
        
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }
        params = {
            "q": search_query,
            "count": self.n_results
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = []
            if "web" in data and "results" in data["web"]:
                for result in data["web"]["results"][:self.n_results]:
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    description = result.get("description", "No description")
                    results.append(f"Title: {title}\nURL: {url}\nDescription: {description}\n")
            
            result_text = "\n".join(results) if results else "No results found"
            
            # Save to cache
            self._save_to_cache(cache_key, result_text)
            
            return result_text
        except Exception as e:
            return f"Error searching: {str(e)}"


def get_cached_search_tool():
    """Tool to search the web using Brave Search with caching"""
    return CachedBraveSearchTool(n_results=5)
