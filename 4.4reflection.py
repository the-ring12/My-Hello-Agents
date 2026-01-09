from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from llm_client import HelloAgentsLLM


load_dotenv()

class Memory:
    """
    一个简单的短期记忆模块，用于存储智能体的行动与反思轨迹
    """

    def __init__(self):
        """
        初始化一个空列表来存储所有记录
        """
        self.records: List[Dict[str, Any]] = []
    
    def add_record(self, record_type: str, content: str):
        """
        向记忆中添加一条新记录。

        参数：
        - record_type(str): 记录的类型 ('execution' 或 'reflection')。
        - content(str): 记录的具体内容（例如，生成的代码或反思的反馈）。
        """
        record = {"type": record_type, "content": content}
        self.records.append(record)
        print(f"📝 记忆已更新，新增一条 '{record_type}' 记录。")
    
    def get_trajectory(self) -> str:
        """
        将所有记忆记录格式化为一个连贯的字符串文本，用于构建提示词。
        """
        trajectory_parts = []
        for record in self.records:
            if record['type'] == 'execution':
                trajectory_parts.append(f"--- 上一轮尝试（代码）---\n{record['content']}")
            elif record['type'] == 'reflection':
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")
        
        return "\n\n".join(trajectory_parts)
    
    def get_last_execution(self) -> Optional[str]:
        """
        获取最近一次的执行结果（例如，最新生成的代码）。
        如果不存在，则返回 None
        """
        for record in reversed(self.records):
            if record['type'] == 'execution':
                return record['content']
        return None    



INITIAL_PROMPT_TEMPLATE = """
你是一个资深的Python程序员，请根据一下要求，编写一个Python函数。
你的代码必须包含完整的函数签名、文档字符串，并遵循PEP 8代码规范。

要求：{task}

请直接输出代码，不要包含任何额外的解释。
"""

REFLECT_PROMPT_TEMPLATE = """
你是一个极其严格的代码评审专家和资深算法工程师，对代码的性能有极致的要求。
你的任务是审查一下Python代码，并专注于找出其在<strong>算法效率</strong>上的主要瓶颈。

# 原始任务：
{task}

# 待审查代码：
```python
{code}
```

请分析该代码的时间复杂度，并思考是否存在一种<strong>算法上更优</strong>的解决方案来显著提升性能，如果存在，请清晰指出当前算法的不足，并提出具体的、可行的改进算法（例如，使用筛法替代试验法）。如果代码在算法层面已经达到最优，才能回答“无需改进”。

请直接输出你的反馈，不要包含任何额外的解释。
"""

REFINE_PROMPT_TEMPLATE = """
你是一位资深的Python程序员，你正在根据一位代码评审专家的反馈来优化你的代码。

# 原始任务：
{task}

# 你上一轮尝试的代码：
```python
{last_code_attempt}
```

# 评审员的反馈：
{feedback}

请根据评审员的反馈，生成一个优化后的新版本代码。
你的代码必须包含完整的函数签名、文档字符串，并遵循PEP 8编码规范。
请直接输出优化后的代码，不要包含任何额外的解释。
"""


class ReflectionAgent:
    def __init__(self, llm_client: HelloAgentsLLM, max_iterations=3):
        self.llm_client = llm_client
        self.memory = Memory()
        self.max_iterations = max_iterations

    def run(self, task: str):
        print(f"\n--- 开始处理任务 ---\n任务：{task}")

        # --- 1. 初始执行 ---
        print("\n--- 正在进行初始尝试 ---")
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_code = self._get_llm_response(initial_prompt)
        self.memory.add_record("execution", initial_code)

        # --- 2. 迭代循环：反思与优化 ---
        for i in range(self.max_iterations):
            print(f"\n--- 第 {i+1}/{self.max_iterations} 轮优化")

            # a. 反思
            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution()
            reflect_prompt = REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code)
            feedback = self._get_llm_response(reflect_prompt)
            self.memory.add_record("reflection", feedback)

            # b. 检查是否需要停止
            if "无需改进" in feedback:
                print("\n✅ 反思认为代码已无需改进，任务完成。")
                break

            # c. 优化
            print("\n-> 正在进行优化...")
            refine_prompt = REFINE_PROMPT_TEMPLATE.format(
                task=task,
                last_code_attempt=last_code,
                feedback=feedback
            )

            refine_code = self._get_llm_response(refine_prompt)
            self.memory.add_record("execution", refine_code)
        
        final_code = self.memory.get_last_execution()
        print(f"\n--- 任务完成 ---\n最终生成的代码：\n{final_code}")
        return final_code
    

    def _get_llm_response(self, prompt: str):
        """
        一个辅助方法，用于调用LLM并获取完整的流式响应。"
        """
        messages = [{"role": "user", "content": prompt}]
        response_text = self.llm_client.think(messages=messages)
        return response_text



if __name__=='__main__':
    llm_client = HelloAgentsLLM()
    agent = ReflectionAgent(llm_client=llm_client)
    agent.run("编写一个Python函数，找出1到n之间所有的素数 (prime numbers)。")
