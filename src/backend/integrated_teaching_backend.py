#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融合教学后端 - 整合用户系统和教学系统
基于现有的PostgreSQL + Redis + MinIO存储架构
"""

import time
import threading
import queue
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

# 导入现有的教学后端和存储服务
from .teaching_backend import TeachingBackend
from ..storage.services.user_service import user_service
from ..storage.services.course_service import course_service
from ..storage.services.learning_session_service import learning_session_service
from ..storage.database.models import UserTeachingSession, TeachingInteraction
from ..storage.database.connection import db_manager
from ..storage.cache.redis_client import cache_manager


class PersonalizedTeachingEngine:
    """个性化教学引擎"""
    
    def generate_personalized_prompt(self, user_data: Dict, course: Dict) -> str:
        """根据用户数据生成个性化教学提示"""
        
        # 基础信息
        grade_level = user_data.get("grade_level", "小学三年级")
        learning_preferences = user_data.get("learning_preferences", {})
        
        # 学习风格适配
        learning_style = learning_preferences.get("learning_style", "混合型")
        style_prompts = {
            "视觉型": "多使用图表、图像描述和视觉化例子，强调色彩和空间关系",
            "听觉型": "重点进行语音表达和听力练习，使用韵律和节拍",
            "动觉型": "设计互动练习和实践活动，鼓励动手操作",
            "混合型": "综合使用多种教学方式，灵活调整教学策略"
        }
        
        # 难度偏好
        difficulty_pref = learning_preferences.get("difficulty_preference", 3)
        difficulty_guidance = {
            1: "使用最简单的词汇和句型，重点关注基础概念，循序渐进",
            2: "适当增加词汇量，引入简单的语法结构，保持耐心", 
            3: "平衡难度，循序渐进地提高要求，适度挑战",
            4: "增加挑战性，引入更复杂的概念，培养深度思考",
            5: "使用高级词汇和复杂结构，注重批判性思维和创新"
        }
        
        # 喜欢的学科
        favorite_subjects = learning_preferences.get("favorite_subjects", [])
        subject_connections = ""
        if favorite_subjects:
            subject_connections = f"可以结合学生喜欢的{', '.join(favorite_subjects)}学科进行跨学科教学，增强学习兴趣。"
        
        # 生成个性化提示
        prompt = f"""你是一位专业的AI教师，正在为{grade_level}的学生教授{course['subject']} - {course['name']}。

学生画像：
- 年级水平：{grade_level}
- 学习风格：{learning_style} - {style_prompts.get(learning_style, '')}
- 难度偏好：{difficulty_pref}/5 - {difficulty_guidance.get(difficulty_pref, '')}
- 兴趣学科：{', '.join(favorite_subjects) if favorite_subjects else '暂无特别偏好'}

课程信息：
- 课程名称：{course['name']}
- 学科类型：{course['subject']}
- 课程难度：{course.get('difficulty_level', 3)}/5
- 教学目标：{', '.join(course.get('teaching_objectives', []))}
- 核心知识点：{', '.join(course.get('knowledge_points', []))}

个性化教学策略：
1. 根据{learning_style}学习风格调整教学方法
2. 严格按照难度偏好{difficulty_pref}/5控制内容复杂度
3. {subject_connections}
4. 保持亲切、耐心、鼓励的教学态度
5. 每次回答控制在2-3句话，保持高度互动性
6. 注重启发式教学，多用提问引导学生主动思考
7. 及时给予正面反馈，建立学习信心

