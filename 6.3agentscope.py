import os
import asyncio
import random
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from collections import Counter

from agentscope.message import Msg
from agentscope.agent import AgentBase
from agentscope.pipeline import MsgHub, sequential_pipeline, fanout_pipeline
from agentscope.formatter import DashScopeMultiAgentFormatter

load_dotenv()


class GameRoles:
    """三国狼人杀角色定义管理类"""

    ROLES = {
        "狼人": {
            "description": "狼人",
            "ability": "夜晚可以击杀一名玩家",
            "win_condition": "消灭所有好人或与好人数量相等",
            "team": "狼人阵营"
        },
        "预言家": {
            "description": "预言家",
            "ability": "每晚可以查验一名玩家的身份",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营"
        },
        "女巫": {
            "description": "女巫",
            "ability": "拥有解药和毒药一瓶，可以救人和杀人",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营"
        },
        "猎人": {
            "description": "猎人",
            "ability": "被投票出局时可以开枪带走一名玩家",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营"
        },
        "村民": {
            "description": "村民",
            "ability": "无特殊技能，依靠推理和投票",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营"
        },
        "守护者": {
            "description": "守护者",
            "ability": "每晚可以守护一名玩家免受狼人攻击",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营"
        }
    }

    CHARACTER_TRAITS = {
        "刘备": "仁德宽厚，善于团结众人，说话温和有礼",
        "关羽": "忠义刚烈，言辞直接，重情重义",
        "张飞": "性格豪爽，说话大声直接，容易冲动",
        "诸葛亮": "智慧超群，分析透彻，言辞谨慎",
        "赵云": "忠勇双全，话语简洁有力",
        "曹操": "雄才大略，善于权谋，话语犀利",
        "司马懿": "深谋远虑，城府极深，言辞含蓄",
        "周瑜": "才华横溢，略显傲气，分析精准",
        "孙权": "年轻有为，善于决断，话语果决"
    }

    @classmethod
    def get_role_desc(cls, role: str) -> str:
        """获取角色描述"""
        return cls.ROLES.get(role, {}).get("description", "未知角色")
    
    @classmethod
    def get_role_ability(cls, role: str) -> str:
        """获取角色技能"""
        return cls.ROLES.get(role, {}).get('ability' "无特殊技能")
    
    @classmethod
    def get_role_trait(cls, character: str) -> str:
        """获取角色性格特点"""
        return cls.CHARACTER_TRAITS.get(character, "性格温和，说话得体")

    @classmethod
    def is_werewolf(cls, role: str) -> bool:
        """判断是否为狼人"""
        return role == "狼人"
    
    @classmethod
    def is_villager_team(cls, role: str) -> bool:
        """判断是否为好人阵营"""
        return cls.ROLES.get(role, {}).get('team') == "好人阵营"
    
    @classmethod
    def get_standard_setup(cls, player_count: int) -> List[str]:
        """获取标准角色配置"""
        if player_count == 6:
            return ["狼人", "狼人", "预言家", "女巫", "村民", "村民"]
        elif player_count == 8:
            return ["狼人", "狼人", "狼人", "预言家", "女巫", "猎人", "村民", "村民"]
        elif player_count == 9:
            return ["狼人", "狼人", "狼人", "预言家", "女巫", "猎人", "守护者", "村民", "村民"]
        else:
            # 默认配置: 约 1/3 狼人
            werewolf_count = max(1, player_count // 3)
            roles = ["狼人"] * werewolf_count

            # 添加神职
            remaining = player_count - werewolf_count
            if remaining >= 1:
                roles.append("预言家")
                remaining -= 1
            if remaining >= 1:
                roles.append("女巫")
                remaining -= 1
            if remaining >= 1:
                roles.append("猎人")
                remaining -= 1
            
            # 剩余为村民
            roles.extend(["村民"] * remaining)

            return roles
        

# --- 三国狼人杀中文提示词 ---
class ChinesePrompt:
    """中文提示词管理类"""

    @staticmethod
    def get_role_prompt(role: str, character: str) -> str:
        """获取角色提示词"""
        base_prompt = f"""你是{character}，在这场狼人杀游戏中扮演{role}。

请严格按照以下JSON格式回复，不要添加任何其他文字：
{{
    "reach_agreement": true/false,
    "confidence_level": 1-10的数字,
    "key_evidence": "你的证据或观点" 
}}

角色特点：
"""
    
        if role == "狼人":
            return base_prompt + f"""
- 你是狼人阵营，目标是消灭所有好人
- 夜晚可以与其他狼人协商击杀目标
- 白天要隐藏身份，误导好人
- 以{character}的性格说话和行动"""
        
        elif role == "预言家":
            return base_prompt + f"""
- 你是好人阵营的预言家，目标是找出所有狼人
- 每晚可以查验一名玩家的真实身份
- 要合理公布查验结果，引导好人投票
- 以{character}的智慧和洞察力分析局势"""
        
        elif role == "女巫":
            return base_prompt + f"""
- 你是好人阵营的女巫，拥有解药和毒药各一瓶
- 解药可以救活被狼人击杀的玩家
- 毒药可以毒杀一名完结
- 要谨慎使用道具，在关键时刻发挥作用"""

        elif role == "猎人":
            return base_prompt + f"""
- 你是好人阵营的猎人
- 被投票出局时可以开枪带走一名玩家
- 要在关键时刻使用技能，带走狼人
- 以{character}的勇猛和决断力行动"""
        
        else: # 村民
            return base_prompt + f"""
- 你是好人阵营的村民
- 没有特殊技能，只能通过推理和投票
- 要仔细观察，找出狼人的破绽
- 以{character}的性格参与讨论"""



# --- 三国狼人杀游戏的结构化输出模型 ---
class DiscussionModelCN(BaseModel):
    """中文版讨论输出格式"""

    reach_agreement: bool = Field(
        description="是否已达成一致意见",
        default=False
    )
    confidence_level: int = Field(
        description="对当前推理的信心程度（1-10）",
        ge=1, 
        le=10,
        default=5
    )
    key_evidence: Optional[str] = Field(
        description="支持你观点的关键证据",
        default=None
    )


def get_vote_model_cn(agents: list[AgentBase]) -> type[BaseModel]:
    """获取中文版投票模型"""

    class VoteModelCN(BaseModel):
        """ 中文版投票输出格式"""

        vote: Literal[tuple(_.name for _ in agents)] = Field(description="你要投票淘汰的玩家姓名")
        reason: str = Field(description="投票理由：简要说明为什么选择此人")
        suspicion_level: int = Field(
            description="对被投票者的怀疑程度（1-10）",
            ge=1,le=10
        )
    
    return VoteModelCN

class WitchActionModelCN(BaseModel):
    """中文版女巫行动模型"""
    use_antidot: bool = Field(description="是否使用解药救人", default=False)
    use_poison: bool = Field(description="是否使用毒药杀人", default=False)
    target_name: Optional[str] = Field(description="目标玩家姓名(救人或毒杀的对象)", default=None)
    action_reason: Optional[str] = Field(description="行动理由", default=None)

def get_seer_model_cn(agents: list[AgentBase]) -> type[BaseModel]:
    """获取中文版预言家模型"""
    
    class SeerModelCN(BaseModel):
        """中文版预言家查验格式"""
        
        target: Literal[tuple(_.name for _ in agents)] = Field(
            description="要查验的玩家姓名",
        )
        check_reason: str = Field(
            description="查验此人的原因",
        )
        priority_level: int = Field(
            description="查验优先级(1-10)",
            ge=1, le=10
        )
    
    return SeerModelCN


def get_hunter_model_cn(agents: list[AgentBase]) -> type[BaseModel]:
    """获取中文版猎人模型"""
    
    class HunterModelCN(BaseModel):
        """中文版猎人开枪格式"""
        
        shoot: bool = Field(
            description="是否使用开枪技能",
        )
        target: Optional[Literal[tuple(_.name for _ in agents)]] = Field(
            description="开枪目标玩家姓名",
            default=None
        )
        shoot_reason: Optional[str] = Field(
            description="开枪理由",
            default=None
        )
    
    return HunterModelCN


class WerewolfKillModelCN(BaseModel):
    """中文版狼人击杀模型"""
    
    target: str = Field(
        description="要击杀的玩家姓名",
    )
    kill_strategy: str = Field(
        description="击杀策略说明",
    )
    team_coordination: Optional[str] = Field(
        description="与狼队友的配合计划",
        default=None
    )


class GameAnalysisModelCN(BaseModel):
    """中文版游戏分析模型"""
    
    suspected_werewolves: List[str] = Field(
        description="怀疑的狼人名单",
        default_factory=list
    )
    trusted_players: List[str] = Field(
        description="信任的玩家名单", 
        default_factory=list
    )
    key_clues: List[str] = Field(
        description="关键线索列表",
        default_factory=list
    )
    next_strategy: str = Field(
        description="下一步策略",
    )

# 游戏常亮
MAX_GAME_ROUND = 10
MAX_DISCUSSION_ROUND = 3
CHINESE_NAME = [
    "刘备", "关羽", "张飞", "诸葛亮", "赵云",
    "曹操", "司马懿", "典韦", "许褚", "夏侯惇", 
    "孙权", "周瑜", "陆逊", "甘宁", "太史慈",
    "吕布", "貂蝉", "董卓", "袁绍", "袁术"
]

def get_chinese_name(character: str = None) -> str:
    """获取中文角色名"""
    if character and character in CHINESE_NAME:
        return character
    return random.choice(CHINESE_NAME)

def format_player_list(players: List[AgentBase], show_roles: bool = False) -> str:
    """格式化玩家列表为中文显示"""
    if not players:
        return "无玩家"
    
    if show_roles:
        return "、".join([f"{p.name}({getattr(p, 'role', "未知")})" for p in players])
    else:
        return "、".join([p.name for p in players])
    
def majority_vote_cn(votes: Dict[str, str]) -> tuple[str, str]:
    """中文版多数投票统计"""
    if not votes:



# 消息的标准结构
message = Msg(
    name="Alice", # 发送者名称
    content="Hello, Bob!", # 消息内容
    role="user", # 角色类型
    metadata={
        "timestamp": "2026-01-08T14:00:00z",
        "message_type": "text",
        "priority": "normal"
    }
)


class CustomAgent(AgentBase):
    def __init__(self, name: str, **kwargs):
        super().__init__(name=name, **kwargs)
        # 智能体初始化逻辑

    def reply(self, x: Msg) -> Msg:
        # 智能体的核心响应逻辑
        response = self.model(x.content)
        return Msg(name=self.name, content=response, role="assistant")
    
    def observe(self, x: Msg) -> None:
        # 智能体的观察逻辑（可选）
        self.memory.add(x)

class ThreeKingdomsWerewolfGame():
    """
    游戏主控制类
    负责维护全局状态（如玩家存活列表、当前游戏阶段）、推进游戏流程（调用夜晚阶段、白天阶段）以及裁定胜负
    """


 
async def warewolf_phase(self, round_num: int):
    """狼人阶段 - 展示消息驱动的协作模式"""
    if not self.warewolves:
        return None
    
    # 通过消息中心建立狼人专属通信频道
    async with MsgHub(
        self.waewolves,
        enable_auto_broadcast=True,
        announcement=await self.moderator.announce(
            f"狼人们，请讨论今晚的击杀目标，存活玩家：{format_player_list(self.alive_players)}"
        ),
    ) as warewolves_hub:
        # 讨论阶段：狼人通过消息交换策略
        for _ in range(MAX_DISCUSSION_ROUNdD):
            for wolf in self.werewolves:
                await wolf(structured_model=DiscussionModelCN)
        
        # 投票阶段：收集并统计狼人的击杀决策
        werewolves_hub.set_auto_broadcast(False)
        kill_votes = await fanout_pipeline(
            self.werewolves,
            msg=await self.moderator.announce("请选择击杀目标"),
            structured_model=WerewolfKillModelCN,
            enable_gather=False
        )
