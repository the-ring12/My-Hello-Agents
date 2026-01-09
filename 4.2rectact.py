import os
from dotenv import load_dotenv
from tavily import TavilyClient
from typing import Literal, Dict, Any
from llm_client import HelloAgentsLLM
from tool import ToolExecutor
import re

load_dotenv()


def search(
        query: str,
        max_result: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = False
    ) -> str:
    """
    一个基于 Tavily 的实战网页搜索引擎工具
    它会智能地解析搜索信息，优先返回直接答案
    """
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "错误：TAVILY_API_KEY 未在 .env 文件中配置。"

        tavily_client = TavilyClient(api_key=api_key)

        return tavily_client.search(
            query,
            max_results=max_result,
            include_raw_content=include_raw_content,
            topic=topic
        )
    except Exception as e:
        return f"搜索时发生错误：{e}"



# --- 工具初始化与使用示例 ---
def main1():
    # 1. 初始化工具执行器
    toolExecutor = ToolExecutor()

    # 2. 注册搜索工具
    search_description = "一个网页搜索引擎，当你需要回答关于时事、事实一级在你的知识中找不到的信息时，应用此工具。"
    toolExecutor.registerTool("Search", search_description, search)

    # 3. 打印可用的工具
    print("\n--- 可用的工具 ---")
    print(toolExecutor.getAvailableTools())

    # 4. 智能体的Action调用，
    print("\n--- 执行 Action：Search['英伟达最新的GPU型号是什么'] ---")
    tool_name = "Search"
    tool_input = "英伟达最新的GPU型号是什么"

    tool_function = toolExecutor.getTool(tool_name)
    if tool_function:
        observation = tool_function(tool_input)
        print("--- 观察（Observation）---")
        print(observation)
    else:
        print(f"错误：未找到名为 '{tool_name}' 的工具")


# ReAct 提示词模版
REACT_PROMPT_TEMPLATE = """
请注意，你是一个有能力调用外部工具的智能助手。

可调用工具如下：
{tools}

请严格按照以下格式进行回应：

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步行动。
Action: 你决定采取的行动，必须是以下格式之一：
- `tool_name[tool_input]`: 调用一个可用工具。
- `Finish[最终答案]`: 当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户最终问题时，你必须在 Action: 字段后使用 finish(answer="...") 来输出最终答案。

现在，请开始解决以下问题：
Question: {question}
History: {history}
""" 

class REACTAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history = []
    
    def run(self, question: str):
        """
        运行ReAct 智能提来回答一个问题
        """
        self.history = [] # 每次运行重置历史记录
        current_step = 0
        
        while current_step < self.max_steps:
            current_step += 1
            print(f"--- 第 {current_step} 步 ---")

            # 1. 格式化提示词
            tools_desc = self.tool_executor.getAvailableTools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=tools_desc,
                question=question,
                history=history_str
            )

            # 2. 调用 LLM 进行思考
            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages)

            if not response_text:
                print("错误：LLM未能返回有效响应。")
                break
            
            # 3. 解析 LLM 的输出
            thought, action = self._parse_output(response_text)

            if thought:
                print(f"思考：{thought}")
            
            if not action:
                print("警告：未能解析出有效的 Action，流程终止。")
                break
            
            # 4. 执行 Action
            if action.startswith("Finish"):
                # 如果时 Finish 指令，提取最终答案并结束
                final_answer = re.search(r"Finish\[(.*)\]", action).group(1)
                print(f"🎉 最终答案: {final_answer}")
                return final_answer

            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                # 无效 Action 格式
                continue

            print(f"🎬 行动: {tool_name}[{tool_input}]")

            tool_function = self.tool_executor.getTool(tool_name)
            if not tool_function:
                observation = f"错误：未找到名为 '{tool_name}' 的工具。"
            else:
                observation = tool_function(tool_input) # 调用真实工具

            print(f"👀 观察: {observation}")

            # 将本轮的Action和Observation添加到历史记录中
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")
        
        # 循环结束
        print("已达到最大步骤，流程终止。")
        return None



    def _parse_output(self, text: str):
        """
        解析 LLM 的输出，提取 Thought 和 Action
        """
        thought_match = re.search(r"Thought: (.*)", text)
        action_match = re.search(r"Action: (.*)", text)
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

    def _parse_action(self, action_text: str):
        """
        解析 Action 字符串，提取工具名称和输入
        """
        match = re.search(r"(\w+)\[(.*)\]", action_text)
        if match:
            return match.group(1), match.group(2)
        return None, None


if __name__ == '__main__':
    # --- 工具初始化与使用示例 ---
    # main1()
    llm_client = HelloAgentsLLM()
    # 初始化工具执行器
    tool_executor = ToolExecutor()

    # 2. 注册搜索工具
    search_description = "一个网页搜索引擎，当你需要回答关于时事、事实一级在你的知识中找不到的信息时，应用此工具。"
    tool_executor.registerTool("Search", search_description, search)


    agent = REACTAgent(llm_client, tool_executor)
    agent.run("华为最新手机以及它的卖点")