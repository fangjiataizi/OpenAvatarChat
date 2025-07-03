"""
数据库连接管理
"""
from contextlib import contextmanager
from typing import Generator, Optional
import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from ..config.storage_config import DatabaseConfig, storage_config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or storage_config.database
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialized = False
    
    def initialize(self):
        """初始化数据库连接"""
        if self._initialized:
            return
        
        try:
            # 创建数据库引擎
            if self.config.type == "sqlite":
                # SQLite配置
                self.engine = create_engine(
                    self.config.url,
                    echo=self.config.echo,
                    connect_args={"check_same_thread": False}  # SQLite需要
                )
            else:
                # PostgreSQL配置
                self.engine = create_engine(
                    self.config.url,
                    echo=self.config.echo,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_pre_ping=True,  # 连接检查
                    pool_recycle=3600    # 1小时回收连接
                )
            
            # 创建会话工厂
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # 创建表
            self.create_tables()
            
            # 初始化基础数据
            self.init_base_data()
            
            self._initialized = True
            logger.info(f"Database initialized: {self.config.type}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_tables(self):
        """创建数据库表"""
        try:
            # 延迟导入避免循环引用
            from .models import Base
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def init_base_data(self):
        """初始化基础数据"""
        try:
            # 暂时跳过基础数据初始化，避免循环导入
            logger.info("Base data initialization skipped to avoid circular imports")
                
        except Exception as e:
            logger.error(f"Failed to initialize base data: {e}")
            # 不抛出异常，基础数据初始化失败不应该影响系统启动
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话的上下文管理器"""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """直接获取数据库会话（需要手动管理）"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()
    
    def health_check(self) -> bool:
        """数据库健康检查"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")


# 全局数据库管理器实例
db_manager = DatabaseManager()


# SQLite优化事件监听器
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite连接优化"""
    if 'sqlite' in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys=ON")
        # 设置同步模式为NORMAL（平衡性能和安全性）
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 启用WAL模式（更好的并发性能）
        cursor.execute("PRAGMA journal_mode=WAL")
        # 设置缓存大小（8MB）
        cursor.execute("PRAGMA cache_size=-8000")
        cursor.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI依赖注入用的数据库会话"""
    with db_manager.get_session() as session:
        yield session 