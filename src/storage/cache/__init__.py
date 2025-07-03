"""
缓存层模块
提供Redis缓存和AI结果缓存功能
"""

from .redis_client import RedisCacheManager, cache_manager


class TeachingCacheKeys:
    """AI教学平台缓存键定义"""
    
    # 用户相关缓存
    USER_SESSION = "user_session"       # 用户会话
    USER_PROFILE = "user_profile"       # 用户档案
    USER_PREFERENCES = "user_preferences"  # 用户偏好
    
    # 课程相关缓存
    COURSE_LIST = "course_list"         # 课程列表
    COURSE_DETAIL = "course_detail"     # 课程详情
    COURSE_DATA = "course_data"         # 课程数据（向后兼容）
    SUBJECT_LIST = "subject_list"       # 学科列表
    
    # 学习会话相关缓存
    LEARNING_SESSION = "learning_session"  # 学习会话
    SESSION_STATS = "session_stats"        # 会话统计
    CHAT_HISTORY = "chat_history"          # 聊天历史
    
    # AI处理缓存
    AI_RESPONSE = "ai_response"         # AI响应缓存
    TTS_CACHE = "tts_cache"            # TTS缓存
    ASR_CACHE = "asr_cache"            # ASR缓存
    AVATAR_CACHE = "avatar_cache"      # Avatar缓存


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