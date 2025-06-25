"""
用户管理服务
"""
import hashlib
import secrets
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database.connection import db_manager
from ..cache.redis_client import cache_manager, TeachingCacheKeys

logger = logging.getLogger(__name__)


class UserService:
    """用户管理服务"""
    
    def __init__(self):
        self.cache = cache_manager
        self.session_ttl = 1800  # 30分钟会话过期
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        # 生成随机盐
        salt = secrets.token_hex(32)
        # 使用PBKDF2进行哈希
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        # 返回盐+哈希的组合
        return f"{salt}:{pwd_hash.hex()}"
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        try:
            salt, pwd_hash = hashed.split(':')
            return pwd_hash == hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        except ValueError:
            return False
    
    def _generate_session_token(self) -> str:
        """生成会话令牌"""
        return secrets.token_urlsafe(32)
    
    def create_user(self, username: str, email: Optional[str] = None, password: Optional[str] = None, 
                   preferences: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """创建新用户"""
        try:
            # 延迟导入避免循环引用
            from ..database.models import User
            
            with db_manager.get_session() as session:
                # 检查用户名是否已存在
                existing_user = session.query(User).filter(User.username == username).first()
                if existing_user:
                    logger.warning(f"Username already exists: {username}")
                    return None
                
                # 创建新用户
                user = User(
                    username=username,
                    email=email,
                    password_hash=self._hash_password(password) if password else None,
                    preferences=preferences or {},
                    created_at=datetime.now()
                )
                
                session.add(user)
                session.commit()
                session.refresh(user)
                
                logger.info(f"User created: {username} (ID: {user.id})")
                return user.to_dict()
                
        except IntegrityError as e:
            logger.error(f"User creation failed - integrity error: {e}")
            return None
        except Exception as e:
            logger.error(f"User creation failed: {e}")
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """用户认证"""
        try:
            # 延迟导入避免循环引用
            from ..database.models import User
            
            with db_manager.get_session() as session:
                user = session.query(User).filter(
                    User.username == username,
                    User.is_active == True
                ).first()
                
                if not user or not user.password_hash:
                    logger.warning(f"Authentication failed: user not found or no password - {username}")
                    return None
                
                if not self._verify_password(password, user.password_hash):
                    logger.warning(f"Authentication failed: invalid password - {username}")
                    return None
                
                # 更新最后登录时间
                user.last_login = datetime.now()
                session.commit()
                
                # 生成会话令牌
                session_token = self._generate_session_token()
                
                # 缓存用户会话
                self.cache.set(
                    TeachingCacheKeys.USER_SESSION,
                    session_token,
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "login_time": datetime.now().isoformat(),
                        "preferences": user.preferences
                    },
                    ttl=self.session_ttl
                )
                
                user_data = user.to_dict()
                user_data["session_token"] = session_token
                
                logger.info(f"User authenticated: {username}")
                return user_data
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_user_by_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """通过会话令牌获取用户信息"""
        try:
            # 先从缓存获取
            session_data = self.cache.get(TeachingCacheKeys.USER_SESSION, session_token)
            if session_data:
                # 延长会话时间
                self.cache.expire(TeachingCacheKeys.USER_SESSION, session_token, self.session_ttl)
                return session_data
            
            logger.warning(f"Session not found or expired: {session_token[:10]}...")
            return None
            
        except Exception as e:
            logger.error(f"Get user by session error: {e}")
            return None
    
    def get_user_by_id(self, user_id: int, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """通过ID获取用户信息"""
        try:
            # 延迟导入避免循环引用
            from ..database.models import User
            
            # 尝试从缓存获取
            if use_cache:
                cached_user = self.cache.get(TeachingCacheKeys.USER_PROFILE, str(user_id))
                if cached_user:
                    return cached_user
            
            # 从数据库获取
            with db_manager.get_session() as session:
                user = session.query(User).filter(
                    User.id == user_id,
                    User.is_active == True
                ).first()
                
                if not user:
                    return None
                
                user_data = user.to_dict()
                
                # 缓存用户信息
                if use_cache:
                    self.cache.set(
                        TeachingCacheKeys.USER_PROFILE,
                        str(user_id),
                        user_data,
                        ttl=3600  # 1小时
                    )
                
                return user_data
                
        except Exception as e:
            logger.error(f"Get user by ID error: {e}")
            return None
    
    def update_user_preferences(self, user_id: int, preferences: Dict[str, Any]) -> bool:
        """更新用户偏好设置"""
        try:
            # 延迟导入避免循环引用
            from ..database.models import User
            
            with db_manager.get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False
                
                # 更新偏好设置
                user.preferences = {**(user.preferences or {}), **preferences}
                session.commit()
                
                # 清理缓存
                self.cache.delete(TeachingCacheKeys.USER_PROFILE, str(user_id))
                
                logger.info(f"User preferences updated: {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Update user preferences error: {e}")
            return False
    
    def logout_user(self, session_token: str) -> bool:
        """用户登出"""
        try:
            # 删除会话缓存
            self.cache.delete(TeachingCacheKeys.USER_SESSION, session_token)
            logger.info(f"User logged out: {session_token[:10]}...")
            return True
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    def get_user_learning_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户学习统计信息"""
        try:
            with db_manager.get_session() as session:
                from ..database.models import LearningSession, LearningRecord
                
                # 学习会话统计
                total_sessions = session.query(LearningSession).filter(
                    LearningSession.user_id == user_id
                ).count()
                
                # 学习记录统计
                total_records = session.query(LearningRecord).filter(
                    LearningRecord.user_id == user_id
                ).count()
                
                # 最近会话
                recent_session = session.query(LearningSession).filter(
                    LearningSession.user_id == user_id
                ).order_by(LearningSession.start_time.desc()).first()
                
                stats = {
                    "total_sessions": total_sessions,
                    "total_interactions": total_records,
                    "last_session": recent_session.start_time.isoformat() if recent_session else None,
                    "total_study_time": 0  # TODO: 计算总学习时间
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Get user learning stats error: {e}")
            return {}
    
    def list_users(self, limit: int = 50, offset: int = 0, active_only: bool = True) -> List[Dict[str, Any]]:
        """获取用户列表"""
        try:
            with db_manager.get_session() as session:
                query = session.query(User)
                
                if active_only:
                    query = query.filter(User.is_active == True)
                
                users = query.offset(offset).limit(limit).all()
                
                return [user.to_dict() for user in users]
                
        except Exception as e:
            logger.error(f"List users error: {e}")
            return []
    
    def deactivate_user(self, user_id: int) -> bool:
        """停用用户"""
        try:
            with db_manager.get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False
                
                user.is_active = False
                session.commit()
                
                # 清理缓存
                self.cache.delete(TeachingCacheKeys.USER_PROFILE, str(user_id))
                
                logger.info(f"User deactivated: {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Deactivate user error: {e}")
            return False


# 全局用户服务实例
user_service = UserService() 