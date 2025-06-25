"""
存储配置管理
"""
import os
from typing import Optional
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: str = Field(default="sqlite")
    url: str = Field(default="sqlite:///./teaching_platform.db")
    echo: bool = Field(default=False)
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)


class CacheConfig(BaseModel):
    """缓存配置"""
    type: str = Field(default="redis")
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = Field(default=None)
    max_connections: int = Field(default=50)


class MinIOConfig(BaseModel):
    """MinIO对象存储配置"""
    endpoint: str = Field(default="localhost:9000")
    access_key: str = Field(default="teaching_admin")
    secret_key: str = Field(default="secure_password_123")
    secure: bool = Field(default=False)
    region: str = Field(default="us-east-1")


class FileStorageConfig(BaseModel):
    """文件存储配置"""
    avatar_storage: str = Field(default="./resource/avatar/")
    cache_storage: str = Field(default="./cache/")
    temp_storage: str = Field(default="./temp/")
    max_file_size: str = Field(default="100MB")


class CleanupConfig(BaseModel):
    """清理策略配置"""
    session_ttl: int = Field(default=86400)  # 24小时
    cache_ttl: int = Field(default=3600)     # 1小时
    temp_file_ttl: int = Field(default=1800) # 30分钟
    ai_cache_ttl: int = Field(default=7200)  # 2小时


class StorageConfig(BaseModel):
    """存储总配置"""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    minio: MinIOConfig = Field(default_factory=MinIOConfig)
    files: FileStorageConfig = Field(default_factory=FileStorageConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)
    
    @classmethod
    def from_env(cls) -> 'StorageConfig':
        """从环境变量创建配置"""
        return cls(
            database=DatabaseConfig(
                type=os.getenv("DB_TYPE", "sqlite"),
                url=os.getenv("DB_URL", "sqlite:///./teaching_platform.db"),
                echo=os.getenv("DB_ECHO", "false").lower() == "true"
            ),
            cache=CacheConfig(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD")
            ),
            minio=MinIOConfig(
                endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", "teaching_admin"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "secure_password_123"),
                secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
            )
        )


# 全局配置实例
storage_config = StorageConfig.from_env() 