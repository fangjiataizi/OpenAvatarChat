"""
课程管理API - AI教学平台
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
import logging

from ..storage.services import course_service, user_service
from ..storage.database.models import SubjectType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/course", tags=["课程管理"])
security = HTTPBearer()


# Pydantic模型定义
class CourseCreateRequest(BaseModel):
    name: str
    subject: str
    grade_level: str
    difficulty_level: int = 1
    description: Optional[str] = None
    ai_teacher_prompt: Optional[str] = None
    teaching_objectives: Optional[List[str]] = None
    knowledge_points: Optional[List[str]] = None
    teaching_materials: Optional[Dict[str, Any]] = None

    @validator('name')
    def validate_name(cls, v):
        if len(v) < 2 or len(v) > 100:
            raise ValueError('课程名称长度必须在2-100个字符之间')
        return v

    @validator('subject')
    def validate_subject(cls, v):
        valid_subjects = [s.value for s in SubjectType]
        if v not in valid_subjects:
            raise ValueError(f'学科必须是以下之一: {", ".join(valid_subjects)}')
        return v

    @validator('difficulty_level')
    def validate_difficulty(cls, v):
        if v < 1 or v > 5:
            raise ValueError('难度等级必须在1-5之间')
        return v


class CourseUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    difficulty_level: Optional[int] = None
    ai_teacher_prompt: Optional[str] = None
    teaching_objectives: Optional[List[str]] = None
    knowledge_points: Optional[List[str]] = None
    teaching_materials: Optional[Dict[str, Any]] = None

    @validator('difficulty_level')
    def validate_difficulty(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('难度等级必须在1-5之间')
        return v


class CourseResponse(BaseModel):
    id: int
    name: str
    subject: str
    grade_level: str
    difficulty_level: int
    description: Optional[str]
    ai_teacher_prompt: Optional[str]
    teaching_objectives: List[str]
    knowledge_points: List[str]
    teaching_materials: Dict[str, Any]
    created_at: str
    updated_at: str
    is_active: bool


class SubjectResponse(BaseModel):
    value: str
    label: str
    description: str


# 依赖注入：获取当前用户
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """获取当前登录用户"""
    token = credentials.credentials
    user_session = user_service.get_user_by_session(token)
    
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_session


# 依赖注入：管理员权限检查
def require_admin():
    """需要管理员权限的装饰器"""
    async def check_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
        if current_user.get('role') != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permission required"
            )
        return current_user
    return check_admin


# 获取可用学科列表
@router.get("/subjects", response_model=List[SubjectResponse], summary="获取学科列表")
async def get_subjects():
    """获取所有可用的学科列表"""
    try:
        subjects = course_service.get_available_subjects()
        return [SubjectResponse(**subject) for subject in subjects]
        
    except Exception as e:
        logger.error(f"Get subjects failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取学科列表失败"
        )


# 获取课程列表
@router.get("/list", response_model=List[CourseResponse], summary="获取课程列表")
async def get_courses(
    grade_level: str,
    subject: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取课程列表
    
    - **grade_level**: 年级（必选）
    - **subject**: 学科筛选（可选）
    
    学生只能查看适合自己年级的课程
    """
    try:
        # 权限检查：学生只能查看自己年级的课程
        if current_user.get('role') == 'student':
            user_grade = current_user.get('grade_level')
            if user_grade and grade_level != user_grade:
                # 如果学生指定了不同的年级，返回空列表
                return []
        
        courses = course_service.get_courses_by_grade_and_subject(grade_level, subject)
        return [CourseResponse(**course) for course in courses]
        
    except Exception as e:
        logger.error(f"Get courses failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取课程列表失败"
        )


