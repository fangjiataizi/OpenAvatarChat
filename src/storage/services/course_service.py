"""
课程管理服务 - AI教学平台
"""
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database.connection import db_manager
from ..cache.redis_client import cache_manager
from ..cache import TeachingCacheKeys

logger = logging.getLogger(__name__)


class CourseService:
    """课程管理服务 - AI教学平台"""
    
    def __init__(self):
        self.cache = cache_manager
        try:
            self.cache.initialize()
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}")
    
    def create_course(self, name: str, subject: str, grade_level: str, 
                     difficulty_level: int = 1, description: Optional[str] = None,
                     ai_teacher_prompt: Optional[str] = None,
                     teaching_objectives: Optional[List[str]] = None,
                     knowledge_points: Optional[List[str]] = None,
                     teaching_materials: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """创建AI教学课程"""
        try:
            from ..database.models import Course, SubjectType
            
            # 验证学科类型
            try:
                subject_enum = SubjectType(subject)
            except ValueError:
                logger.error(f"Invalid subject type: {subject}")
                return None
            
            with db_manager.get_session() as session:
                # 生成默认AI教师提示词
                if not ai_teacher_prompt:
                    ai_teacher_prompt = self._generate_default_prompt(subject, grade_level)
                
                course = Course(
                    name=name,
                    subject=subject_enum,
                    grade_level=grade_level,
                    difficulty_level=difficulty_level,
                    description=description,
                    ai_teacher_prompt=ai_teacher_prompt,
                    teaching_objectives=teaching_objectives or [],
                    knowledge_points=knowledge_points or [],
                    teaching_materials=teaching_materials or {},
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                session.add(course)
                session.commit()
                session.refresh(course)
                
                logger.info(f"Course created: {name} (ID: {course.id})")
                
                # 清理相关缓存
                self._clear_course_cache(subject, grade_level)
                
                return course.to_dict()
                
        except Exception as e:
            logger.error(f"Course creation failed: {e}")
            return None
    
    def get_courses_by_grade_and_subject(self, grade_level: str, subject: Optional[str] = None) -> List[Dict[str, Any]]:
        """根据年级和学科获取课程列表"""
        try:
            from ..database.models import Course, SubjectType
            
            # 尝试从缓存获取
            cache_key = f"{grade_level}_{subject or 'all'}"
            cached_courses = self.cache.get(TeachingCacheKeys.COURSE_LIST, cache_key)
            if cached_courses:
                return cached_courses
            
            with db_manager.get_session() as session:
                query = session.query(Course).filter(
                    Course.grade_level == grade_level,
                    Course.is_active == True
                )
                
                if subject:
                    try:
                        subject_enum = SubjectType(subject)
                        query = query.filter(Course.subject == subject_enum)
                    except ValueError:
                        logger.warning(f"Invalid subject type: {subject}")
                        return []
                
                courses = query.order_by(Course.difficulty_level, Course.created_at).all()
                course_list = [course.to_dict() for course in courses]
                
                # 缓存结果
                self.cache.set(
                    TeachingCacheKeys.COURSE_LIST,
                    cache_key,
                    course_list,
                    ttl=3600  # 1小时
                )
                
                return course_list
                
        except Exception as e:
            logger.error(f"Get courses error: {e}")
            return []
    
    def get_available_subjects(self) -> List[Dict[str, Any]]:
        """获取可用的学科列表"""
        try:
            from ..database.models import SubjectType
            
            subjects = []
            for subject in SubjectType:
                subjects.append({
                    'value': subject.value,
                    'label': self._get_subject_label(subject.value),
                    'description': self._get_subject_description(subject.value)
                })
            
            return subjects
            
        except Exception as e:
            logger.error(f"Get subjects error: {e}")
            return []
    
    def get_course_by_id(self, course_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取课程详情"""
        try:
            from ..database.models import Course
            
            # 尝试从缓存获取
            cached_course = self.cache.get(TeachingCacheKeys.COURSE_DETAIL, str(course_id))
            if cached_course:
                return cached_course
            
            with db_manager.get_session() as session:
                course = session.query(Course).filter(
                    Course.id == course_id,
                    Course.is_active == True
                ).first()
                
                if not course:
                    return None
                
                course_data = course.to_dict()
                
                # 缓存课程详情
                self.cache.set(
                    TeachingCacheKeys.COURSE_DETAIL,
                    str(course_id),
                    course_data,
                    ttl=1800  # 30分钟
                )
                
                return course_data
                
        except Exception as e:
            logger.error(f"Get course by ID error: {e}")
            return None
    
    def update_course(self, course_id: int, **kwargs) -> bool:
        """更新课程信息"""
        try:
            from ..database.models import Course
            
            with db_manager.get_session() as session:
                course = session.query(Course).filter(Course.id == course_id).first()
                if not course:
                    return False
                
                # 更新允许的字段
                allowed_fields = [
                    'name', 'description', 'difficulty_level', 'ai_teacher_prompt',
                    'teaching_objectives', 'knowledge_points', 'teaching_materials'
                ]
                
                for field, value in kwargs.items():
                    if field in allowed_fields and hasattr(course, field):
                        setattr(course, field, value)
                
                course.updated_at = datetime.now()
                session.commit()
                
                # 清理缓存
                self._clear_course_cache_by_id(course_id)
                self._clear_course_cache(course.subject.value, course.grade_level)
                
                logger.info(f"Course updated: {course_id}")
                return True
                
        except Exception as e:
            logger.error(f"Update course error: {e}")
            return False
    
    def get_recommended_courses(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """为学生推荐课程"""
        try:
            from ..database.models import User, Course, LearningSession
            
            with db_manager.get_session() as session:
                # 获取用户信息
                user = session.query(User).filter(User.id == user_id).first()
                if not user or not user.grade_level:
                    return []
                
                # 获取用户已学习的课程
                learned_courses = session.query(LearningSession.course_id).filter(
                    LearningSession.user_id == user_id,
                    LearningSession.status == 'completed'
                ).subquery()
                
                # 推荐同年级的课程，排除已学习的
                query = session.query(Course).filter(
                    Course.grade_level == user.grade_level,
                    Course.is_active == True,
                    ~Course.id.in_(learned_courses)
                )
                
                # 根据用户学习偏好排序
                learning_preferences = user.learning_preferences or {}
                preferred_subject = learning_preferences.get('preferred_subject')
                
                if preferred_subject:
                    # 优先推荐偏好学科
                    query = query.order_by(
                        Course.subject == preferred_subject,
                        Course.difficulty_level,
                        Course.created_at.desc()
                    )
                else:
                    query = query.order_by(Course.difficulty_level, Course.created_at.desc())
                
                courses = query.limit(limit).all()
                return [course.to_dict() for course in courses]
                
        except Exception as e:
            logger.error(f"Get recommended courses error: {e}")
            return []
    
    def _generate_default_prompt(self, subject: str, grade_level: str) -> str:
        """生成默认的AI教师提示词"""
        subject_labels = {
            'math': '数学',
            'chinese': '语文', 
            'english': '英语',
            'physics': '物理',
            'chemistry': '化学',
            'biology': '生物',
            'history': '历史',
            'geography': '地理'
        }
        
        subject_name = subject_labels.get(subject, subject)
        
        return f"""你是一位专业的{subject_name}AI教师，正在为{grade_level}的学生进行1对1在线教学。

教学要求：
1. 语言简洁易懂，适合{grade_level}学生的理解水平
2. 每次回答控制在2-3句话内，避免信息过载
3. 多用启发式提问，引导学生思考
4. 及时给予鼓励和正面反馈
5. 根据学生反应调整教学节奏

教学风格：
- 亲切友好，有耐心
- 善于用生动的比喻和例子
- 注重互动，让学生参与进来
- 发现学生错误时，温和地引导纠正

请始终保持专业的教师身份，为学生提供高质量的{subject_name}教学服务。"""
    
    def _get_subject_label(self, subject: str) -> str:
        """获取学科中文名称"""
        labels = {
            'math': '数学',
            'chinese': '语文',
            'english': '英语', 
            'physics': '物理',
            'chemistry': '化学',
            'biology': '生物',
            'history': '历史',
            'geography': '地理'
        }
        return labels.get(subject, subject)
    
    def _get_subject_description(self, subject: str) -> str:
        """获取学科描述"""
        descriptions = {
            'math': 'AI数学老师，专注数学思维培养',
            'chinese': 'AI语文老师，提升语言文字能力',
            'english': 'AI英语老师，打造英语学习环境',
            'physics': 'AI物理老师，探索科学奥秘',
            'chemistry': 'AI化学老师，了解物质变化',
            'biology': 'AI生物老师，认识生命科学',
            'history': 'AI历史老师，穿越时空学历史',
            'geography': 'AI地理老师，认识我们的地球'
        }
        return descriptions.get(subject, f'{subject}学科AI教师')
    
    def _clear_course_cache(self, subject: str, grade_level: str):
        """清理课程相关缓存"""
        # 清理课程列表缓存
        cache_keys = [
            f"{grade_level}_{subject}",
            f"{grade_level}_all"
        ]
        for key in cache_keys:
            self.cache.delete(TeachingCacheKeys.COURSE_LIST, key)
    
    def _clear_course_cache_by_id(self, course_id: int):
        """根据课程ID清理缓存"""
        self.cache.delete(TeachingCacheKeys.COURSE_DETAIL, str(course_id))


# 全局课程服务实例
course_service = CourseService() 