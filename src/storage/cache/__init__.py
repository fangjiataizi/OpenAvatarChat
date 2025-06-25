"""
缓存层模块
提供Redis缓存和AI结果缓存功能
"""

from .redis_client import RedisCacheManager, cache_manager


class TeachingCacheKeys:
    """教学平台缓存键定义"""
    LEARNING_SESSION = "learning_session"
    USER_PREFERENCES = "user_preferences"
    COURSE_DATA = "course_data"
    CHAT_HISTORY = "chat_history"
    AI_RESPONSE = "ai_response"
    TTS_CACHE = "tts_cache"
    ASR_CACHE = "asr_cache"
    AVATAR_CACHE = "avatar_cache"


class AICacheManager:
    """AI结果缓存管理器"""
    
    def __init__(self, cache_manager: RedisCacheManager):
        self.cache_manager = cache_manager
    
    def cache_ai_result(self, cache_type: str, input_hash: str, result_data: dict, ttl: int = 3600):
        """缓存AI处理结果"""
        cache_key = f"ai_cache:{cache_type}:{input_hash}"
        return self.cache_manager.set(cache_key, result_data, ttl=ttl)
    
    def get_ai_result(self, cache_type: str, input_hash: str):
        """获取AI缓存结果"""
        cache_key = f"ai_cache:{cache_type}:{input_hash}"
        return self.cache_manager.get(cache_key)
    
    def clear_ai_cache(self, cache_type: str = None):
        """清理AI缓存"""
        if cache_type:
            pattern = f"ai_cache:{cache_type}:*"
        else:
            pattern = "ai_cache:*"
        return self.cache_manager.delete_pattern(pattern)


# 全局AI缓存实例
ai_cache = AICacheManager(cache_manager)

__all__ = [
    'RedisCacheManager', 'cache_manager',
    'TeachingCacheKeys', 'AICacheManager', 'ai_cache'
] 