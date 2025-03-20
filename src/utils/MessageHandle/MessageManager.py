import asyncio
from datetime import datetime, timedelta
import html
import re
import threading
import time
import traceback
from typing import Callable, Dict, List, Optional
from src.utils.MessageHandle.KMessage import KMessage
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from src.utils.MessageHandle.MessageSenderType import MessageSenderType
from src.utils.MessageHandle.MessageType import MessageType
from src.utils.MessageHandle.MessageId import MessageId
from nonebot.log import logger


class MessageManager:
    def __init__(self, time_interval: int = 10):
        # 消息队列，字典是用户id，列表是消息列表
        # 一个Message是一句话（一行）
        # 取末尾的最后一条的生成时间来计算是否需要处理该队列
        self.private_message_queue: Dict[str, List[KMessage]] = {}
        self.private_recent_message_time: Dict[str, datetime] = {}
        # 保存私聊消息队列处理线程
        self.private_queue_thread: threading.Thread | None = None
        # 添加一个event来控制线程私聊消息队列线程退出
        self.private_queue_stop_event: threading.Event = threading.Event()
        self.init_private_queue_handle()
        # 私聊消息队列处理时间间隔（打字等待时间）
        # 当前疑问：如果处理一个队列时还有消息增加，是否会导致bug
        self.time_interval = time_interval
        # 消息处理器列表
        self.message_processors = []

    def message_processor(self, func):
        """装饰器，用于注册消息处理方法
        
        Args:
            func: 处理函数，接受两个参数：用户ID(str)和消息(KMessage)，返回str
            
        Returns:
            func: 原处理函数
        """
        self.message_processors.append(func)
        return func
    
    async def process_message(self, user_id: str, message: str) -> str:
        """异步调用所有注册的消息处理方法，并将结果聚合
        
        Args:
            user_id (str): 用户ID
            message (str): 处理后的可大模型可理解的消息
            
        Returns:
            str: 聚合的处理结果
        """
        results = []
        
        # 异步调用所有处理器
        for processor in self.message_processors:
            try:
                result = await processor(user_id, message)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"消息处理器执行异常: {e}\n{traceback.format_exc()}")
        
        # 聚合结果
        return "".join(results)

    async def add_private_message(self, message: Message, user_id: str):
        """处理将私聊消息添加到消息队列中

        Args:
            message (KMessage): 消息对象
        """
        add_message = self.receive_private_message(message, user_id)
        self.private_message_queue[message.sender_id] += add_message
        self.private_recent_message_time[message.sender_id] = datetime.now()
    
    async def receive_private_message(
        self, 
        message: Message, 
        user_id: str
        ) -> List[KMessage]:
        """这个方法用于处理收到的消息到KMessage

        Args:
            message (Message): NoneBot收到的待处理Message
            user_id (str): Message的来源用户id

        Returns:
            KMessage: 格式化到KMessage
        """
        res: List[KMessage] = []
        for seg in message:
            message_type = self._format_message_type(seg)
            message_content = self._format_message_content(seg, message_type)
            res.append(
                KMessage(
                MessageId(user_id), 
                message_type, 
                MessageSenderType.PRIVATE, 
                message_content
                )
            )
        return res
            
    
    async def _format_message_type(self, message: MessageSegment) -> MessageType:
        """用于将NoneBot的Message类型转换为KMessage的MessageType

        Args:
            message (Message): 需要获取格式的Message(MessageSegment)

        Returns:
            MessageType: 格式化后的MessageType
        """
        if message.type == "text":
            return MessageType.TEXT
        elif message.type == "image":
            if "summary" in message.data and "动画表情" in message.data["summary"]:
                # 检测是否是动画表情
                return MessageType.ANIMATION_FACE
            else:
                return MessageType.IMAGE
        elif message.type == "face":
            return MessageType.FACE
        elif message.type == "record":
            return MessageType.RECORD
        elif message.type == "file":
            return MessageType.FILE
        else:
            raise ValueError(f"不支持的消息类型: {message.type}")
        
    async def _format_message_content(self, 
                                    message: MessageSegment, 
                                    message_type: MessageType
                                    ) -> str:
        """用于格式化不同消息的内容（只保留必要内容）到str

        Args:
            message (MessageSegment): 要格式的消息段

        Returns:
            str: 必要内容
        """
        if message_type is MessageType.TEXT:
            return message
        elif message_type is MessageType.FACE:
            return await self._decode_face(str(message.data["raw"]))
        elif message_type in [MessageType.IMAGE, MessageType.RECORD, MessageType.FILE, MessageType.ANIMATION_FACE]:
            return message.data.get("file") or message.data.get("path")
    
    async def _decode_face(self, face_raw_content: str) -> Optional[str | None]:
        """这个方法用于将qq的黄脸表情解析到对应的中文意思（大概的）

        Args:
            face_raw_content (str): 表情数据的raw内容

        Returns:
            Optional[str | None]: 解码后的表情中文
        """
        html_part = re.search(r"'faceText': '(.*?)'", face_raw_content).group(1)
        decoded_text = html.unescape(html_part)
        if decoded_text.startswith('[') and decoded_text.endswith(']'):
            chinese_text = decoded_text[1:-1]
            return chinese_text
        else:
            return None
        
    def init_private_queue_handle(self):
        """
        这个方法用于初始化私聊消息队列处理器
        """
        self.private_queue_thread = threading.Thread(
            target=self._run_async_queue_handler, 
            args=(self._private_queue_handle,)
            )
        self.private_queue_thread.daemon = True  # 设置为守护线程，这样主线程退出时它会自动退出
        self.private_queue_thread.start()
    
    def _run_async_queue_handler(self, target_func: Callable):
        """
        在线程中运行异步处理队列的方法
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(target_func)
        except Exception as e:
            # 处理异常
            logger.error(f"队列处理器异常: {e} \n 异常信息: {traceback.format_exc()}")
        finally:
            loop.close()
        
    async def _private_queue_handle(self):
        """
        这个方法用于处理私聊消息队列
        """
        while not self.private_queue_stop_event.is_set():
            # 按照时间顺序处理私聊消息队列
            # 遍历用户
            for user_id, messages in self.private_message_queue.items():
                # 检查某个用户信息是否超过时间间隔——超过则处理
                if (
                    datetime.now() - self.private_recent_message_time[user_id]) < timedelta(seconds=self.time_interval):
                    # 未超过时间间隔，跳过
                    continue
                # 超过时间间隔，处理
                messages = []
                # 要遍历消息，处理为大模型方便处理的格式
