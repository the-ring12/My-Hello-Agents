
from typing import Any, Callable
from .base import Tool


class ToolRegistry:
    """HelloAgents 工具注册表"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._functions: dict[str, dict[str, Any]] = {}

    def register_tool(self, tool: Tool):
        """注册 Tool 对象"""
        if tool.name in self._tools:
            print(f"⚠️ 警告:工具 '{tool.name}' 已存在，将被覆盖。")
        self._tools[tool.name] = tool
        print(f"✅ 工具 '{tool.name}' 注册成功。")

    def registry_function(self, name: str, description: str, func: Callable[[str], str]):
        """
        直接注册函数作为工具
        
        Args:
            name (str): 工具名称
            description (str): 工具描述
            func (Callable[[str], str]): 工具函数，接受字符串参数，返回字符串结果
        """
        if name in self._functions:
            print(f"⚠️ 警告:工具 '{name}' 已存在，将被覆盖。")
        self._functions[name] = {
            "description": description,
            "function": func
        }
        print(f"✅ 工具 '{name}' 已注册。")

    
    def get_tool_description(self) -> str:
        """获取所有可用工具的格式化描述字符串"""
        descriptions = []

        # Tool 对象描述
        for tool in self._tools.values():
            descriptions.append(f"{tool.name}: {tool.description}")
        
        # 函数工具描述
        for name, info in self._functions.items():
            descriptions.append(f"{name}: {info['description']}")

        return "\n".join(descriptions) if descriptions else "暂无可用工具。"
    
    
