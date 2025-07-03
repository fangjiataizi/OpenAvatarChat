"""
用户管理API - AI教学平台
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
import logging

from ..storage.services import user_service, course_service
from ..storage.database.models import UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user", tags=["用户管理"])
security = HTTPBearer()


# Pydantic模型定义
class StudentRegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    grade_level: Optional[str] = None
    parent_contact: Optional[str] = None
    learning_preferences: Optional[Dict[str, Any]] = None

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50个字符之间')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('密码长度至少6个字符')
        return v


class AdminRegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50个字符之间')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('管理员密码长度至少8个字符')
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    grade_level: Optional[str] = None
    parent_contact: Optional[str] = None
    learning_preferences: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    grade_level: Optional[str] = None
    parent_contact: Optional[str] = None
    learning_preferences: Optional[Dict[str, Any]] = None
    created_at: str
    last_login: Optional[str] = None
    is_active: bool


class LoginResponse(BaseModel):
    user: UserResponse
    session_token: str
    message: str


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


# 依赖注入：权限检查
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


# 用户注册API
@router.post("/register/student", response_model=UserResponse, summary="学生注册")
async def register_student(request: StudentRegisterRequest):
    """
    学生用户注册
    
    - **username**: 用户名（3-50字符）
    - **password**: 密码（至少6字符）
    - **email**: 邮箱（可选）
    - **grade_level**: 年级（如：小学三年级）
    - **parent_contact**: 家长联系方式
    - **learning_preferences**: 学习偏好设置
    """
    try:
        user_data = user_service.create_student(
            username=request.username,
            password=request.password,
            email=request.email,
            grade_level=request.grade_level,
            parent_contact=request.parent_contact,
            learning_preferences=request.learning_preferences
        )
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在或注册失败"
            )
        
        return UserResponse(**user_data)
        
    except Exception as e:
        logger.error(f"Student registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.post("/register/admin", response_model=UserResponse, summary="管理员注册")
async def register_admin(
    request: AdminRegisterRequest,
    _: Dict[str, Any] = Depends(require_admin())
):
    """
    管理员用户注册（需要现有管理员权限）
    
    - **username**: 用户名（3-50字符）
    - **password**: 密码（至少8字符）
    - **email**: 邮箱（可选）
    """
    try:
        user_data = user_service.create_admin(
            username=request.username,
            password=request.password,
            email=request.email
        )
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在或注册失败"
            )
        
        return UserResponse(**user_data)
        
    except Exception as e:
        logger.error(f"Admin registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="管理员注册失败"
        )


# 用户登录API
@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(request: LoginRequest):
    """
    用户登录认证
    
    - **username**: 用户名
    - **password**: 密码
    
    返回用户信息和会话令牌
    """
    try:
        auth_result = user_service.authenticate_user(
            username=request.username,
            password=request.password
        )
        
        if not auth_result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        session_token = auth_result.pop('session_token')
        
        return LoginResponse(
            user=UserResponse(**auth_result),
            session_token=session_token,
            message="登录成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


# 用户登出API
@router.post("/logout", summary="用户登出")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """用户登出，清除会话"""
    try:
        token = credentials.credentials
        success = user_service.logout_user(token)
        
        if success:
            return {"message": "登出成功"}
        else:
            return {"message": "登出失败"}
            
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        return {"message": "登出过程中发生错误"}


# 获取当前用户信息
@router.get("/profile", response_model=UserResponse, summary="获取用户信息")
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取当前登录用户的详细信息"""
    try:
        user_data = user_service.get_user_by_id(current_user['user_id'])
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户信息不存在"
            )
        
        return UserResponse(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


# 更新用户信息
@router.put("/profile", response_model=UserResponse, summary="更新用户信息")
async def update_profile(
    request: UserUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """更新当前用户的个人信息"""
    try:
        user_id = current_user['user_id']
        
        # 只允许学生更新特定字段
        if current_user.get('role') == 'student':
            success = user_service.update_student_profile(
                user_id=user_id,
                grade_level=request.grade_level,
                parent_contact=request.parent_contact,
                learning_preferences=request.learning_preferences
            )
        else:
            # 管理员可能需要其他更新逻辑
            success = False
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="更新用户信息失败"
            )
        
        # 返回更新后的用户信息
        updated_user = user_service.get_user_by_id(user_id, use_cache=False)
        return UserResponse(**updated_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户信息失败"
        )


# 获取学生列表（管理员功能）
@router.get("/students", response_model=List[UserResponse], summary="获取学生列表")
async def get_students(
    limit: int = 50,
    offset: int = 0,
    grade_level: Optional[str] = None,
    _: Dict[str, Any] = Depends(require_admin())
):
    """
    获取学生用户列表（管理员功能）
    
    - **limit**: 返回数量限制（默认50）
    - **offset**: 偏移量（用于分页）
    - **grade_level**: 按年级筛选（可选）
    """
    try:
        students = user_service.get_students_list(
            limit=limit,
            offset=offset,
            grade_level=grade_level
        )
        
        return [UserResponse(**student) for student in students]
        
    except Exception as e:
        logger.error(f"Get students failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取学生列表失败"
        )


# 获取用户学习统计
@router.get("/stats/{user_id}", summary="获取用户学习统计")
async def get_user_stats(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取用户学习统计信息
    
    学生只能查看自己的统计，管理员可以查看任何用户的统计
    """
    try:
        # 权限检查：学生只能查看自己的统计
        if current_user.get('role') == 'student' and current_user.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能查看自己的学习统计"
            )
        
        stats = user_service.get_user_learning_stats(user_id)
        
        return {
            "user_id": user_id,
            "statistics": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取学习统计失败"
        )


# 获取推荐课程
@router.get("/recommendations", summary="获取推荐课程")
async def get_recommendations(
    limit: int = 5,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取为当前用户推荐的课程"""
    try:
        user_id = current_user['user_id']
        recommendations = course_service.get_recommended_courses(user_id, limit)
        
        return {
            "user_id": user_id,
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"Get recommendations failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取推荐课程失败"
        )


# 健康检查
@router.get("/health", summary="用户服务健康检查")
async def health_check():
    """用户服务健康检查"""
    return {
        "status": "healthy",
        "service": "user_api",
        "version": "1.0.0"
    } 