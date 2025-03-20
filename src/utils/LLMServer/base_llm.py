from abc import ABC, abstractmethod
import asyncio
import uuid
import time
import re
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional, Any, Set
from src.utils.Bases.ScopeBase import ScopeBase

class ConversationRecord:
    """对话记录类，记录单次对话的信息"""
    
    def __init__(self, user_id: str, chat_prompt: str):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.chat_prompt = chat_prompt
        self.ai_response = ""
        self.start_time = datetime.now()
        self.end_time = None
        self.duration = None
    
    def complete(self, ai_response: str):
        """完成对话，记录AI响应和结束时间"""
        self.ai_response = ai_response
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        
    def to_dict(self) -> Dict[str, Any]:
        """将对话记录转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "chat_prompt": self.chat_prompt,
            "ai_response": self.ai_response,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration
        }

class UserContext:
    """用户上下文类，管理单个用户的对话历史"""
    
    def __init__(self, max_pairs: int):
        self.history: List[Tuple[str, str]] = []  # [(用户问题, AI回答), ...]
        self.max_pairs = max_pairs
        self.conversation_records: Dict[str, ConversationRecord] = {}
    
    def add_pair(self, user_message: str, ai_message: str, record: ConversationRecord) -> List[Tuple[str, str]]:
        """添加一对对话，并返回被移除的对话对（如果有）"""
        removed = []
        
        # 如果历史对话数量达到上限，移除最早的对话
        if len(self.history) >= self.max_pairs:
            removed = self.history[:len(self.history) - self.max_pairs + 1]
            self.history = self.history[len(self.history) - self.max_pairs + 1:]
        
        # 添加新对话
        self.history.append((user_message, ai_message))
        self.conversation_records[record.id] = record
        
        return removed
    
    def get_history(self) -> List[Tuple[str, str]]:
        """获取历史对话"""
        return self.history
    
    def get_conversation_record(self, record_id: str) -> Optional[ConversationRecord]:
        """根据ID获取对话记录"""
        return self.conversation_records.get(record_id)
    
    def get_all_conversation_records(self) -> Dict[str, ConversationRecord]:
        """获取所有对话记录"""
        return self.conversation_records
    
    def clear(self):
        """清空历史对话"""
        self.history = []
        self.conversation_records = {}

class BaseLLM(ScopeBase, ABC):
    """LLM基类，管理上下文和对话历史"""
    
    def __init__(self, 
                is_single: bool = False,
                obj_key: Optional[str] = None,
                sys_prompt: str = "", 
                enable_context: bool = True, 
                max_pairs: int = 10,
                # OpenAI 类似参数
                url: str = "",
                api_key: str = "",
                model: str = "gpt-3.5-turbo",
                max_tokens: int = 2048,
                temperature: float = 0.7,
                top_p: float = 1.0,
                frequency_penalty: float = 0.0,
                presence_penalty: float = 0.0):
        """
        初始化LLM基类
        
        Args:
            sys_prompt (str): 系统提示词，不计入对话对数
            enable_context (bool): 是否启用上下文管理
            max_pairs (int): 最大对话对数（一个完整的对话对由用户问题和AI回复组成）
            is_single (bool): 是否为单例模式
            obj_key (str, optional): 作用域键
            url (str): API接口URL
            api_key (str): API密钥
            model (str): 模型名称
            max_tokens (int): 最大生成token数
            temperature (float): 温度参数，控制随机性
            top_p (float): 核采样参数
            frequency_penalty (float): 频率惩罚
            presence_penalty (float): 存在惩罚
        """
        self.sys_prompt = sys_prompt
        self.enable_context = enable_context
        self.max_pairs = max_pairs
        self.user_contexts: Dict[str, UserContext] = {}
        self._hook_functions: Set[Callable] = set()
        
        # 保存API参数
        self.url = url
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
    
    def hook(self, func: Callable):
        """
        装饰器，用于注册钩子方法
        
        Args:
            func: 钩子函数，将在内容超出最大对数被丢弃时被调用
                  函数签名应为 async def hook_func(user_id: str, removed_pairs: List[Tuple[str, str]], record_id: str)
        
        Returns:
            func: 原钩子函数
        """
        self._hook_functions.add(func)
        return func
    
    def _get_user_context(self, user_id: str) -> UserContext:
        """
        获取用户上下文，如果不存在则创建
        
        Args:
            user_id (str): 用户ID
        
        Returns:
            UserContext: 用户上下文
        """
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = UserContext(self.max_pairs)
        return self.user_contexts[user_id]
    
    async def _run_hooks(self, user_id: str, removed_pairs: List[Tuple[str, str]], record_id: str):
        """
        运行所有钩子函数
        
        Args:
            user_id (str): 用户ID
            removed_pairs (List[Tuple[str, str]]): 被移除的对话对
            record_id (str): 对话记录ID
        """
        if not removed_pairs:
            return
            
        for hook_func in self._hook_functions:
            try:
                if asyncio.iscoroutinefunction(hook_func):
                    await hook_func(user_id, removed_pairs, record_id)
                else:
                    hook_func(user_id, removed_pairs, record_id)
            except Exception as e:
                print(f"钩子函数执行异常: {e}")
    
    def _format_chat_prompt(self, user_id: str, message: str) -> str:
        """
        格式化聊天提示词，包含历史对话
        
        Args:
            user_id (str): 用户ID
            message (str): 用户消息
        
        Returns:
            str: 格式化后的聊天提示词
        """
        if not self.enable_context:
            return message
            
        user_context = self._get_user_context(user_id)
        history = user_context.get_history()
        
        formatted_prompt = self.sys_prompt + "\n\n"
        
        # 添加历史对话
        for user_msg, ai_msg in history:
            formatted_prompt += f"用户: {user_msg}\nAI: {ai_msg}\n\n"
        
        # 添加当前提示词
        formatted_prompt += f"用户: {message}\nAI: "
        
        return formatted_prompt
    
    async def chat(self, user_id: str, message: str) -> Tuple[str, str]:
        """
        与LLM进行对话，自动管理上下文
        
        Args:
            user_id (str): 用户ID
            message (str): 用户消息
        
        Returns:
            Tuple[str, str]: (AI回复, 对话记录ID)
        """
        chat_prompt = self._format_chat_prompt(user_id, message)
        
        # 创建对话记录
        record = ConversationRecord(user_id, chat_prompt)
        
        # 调用API生成回复
        ai_response = await self.api_response(chat_prompt)
        
        # 完成对话记录
        record.complete(ai_response)
        
        # 如果启用上下文管理，更新用户上下文
        if self.enable_context:
            user_context = self._get_user_context(user_id)
            removed_pairs = user_context.add_pair(message, ai_response, record)
            
            # 如有对话被移除，运行钩子函数
            await self._run_hooks(user_id, removed_pairs, record.id)
        
        return ai_response, record.id
    
    @abstractmethod
    async def api_response(self, prompt: str) -> str:
        """
        调用API生成回复，由子类实现
        
        Args:
            prompt (str): 提示词
        
        Returns:
            str: AI生成的回复
        """
        pass
    
    def get_conversation_record(self, user_id: str, record_id: str) -> Optional[ConversationRecord]:
        """
        获取对话记录
        
        Args:
            user_id (str): 用户ID
            record_id (str): 对话记录ID
        
        Returns:
            Optional[ConversationRecord]: 对话记录，如果不存在则返回None
        """
        user_context = self._get_user_context(user_id)
        return user_context.get_conversation_record(record_id)
    
    def search_conversations(self, user_id: str, pattern: str) -> List[ConversationRecord]:
        """
        根据正则表达式搜索用户的对话记录
        
        Args:
            user_id (str): 用户ID
            pattern (str): 正则表达式模式
        
        Returns:
            List[ConversationRecord]: 匹配的对话记录列表
        """
        user_context = self._get_user_context(user_id)
        records = user_context.get_all_conversation_records()
        
        result = []
        try:
            regex = re.compile(pattern)
            
            for record_id, record in records.items():
                # 在用户消息和AI回复中搜索
                if (regex.search(record.chat_prompt) or 
                    regex.search(record.ai_response)):
                    result.append(record)
        except Exception as e:
            print(f"正则表达式搜索异常: {e}")
        
        return result
    
    def search_all_user_conversations(self, pattern: str) -> Dict[str, List[ConversationRecord]]:
        """
        搜索所有用户的对话记录
        
        Args:
            pattern (str): 正则表达式模式
        
        Returns:
            Dict[str, List[ConversationRecord]]: 按用户ID组织的匹配记录列表
        """
        result = {}
        
        for user_id in self.user_contexts:
            matches = self.search_conversations(user_id, pattern)
            if matches:
                result[user_id] = matches
        
        return result
    
    def clear_user_context(self, user_id: str):
        """
        清空用户上下文
        
        Args:
            user_id (str): 用户ID
        """
        if user_id in self.user_contexts:
            self.user_contexts[user_id].clear()
    
    def clear_all_contexts(self):
        """清空所有用户上下文"""
        self.user_contexts.clear()
