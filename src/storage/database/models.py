"""
SQLAlchemy数据库模型定义
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
import json

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), index=True)
    password_hash = Column(String(255))
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # 关系
    learning_sessions = relationship("LearningSession", back_populates="user")
    learning_records = relationship("LearningRecord", back_populates="user")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'preferences': self.preferences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }


class Course(Base):
    """课程表"""
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    subject = Column(String(50), nullable=False, index=True)
    difficulty_level = Column(Integer, default=1, index=True)
    description = Column(Text)
    content_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    
    # 关系
    learning_sessions = relationship("LearningSession", back_populates="course")
    learning_records = relationship("LearningRecord", back_populates="course")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'difficulty_level': self.difficulty_level,
            'description': self.description,
            'content_data': self.content_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }


class LearningSession(Base):
    """学习会话表"""
    __tablename__ = "learning_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey('courses.id'), index=True)
    session_key = Column(String(64), unique=True, nullable=False, index=True)
    start_time = Column(DateTime, default=func.now(), index=True)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    chat_history = Column(JSON, default=list)
    session_metadata = Column(JSON, default=dict)
    status = Column(String(20), default='active', index=True)
    
    # 关系
    user = relationship("User", back_populates="learning_sessions")
    course = relationship("Course", back_populates="learning_sessions")
    learning_records = relationship("LearningRecord", back_populates="session")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'course_id': self.course_id,
            'session_key': self.session_key,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'chat_history': self.chat_history,
            'session_metadata': self.session_metadata,
            'status': self.status
        }
    
    def add_chat_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加聊天消息到历史记录"""
        if not self.chat_history:
            self.chat_history = []
        
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.chat_history.append(message)
        
        # 限制历史记录长度，避免数据过大
        if len(self.chat_history) > 1000:
            self.chat_history = self.chat_history[-500:]  # 保留最近500条


class AICache(Base):
    """AI处理结果缓存表"""
    __tablename__ = "ai_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    cache_type = Column(String(50), nullable=False, index=True)  # 'asr', 'tts', 'avatar', 'llm'
    input_hash = Column(String(64), nullable=False, index=True)
    output_data = Column(JSON)
    file_path = Column(Text)  # MinIO对象路径
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, index=True)
    access_count = Column(Integer, default=0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'cache_key': self.cache_key,
            'cache_type': self.cache_type,
            'input_hash': self.input_hash,
            'output_data': self.output_data,
            'file_path': self.file_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'access_count': self.access_count
        }
    
    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return self.expires_at and datetime.now() > self.expires_at


class LearningRecord(Base):
    """用户学习记录表"""
    __tablename__ = "learning_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey('courses.id'), index=True)
    session_id = Column(Integer, ForeignKey('learning_sessions.id'), index=True)
    interaction_type = Column(String(50), index=True)  # 'question', 'answer', 'correction'
    content_text = Column(Text)
    ai_response = Column(Text)
    timestamp = Column(DateTime, default=func.now(), index=True)
    record_metadata = Column(JSON, default=dict)
    
    # 关系
    user = relationship("User", back_populates="learning_records")
    course = relationship("Course", back_populates="learning_records")
    session = relationship("LearningSession", back_populates="learning_records")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'course_id': self.course_id,
            'session_id': self.session_id,
            'interaction_type': self.interaction_type,
            'content_text': self.content_text,
            'ai_response': self.ai_response,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.record_metadata
        }


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(JSON)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 