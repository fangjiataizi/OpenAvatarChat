"""
AI教学平台存储层
提供PostgreSQL + Redis + MinIO三层存储架构
"""

from .config.storage_config import StorageConfig
from .database.connection import DatabaseManager, db_manager
from .cache.redis_client import RedisCacheManager, cache_manager
from .services.user_service import UserService, user_service

__all__ = [
    'StorageConfig',
    'DatabaseManager', 'db_manager',
    'RedisCacheManager', 'cache_manager',
    'UserService', 'user_service'
] 