"""
Redis缓存管理器
"""
import json
import pickle
import hashlib
from typing import Any, Optional, Dict, List, Union
import logging
from datetime import timedelta

import redis
from redis.connection import ConnectionPool

from ..config.storage_config import CacheConfig, storage_config

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """Redis缓存管理器"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or storage_config.cache
        self.client: Optional[redis.Redis] = None
        self.pool: Optional[ConnectionPool] = None
        self._initialized = False
    
    def initialize(self):
        """初始化Redis连接"""
        if self._initialized:
            return
        
        try:
            # 创建连接池
            self.pool = ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                max_connections=self.config.max_connections,
                decode_responses=True,  # 自动解码响应
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # 创建Redis客户端
            self.client = redis.Redis(connection_pool=self.pool)
            
            # 测试连接
            self.client.ping()
            
            self._initialized = True
            logger.info(f"Redis initialized: {self.config.host}:{self.config.port}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            # Redis连接失败不应该影响系统启动，使用内存缓存作为降级方案
            self._fallback_cache = {}
            logger.warning("Using in-memory cache as fallback")
    
    def _get_key(self, prefix: str, key: str) -> str:
        """生成完整的缓存键"""
        return f"teaching:{prefix}:{key}"
    
    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value)
        else:
            # 复杂对象使用pickle序列化，然后base64编码
            import base64
            pickled = pickle.dumps(value)
            return base64.b64encode(pickled).decode('utf-8')
    
    def _deserialize_value(self, value: str) -> Any:
        """反序列化值"""
        try:
            # 先尝试JSON解析
            return json.loads(value)
        except json.JSONDecodeError:
            # JSON解析失败，尝试pickle反序列化
            try:
                import base64
                pickled = base64.b64decode(value.encode('utf-8'))
                return pickle.loads(pickled)
            except Exception:
                # 如果都失败了，返回原始字符串
                return value
    
    def set(self, prefix: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存"""
        if not self._initialized or not self.client:
            # 降级到内存缓存
            cache_key = self._get_key(prefix, key)
            self._fallback_cache[cache_key] = value
            return True
        
        try:
            cache_key = self._get_key(prefix, key)
            serialized_value = self._serialize_value(value)
            
            if ttl:
                return self.client.setex(cache_key, ttl, serialized_value)
            else:
                return self.client.set(cache_key, serialized_value)
                
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    def get(self, prefix: str, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self._initialized or not self.client:
            # 降级到内存缓存
            cache_key = self._get_key(prefix, key)
            return self._fallback_cache.get(cache_key)
        
        try:
            cache_key = self._get_key(prefix, key)
            value = self.client.get(cache_key)
            
            if value is None:
                return None
            
            return self._deserialize_value(value)
            
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def delete(self, prefix: str, key: str) -> bool:
        """删除缓存"""
        if not self._initialized or not self.client:
            # 降级到内存缓存
            cache_key = self._get_key(prefix, key)
            self._fallback_cache.pop(cache_key, None)
            return True
        
        try:
            cache_key = self._get_key(prefix, key)
            return bool(self.client.delete(cache_key))
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def exists(self, prefix: str, key: str) -> bool:
        """检查缓存是否存在"""
        if not self._initialized or not self.client:
            cache_key = self._get_key(prefix, key)
            return cache_key in self._fallback_cache
        
        try:
            cache_key = self._get_key(prefix, key)
            return bool(self.client.exists(cache_key))
            
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    def expire(self, prefix: str, key: str, ttl: int) -> bool:
        """设置缓存过期时间"""
        if not self._initialized or not self.client:
            return True  # 内存缓存不支持TTL
        
        try:
            cache_key = self._get_key(prefix, key)
            return bool(self.client.expire(cache_key, ttl))
            
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False
    
    def get_pattern_keys(self, prefix: str, pattern: str) -> List[str]:
        """根据模式获取键列表"""
        if not self._initialized or not self.client:
            return []
        
        try:
            search_pattern = self._get_key(prefix, pattern)
            keys = self.client.keys(search_pattern)
            # 移除前缀，返回原始键名
            prefix_len = len(f"teaching:{prefix}:")
            return [key[prefix_len:] for key in keys]
            
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []
    
    def delete_pattern(self, pattern: str) -> int:
        """根据模式删除缓存键"""
        if not self._initialized or not self.client:
            # 清理内存缓存
            keys_to_remove = [k for k in self._fallback_cache.keys() if pattern.replace('*', '') in k]
            for key in keys_to_remove:
                del self._fallback_cache[key]
            return len(keys_to_remove)
        
        try:
            # 使用Redis的SCAN命令安全地删除匹配的键
            keys_to_delete = []
            for key in self.client.scan_iter(match=f"teaching:{pattern}"):
                keys_to_delete.append(key)
            
            if keys_to_delete:
                return self.client.delete(*keys_to_delete)
            return 0
            
        except Exception as e:
            logger.error(f"Redis delete pattern error: {e}")
            return 0
    
    def clear_prefix(self, prefix: str) -> int:
        """清除指定前缀的所有缓存"""
        if not self._initialized or not self.client:
            # 清理内存缓存
            prefix_pattern = f"teaching:{prefix}:"
            keys_to_remove = [k for k in self._fallback_cache.keys() if k.startswith(prefix_pattern)]
            for key in keys_to_remove:
                del self._fallback_cache[key]
            return len(keys_to_remove)
        
        try:
            pattern = self._get_key(prefix, "*")
            keys = self.client.keys(pattern)
            
            if keys:
                return self.client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Redis clear prefix error: {e}")
            return 0
    
    def health_check(self) -> bool:
        """Redis健康检查"""
        if not self._initialized or not self.client:
            return False
        
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取Redis信息"""
        if not self._initialized or not self.client:
            return {"status": "fallback_mode", "type": "memory"}
        
        try:
            info = self.client.info()
            return {
                "status": "connected",
                "version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "keyspace": info.get("db0", {})
            }
        except Exception as e:
            logger.error(f"Redis info error: {e}")
            return {"status": "error", "error": str(e)}


class AIResultCache:
    """AI结果专用缓存管理"""
    
    def __init__(self, cache_manager: RedisCacheManager):
        self.cache = cache_manager
        self.default_ttl = storage_config.cleanup.ai_cache_ttl
    
    def _generate_input_hash(self, input_data: Any) -> str:
        """生成输入数据的哈希值"""
        if isinstance(input_data, str):
            content = input_data.encode('utf-8')
        else:
            content = str(input_data).encode('utf-8')
        
        return hashlib.md5(content).hexdigest()
    
    def set_asr_result(self, audio_hash: str, result: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """缓存ASR结果"""
        return self.cache.set(
            TeachingCacheKeys.AI_ASR_RESULT,
            audio_hash,
            result,
            ttl or self.default_ttl
        )
    
    def get_asr_result(self, audio_hash: str) -> Optional[Dict[str, Any]]:
        """获取ASR缓存结果"""
        return self.cache.get(TeachingCacheKeys.AI_ASR_RESULT, audio_hash)
    
    def set_tts_result(self, text: str, audio_data: bytes, metadata: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """缓存TTS结果"""
        text_hash = self._generate_input_hash(text)
        result = {
            "audio_data": audio_data,
            "metadata": metadata,
            "text": text
        }
        return self.cache.set(
            TeachingCacheKeys.AI_TTS_RESULT,
            text_hash,
            result,
            ttl or self.default_ttl
        )
    
    def get_tts_result(self, text: str) -> Optional[Dict[str, Any]]:
        """获取TTS缓存结果"""
        text_hash = self._generate_input_hash(text)
        return self.cache.get(TeachingCacheKeys.AI_TTS_RESULT, text_hash)
    
    def set_llm_result(self, prompt: str, response: str, metadata: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """缓存LLM结果"""
        prompt_hash = self._generate_input_hash(prompt)
        result = {
            "response": response,
            "metadata": metadata,
            "prompt": prompt
        }
        return self.cache.set(
            TeachingCacheKeys.AI_LLM_RESULT,
            prompt_hash,
            result,
            ttl or self.default_ttl
        )
    
    def get_llm_result(self, prompt: str) -> Optional[Dict[str, Any]]:
        """获取LLM缓存结果"""
        prompt_hash = self._generate_input_hash(prompt)
        return self.cache.get(TeachingCacheKeys.AI_LLM_RESULT, prompt_hash)


# 全局缓存管理器实例
cache_manager = RedisCacheManager()
ai_cache = AIResultCache(cache_manager) 