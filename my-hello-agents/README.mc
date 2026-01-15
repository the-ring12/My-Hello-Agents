

hello-agents/
├── hello_agents/
│ │
│ ├── core/ # 核心框架层
│ │ ├── agent.py # Agent基类
│ │ ├── llm.py # HelloAgentsLLM统一接口
│ │ ├── message.py # 消息系统
│ │ ├── config.py # 配置管理
│ │ └── exceptions.py # 异常体系
│ │
│ ├── agents/ # Agent实现层
│ │ ├── simple_agent.py # SimpleAgent实现
│ │ ├── react_agent.py # ReActAgent实现
│ │ ├── reflection_agent.py # ReflectionAgent实现
│ │ └── plan_solve_agent.py # PlanAndSolveAgent实现
│ │
│ ├── tools/ # 工具系统层
│ │ ├── base.py # 工具基类
│ │ ├── registry.py # 工具注册机制
│ │ ├── chain.py # 工具链管理系统
│ │ ├── async_executor.py # 异步工具执行器
│ │ └── builtin/ # 内置工具集
│ │ ├── calculator.py # 计算工具
│ │ └── search.py # 搜索工具
└──


https://github.com/jjyaoao/HelloAgents/blob/main/hello_agents/core/llm.py