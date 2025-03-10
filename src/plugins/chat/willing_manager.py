import asyncio
from typing import Dict
from loguru import logger

from typing import Dict
from loguru import logger

from .config import global_config
from .message_base import UserInfo, GroupInfo
from .chat_stream import chat_manager,ChatStream


class WillingManager:
    def __init__(self):
        self.chat_reply_willing: Dict[str, float] = {}  # 存储每个聊天流的回复意愿
        self.chat_reply_willing: Dict[str, float] = {}  # 存储每个聊天流的回复意愿
        self._decay_task = None
        self._started = False
        self.min_reply_willing = 0.01
        self.attenuation_coefficient = 0.75

    async def _decay_reply_willing(self):
        """定期衰减回复意愿"""
        while True:
            await asyncio.sleep(5)
            for chat_id in self.chat_reply_willing:
                self.chat_reply_willing[chat_id] = max(0, self.chat_reply_willing[chat_id] * 0.6)
            for chat_id in self.chat_reply_willing:
                self.chat_reply_willing[chat_id] = max(0, self.chat_reply_willing[chat_id] * 0.6)
                
    def get_willing(self,chat_stream:ChatStream) -> float:
        """获取指定聊天流的回复意愿"""
        stream = chat_stream
        if stream:
            return self.chat_reply_willing.get(stream.stream_id, 0)
        return 0
    
    def set_willing(self, chat_id: int, willing: float):
        """设置指定群组的回复意愿"""
        self.group_reply_willing[chat_id] = willing
        
    async def change_reply_willing_received(self, 
                                          chat_stream:ChatStream,
                                          topic: str = None,
                                          is_mentioned_bot: bool = False,
                                          config = None,
                                          is_emoji: bool = False,
                                          interested_rate: float = 0) -> float:
        """改变指定聊天流的回复意愿并返回回复概率"""
        # 获取或创建聊天流
        stream = chat_stream
        chat_id = stream.stream_id
        group_id = stream.group_info.group_id

        # 若非目标回复群组，则直接return
        if group_id not in config.talk_allowed_groups:
            reply_probability = 0
            return reply_probability

        
        current_willing = self.chat_reply_willing.get(chat_id, 0)
        
        logger.debug(f"[{chat_id}]的初始回复意愿: {current_willing}")


        # 根据消息类型（被cue/表情包）调控
        if is_mentioned_bot:
            current_willing = min(
                3.0,
                current_willing + 0.9
            )
            logger.debug(f"被提及, 当前意愿: {current_willing}")

        if is_emoji:
            current_willing *= 0.1
            logger.debug(f"表情包, 当前意愿: {current_willing}")

        # 兴趣放大系数，若兴趣 > 0.4则增加回复概率
        interested_rate_amplifier = global_config.response_interested_rate_amplifier
        logger.debug(f"放大系数_interested_rate: {interested_rate_amplifier}")
        interested_rate *= interested_rate_amplifier

        current_willing += max(
            0.0,
            interested_rate - 0.4
        )

        # 回复意愿系数调控，独立乘区
        willing_amplifier = max(
            global_config.response_willing_amplifier,
            self.min_reply_willing
        )
        current_willing *= willing_amplifier
        logger.debug(f"放大系数_willing: {global_config.response_willing_amplifier}, 当前意愿: {current_willing}")

        # 回复概率迭代，保底0.01回复概率
        reply_probability = max(
            (current_willing - 0.45) * 2,
            self.min_reply_willing
        )

        # 降低目标低频群组回复概率
        down_frequency_rate = max(
            1.0,
            global_config.down_frequency_rate
        )
        if group_id in config.talk_frequency_down_groups:
            reply_probability = reply_probability / down_frequency_rate

        reply_probability = min(reply_probability, 1)

        self.group_reply_willing[group_id] = min(current_willing, 3.0)
        logger.debug(f"当前群组{group_id}回复概率：{reply_probability}")
        return reply_probability
    
    def change_reply_willing_sent(self, chat_stream:ChatStream):
        """开始思考后降低聊天流的回复意愿"""
        stream = chat_stream
        if stream:
            current_willing = self.chat_reply_willing.get(stream.stream_id, 0)
            self.chat_reply_willing[stream.stream_id] = max(0, current_willing - 2)
        
    def change_reply_willing_after_sent(self,chat_stream:ChatStream):
        """发送消息后提高聊天流的回复意愿"""
        stream = chat_stream
        if stream:
            current_willing = self.chat_reply_willing.get(stream.stream_id, 0)
            if current_willing < 1:
                self.chat_reply_willing[stream.stream_id] = min(1, current_willing + 0.2)
        
    async def ensure_started(self):
        """确保衰减任务已启动"""
        if not self._started:
            if self._decay_task is None:
                self._decay_task = asyncio.create_task(self._decay_reply_willing())
            self._started = True


# 创建全局实例
willing_manager = WillingManager()
