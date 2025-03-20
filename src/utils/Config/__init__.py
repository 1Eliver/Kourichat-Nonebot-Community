import toml
import threading
from typing import Any, Dict, Optional
from pathlib import Path
from src.utils.Bases.ScopeBase import ScopeBase

class ConfigManager(ScopeBase):
    def __init__(
        self, 
        config_path: str = "./config/bot_config.toml", 
        template_path: Optional[str] = None, 
        key: Optional[str] = None,
        is_single: bool = True
        ):
        """初始化日志管理器

        Args:
            config_path (str): 配置文件地址
            template_path (Optional[str], optional): 配置模板文件
            key (Optional[str], optional): 作用域id
            is_single (bool, optional): 是否是单例模式
        """
        super().__init__(is_single, key)
        self._config_path = Path(config_path)
        self._template_path = Path(template_path) if template_path else None
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load_config()

    def _sync_config_format(self, config: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
        """同步配置格式到模板格式

        Args:
            config (Dict[str, Any]): 当前配置
            template (Dict[str, Any]): 模板配置

        Returns:
            Dict[str, Any]: 同步后的配置
        """
        result = {}
        for key, template_value in template.items():
            if isinstance(template_value, dict):
                # 如果是字典类型，递归同步
                config_value = config.get(key, {})
                if isinstance(config_value, dict):
                    result[key] = self._sync_config_format(config_value, template_value)
                else:
                    result[key] = {}
            else:
                # 如果不是字典类型，保留原值或使用模板默认值
                result[key] = config.get(key, template_value)
        return result

    def _load_config(self) -> None:
        """加载配置文件，如果不存在则创建，如果存在则检查格式"""
        with self._lock:
            if not self._config_path.exists():
                if self._template_path and self._template_path.exists():
                    with open(self._template_path, 'r', encoding='utf-8') as tf:
                        self._config = toml.load(tf) or {}
                    self._save_config()
                else:
                    self._config = {}
            else:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = toml.load(f) or {}
                
                # 如果存在模板文件，检查并同步格式
                if self._template_path and self._template_path.exists():
                    with open(self._template_path, 'r', encoding='utf-8') as tf:
                        template_config = toml.load(tf) or {}
                    self._config = self._sync_config_format(self._config, template_config)
                    self._save_config()

    def _save_config(self) -> None:
        """保存配置到文件，保持与模板相同的顺序"""
        with self._lock:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                toml.dump(self._config, f)

    def __getitem__(self, key: str) -> Any:
        """获取配置项"""
        with self._lock:
            return self._config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """设置配置项并保存"""
        with self._lock:
            self._config[key] = value
            self._save_config()

    def __contains__(self, key: str) -> bool:
        """检查配置项是否存在"""
        with self._lock:
            return key in self._config

    def get(self, key: str, default: Any = None) -> Any:
        """安全获取配置项，如果不存在返回默认值"""
        with self._lock:
            return self._config.get(key, default)

    def update(self, config_dict: Dict[str, Any]) -> None:
        """批量更新配置并保存"""
        with self._lock:
            self._config.update(config_dict)
            self._save_config()

    def reload(self) -> None:
        """重新加载配置文件"""
        self._load_config()

    @property
    def config(self) -> Dict[str, Any]:
        """获取完整的配置字典（只读）"""
        with self._lock:
            return self._config.copy()
