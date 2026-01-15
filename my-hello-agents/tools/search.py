
import os
from typing import Optional
from .base import Tool
from tavily import TavilyClient

class SearchTool(Tool):
    """
    智能混合搜索工具

    支持多种搜索引擎后端，智能选择最佳搜索源：
    1. 混合模式(hybrid) - 智能选择 TAVILY 或 SERPAPI
    2. Tavily API(tavily) - 专业AI搜索
    3. SerpAPI(serpapi) - 传统Google搜索
    """

    def __init__(self, backend: str = "hybrid", tavily_key: Optional[str] = None, serpapi_key: Optional[str] = None):
        super().__init__(
            name="search",
            description="一个智能网页搜索引擎，支持混合搜索模式，自动选择最佳搜索源。"
        )
        self.backend = backend
        self.tavily_key = tavily_key or os.getenv("TAVILY_API_KEY")
        self.serpapi_key = serpapi_key or os.getenv("SERPAPI_API_KEY")
        self.available_backends = []
        self._setup_backends()

    def _setup_backends(self):
        self.tavily_client = TavilyClient(self.tavily_key) if self.tavily_key else None
        pass

    def _search_tavily(self, query: str) -> str:
        """使用 Tavily 搜索"""
        response = self.tavily_client.search(
            query=query,
            search_depth="basic",
            include_answer=True,
            max_results=3
        )

        result = f"🎯 Tavily AI搜索结果:{response.get('answer', '未找到直接答案')}\n\n"

        for i, item in enumerate(response.get("results", [])[:3], 1):
            result += f"[{i}]. {item.get('title', '')}"
            result += f"     {item.get('content', '')[:200]}...\n"
            result += f"     来源: {item.get('url', '')}\n\n"
        
        return result
