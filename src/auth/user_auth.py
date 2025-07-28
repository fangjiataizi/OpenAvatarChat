#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户认证管理 - 集成到教学平台
"""

import gradio as gr
from typing import Optional, Dict, Any, Tuple
from loguru import logger
# from src.storage.services.user_service import user_service  # 临时禁用


class UserAuthManager:
    """用户认证管理器 - 负责用户会话管理和权限控制"""
    
    def __init__(self):
        self.current_user = None
        self.current_session_token = None
        self.auth_required = True  # 是否需要登录
    
    def login_user(self, username: str, password: str) -> Tuple[bool, str, Dict]:
        """用户登录"""
        try:
            if not username.strip() or not password.strip():
                return False, "用户名和密码不能为空", {}
            
            # 临时简化认证逻辑
            user_data = None  # user_service.authenticate_user(username, password)
            
            if user_data:
                self.current_user = user_data
                self.current_session_token = user_data["session_token"]
                
                logger.info(f"User login successful: {username} (Role: {user_data.get('role')})")
                return True, f"欢迎回来，{user_data['username']}！", user_data
            else:
                logger.warning(f"User login failed: {username}")
                return False, "用户名或密码错误", {}
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False, f"登录出现错误: {str(e)}", {}
    
    def register_user(self, username: str, password: str, confirm_password: str, 
                     email: str = "", grade_level: str = "") -> Tuple[bool, str, Dict]:
        """用户注册"""
        try:
            # 基本验证
            if not username.strip():
                return False, "用户名不能为空", {}
            
            if len(username) < 3 or len(username) > 20:
                return False, "用户名长度必须在3-20个字符之间", {}
            
            if not password.strip():
                return False, "密码不能为空", {}
            
            if len(password) < 6:
                return False, "密码长度至少6位", {}
            
            if password != confirm_password:
                return False, "两次输入的密码不一致", {}
            
            # 临时禁用用户创建
            user_data = None  # user_service.create_student(...)
            
            if user_data:
                logger.info(f"User registration successful: {username}")
                return True, f"注册成功！欢迎 {username}，请登录开始学习", user_data
            else:
                return False, "注册失败，用户名可能已存在", {}
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False, f"注册出现错误: {str(e)}", {}
    
    def logout_user(self) -> Tuple[bool, str]:
        """用户登出"""
        try:
            # 临时禁用登出服务
            # if self.current_session_token:
            #     user_service.logout_user(self.current_session_token)
            
            username = self.current_user.get('username', '用户') if self.current_user else '用户'
            self.current_user = None
            self.current_session_token = None
            
            logger.info(f"User logout: {username}")
            return True, f"再见，{username}！"
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False, f"登出错误: {str(e)}"
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """获取当前登录用户"""
        return self.current_user
    
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self.current_user is not None and self.current_session_token is not None
    
    def is_admin(self) -> bool:
        """检查是否为管理员"""
        return self.current_user and self.current_user.get('role') == 'admin'
    
    def is_student(self) -> bool:
        """检查是否为学生"""
        return self.current_user and self.current_user.get('role') == 'student'
    
    def require_auth(self, required_role: str = "student") -> bool:
        """检查用户权限"""
        if not self.auth_required:
            return True
            
        if not self.is_authenticated():
            return False
            
        # 临时简化权限检查
        # if self.current_session_token:
        #     return user_service.check_permission(self.current_session_token, required_role)
        
        return False
    
    def get_user_display_name(self) -> str:
        """获取用户显示名称"""
        if not self.current_user:
            return "游客"
        
        username = self.current_user.get('username', '用户')
        role = self.current_user.get('role', '')
        role_display = {
            'admin': '管理员',
            'student': '学生',
            'parent': '家长'
        }.get(role, '')
        
        return f"{username} ({role_display})" if role_display else username
    
    def get_user_learning_info(self) -> Dict[str, Any]:
        """获取用户学习相关信息"""
        if not self.current_user:
            return {}
        
        user_id = self.current_user.get('id')
        if user_id:
            # stats = user_service.get_user_learning_stats(user_id)
            stats = {}  # 临时禁用统计
            return {
                'user_id': user_id,
                'username': self.current_user.get('username'),
                'grade_level': self.current_user.get('grade_level'),
                'learning_preferences': self.current_user.get('learning_preferences', {}),
                'stats': stats
            }
        
        return {}
    
    def set_auth_required(self, required: bool):
        """设置是否需要认证（用于开发和测试）"""
        self.auth_required = required
        logger.info(f"Auth requirement set to: {required}")


# 全局认证管理器实例
auth_manager = UserAuthManager()