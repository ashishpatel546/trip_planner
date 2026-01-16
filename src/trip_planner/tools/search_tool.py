from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os
import requests


class BraveSearchInput(BaseModel):
    """Input schema for BraveSearchTool."""
    search_query: str = Field(..., description="The search query to search the internet with")


class BraveSearchTool(BaseTool):
    name: str = "Brave Web Search the internet"
    description: str = "A tool that can be used to search the internet with a search_query."
    args_schema: type[BaseModel] = BraveSearchInput
    n_results: int = 5

    def _run(self, search_query: str) -> str:
        """Search the internet using Brave Search API."""
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
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            if "web" in data and "results" in data["web"]:
                for result in data["web"]["results"][:self.n_results]:
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    description = result.get("description", "No description")
                    results.append(f"Title: {title}\nURL: {url}\nDescription: {description}\n")
            
            return "\n".join(results) if results else "No results found"
        except Exception as e:
            return f"Error searching: {str(e)}"


def get_search_tool():
    """Tool to search the web using Brave Search"""
    return BraveSearchTool(n_results=5)