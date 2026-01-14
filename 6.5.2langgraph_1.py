from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from tavily import TavilyClient
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver



load_dotenv()


class SearchState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str         # 经过 LLM 理解后的用户需求总结
    search_query: str       # 优化后用于 Tavily Api 的搜索查询
    search_result: str      # Tavily 搜索返回的结果
    final_answer: str       # 最终生成的答案
    step: str               # 标记当前步骤


# 初始化模型
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL_ID"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    temperature=0.7
)

# 初始化Tavilt客户端
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# --- 定义节点 ---
def understand_query_node(state: SearchState) -> dict:
    """步骤1：理解用户查询并生成搜索关键词"""
    user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break

    understand_prompt = f"""分析用户的查询："{user_message}"
请完成两个任务：
1. 简洁总结用户想要了解什么
2. 生成最适合搜索引擎的关键词（中英文均可，要精准）

格式：
理解：[用户需求总结]
搜索词：[最佳搜索关键词]"""
    
    response = llm.invoke([SystemMessage(content=understand_prompt)])

    # 提取搜索关键词
    response_text = response.content
    # 解析 LLM 的输出，提取搜索关键词
    serach_query = user_message # 默认使用原始查询

    if "搜索词：" in response_text:
        serach_query = response_text.split("搜索词：")[1].strip()
    elif "搜索关键词：" in response_text:
        serach_query = response_text.split("搜索关键词：")[1].strip()
    
    return {
        "user_query": response_text,
        "search_query": serach_query,
        "step": "understood",
        "messages": [AIMessage(content=f"我将为你搜索：{serach_query}")]
    }

def tavily_search_node(state: SearchState) -> dict:
    """步骤2：使用 Tavily API 进行搜索"""
    search_query = state["search_query"]
    
    try:
        print(f"🔍 正在搜索: {search_query}")

        response = tavily_client.search(
            query=search_query, 
            search_depth="basic",
            include_answer=True,
            include_raw_content=False,
            max_results=5
        )

        # 处理搜索结果
        search_results = ""

        # 优先使用 Tavily 的综合答案
        if response.get("answer"):
            search_results = f"综合答案：\n{response["answer"]}\n\n"

        # 添加具体的搜索结果
        if response.get("results"):
            search_results += "相关信息：\n"
            for i, result in enumerate(response["results"][:3], 1):
                title = result.get("title", "")
                content = result.get("content", "")
                url = result.get("url", "")
                search_results += f"{i}. {title}\n{content}\n来源: {url}\n\n"
        
        if not search_results:
            search_results = "抱歉，没有找到相关信息。 "
        
        return {
            "search_result": search_results,
            "step": "searched",
            "messages": [AIMessage(content=f"✅ 搜索完成！找到了相关信息，正在为您整理答案...")]
        }
    except Exception as e:
        error_msg = f"搜索时出错: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "search_result": f"搜索失败：{error_msg}",
            "step": "search_field",
            "messages": [AIMessage(content=f"❌ 搜索遇到问题，我将基于已有知识为您回答。")]
        }
    
def generate_answer_node(state: SearchState) -> dict:
    """步骤3：基于搜索结果生成最终答案"""
    if state["step"] == "search_field":
        # 如果搜索失败，执行回退策略，基于 LLM 自身知识回答
        fallback_prompt = f"""搜索API暂时不可用，请基于你的知识回答用户的问题:
用户问题：{state['user_query']}

请提供一个有用的回答，并说明基于已有知识的回答。"""
        response = llm.invoke([SystemMessage(content=fallback_prompt)])
    else:
        # 搜索成功，基于搜索结果生成答案
        answer_prompt = f"""基于以下搜索结果为用户提供完整、准确的答案：

用户问题: {state['user_query']}

搜索结果：\n{state['search_result']}

请要求：
1. 综合搜索结果，提供准确、有用的回答
2. 如果是技术问题，提供具体的解决方案或代码
3. 引用重要信息的来源
4. 回答要结构清晰、易于理解
5. 如果搜索结果不够完整，请说明并提供补充建议"""
        
        response = llm.invoke([SystemMessage(content=answer_prompt)])
    
    return {
        "final_answer": response.content,
        "step": "completed",
        "messages": [AIMessage(content=response.content)]
    }

# --- 构建状态图 ---

def create_search_assistant():
    workflow = StateGraph(SearchState)

    # 添加节点
    workflow.add_node("ubderstand", understand_query_node)
    workflow.add_node("search", tavily_search_node)
    workflow.add_node("answer", generate_answer_node)

    # 设置线性流程
    workflow.add_edge(START, "ubderstand")
    workflow.add_edge("ubderstand", "search")
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", END)

    # 编译图
    memory = InMemorySaver()
    app = workflow.compile(checkpointer=memoryjinti)
    return app


async def main():
    if not os.getenv("TAVILY_API_KEY"):
        print("❌ 错误: 请在 .env 文件中设置 TAVILY_API_KEY 环境变量！")
        return
    
    app = create_search_assistant()

    print("🔍 智能搜索助手启动！")
    print("我会使用Tavily API为您搜索最新、最准确的信息")
    print("支持各种问题：新闻、技术、知识问答等")
    print("输入 'quit' 退出\m")

    session_count = 0

    while True:
        user_input = input("🤔 您想了解什么: ").strip()

        if user_input.lower() in ["quit", "exit", "q", "退出"]:
            print("👋 感谢使用智能搜索助手！再见！")
            break

        if not user_input:
            continue

        session_count += 1
        config = {"configurable": {"thread_id": f"search_session_{session_count}"}}

        # 初始状态
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "user_query": "",
            "search_query": "",
            "search_result": "",
            "final_answer": "",
            "step": "start"
        }

        try:
            print("\n⏳ 正在处理您的请求，请稍候...\n")

            async for output in app.astream(initial_state, config=config):
                for node_name, node_output in output.items():
                    if "messages" in node_output and node_output["messages"]:
                        latest_message = node_output["messages"][-1]
                        if isinstance(latest_message, AIMessage):
                            if node_name == "understand":
                                print(f"🧠 理解阶段: {latest_message.content}")
                            elif node_name == "search":
                                print(f"🔍 搜索阶段: {latest_message.content}")
                            elif node_name == "answer":
                                print(f"\n💡 最终回答:\n{latest_message.content}")
            
            print("\n✅ 请求处理完毕！\n")
        
        except Exception as e:
            print(f"❌ 处理请求时出错: {str(e)}\n")
            print("请重新输入您的问题。\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
            

