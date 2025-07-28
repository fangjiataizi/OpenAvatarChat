#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台 - 统一API接口层
负责连接前端和后端，提供清晰的接口定义
整合了课程管理、对话处理、实时更新等功能
"""

import os
import gradio as gr
from typing import List, Dict, Tuple, Any
from loguru import logger
from dotenv import load_dotenv

# 确保在模块加载时就加载环境变量
load_dotenv()

from teaching_backend import teaching_backend
from teaching_frontend import teaching_frontend


class TeachingAPI:
    """教学平台API接口类"""
    
    def __init__(self):
        self.backend = teaching_backend
        self.frontend = teaching_frontend
    
    def initialize(self, engine_config, app, demo, rtc_container, storage_enabled=False):
        """初始化系统"""
        logger.info("Using standard backend")
        
        # 设置前端更新回调，让AI主动消息能立即更新前端
        self.backend.set_frontend_update_callback(self.update_real_chat_display)
        logger.info("Frontend update callback set for real-time AI message display")
        
        success = self.backend.initialize_chat_engine(engine_config, app, demo, rtc_container)
        if success:
            self.backend.start_log_monitor()
        
        # 初始化用户认证系统
        auth_success = self.backend.initialize_auth()
        if auth_success:
            logger.info("User authentication system ready")
        else:
            logger.warning("Running without user authentication")
        
        return success
    
    # ========== 用户认证管理 ==========
    
    def handle_login(self, username: str, password: str) -> Tuple[bool, str, bool, str, str]:
        """处理用户登录"""
        if not self.backend.auth_manager:
            return False, "认证系统未初始化", False, "", ""
        
        success, message, user_data = self.backend.auth_manager.login_user(username, password)
        
        if success:
            # 生成用户信息HTML
            display_name = self.backend.auth_manager.get_user_display_name()
            user_info_html = f"""
            <div class="user-info">
                <span>👤 {display_name}</span>
            </div>
            """
            return True, message, True, user_info_html, ""
        else:
            return False, message, False, "", f"❌ {message}"
    
    def handle_login_simple(self, username: str, password: str):
        """简化的登录处理"""
        logger.info(f"Login attempt for user: {username}")
        
        try:
            # 临时简化处理：直接验证演示账户
            if username == 'student1' and password == '123456':
                user_info_html = """
                <div class="user-info">
                    <span>👤 student1 (学生)</span>
                </div>
                """
                logger.info("Demo login successful for student1")
                return (
                    gr.update(visible=False),  # login_page 隐藏
                    gr.update(visible=True),   # course_selection_page 显示
                    user_info_html,            # user_info
                    "✅ 登录成功！"             # login_status
                )
            elif username == 'admin' and password == 'admin123':
                user_info_html = """
                <div class="user-info">
                    <span>👤 admin (管理员)</span>
                </div>
                """
                logger.info("Demo login successful for admin")
                return (
                    gr.update(visible=False),  # login_page 隐藏
                    gr.update(visible=True),   # course_selection_page 显示
                    user_info_html,            # user_info
                    "✅ 登录成功！"             # login_status
                )
            else:
                # 登录失败
                logger.warning(f"Login failed for: {username}")
                return (
                    gr.update(visible=True),   # login_page 保持显示
                    gr.update(visible=False),  # course_selection_page 隐藏
                    "用户: 未登录",              # user_info
                    "❌ 用户名或密码错误"        # login_status
                )
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            import traceback
            logger.error(f"Login traceback: {traceback.format_exc()}")
            return (
                gr.update(visible=True),   # login_page 保持显示
                gr.update(visible=False),  # course_selection_page 隐藏
                "用户: 未登录",              # user_info
                f"❌ 登录出现错误: {str(e)}"  # login_status
            )
    
    def _user_exists(self, username: str) -> bool:
        """检查用户是否存在"""
        try:
            # from src.storage.services.user_service import user_service  # 临时禁用
            # 尝试简单的用户查询
            return False  # 暂时总是返回False，让系统创建演示用户
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return False
    
    def _create_demo_user(self, username: str, password: str):
        """创建演示用户"""
        try:
            # from src.storage.services.user_service import user_service  # 临时禁用
            
            # 临时禁用用户创建
            # if username == 'student1':
            #     user_service.create_student(...)
            logger.info(f"Demo user creation disabled for: {username}")
                
        except Exception as e:
            logger.error(f"Error creating demo user: {e}")
            import traceback
            logger.error(f"Demo user creation traceback: {traceback.format_exc()}")
    
    def handle_register(self, username: str, email: str, password: str, 
                       confirm_password: str, grade: str) -> Tuple[bool, str]:
        """处理用户注册"""
        if not self.backend.auth_manager:
            return False, "认证系统未初始化"
        
        success, message, user_data = self.backend.auth_manager.register_user(
            username, password, confirm_password, email, grade
        )
        
        return success, message
    
    def handle_logout(self) -> Tuple[bool, str, bool, str]:
        """处理用户登出"""
        if not self.backend.auth_manager:
            return False, "认证系统未初始化", True, ""
        
        success, message = self.backend.auth_manager.logout_user()
        
        # 返回到登录页面
        empty_user_info = """
        <div class="user-info">
            <span>👤 用户: 未登录</span>
        </div>
        """
        
        return success, message, True, empty_user_info
    
    def handle_logout_simple(self):
        """简化的登出处理"""
        logger.info("User logout")
        
        if self.backend.auth_manager:
            self.backend.auth_manager.logout_user()
        
        empty_user_info = """
        <div class="user-info">
            <span>👤 用户: 未登录</span>
        </div>
        """
        
        return (
            gr.update(visible=True),   # login_page 显示
            gr.update(visible=False),  # course_selection_page 隐藏
            empty_user_info            # user_info
        )
    
    def check_authentication(self) -> bool:
        """检查用户是否已认证"""
        # 临时简化：总是返回True，允许访问课程
        return True
    
    # ========== 课程会话管理 ==========
    
    def start_learning_session(self, course: str, difficulty: str, goal: str) -> Tuple[Any, ...]:
        """开始学习会话 - API接口"""
        logger.info(f"Starting learning session: course={course}, difficulty={difficulty}, goal={goal}")
        
        # 检查用户认证
        if not self.check_authentication():
            logger.warning("Attempt to start session without authentication")
            return (
                gr.update(visible=False),  # course_selection_page - 隐藏课程选择页面
                gr.update(visible=False),  # teacher_chat_page - 隐藏教师对话页面
                "请先登录",
                self.frontend.build_chat_html([])
            )
        
        # 设置当前会话信息（用于AI主动问候）
        self.backend.set_current_session_info(course, difficulty, goal)
        
        # 创建学习会话
        session_data = self.backend.create_learning_session(course, difficulty, goal)
        
        # 生成前端显示内容
        course_info_html = self.frontend.create_course_info_html(course, difficulty, goal)
        real_chat_html = self.frontend.build_chat_html([])
        
        logger.info("Session started successfully, switching to teacher chat page")
        
        return (
            gr.update(visible=False),  # course_selection_page - 隐藏课程选择页面
            gr.update(visible=True),   # teacher_chat_page - 显示教师对话页面
            course_info_html,          # course_info - 更新课程信息
            real_chat_html,           # real_chat_display - 显示初始对话
            '<div><span class="status-indicator status-ready"></span>小慧老师已就绪</div>',  # teacher_status
            course,                    # current_course
            difficulty,                # current_difficulty
            goal,                      # current_goal
            session_data['chat_history']  # chat_history
        )
    
    def back_to_course_selection(self) -> Tuple[Any, ...]:
        """返回课程选择页面 - API接口"""
        # 停止AI教学活动和清空后端状态
        self.backend._stop_ai_teaching()
        self.backend.clear_chat_messages()
        
        return (
            gr.update(visible=True),   # 显示课程选择页面
            gr.update(visible=False),  # 隐藏教师对话页面
            "",                        # 清空课程信息
            self.frontend._get_initial_chat_html(),  # 重置对话显示
            '<div><span class="status-indicator status-ready"></span>系统就绪</div>',  # 重置状态
            "",                        # 清空当前课程
            "",                        # 清空当前难度
            "",                        # 清空当前目标
            []                         # 清空聊天历史
        )
    
    # ========== 消息处理 ==========
    
    def send_message(self, message: str, chat_hist: List[Dict], course: str, difficulty: str) -> Tuple[str, List[Dict], Any]:
        """发送学生消息并获取AI教师回复 - API接口"""
        if not message.strip():
            return "", chat_hist, gr.update()
        
        # 处理消息
        updated_history, teacher_response = self.backend.process_student_message(
            message, chat_hist, course, difficulty
        )
        
        # 生成前端显示HTML
        chat_html = self.frontend.build_backup_chat_html(updated_history)
        
        return "", updated_history, gr.update(value=chat_html)
    
    def quick_reply(self, reply_text: str, chat_hist: List[Dict], course: str, difficulty: str) -> Tuple[str, List[Dict], Any]:
        """处理快捷回复 - API接口"""
        return self.send_message(reply_text, chat_hist, course, difficulty)
    
    # ========== 实时对话管理 ==========
    
    def update_real_chat_display(self) -> Any:
        """更新真实对话显示 - API接口"""
        messages = self.backend.get_all_chat_messages()
        chat_html = self.frontend.build_chat_html(messages)
        return gr.update(value=chat_html)
    
    def refresh_chat_display(self) -> Any:
        """刷新对话显示 - API接口"""
        return self.update_real_chat_display()
    
    def clear_chat_display(self) -> Any:
        """清空对话显示 - API接口"""
        self.backend.clear_chat_messages()
        return gr.update(value=self.frontend._get_initial_chat_html())
    
    def test_chat_display(self) -> Any:
        """测试对话显示 - API接口"""
        success = self.backend.add_test_message()
        if success:
            return self.update_real_chat_display()
        return gr.update()
    
    # ========== 调试和监控 ==========
    
    def get_debug_info(self) -> Any:
        """获取调试信息 - API接口"""
        debug_info = self.backend.get_debug_info()
        debug_html = self.frontend.create_debug_info_html(debug_info)
        return gr.update(value=debug_html)
    
    def auto_update_chat(self) -> Any:
        """自动更新对话（定时器触发）- API接口"""
        return self.update_real_chat_display()
    
    def toggle_auto_refresh(self, current_state: bool) -> Tuple[Any, bool]:
        """切换自动刷新状态"""
        new_state = not current_state
        button_text = "🔄 自动刷新: 启用" if new_state else "🔄 自动刷新: 禁用"
        button_variant = "primary" if new_state else "secondary"
        
        return gr.update(value=button_text, variant=button_variant), new_state
    
    # ========== 事件绑定 ==========
    
    def bind_events(self, components: Dict[str, Any]):
        """绑定所有UI事件 - API接口"""
        
        # ========== 用户认证相关事件 ==========
        
        # 登录按钮事件
        if 'login_btn' in components:
            components['login_btn'].click(
                fn=self.handle_login_simple,
                inputs=[
                    components['username'],
                    components['password']
                ],
                outputs=[
                    components['login_page'],           # 隐藏/显示登录页面
                    components['course_selection_page'], # 显示/隐藏课程选择页面
                    components['user_info'],            # 更新用户信息
                    components['login_status']          # 登录状态消息
                ]
            )
        
        # 注册按钮事件
        if 'register_btn' in components:
            components['register_btn'].click(
                fn=self.handle_register,
                inputs=[
                    components['reg_username'],
                    components['reg_email'],
                    components['reg_password'],
                    components['reg_confirm_password'],
                    components['reg_grade']
                ],
                outputs=[
                    components['register_status']
                ]
            )
        
        # 显示注册表单事件
        if 'show_register_btn' in components:
            components['show_register_btn'].click(
                fn=lambda: gr.update(visible=True),
                outputs=[components['register_section']]
            )
        
        # 返回登录事件
        if 'back_to_login_btn' in components:
            components['back_to_login_btn'].click(
                fn=lambda: gr.update(visible=False),
                outputs=[components['register_section']]
            )
        
        # 登出按钮事件
        if 'logout_btn' in components:
            components['logout_btn'].click(
                fn=self.handle_logout_simple,
                outputs=[
                    components['login_page'],           # 显示登录页面
                    components['course_selection_page'], # 隐藏课程选择页面
                    components['user_info']             # 清空用户信息
                ]
            )
        
        # ========== 课程学习相关事件 ==========
        
        # 开始学习按钮事件
        components['start_button'].click(
            fn=self.start_learning_session,
            inputs=[
                components['course_dropdown'], 
                components['difficulty_radio'], 
                components['learning_goal']
            ],
            outputs=[
                components['course_selection_page'], 
                components['teacher_chat_page'], 
                components['course_info'],
                components['real_chat_display'], 
                components['teacher_status'], 
                components['current_course'],
                components['current_difficulty'], 
                components['current_goal'], 
                components['chat_history']
            ]
        )
        
        # 返回课程选择按钮事件
        components['back_button'].click(
            fn=self.back_to_course_selection,
            outputs=[
                components['course_selection_page'], 
                components['teacher_chat_page'], 
                components['course_info'],
                components['real_chat_display'], 
                components['status_display'], 
                components['current_course'],
                components['current_difficulty'], 
                components['current_goal'], 
                components['chat_history']
            ]
        )
        
        # 真实对话控制按钮事件
        components['refresh_chat_btn'].click(
            fn=self.refresh_chat_display,
            outputs=[components['real_chat_display']]
        )
        
        components['clear_chat_btn'].click(
            fn=self.clear_chat_display,
            outputs=[components['real_chat_display']]
        )
        
        components['auto_toggle_btn'].click(
            fn=self.toggle_auto_refresh,
            inputs=[components['auto_refresh_state']],
            outputs=[components['auto_toggle_btn'], components['auto_refresh_state']]
        )
        
        # Timer定时器（现代化响应式更新）
        if 'refresh_timer' in components:
            # 使用Timer每2秒自动更新对话显示
            components['refresh_timer'].tick(
                fn=self.update_real_chat_display,
                inputs=[],
                outputs=[components['real_chat_display']]
            )
            
            logger.info("🎯 Timer-based auto-refresh configured (every 2 seconds)")

    
    def stop(self):
        """停止API服务"""
        self.backend.stop_log_monitor()

    def get_message_update_trigger(self) -> int:
        """获取消息更新触发器值 - 用于前端状态监听"""
        return self.backend.message_update_trigger
        
    def auto_update_chat_reactive(self, trigger_value: int) -> Any:
        """基于触发器的响应式自动更新对话"""
        # 当触发器值变化时，自动更新聊天显示
        return self.update_real_chat_display()


# 全局API实例
teaching_api = TeachingAPI()