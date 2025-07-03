"""
SQLAlchemy数据库模型定义
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
import json
from enum import Enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float, Enum as SQLAEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class UserRole(Enum):
    """用户角色枚举"""
    STUDENT = "student"  # 学生
    ADMIN = "admin"      # 平台管理员
    PARENT = "parent"    # 家长（未来扩展）


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), index=True)
    password_hash = Column(String(255))
    
    # 用户角色相关字段
    role = Column(SQLAEnum(UserRole), default=UserRole.STUDENT, nullable=False, index=True)
    
    # 学生特有字段
    grade_level = Column(String(20))  # 年级：如"小学三年级"、"初中一年级"
    parent_contact = Column(String(100))  # 家长联系方式
    learning_preferences = Column(JSON, default=dict)  # 学习偏好设置
    
    # 通用字段
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # 关系
    learning_sessions = relationship("LearningSession", back_populates="user")
    learning_records = relationship("LearningRecord", back_populates="user")
    teaching_sessions = relationship("UserTeachingSession", back_populates="user")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value if self.role else None,
            'grade_level': self.grade_level,
            'parent_contact': self.parent_contact,
            'learning_preferences': self.learning_preferences,
            'preferences': self.preferences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }
    
    def is_student(self) -> bool:
        """判断是否为学生用户"""
        return self.role == UserRole.STUDENT
    
    def is_admin(self) -> bool:
        """判断是否为管理员用户"""
        return self.role == UserRole.ADMIN
    
    def is_parent(self) -> bool:
        """判断是否为家长用户"""
        return self.role == UserRole.PARENT


class SubjectType(Enum):
    """学科类型枚举"""
    MATH = "math"           # 数学
    CHINESE = "chinese"     # 语文
    ENGLISH = "english"     # 英语
    PHYSICS = "physics"     # 物理
    CHEMISTRY = "chemistry" # 化学
    BIOLOGY = "biology"     # 生物
    HISTORY = "history"     # 历史
    GEOGRAPHY = "geography" # 地理


class Course(Base):
    """课程表 - AI教学课程"""
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    subject = Column(SQLAEnum(SubjectType), nullable=False, index=True)
    grade_level = Column(String(20), nullable=False, index=True)  # 适用年级
    difficulty_level = Column(Integer, default=1, index=True)     # 难度等级 1-5
    
    # AI教学相关字段
    ai_teacher_prompt = Column(Text)  # AI教师的系统提示词
    teaching_objectives = Column(JSON, default=list)  # 教学目标列表
    knowledge_points = Column(JSON, default=list)     # 知识点列表
    teaching_materials = Column(JSON, default=dict)   # 教学素材（文档、图片等）
    
    # 基础字段
    description = Column(Text)
    content_data = Column(JSON, default=dict)  # 课程内容数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # 关系
    learning_sessions = relationship("LearningSession", back_populates="course")
    learning_records = relationship("LearningRecord", back_populates="course")
    teaching_sessions = relationship("UserTeachingSession", back_populates="course")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject.value if self.subject else None,
            'grade_level': self.grade_level,
            'difficulty_level': self.difficulty_level,
            'ai_teacher_prompt': self.ai_teacher_prompt,
            'teaching_objectives': self.teaching_objectives,
            'knowledge_points': self.knowledge_points,
            'teaching_materials': self.teaching_materials,
            'description': self.description,
            'content_data': self.content_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
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
        
        # 🔧 修复SQLAlchemy JSON列更新问题：创建新列表而不是直接修改
        new_history = list(self.chat_history)
        new_history.append(message)
        
        # 限制历史记录长度，避免数据过大
        if len(new_history) > 1000:
            new_history = new_history[-500:]  # 保留最近500条
        
        # 替换整个列表以触发SQLAlchemy的change tracking
        self.chat_history = new_history


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


class UserTeachingSession(Base):
    """用户教学会话表 - 融合用户系统和教学系统"""
    __tablename__ = 'user_teaching_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False, index=True)
    session_key = Column(String(255), unique=True, nullable=False, index=True)  # 会话唯一标识
    
    # 会话状态
    status = Column(SQLAEnum('active', 'paused', 'completed', name='session_status'), default='active', index=True)
    current_stage = Column(String(50), default='greeting', index=True)  # greeting, teaching, practice, assessment
    
    # 时间信息
    start_time = Column(DateTime, default=func.now(), index=True)
    last_activity = Column(DateTime, default=func.now())
    end_time = Column(DateTime)  # 会话结束时间
    total_duration = Column(Integer, default=0)  # 总学习时长（秒）
    
    # 学习数据
    chat_history = Column(JSON, default=list)  # 对话历史
    learning_progress = Column(JSON, default=dict)  # 学习进度
    achievements = Column(JSON, default=list)  # 学习成就
    session_summary = Column(Text)  # 会话总结
    
    # 个性化设置
    ai_teacher_config = Column(JSON, default=dict)  # AI教师配置
    personalized_prompts = Column(JSON, default=dict)  # 个性化提示词
    user_preferences = Column(JSON, default=dict)  # 用户在此会话中的偏好
    
    # 统计数据
    message_count = Column(Integer, default=0)  # 消息总数
    ai_response_count = Column(Integer, default=0)  # AI响应次数
    avg_response_time = Column(Float, default=0.0)  # 平均响应时间
    user_satisfaction = Column(Float)  # 用户满意度评分
    
    # 元数据
    session_metadata = Column(JSON, default=dict)  # 会话元数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="teaching_sessions")
    course = relationship("Course", back_populates="teaching_sessions")
    interactions = relationship("TeachingInteraction", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'course_id': self.course_id,
            'session_key': self.session_key,
            'status': self.status,
            'current_stage': self.current_stage,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_duration': self.total_duration,
            'chat_history': self.chat_history or [],
            'learning_progress': self.learning_progress or {},
            'achievements': self.achievements or [],
            'session_summary': self.session_summary,
            'ai_teacher_config': self.ai_teacher_config or {},
            'personalized_prompts': self.personalized_prompts or {},
            'user_preferences': self.user_preferences or {},
            'message_count': self.message_count,
            'ai_response_count': self.ai_response_count,
            'avg_response_time': self.avg_response_time,
            'user_satisfaction': self.user_satisfaction,
            'session_metadata': self.session_metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def add_chat_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加聊天消息到历史记录"""
        if not self.chat_history:
            self.chat_history = []
        
        message = {
            'role': role,  # 'human', 'avatar', 'system'
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # 创建新列表以触发SQLAlchemy的change tracking
        new_history = list(self.chat_history)
        new_history.append(message)
        
        # 限制历史记录长度
        if len(new_history) > 1000:
            new_history = new_history[-500:]  # 保留最近500条
        
        self.chat_history = new_history
        self.message_count = len(new_history)
        
        # 更新AI响应计数
        if role == 'avatar':
            self.ai_response_count += 1
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()
    
    def calculate_duration(self):
        """计算会话总时长"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.total_duration = int(delta.total_seconds())
        elif self.start_time:
            delta = datetime.now() - self.start_time
            self.total_duration = int(delta.total_seconds())


class TeachingInteraction(Base):
    """教学互动记录表 - 详细的教学交互数据"""
    __tablename__ = 'teaching_interactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('user_teaching_sessions.id'), nullable=False, index=True)
    
    # 互动内容
    user_input = Column(Text, nullable=False)  # 用户输入
    ai_response = Column(Text, nullable=False)  # AI回复
    interaction_type = Column(String(50), default='normal', index=True)  # normal, question, practice, assessment, greeting
    
    # 元数据
    timestamp = Column(DateTime, default=func.now(), index=True)
    response_time = Column(Float)  # AI响应时间（毫秒）
    user_engagement = Column(Float)  # 用户参与度评分 0-1
    
    # 教学数据
    knowledge_points = Column(JSON, default=list)  # 涉及的知识点
    difficulty_level = Column(Integer, default=3)  # 当前难度等级 1-5
    correctness_score = Column(Float)  # 正确性评分 0-1（如果适用）
    learning_effectiveness = Column(Float)  # 学习效果评分 0-1
    
    # AI分析数据
    sentiment_score = Column(Float)  # 情感评分 -1到1
    comprehension_level = Column(Float)  # 理解程度 0-1
    engagement_indicators = Column(JSON, default=dict)  # 参与度指标
    
    # 上下文信息
    context_data = Column(JSON, default=dict)  # 上下文数据
    system_prompt_used = Column(Text)  # 使用的系统提示词
    model_parameters = Column(JSON, default=dict)  # 模型参数
    
    # 元数据
    interaction_metadata = Column(JSON, default=dict)  # 交互元数据
    created_at = Column(DateTime, default=func.now())
    
    # 关系
    session = relationship("UserTeachingSession", back_populates="interactions")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_input': self.user_input,
            'ai_response': self.ai_response,
            'interaction_type': self.interaction_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'response_time': self.response_time,
            'user_engagement': self.user_engagement,
            'knowledge_points': self.knowledge_points or [],
            'difficulty_level': self.difficulty_level,
            'correctness_score': self.correctness_score,
            'learning_effectiveness': self.learning_effectiveness,
            'sentiment_score': self.sentiment_score,
            'comprehension_level': self.comprehension_level,
            'engagement_indicators': self.engagement_indicators or {},
            'context_data': self.context_data or {},
            'system_prompt_used': self.system_prompt_used,
            'model_parameters': self.model_parameters or {},
            'interaction_metadata': self.interaction_metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        } 