from abc import ABC
from typing import Dict, TypeVar, Type, Optional, Any

T = TypeVar('T', bound='ScopeBase')

class ScopeBase(ABC):
    """
    作用域模式基类
    支持单例模式和作用域模式
    """
    _instances: Dict[str, Dict[str, Any]] = {}
    
    def __new__(cls: Type[T], is_single: bool = False, obj_key: Optional[str] = None, *args, **kwargs) -> T:
        # 获取类名作为基础键
        cls_name = cls.__name__
        
        # 如果不是单例模式且没有指定作用域，则正常初始化
        if not is_single and obj_key is None:
            return super().__new__(cls)
            
        # 确保类在实例字典中有对应的条目
        if cls_name not in cls._instances:
            cls._instances[cls_name] = {}
            
        # 确定对象键
        key = "singleton" if is_single else obj_key
        
        # 如果实例不存在，创建新实例
        if key not in cls._instances[cls_name]:
            instance = super().__new__(cls)
            cls._instances[cls_name][key] = instance
            
        return cls._instances[cls_name][key]
    
    @classmethod
    def clear_instances(cls, obj_key: Optional[str] = None):
        """
        清除实例缓存
        :param obj_key: 指定要清除的作用域key，如果为None则清除所有
        """
        cls_name = cls.__name__
        if obj_key is None:
            if cls_name in cls._instances:
                del cls._instances[cls_name]
        else:
            if cls_name in cls._instances and obj_key in cls._instances[cls_name]:
                del cls._instances[cls_name][obj_key]