# 获取课程详情
@router.get("/{course_id}", response_model=CourseResponse, summary="获取课程详情")
async def get_course(
    course_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取指定课程的详细信息"""
    try:
        course = course_service.get_course_by_id(course_id)
        
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="课程不存在"
            )
        
        # 权限检查：学生只能查看适合自己年级的课程
        if current_user.get('role') == 'student':
            user_grade = current_user.get('grade_level')
            if user_grade and course['grade_level'] != user_grade:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="只能查看适合自己年级的课程"
                )
        
        return CourseResponse(**course)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get course failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取课程详情失败"
        )


# 创建课程（管理员功能）
@router.post("/create", response_model=CourseResponse, summary="创建课程")
async def create_course(
    request: CourseCreateRequest,
    _: Dict[str, Any] = Depends(require_admin())
):
    """
    创建新课程（管理员功能）
    
    - **name**: 课程名称
    - **subject**: 学科类型
    - **grade_level**: 适用年级
    - **difficulty_level**: 难度等级（1-5）
    - **description**: 课程描述
    - **ai_teacher_prompt**: AI教师提示词（可选，会自动生成）
    - **teaching_objectives**: 教学目标列表
    - **knowledge_points**: 知识点列表
    - **teaching_materials**: 教学素材
    """
    try:
        course_data = course_service.create_course(
            name=request.name,
            subject=request.subject,
            grade_level=request.grade_level,
            difficulty_level=request.difficulty_level,
            description=request.description,
            ai_teacher_prompt=request.ai_teacher_prompt,
            teaching_objectives=request.teaching_objectives,
            knowledge_points=request.knowledge_points,
            teaching_materials=request.teaching_materials
        )
        
        if not course_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="课程创建失败"
            )
        
        return CourseResponse(**course_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create course failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建课程失败"
        )


# 更新课程（管理员功能）
@router.put("/{course_id}", response_model=CourseResponse, summary="更新课程")
async def update_course(
    course_id: int,
    request: CourseUpdateRequest,
    _: Dict[str, Any] = Depends(require_admin())
):
    """
    更新课程信息（管理员功能）
    
    只有提供的字段会被更新，其他字段保持不变
    """
    try:
        # 检查课程是否存在
        existing_course = course_service.get_course_by_id(course_id)
        if not existing_course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="课程不存在"
            )
        
        # 构建更新字典，只包含非None的字段
        update_data = {}
        for field, value in request.dict().items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段"
            )
        
        success = course_service.update_course(course_id, **update_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="课程更新失败"
            )
        
        # 返回更新后的课程信息
        updated_course = course_service.get_course_by_id(course_id)
        return CourseResponse(**updated_course)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update course failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新课程失败"
        )


# 获取推荐课程
@router.get("/recommend/for-me", summary="获取个人推荐课程")
async def get_my_recommendations(
    limit: int = 5,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取为当前用户推荐的课程"""
    try:
        user_id = current_user['user_id']
        recommendations = course_service.get_recommended_courses(user_id, limit)
        
        return {
            "user_id": user_id,
            "recommendations": [CourseResponse(**course) for course in recommendations]
        }
        
    except Exception as e:
        logger.error(f"Get recommendations failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取推荐课程失败"
        )


# 搜索课程
@router.get("/search", response_model=List[CourseResponse], summary="搜索课程")
async def search_courses(
    keyword: str,
    grade_level: Optional[str] = None,
    subject: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    搜索课程
    
    - **keyword**: 搜索关键词（课程名称或描述）
    - **grade_level**: 年级筛选
    - **subject**: 学科筛选
    """
    try:
        # 对于学生用户，如果没有指定年级，使用其自己的年级
        if current_user.get('role') == 'student' and not grade_level:
            grade_level = current_user.get('grade_level')
        
        # 这里简化实现，实际可以在course_service中添加搜索方法
        if grade_level:
            courses = course_service.get_courses_by_grade_and_subject(grade_level, subject)
        else:
            # 管理员可以查看所有年级的课程
            courses = []
            # 这里需要实现跨年级搜索的逻辑
        
        # 简单的关键词筛选
        if keyword:
            keyword_lower = keyword.lower()
            filtered_courses = []
            for course in courses:
                if (keyword_lower in course['name'].lower() or 
                    (course.get('description') and keyword_lower in course['description'].lower())):
                    filtered_courses.append(course)
            courses = filtered_courses
        
        return [CourseResponse(**course) for course in courses]
        
    except Exception as e:
        logger.error(f"Search courses failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索课程失败"
        )


# 获取课程统计信息（管理员功能）
@router.get("/stats/overview", summary="获取课程统计")
async def get_course_stats(
    _: Dict[str, Any] = Depends(require_admin())
):
    """获取课程的统计信息（管理员功能）"""
    try:
        # 这里可以实现各种课程统计
        # 目前简化返回基本统计信息
        return {
            "total_courses": 0,  # 实际实现中应该查询数据库
            "courses_by_subject": {},
            "courses_by_grade": {},
            "active_courses": 0
        }
        
    except Exception as e:
        logger.error(f"Get course stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取课程统计失败"
        )


# 健康检查
@router.get("/health", summary="课程服务健康检查")
async def health_check():
    """课程服务健康检查"""
    return {
        "status": "healthy",
        "service": "course_api",
        "version": "1.0.0"
    } 