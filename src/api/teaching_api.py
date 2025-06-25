#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台 - API接口层
负责连接前端和后端，提供清晰的接口定义
"""

import gradio as gr
from typing import List, Dict, Tuple, Any
from loguru import logger

from src.backend.teaching_backend import teaching_backend
from src.frontend.teaching_frontend import teaching_frontend


class TeachingAPI:
    """教学平台API接口类"""
    
    def __init__(self):
        self.backend = teaching_backend
        self.frontend = teaching_frontend
    
    def initialize(self, engine_config, app, demo, rtc_container, storage_enabled=False):
        """初始化系统"""
        if storage_enabled:
            try:
                from src.backend.teaching_backend_with_storage import TeachingBackendWithStorage
                self.backend = TeachingBackendWithStorage()
                logger.info("Using storage-enabled backend")
            except ImportError:
                logger.warning("Storage backend not available, using standard backend")
                storage_enabled = False
        
        if not storage_enabled:
            logger.info("Using standard backend")
        
        # 设置前端更新回调，让AI主动消息能立即更新前端
        self.backend.set_frontend_update_callback(self.update_real_chat_display)
        logger.info("Frontend update callback set for real-time AI message display")
        
        success = self.backend.initialize_chat_engine(engine_config, app, demo, rtc_container)
        if success:
            self.backend.start_log_monitor()
        return success
    
    # ========== 课程会话管理 ==========
    
    def start_learning_session(self, course: str, difficulty: str, goal: str) -> Tuple[Any, ...]:
        """开始学习会话 - API接口"""
        logger.info(f"Starting learning session: course={course}, difficulty={difficulty}, goal={goal}")
        
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
        # 清空后端状态
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
        
        # # 发送消息事件
        # components['backup_send'].click(
        #     fn=self.send_message,
        #     inputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['current_course'], 
        #         components['current_difficulty']
        #     ],
        #     outputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['backup_chat_display']
        #     ]
        # )
        
        # components['backup_input'].submit(
        #     fn=self.send_message,
        #     inputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['current_course'], 
        #         components['current_difficulty']
        #     ],
        #     outputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['backup_chat_display']
        #     ]
        # )
        
        # # 快捷回复按钮事件
        # components['quick_reply_1'].click(
        #     fn=lambda ch, c, d: self.quick_reply("我听懂了", ch, c, d),
        #     inputs=[
        #         components['chat_history'], 
        #         components['current_course'], 
        #         components['current_difficulty']
        #     ],
        #     outputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['backup_chat_display']
        #     ]
        # )
        
        # components['quick_reply_2'].click(
        #     fn=lambda ch, c, d: self.quick_reply("请再解释一遍", ch, c, d),
        #     inputs=[
        #         components['chat_history'], 
        #         components['current_course'], 
        #         components['current_difficulty']
        #     ],
        #     outputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['backup_chat_display']
        #     ]
        # )
        
        # components['quick_reply_3'].click(
        #     fn=lambda ch, c, d: self.quick_reply("我有问题", ch, c, d),
        #     inputs=[
        #         components['chat_history'], 
        #         components['current_course'], 
        #         components['current_difficulty']
        #     ],
        #     outputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['backup_chat_display']
        #     ]
        # )
        
        # components['quick_reply_4'].click(
        #     fn=lambda ch, c, d: self.quick_reply("下一个知识点", ch, c, d),
        #     inputs=[
        #         components['chat_history'], 
        #         components['current_course'], 
        #         components['current_difficulty']
        #     ],
        #     outputs=[
        #         components['backup_input'], 
        #         components['chat_history'], 
        #         components['backup_chat_display']
        #     ]
        # )
        
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
        
        # # 调试信息按钮事件
        # components['debug_btn'].click(
        #     fn=self.get_debug_info,
        #     outputs=[components['debug_info_display']]
        # )
        
        # 🎯 方案一：Timer定时器（现代化响应式更新）
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