#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融合教学API - 整合用户系统和AI教学系统
提供统一的认证和教学接口
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import time
from loguru import logger

# 导入用户系统和教学系统
from .user_api import router as user_router
from .course_api import router as course_router
from ..storage.services.user_service import user_service
from ..storage.services.course_service import course_service
from ..backend.integrated_teaching_backend import multi_user_teaching_manager
from ..storage.database.connection import db_manager


# Pydantic模型定义
class StartTeachingSessionRequest(BaseModel):
    course_id: int = Field(..., description="课程ID")
    preferences: Optional[Dict] = Field(None, description="会话偏好设置")


class SendMessageRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_key: str = Field(..., description="会话标识")


class TeachingSessionResponse(BaseModel):
    session_key: str
    course_info: Dict
    user_info: Dict
    welcome_message: str
    personalized_settings: Dict
    status: str


class MessageResponse(BaseModel):
    response: str
    chat_history: List[Dict]
    response_time: float
    session_info: Dict
    recommendations: Optional[List[Dict]] = None
    status: str


# 安全配置
security = HTTPBearer()


class IntegratedTeachingAPI:
    """融合的教学API类"""
    
    def __init__(self):
        self.app = FastAPI(
            title="AI教学平台集成API",
            description="融合用户管理和AI教学的统一API接口",
            version="1.0.0"
        )
        
        # 配置CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 注册路由
        self._register_routes()
        
        # 包含现有的用户和课程API
        self.app.include_router(user_router, prefix="/api/users", tags=["用户管理"])
        self.app.include_router(course_router, prefix="/api/courses", tags=["课程管理"])
    
    def _register_routes(self):
        """注册融合教学的API路由"""
        
        @self.app.get("/")
        async def root():
            """API根路径"""
            return {
                "service": "AI教学平台集成API",
                "version": "1.0.0",
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "features": [
                    "用户认证管理",
                    "课程管理",
                    "个性化AI教学",
                    "多用户并发支持",
                    "学习进度跟踪"
                ]
            }
        
        @self.app.get("/api/health")
        async def health_check():
            """系统健康检查"""
            try:
                # 检查数据库连接
                db_healthy = db_manager.health_check()
                
                # 检查教学管理器
                manager_healthy = len(multi_user_teaching_manager.user_backends) >= 0
                
                return {
                    "status": "healthy" if db_healthy and manager_healthy else "unhealthy",
                    "database": "connected" if db_healthy else "disconnected",
                    "teaching_manager": "ready" if manager_healthy else "error",
                    "active_sessions": len(multi_user_teaching_manager.teaching_sessions),
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                raise HTTPException(status_code=500, detail="System health check failed")
        
        @self.app.post("/api/teaching/start-session", response_model=TeachingSessionResponse)
        async def start_teaching_session(
            request: StartTeachingSessionRequest,
            current_user: Dict = Depends(self.get_current_user)
        ):
            """启动AI教学会话"""
            try:
                user_id = current_user["user_id"]
                session_token = current_user["session_token"]
                
                # 验证课程存在
                course = course_service.get_course_by_id(request.course_id)
                if not course:
                    raise HTTPException(status_code=404, detail="Course not found")
                
                # 检查是否已有活跃会话
                existing_session = multi_user_teaching_manager.get_user_session_status(user_id)
                if existing_session and existing_session.get("status") == "active":
                    # 结束现有会话
                    multi_user_teaching_manager.end_teaching_session(
                        user_id, existing_session["session_key"]
                    )
                
                # 创建新的教学会话
                session_data = multi_user_teaching_manager.create_teaching_session(
                    user_id, request.course_id, session_token
                )
                
                logger.info(f"Teaching session started for user {user_id}, course {request.course_id}")
                
                return TeachingSessionResponse(
                    session_key=session_data["session_key"],
                    course_info=session_data["course_info"],
                    user_info=session_data["user_info"],
                    welcome_message=session_data["welcome_message"],
                    personalized_settings=session_data["personalized_settings"],
                    status=session_data["status"]
                )
                
            except Exception as e:
                logger.error(f"Failed to start teaching session: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/teaching/send-message", response_model=MessageResponse)
        async def send_teaching_message(
            request: SendMessageRequest,
            current_user: Dict = Depends(self.get_current_user)
        ):
            """发送教学消息"""
            try:
                user_id = current_user["user_id"]
                
                # 验证会话
                session_status = multi_user_teaching_manager.get_user_session_status(user_id)
                if not session_status or session_status.get("session_key") != request.session_key:
                    raise HTTPException(status_code=404, detail="Invalid teaching session")
                
                # 处理消息
                response_data = multi_user_teaching_manager.process_user_message(
                    user_id, request.message, request.session_key
                )
                
                # 添加推荐课程
                if "recommendations" not in response_data:
                    # 获取当前课程ID
                    current_course_id = session_status.get("course_info", {}).get("id")
                    if current_course_id:
                        recommendations = multi_user_teaching_manager.personalized_engine.get_recommended_next_topics(
                            user_id, current_course_id
                        )
                        response_data["recommendations"] = recommendations
                
                logger.info(f"Message processed for user {user_id}, response time: {response_data['response_time']:.2f}ms")
                
                return MessageResponse(**response_data)
                
            except Exception as e:
                logger.error(f"Failed to process teaching message: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/teaching/session-status")
        async def get_teaching_session_status(
            current_user: Dict = Depends(self.get_current_user)
        ):
            """获取当前教学会话状态"""
            try:
                user_id = current_user["user_id"]
                session_status = multi_user_teaching_manager.get_user_session_status(user_id)
                
                if not session_status:
                    return {"status": "no_active_session"}
                
                return {
                    "status": "active_session",
                    "session_data": session_status
                }
                
            except Exception as e:
                logger.error(f"Failed to get session status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/teaching/end-session")
        async def end_teaching_session(
            session_key: str,
            current_user: Dict = Depends(self.get_current_user)
        ):
            """结束教学会话"""
            try:
                user_id = current_user["user_id"]
                
                success = multi_user_teaching_manager.end_teaching_session(user_id, session_key)
                
                if success:
                    logger.info(f"Teaching session ended for user {user_id}")
                    return {"status": "success", "message": "Teaching session ended"}
                else:
                    raise HTTPException(status_code=404, detail="Session not found or already ended")
                
            except Exception as e:
                logger.error(f"Failed to end teaching session: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/teaching/recommendations")
        async def get_course_recommendations(
            current_course_id: Optional[int] = None,
            current_user: Dict = Depends(self.get_current_user)
        ):
            """获取个性化课程推荐"""
            try:
                user_id = current_user["user_id"]
                
                # 如果没有指定当前课程，尝试从活跃会话获取
                if not current_course_id:
                    session_status = multi_user_teaching_manager.get_user_session_status(user_id)
                    if session_status:
                        current_course_id = session_status.get("course_info", {}).get("id")
                
                if current_course_id:
                    recommendations = multi_user_teaching_manager.personalized_engine.get_recommended_next_topics(
                        user_id, current_course_id
                    )
                else:
                    # 如果没有当前课程，基于用户偏好推荐
                    user_data = user_service.get_user_by_id(user_id)
                    grade_level = user_data.get("grade_level", "小学三年级") if user_data else "小学三年级"
                    recommendations = course_service.get_courses_by_grade_level(grade_level)[:5]
                    recommendations = [{"course": course, "reason": "适合年级", "confidence": 0.8} 
                                     for course in recommendations]
                
                return {
                    "recommendations": recommendations,
                    "total_count": len(recommendations),
                    "user_id": user_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get recommendations: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/teaching/stats")
        async def get_teaching_statistics(
            current_user: Dict = Depends(self.get_current_user)
        ):
            """获取用户学习统计"""
            try:
                user_id = current_user["user_id"]
                
                # 获取用户学习统计
                learning_stats = user_service.get_user_learning_stats(user_id)
                
                # 获取当前活跃会话信息
                session_status = multi_user_teaching_manager.get_user_session_status(user_id)
                
                return {
                    "user_id": user_id,
                    "learning_stats": learning_stats,
                    "current_session": session_status,
                    "platform_stats": {
                        "total_users": len(multi_user_teaching_manager.user_backends),
                        "active_sessions": len(multi_user_teaching_manager.teaching_sessions)
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to get teaching statistics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
        """获取当前认证用户信息"""
        try:
            token = credentials.credentials
            
            # 验证token并获取用户信息
            user_data = user_service.get_user_by_session(token)
            
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return {
                "user_id": user_data["id"],
                "username": user_data["username"],
                "role": user_data["role"],
                "session_token": token,
                "user_data": user_data
            }
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"},
            )


# 创建应用实例
integrated_api = IntegratedTeachingAPI()
app = integrated_api.app


# 如果直接运行此文件，启动服务器
if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Integrated Teaching API server...")
    uvicorn.run(
        "integrated_teaching_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    ) 