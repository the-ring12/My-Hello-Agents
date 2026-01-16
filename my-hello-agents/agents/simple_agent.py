"""简单 Agent 实现 - 基于 OpenAI 原生 API"""

from typing import Optional, Iterator, TYPE_CHECKING
import re

from ..core.agent import Agent
from ..core.llm import HelloAgentsLLM
from ..core.config import Config
from ..core.message import Message

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry


class SimpleAgent(Agent):
    """简单的对话 Agent，支持可选的工具调用"""

    def __init__(
        self, 
        name: str, 
        llm: HelloAgentsLLM, 
        system_prompt: Optional[str] = None, 
        config: Optional[Config] = None,
        tool_registry: Optional['ToolRegistry'] = None,
        enable_tool_calling: bool = True
    ):
        """
        初始化 SimpleAgent

        Args:
            name: Agent 名称
            llm: LLM 实例
            system_prompt: 系统提示词
            config: 配置对象
            tool_registry: 工具注册表（可选，如果提供则启用工具调用）
            enable_tool_calling: 是否启用工具调用（只有在提供 tool_registry 时生效）
        """
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling

    def _get_enhanced_system_prompt(self) -> str:
        """构建增强的系统提示词，包含工具信息"""
        base_prompt = self.system_prompt or "你是一个有用的 AI 助手。"

        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt
        
        # 获取工具描述
        tools_description = self.tool_registry.get_tool_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt
        
        tools_section = f"""
\n## 可用工具
你可以使用以下工具来帮助回答问题：
{tools_description}

## 工具调用格式
当需要使用工具时，请使用以下格式：
[TOOL_CALL: {{tool_name}}:{{parameters}}]

### 参数格式说明
1. **多个参数**: 使用 `key=value` 格式，用逗号分隔
    示例：`[TOOL_CALL: caculator_multiply:a=12,b=8]
    示例：`[TOOL_CALL: filesystem_read_file:path=README.md]

2. **单个参数**: 直接使用 `key=value`
    示例：`[TOOL_CALL: search:query=Python编程]

3. **简单查询**: 可以直接传入文本
    示例：`[TOOL_CALL: search:Python编程]

### 重要提示
- 参数必须与工具定义的参数名完全匹配
- 数字参数直接写数字，不需要引号：`a=12` 而不是 `a=\"12\"`
- 文件路径鞥字符串参数直接写： `path=READMER.md`
- 工具调用结果会自动插入到对话中，然后你可以基于结果继续回答
"""
        
        return base_prompt + tools_section

    def _parse_tool_call(self, text: str) -> list:
        """解析文本中的工具调用"""
        pattern = r"\[TOOL_CALL: ([^:]+):([^\]]+)\]"
        matches = re.findall(pattern, text)

        tool_calls = []
        for tool_name, parameters in matches:
            tool_calls.append({
                "tool_name": tool_name,
                "parameter": parameters.strip(),
                "original": f'[TOOL_CALL: {tool_name}:{parameters}]'
            })

        return tool_calls
    
    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行工具调用"""
        if not self.tool_registry:
            return f"❌ 错误：未配置工具注册表"
        
        try:
            # 获取 Tool 对象
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                return f"❌ 错误：未找到工具 '{tool_name}'"
            
            # 智能参数解析
            param_dict = self._parse_tool_parameter(tool_name, parameters)

            # 调用工具
            result = tool.run(param_dict)
            return f"🔧 工具 {tool_name} 执行结果：\n{result}"
        except Exception as e:
            return f"❌ 工具调用失败：{str(e)}"

    def _parse_tool_parameter(self, tool_name: str, parameters: str) -> dict:
        """智能解析参数工具"""
        import json
        param_dict = {}

        # 尝试解析 JSON 格式
        if parameters.strip().startswith('{'):
            try:
                param_dict = json.load(parameters)
                # JSON 解析成功，进行类型转换
                param_dict = self._convert_parameter_types(tool_name, param_dict)
                return param_dict
            except json.JSONDecodeError:
                # JSON 解析失败，继续使用其他方式
                pass
        
        if '=' in parameters:
            # 格式: key=value 或 action=search,query=Python
            if ',' in parameters:
                # 多个参数：action=search,query=Python,limit=3
                pairs = parameters.split(',')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        param_dict[key.strip()] = value.strip()
            else:
                # 单个参数： key=value
                key, value = pair.split('=', 1)
                param_dict[key.strip()] = value.strip()
        
            # 类型转换
            param_dict = self._convert_parameter_types(tool_name, param_dict)

            # 智能推断 action(如果没有指定)
            if 'action' not in param_dict:
                param_dict = self._infer_action(tool_name, param_dict)
        
        else:
            # 直接传入参数，根据工具类型智能推断
            param_dict = self._infer_simple_parameters(tool_name, parameters)
        
        return param_dict

    def _convert_parameter_types(self, tool_name: str, param_dict: dict) -> dict:
        """
        根据工具的参数定义转换参数类型

        Args:
            tool_name: 工具名称
            param_dict: 参数字典

        Returns:
            类型转换后的参数字典
        """
        if not self.tool_registry:
            return param_dict

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return param_dict
        
        # 获取工具的采纳数定义
        try:
            tool_params = tool.get_parameters()
        except:
            return param_dict
        
        # 创建参数类型映射
        param_types = {}
        for param in tool_params:
            param_types[param.name] = param.type

        # 转换参数类型
        converted_dict = {}
        for key, value in param_dict.items():
            if key in param_types:
                param_type = param_types[key]
                try:
                    if param_type == 'number' or param_type == 'integer':
                        # 转换为数字
                        if isinstance(value, str):
                            converted_dict[key] = float(value) if param_type == 'number' else int(value)
                        else:
                            converted_dict[key] = value
                    elif param_type == 'boolean':
                        # 转换为布尔值
                        if isinstance(value, str):
                            converted_dict[key] = value.lower() in ('true', '1', 'yes')
                        else:
                            converted_dict[key] = bool(value)
                    else:
                        converted_dict[key] = value
                except (ValueError, TypeError):
                    # 转换失败，保持原值
                    converted_dict[key] = value
            else:
                converted_dict[key] = value
        
        return converted_dict
    
    def _infer_action(self, tool_name: str, param_dict: dict) -> dict:
        """根据工具类型和参数推断 action"""
        if tool_name == 'memory':
            if 'recall' in param_dict:
                param_dict['action'] = 'search'
                # TODO