请严格按照学生的个性化特点进行教学，确保教学内容和方式完全适合这位学生。
"""
        return prompt.strip()
    
    def generate_welcome_message(self, user_data: Dict, course: Dict) -> str:
        """生成个性化欢迎消息"""
        grade_level = user_data.get("grade_level", "同学")
        username = user_data.get("username", "同学")
        
        welcome_templates = [
            f"你好{username}！我是你的AI老师小慧。今天我们来学习《{course['name']}》，我会根据你{grade_level}的水平来调整教学内容。准备好开始这次有趣的学习之旅了吗？",
            f"欢迎{username}！很高兴能为你上《{course['name']}》课程。作为{grade_level}的学生，我会用最适合你的方式来讲解。有什么问题随时告诉我哦！",
            f"Hi {username}！今天我们要探索《{course['name']}》的精彩世界。我会根据你的学习特点来设计课程内容，让学习变得轻松有趣。我们开始吧！"
        ]
        
        # 根据用户ID选择模板，保证一致性
        template_index = hash(user_data.get("id", 0)) % len(welcome_templates)
        return welcome_templates[template_index]
    
    def get_recommended_next_topics(self, user_id: int, current_course_id: int) -> List[Dict]:
        """基于学习进度推荐下一个学习主题"""
        try:
            # 获取用户学习历史
            learning_stats = user_service.get_user_learning_stats(user_id)
            
            # 获取当前课程信息
            current_course = course_service.get_course_by_id(current_course_id)
            if not current_course:
                return []
            
            recommendations = []
            
            # 1. 同学科进阶课程推荐
            advanced_courses = course_service.get_courses_by_subject_and_difficulty(
                current_course['subject'], 
                min_difficulty=current_course['difficulty_level'] + 1
            )
            
            for course in advanced_courses[:2]:  # 限制数量
                recommendations.append({
                    "course": course,
                    "reason": "学科进阶",
                    "confidence": 0.9,
                    "recommendation_type": "advanced"
                })
            
            # 2. 相关难度课程推荐
            similar_courses = course_service.get_courses_by_difficulty(
                current_course['difficulty_level']
            )
            
            for course in similar_courses:
                if course['id'] != current_course_id and course['subject'] != current_course['subject']:
                    recommendations.append({
                        "course": course,
                        "reason": "相似难度",
                        "confidence": 0.7,
                        "recommendation_type": "similar"
                    })
                    if len(recommendations) >= 4:  # 控制总数
                        break
            
            # 3. 基于用户兴趣推荐
            user_data = user_service.get_user_by_id(user_id)
            if user_data:
                favorite_subjects = user_data.get('learning_preferences', {}).get('favorite_subjects', [])
                
                for subject in favorite_subjects:
                    if subject != current_course['subject']:
                        subject_courses = course_service.get_courses_by_subject(subject)
                        for course in subject_courses[:1]:  # 每个学科推荐1个
                            recommendations.append({
                                "course": course,
                                "reason": "兴趣匹配",
                                "confidence": 0.8,
                                "recommendation_type": "interest"
                            })
            
            # 按置信度排序并去重
            seen_courses = set()
            filtered_recommendations = []
            
            for rec in sorted(recommendations, key=lambda x: x['confidence'], reverse=True):
                course_id = rec['course']['id']
                if course_id not in seen_courses:
                    seen_courses.add(course_id)
                    filtered_recommendations.append(rec)
                    
                if len(filtered_recommendations) >= 5:  # 最多返回5个推荐
                    break
            
            return filtered_recommendations
            
        except Exception as e:
            logger.error(f"Failed to get recommendations for user {user_id}: {e}")
            return []


class MultiUserTeachingManager:
    """多用户教学管理器 - 支持并发教学会话"""
    
    def __init__(self):
        self.user_backends = {}  # {user_id: TeachingBackend实例}
        self.session_locks = {}  # {user_id: threading.Lock}
        self.teaching_sessions = {}  # {user_id: UserTeachingSession}
        self.personalized_engine = PersonalizedTeachingEngine()
        
    def get_user_backend(self, user_id: int) -> TeachingBackend:
        """获取或创建用户专属的教学后端"""
        if user_id not in self.user_backends:
            # 为每个用户创建独立的教学后端
            backend = TeachingBackend()
            backend.current_user_id = user_id
            backend.real_chat_queue = queue.Queue()  # 独立的消息队列
            backend.session_state = self._init_user_session_state(user_id)
            
            # 设置用户专属的前端更新回调
            backend.set_frontend_update_callback(
                lambda: self._trigger_user_frontend_update(user_id)
            )
            
            self.user_backends[user_id] = backend
            self.session_locks[user_id] = threading.Lock()
            
            logger.info(f"Created teaching backend for user {user_id}")
            
        return self.user_backends[user_id]
    
    def _init_user_session_state(self, user_id: int) -> Dict:
        """初始化用户会话状态"""
        return {
            "user_id": user_id,
            "course": None,
            "difficulty": None, 
            "goal": None,
            "stage": "init",  # init, greeting, waiting_user_input, teaching, practice
            "ai_teaching_active": False,
            "last_user_activity": time.time(),
            "message_count": 0,
            "session_start_time": time.time()
        }
    
    def _trigger_user_frontend_update(self, user_id: int):
        """触发特定用户的前端更新"""
        # 这里可以实现用户专属的前端更新逻辑
        # 例如通过WebSocket推送给特定用户
        logger.debug(f"Frontend update triggered for user {user_id}")
    
    def create_teaching_session(self, user_id: int, course_id: int, session_token: str) -> Dict:
        """为用户创建教学会话"""
        try:
            with self.session_locks.get(user_id, threading.Lock()):
                # 验证用户
                user_data = user_service.get_user_by_id(user_id)
                if not user_data:
                    raise ValueError("User not found")
                
                # 验证课程
                course = course_service.get_course_by_id(course_id)
                if not course:
                    raise ValueError("Course not found")
                
                # 检查用户权限（年级匹配等）
                if not self._check_course_permission(user_data, course):
                    raise PermissionError("Course access denied for this grade level")
                
                # 获取用户教学后端
                backend = self.get_user_backend(user_id)
                
                # 生成会话key
                session_key = f"teaching_{user_id}_{course_id}_{int(time.time())}"
                
                # 创建数据库记录
                session_data = {
                    "user_id": user_id,
                    "course_id": course_id,
                    "session_key": session_key,
                    "status": "active",
                    "current_stage": "greeting",
                    "ai_teacher_config": {},
                    "user_preferences": user_data.get("learning_preferences", {}),
                    "session_metadata": {
                        "session_token": session_token,
                        "created_by_api": True
                    }
                }
                
                # 保存到数据库
                with db_manager.get_session() as db_session:
                    teaching_session = UserTeachingSession(**session_data)
                    db_session.add(teaching_session)
                    db_session.flush()  # 获取ID
                    
                    session_id = teaching_session.id
                    
                # 缓存到Redis
                cache_key = f"teaching_session:{user_id}"
                cache_manager.setex(cache_key, 3600, json.dumps({
                    "session_id": session_id,
                    "session_key": session_key,
                    "course_id": course_id,
                    "status": "active"
                }))
                
                # 保存到内存
                self.teaching_sessions[user_id] = teaching_session
                
                # 更新教学后端状态
                backend.current_course = course['name']
                backend.current_difficulty = f"Level {course['difficulty_level']}"
                backend.current_goal = "个性化教学"
                backend.session_state.update({
                    "course": course['name'],
                    "difficulty": course['difficulty_level'],
                    "stage": "greeting"
                })
                
                # 生成个性化欢迎消息
                welcome_message = self.personalized_engine.generate_welcome_message(
                    user_data, course
                )
                
                logger.info(f"Teaching session created: {session_key} for user {user_id}")
                
                return {
                    "session_id": session_id,
                    "session_key": session_key,
                    "course_info": course,
                    "user_info": {
                        "username": user_data["username"],
                        "grade_level": user_data.get("grade_level"),
                        "learning_preferences": user_data.get("learning_preferences", {})
                    },
                    "welcome_message": welcome_message,
                    "personalized_settings": session_data["user_preferences"],
                    "status": "created"
                }
                
        except Exception as e:
            logger.error(f"Failed to create teaching session for user {user_id}: {e}")
            raise
    
    def _check_course_permission(self, user_data: Dict, course: Dict) -> bool:
        """检查用户是否有权限访问课程"""
        # 基础权限检查
        if not user_data.get("is_active", True):
            return False
        
        # 年级匹配检查（可以根据需要扩展）
        user_grade = user_data.get("grade_level", "")
        course_grade = course.get("grade_level", "")
        
        # 简单的年级匹配逻辑，可以根据需要完善
        if course_grade and user_grade:
            # 这里可以实现更复杂的年级匹配逻辑
            pass
        
        return True
    
    def process_user_message(self, user_id: int, message: str, session_key: str) -> Dict:
        """处理特定用户的消息"""
        try:
            with self.session_locks.get(user_id, threading.Lock()):
                # 获取教学会话
                teaching_session = self.teaching_sessions.get(user_id)
                if not teaching_session or teaching_session.session_key != session_key:
                    raise ValueError("Invalid teaching session")
                
                # 获取用户和课程信息
                user_data = user_service.get_user_by_id(user_id)
                course = course_service.get_course_by_id(teaching_session.course_id)
                
                if not user_data or not course:
                    raise ValueError("User or course not found")
                
                # 获取用户教学后端
                backend = self.get_user_backend(user_id)
                
                # 生成个性化系统提示
                personalized_prompt = self.personalized_engine.generate_personalized_prompt(
                    user_data, course
                )
                
                # 更新LLM配置以使用个性化提示
                if backend.llm_config:
                    backend.llm_config['system_prompt'] = personalized_prompt
                
                # 获取对话历史
                chat_history = backend.get_real_chat_messages()
                
                # 记录开始时间
                start_time = time.time()
                
                # 生成AI响应
                response = backend.generate_teaching_response(
                    message, 
                    course['name'], 
                    f"Level {course['difficulty_level']}", 
                    chat_history
                )
                
                # 计算响应时间
                response_time = (time.time() - start_time) * 1000  # 毫秒
                
                # 更新会话消息
                backend._add_real_chat_message('human', message)
                backend._add_real_chat_message('avatar', response)
                
                # 保存到数据库
                self._save_interaction(teaching_session.id, message, response, response_time, personalized_prompt)
                
                # 更新会话活动时间
                self._update_session_activity(teaching_session)
                
                # 获取推荐内容
                recommendations = self.personalized_engine.get_recommended_next_topics(
                    user_id, teaching_session.course_id
                )
                
                return {
                    "response": response,
                    "chat_history": backend.get_real_chat_messages(),
                    "recommendations": recommendations,
                    "response_time": response_time,
                    "session_info": {
                        "stage": teaching_session.current_stage,
                        "message_count": teaching_session.message_count + 2,  # +1 user +1 ai
                        "duration": int(time.time() - teaching_session.start_time.timestamp())
                    },
                    "status": "success"
                }
                
        except Exception as e:
            logger.error(f"Failed to process message for user {user_id}: {e}")
            raise
    
    def _save_interaction(self, session_id: int, user_input: str, ai_response: str, 
                         response_time: float, system_prompt: str):
        """保存教学互动记录"""
        try:
            with db_manager.get_session() as db_session:
                interaction = TeachingInteraction(
                    session_id=session_id,
                    user_input=user_input,
                    ai_response=ai_response,
                    interaction_type="normal",
                    response_time=response_time,
                    system_prompt_used=system_prompt,
                    model_parameters={"temperature": 0.7, "max_tokens": 1024}
                )
                db_session.add(interaction)
                
                # 同时更新会话的消息计数
                session = db_session.query(UserTeachingSession).filter_by(id=session_id).first()
                if session:
                    session.message_count += 2  # user + ai
                    session.ai_response_count += 1
                    session.last_activity = datetime.now()
                    
                    # 更新平均响应时间
                    if session.avg_response_time == 0:
                        session.avg_response_time = response_time
                    else:
                        session.avg_response_time = (session.avg_response_time + response_time) / 2
                
        except Exception as e:
            logger.error(f"Failed to save interaction for session {session_id}: {e}")
    
    def _update_session_activity(self, teaching_session):
        """更新会话活动时间"""
        teaching_session.update_activity()
        
        # 更新缓存
        cache_key = f"teaching_session:{teaching_session.user_id}"
        cached_data = cache_manager.get(cache_key)
        if cached_data:
            session_data = json.loads(cached_data)
            session_data["last_activity"] = datetime.now().isoformat()
            cache_manager.setex(cache_key, 3600, json.dumps(session_data))
    
    def get_user_session_status(self, user_id: int) -> Optional[Dict]:
        """获取用户会话状态"""
        try:
            # 先从缓存获取
            cache_key = f"teaching_session:{user_id}"
            cached_data = cache_manager.get(cache_key)
            
            if cached_data:
                session_data = json.loads(cached_data)
                
                # 从数据库获取详细信息
                with db_manager.get_session() as db_session:
                    session = db_session.query(UserTeachingSession).filter_by(
                        id=session_data["session_id"]
                    ).first()
                    
                    if session:
                        return {
                            "session_key": session.session_key,
                            "status": session.status,
                            "current_stage": session.current_stage,
                            "course_info": course_service.get_course_by_id(session.course_id),
                            "message_count": session.message_count,
                            "duration": session.total_duration,
                            "last_activity": session.last_activity.isoformat() if session.last_activity else None
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session status for user {user_id}: {e}")
            return None
    
    def end_teaching_session(self, user_id: int, session_key: str) -> bool:
        """结束教学会话"""
        try:
            with self.session_locks.get(user_id, threading.Lock()):
                # 更新数据库
                with db_manager.get_session() as db_session:
                    session = db_session.query(UserTeachingSession).filter_by(
                        user_id=user_id,
                        session_key=session_key
                    ).first()
                    
                    if session:
                        session.status = 'completed'
                        session.end_time = datetime.now()
                        session.calculate_duration()
                        
                        # 生成会话总结
                        session.session_summary = self._generate_session_summary(session)
                
                # 清理缓存
                cache_key = f"teaching_session:{user_id}"
                cache_manager.delete(cache_key)
                
                # 清理内存
                if user_id in self.teaching_sessions:
                    del self.teaching_sessions[user_id]
                
                # 停止用户后端
                if user_id in self.user_backends:
                    backend = self.user_backends[user_id]
                    backend._stop_ai_teaching()
                    del self.user_backends[user_id]
                
                if user_id in self.session_locks:
                    del self.session_locks[user_id]
                
                logger.info(f"Teaching session ended: {session_key} for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to end teaching session for user {user_id}: {e}")
            return False
    
    def _generate_session_summary(self, session: UserTeachingSession) -> str:
        """生成会话总结"""
        try:
            course = course_service.get_course_by_id(session.course_id)
            course_name = course['name'] if course else "未知课程"
            
            summary = f"""学习会话总结
课程：{course_name}
时长：{session.total_duration // 60}分{session.total_duration % 60}秒
消息数：{session.message_count}条
AI回复：{session.ai_response_count}次
平均响应时间：{session.avg_response_time:.2f}ms
学习阶段：{session.current_stage}
"""
            return summary
        except Exception as e:
            logger.error(f"Failed to generate session summary: {e}")
            return "会话总结生成失败"


# 全局多用户教学管理器实例
multi_user_teaching_manager = MultiUserTeachingManager() 