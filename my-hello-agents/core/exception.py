"""异常体系"""

class HelloAgentsException(Exception):
    """HelloAgents 基础异常类"""
    pass

class LLMException(HelloAgentsException):
    """与 LLM 相关的异常"""
    pass

class AgentException(HelloAgentsException):
    """与 Agent 相关的异常"""
    pass

class ConfigException(HelloAgentsException):
    """配置相关异常"""
    pass

class ToolException(HelloAgentsException):
    """工具相关异常"""
    pass