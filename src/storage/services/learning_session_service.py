"""
学习会话管理服务
"""
import secrets
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database.connection import db_manager
from ..cache.redis_client import cache_manager
from ..cache import TeachingCacheKeys

logger = logging.getLogger(__name__)


class LearningSessionService:
    """学习会话管理服务"""
    
    def __init__(self):
        self.cache = cache_manager
        # 初始化缓存管理器
        try:
            self.cache.initialize()
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}")
    
    def create_session(self, user_id: int, course_name: str, difficulty: str, goal: str, 
                      course_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """创建新的学习会话"""
        try:
            # 延迟导入避免循环引用
            from ..database.models import LearningSession
            
            # 生成唯一会话key
            session_key = f"session_{secrets.token_hex(16)}"
            
            # 创建会话元数据
            session_metadata = {
                "course_name": course_name,
                "difficulty": difficulty,
                "goal": goal,
                "created_at": datetime.now().isoformat(),
                "ai_proactive_count": 0,
                "user_response_count": 0
            }
            
            with db_manager.get_session() as session:
                # 创建学习会话记录
                learning_session = LearningSession(
                    user_id=user_id,
                    course_id=course_id,
                    session_key=session_key,
                    chat_history=[],
                    session_metadata=session_metadata,
                    status='active'
                )
                
                session.add(learning_session)
                session.commit()
                session.refresh(learning_session)
                
                # 缓存会话信息
                session_data = learning_session.to_dict()
                self.cache.set(
                    TeachingCacheKeys.LEARNING_SESSION,
                    session_key,
                    session_data,
                    ttl=7200  # 2小时
                )
                
                logger.info(f"Learning session created: {session_key}")
                return session_data
                
        except Exception as e:
            logger.error(f"Create learning session error: {e}")
            return None
    
    def get_session(self, session_key: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取学习会话信息"""
        try:
            # 先从缓存获取
            if use_cache:
                cached_session = self.cache.get(TeachingCacheKeys.LEARNING_SESSION, session_key)
                if cached_session:
                    return cached_session
            
            # 从数据库获取
            with db_manager.get_session() as session:
                from ..database.models import LearningSession
                
                learning_session = session.query(LearningSession).filter(
                    LearningSession.session_key == session_key
                ).first()
                
                if not learning_session:
                    return None
                
                session_data = learning_session.to_dict()
                
                # 更新缓存
                if use_cache:
                    self.cache.set(
                        TeachingCacheKeys.LEARNING_SESSION,
                        session_key,
                        session_data,
                        ttl=7200
                    )
                
                return session_data
                
        except Exception as e:
            logger.error(f"Get learning session error: {e}")
            return None
    
    def add_message_to_session(self, session_key: str, role: str, content: str, 
                              message_type: str = "normal", metadata: Optional[Dict] = None) -> bool:
        """向会话添加消息"""
        try:
            with db_manager.get_session() as session:
                from ..database.models import LearningSession
                
                learning_session = session.query(LearningSession).filter(
                    LearningSession.session_key == session_key
                ).first()
                
                if not learning_session:
                    logger.warning(f"Session not found: {session_key}")
                    return False
                
                # 添加消息到会话
                learning_session.add_chat_message(role, content, {
                    "type": message_type,
                    "timestamp": datetime.now().isoformat(),
                    **(metadata or {})
                })
                
                # 更新统计信息 - 修复JSON列更新问题
                metadata = dict(learning_session.session_metadata or {})
                if message_type == "proactive":
                    metadata["ai_proactive_count"] = metadata.get("ai_proactive_count", 0) + 1
                elif role == "human":
                    metadata["user_response_count"] = metadata.get("user_response_count", 0) + 1
                learning_session.session_metadata = metadata
                
                session.commit()
                
                # 更新缓存
                session_data = learning_session.to_dict()
                self.cache.set(
                    TeachingCacheKeys.LEARNING_SESSION,
                    session_key,
                    session_data,
                    ttl=7200
                )
                
                logger.debug(f"Message added to session {session_key}: {role} - {content[:50]}...")
                return True
                
        except Exception as e:
            logger.error(f"Add message to session error: {e}")
            return False
    
    def end_session(self, session_key: str) -> bool:
        """结束学习会话"""
        try:
            with db_manager.get_session() as session:
                from ..database.models import LearningSession
                
                learning_session = session.query(LearningSession).filter(
                    LearningSession.session_key == session_key
                ).first()
                
                if not learning_session:
                    return False
                
                # 计算会话时长
                if learning_session.start_time:
                    duration = datetime.now() - learning_session.start_time
                    learning_session.duration_seconds = int(duration.total_seconds())
                
                learning_session.end_time = datetime.now()
                learning_session.status = 'completed'
                
                session.commit()
                
                # 清理缓存
                self.cache.delete(TeachingCacheKeys.LEARNING_SESSION, session_key)
                
                logger.info(f"Learning session ended: {session_key}")
                return True
                
        except Exception as e:
            logger.error(f"End learning session error: {e}")
            return False
    
    def get_user_sessions(self, user_id: int, limit: int = 10, status: str = None) -> List[Dict[str, Any]]:
        """获取用户的学习会话列表"""
        try:
            with db_manager.get_session() as session:
                from ..database.models import LearningSession
                
                query = session.query(LearningSession).filter(
                    LearningSession.user_id == user_id
                )
                
                if status:
                    query = query.filter(LearningSession.status == status)
                
                sessions = query.order_by(
                    LearningSession.start_time.desc()
                ).limit(limit).all()
                
                return [s.to_dict() for s in sessions]
                
        except Exception as e:
            logger.error(f"Get user sessions error: {e}")
            return []
    
    def get_session_statistics(self, session_key: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            session_data = self.get_session(session_key)
            if not session_data:
                return {}
            
            chat_history = session_data.get('chat_history', [])
            metadata = session_data.get('session_metadata', {})
            
            stats = {
                "total_messages": len(chat_history),
                "ai_proactive_count": metadata.get("ai_proactive_count", 0),
                "user_response_count": metadata.get("user_response_count", 0),
                "session_duration": session_data.get('duration_seconds'),
                "start_time": session_data.get('start_time'),
                "end_time": session_data.get('end_time'),
                "status": session_data.get('status')
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Get session statistics error: {e}")
            return {}
    
    def cleanup_expired_sessions(self, hours_old: int = 24) -> int:
        """清理过期的会话"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_old)
            
            with db_manager.get_session() as session:
                from ..database.models import LearningSession
                
                # 查找过期的活跃会话
                expired_sessions = session.query(LearningSession).filter(
                    LearningSession.status == 'active',
                    LearningSession.start_time < cutoff_time
                ).all()
                
                count = 0
                for expired_session in expired_sessions:
                    expired_session.status = 'expired'
                    expired_session.end_time = datetime.now()
                    count += 1
                
                session.commit()
                
                logger.info(f"Cleaned up {count} expired sessions")
                return count
                
        except Exception as e:
            logger.error(f"Cleanup expired sessions error: {e}")
            return 0


# 全局学习会话服务实例
learning_session_service = LearningSessionService() 