#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融合前端界面 - 用户系统 + AI教学系统
基于现有PostgreSQL存储架构的简化版本
"""

import gradio as gr
import time
from typing import Dict, List, Tuple, Optional
from loguru import logger

from ..storage.services.user_service import user_service
from ..storage.services.course_service import course_service
from ..backend.integrated_teaching_backend import multi_user_teaching_manager


class IntegratedFrontend:
    """融合前端类"""
    
    def __init__(self):
        self.current_user_session = None
        self.current_teaching_session = None
    
    def create_interface(self):
        """创建融合界面"""
        with gr.Blocks(title="🎓 AI教学平台", theme=gr.themes.Soft()) as interface:
            
            # 全局状态
            user_state = gr.State({"logged_in": False, "user": None, "token": None})
            session_state = gr.State({"active": False, "session_key": None, "course": None})
            
            # 顶部标题和用户信息
            with gr.Row():
                gr.Markdown("# 🎓 AI个性化教学平台")
                user_info = gr.Markdown("请登录", elem_id="user-info")
                login_btn = gr.Button("登录", size="sm")
            
            # 主要内容
            with gr.Tabs() as main_tabs:
                # 登录/注册标签页
                with gr.Tab("登录", visible=True) as login_tab:
                    login_components = self._create_login_tab()
                
                # 课程选择标签页
                with gr.Tab("选择课程", visible=False) as course_tab:
                    course_components = self._create_course_tab()
                
                # AI教学标签页
                with gr.Tab("AI教学", visible=False) as teaching_tab:
                    teaching_components = self._create_teaching_tab()
                
                # 学习进度标签页
                with gr.Tab("学习进度", visible=False) as progress_tab:
                    progress_components = self._create_progress_tab()
            
            # 绑定事件
            self._bind_events(
                user_state, session_state, user_info, login_btn,
                login_tab, course_tab, teaching_tab, progress_tab,
                login_components, course_components, teaching_components, progress_components
            )
            
        return interface
    
    def _create_login_tab(self):
        """创建登录标签页"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🔐 用户登录")
                
                with gr.Tab("登录"):
                    username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                    password = gr.Textbox(label="密码", type="password", placeholder="请输入密码")
                    login_submit_btn = gr.Button("登录", variant="primary")
                    login_msg = gr.Markdown("")
                
                with gr.Tab("注册"):
                    reg_username = gr.Textbox(label="用户名")
                    reg_email = gr.Textbox(label="邮箱")
                    reg_password = gr.Textbox(label="密码", type="password")
                    reg_grade = gr.Dropdown(
                        label="年级",
                        choices=["小学一年级", "小学二年级", "小学三年级", "小学四年级", 
                                "小学五年级", "小学六年级", "初中一年级", "初中二年级", "初中三年级"],
                        value="小学三年级"
                    )
                    register_btn = gr.Button("注册", variant="secondary")
                    register_msg = gr.Markdown("")
            
            with gr.Column():
                gr.Markdown("""
                ## 🌟 AI教学平台特色
                
                ### ✨ 个性化教学
                - 🎯 根据年级和学习偏好定制内容
                - 🧠 智能难度调节
                - 💬 实时对话式教学
                
                ### 📚 丰富课程
                - 📖 数学、语文、英语、科学全覆盖
                - 🎓 多年级课程体系
                - 🏆 个性化推荐
                """)
        
        return {
            "username": username, "password": password, "login_submit_btn": login_submit_btn, "login_msg": login_msg,
            "reg_username": reg_username, "reg_email": reg_email, "reg_password": reg_password, 
            "reg_grade": reg_grade, "register_btn": register_btn, "register_msg": register_msg
        }
    
    def _create_course_tab(self):
        """创建课程选择标签页"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 📚 选择课程")
                
                # 筛选器
                subject_filter = gr.Dropdown(
                    label="学科筛选",
                    choices=["全部", "数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理"],
                    value="全部"
                )
                difficulty_filter = gr.Dropdown(
                    label="难度筛选", 
                    choices=["全部", "1-基础", "2-初级", "3-中级", "4-高级", "5-专家"],
                    value="全部"
                )
                
                # 课程列表
                course_list = gr.DataFrame(
                    headers=["ID", "课程名称", "学科", "难度", "描述"],
                    datatype=["number", "str", "str", "number", "str"],
                    interactive=False
                )
                
                refresh_courses_btn = gr.Button("刷新课程", variant="secondary")
                
            with gr.Column():
                course_detail = gr.Markdown("## 课程详情\n请选择课程")
                selected_course_id = gr.Number(label="选中课程ID", visible=False)
                start_learning_btn = gr.Button("开始学习", variant="primary", size="lg")
                
                recommendations = gr.Markdown("## 🎯 推荐课程")
        
        return {
            "subject_filter": subject_filter, "difficulty_filter": difficulty_filter,
            "course_list": course_list, "refresh_courses_btn": refresh_courses_btn,
            "course_detail": course_detail, "selected_course_id": selected_course_id,
            "start_learning_btn": start_learning_btn, "recommendations": recommendations
        }
    
    def _create_teaching_tab(self):
        """创建AI教学标签页"""
        with gr.Row():
            with gr.Column(scale=3):
                current_course = gr.Markdown("## 📖 当前课程\n请先选择课程")
                
                chat_display = gr.Chatbot(
                    label="💬 与AI老师对话",
                    height=400
                )
                
                with gr.Row():
                    user_input = gr.Textbox(
                        label="",
                        placeholder="输入您的问题或回答...",
                        lines=2,
                        scale=4
                    )
                    send_btn = gr.Button("发送", variant="primary", scale=1)
                
                # 快捷回复
                with gr.Row():
                    quick_1 = gr.Button("我不明白", size="sm")
                    quick_2 = gr.Button("请再解释", size="sm") 
                    quick_3 = gr.Button("继续", size="sm")
                    quick_4 = gr.Button("我学会了", size="sm")
            
            with gr.Column(scale=1):
                learning_status = gr.Markdown("## 📊 学习状态\n暂无会话")
                
                end_session_btn = gr.Button("结束会话", variant="stop", visible=False)
                
                related_courses = gr.Markdown("## 🎯 相关课程")
        
        return {
            "current_course": current_course, "chat_display": chat_display,
            "user_input": user_input, "send_btn": send_btn,
            "quick_1": quick_1, "quick_2": quick_2, "quick_3": quick_3, "quick_4": quick_4,
            "learning_status": learning_status, "end_session_btn": end_session_btn,
            "related_courses": related_courses
        }
    
    def _create_progress_tab(self):
        """创建学习进度标签页"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 📈 学习进度")
                
                overall_stats = gr.Markdown("### 📊 总体统计\n加载中...")
                
                course_progress = gr.DataFrame(
                    headers=["课程", "学习次数", "总时长", "最后学习"],
                    datatype=["str", "number", "str", "str"],
                    interactive=False
                )
                
                refresh_stats_btn = gr.Button("刷新统计", variant="secondary")
            
            with gr.Column():
                achievements = gr.Markdown("## 🏆 学习成就\n暂无成就")
                recommended_next = gr.Markdown("## 🎯 推荐继续学习")
        
        return {
            "overall_stats": overall_stats, "course_progress": course_progress,
            "refresh_stats_btn": refresh_stats_btn, "achievements": achievements,
            "recommended_next": recommended_next
        }
    
    def _bind_events(self, user_state, session_state, user_info, login_btn,
                    login_tab, course_tab, teaching_tab, progress_tab,
                    login_components, course_components, teaching_components, progress_components):
        """绑定事件处理"""
        
        # 登录事件
        login_components["login_submit_btn"].click(
            fn=self._handle_login,
            inputs=[login_components["username"], login_components["password"], user_state],
            outputs=[user_state, user_info, login_btn, login_tab, course_tab, teaching_tab, progress_tab, login_components["login_msg"]]
        )
        
        # 注册事件
        login_components["register_btn"].click(
            fn=self._handle_register,
            inputs=[login_components["reg_username"], login_components["reg_email"], 
                   login_components["reg_password"], login_components["reg_grade"]],
            outputs=[login_components["register_msg"]]
        )
        
        # 登出事件
        login_btn.click(
            fn=self._handle_logout,
            inputs=[user_state],
            outputs=[user_state, user_info, login_btn, login_tab, course_tab, teaching_tab, progress_tab]
        )
        
        # 刷新课程事件
        course_components["refresh_courses_btn"].click(
            fn=self._load_courses,
            inputs=[user_state, course_components["subject_filter"], course_components["difficulty_filter"]],
            outputs=[course_components["course_list"], course_components["recommendations"]]
        )
        
        # 开始学习事件
        course_components["start_learning_btn"].click(
            fn=self._start_learning,
            inputs=[course_components["selected_course_id"], user_state, session_state],
            outputs=[session_state, teaching_components["current_course"], teaching_components["chat_display"], 
                    teaching_components["learning_status"], teaching_tab]
        )
        
        # 发送消息事件
        teaching_components["send_btn"].click(
            fn=self._send_message,
            inputs=[teaching_components["user_input"], user_state, session_state],
            outputs=[teaching_components["chat_display"], teaching_components["user_input"], 
                    teaching_components["learning_status"], teaching_components["related_courses"]]
        )
    
    def _handle_login(self, username: str, password: str, user_state: Dict) -> Tuple:
        """处理登录"""
        try:
            result = user_service.authenticate_user(username, password)
            
            if result["success"]:
                new_state = {
                    "logged_in": True,
                    "user": result["user"],
                    "token": result["token"]
                }
                
                user_info_text = f"👤 {result['user']['username']} ({result['user'].get('grade_level', 'N/A')})"
                
                return (
                    new_state,
                    user_info_text,
                    gr.update(value="登出", variant="secondary"),
                    gr.update(visible=False),  # login_tab
                    gr.update(visible=True),   # course_tab
                    gr.update(visible=True),   # teaching_tab
                    gr.update(visible=True),   # progress_tab
                    "✅ 登录成功！"
                )
            else:
                return (
                    user_state, gr.update(), gr.update(), 
                    gr.update(), gr.update(), gr.update(), gr.update(),
                    f"❌ 登录失败：{result['message']}"
                )
        except Exception as e:
            logger.error(f"Login error: {e}")
            return (
                user_state, gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(),
                f"❌ 登录错误：{str(e)}"
            )
    
    def _handle_register(self, username: str, email: str, password: str, grade: str) -> str:
        """处理注册"""
        try:
            if not username or not email or not password:
                return "❌ 请填写所有信息"
            
            result = user_service.create_user({
                "username": username,
                "email": email,
                "password": password,
                "grade_level": grade,
                "role": "student"
            })
            
            if result["success"]:
                return "✅ 注册成功！请登录。"
            else:
                return f"❌ 注册失败：{result['message']}"
        except Exception as e:
            logger.error(f"Register error: {e}")
            return f"❌ 注册错误：{str(e)}"
    
    def _handle_logout(self, user_state: Dict) -> Tuple:
        """处理登出"""
        try:
            if user_state.get("token"):
                user_service.logout_user(user_state["token"])
            
            new_state = {"logged_in": False, "user": None, "token": None}
            
            return (
                new_state,
                "请登录",
                gr.update(value="登录", variant="primary"),
                gr.update(visible=True),   # login_tab
                gr.update(visible=False),  # course_tab
                gr.update(visible=False),  # teaching_tab
                gr.update(visible=False)   # progress_tab
            )
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return (user_state, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    
    def _load_courses(self, user_state: Dict, subject_filter: str, difficulty_filter: str) -> Tuple:
        """加载课程列表"""
        try:
            if not user_state.get("logged_in"):
                return ([], "请先登录")
            
            # 获取课程列表
            courses = course_service.get_all_courses()
            
            # 应用筛选
            if subject_filter != "全部":
                courses = [c for c in courses if c.get("subject") == subject_filter.lower()]
            
            if difficulty_filter != "全部":
                difficulty = int(difficulty_filter.split("-")[0])
                courses = [c for c in courses if c.get("difficulty_level") == difficulty]
            
            # 转换为DataFrame格式
            course_data = []
            for course in courses:
                course_data.append([
                    course["id"],
                    course["name"],
                    course["subject"],
                    course["difficulty_level"],
                    course.get("description", "")[:100] + "..." if len(course.get("description", "")) > 100 else course.get("description", "")
                ])
            
            # 获取推荐课程
            rec_text = "## 🎯 推荐课程\n\n暂无推荐"
            
            return (course_data, rec_text)
            
        except Exception as e:
            logger.error(f"Load courses error: {e}")
            return ([], f"❌ 加载课程失败：{str(e)}")
    
    def _start_learning(self, course_id: int, user_state: Dict, session_state: Dict) -> Tuple:
        """开始学习"""
        try:
            if not user_state.get("logged_in") or not course_id:
                return (session_state, "❌ 请先登录并选择课程", [], "未启动", gr.update())
            
            user_id = user_state["user"]["id"]
            token = user_state["token"]
            
            # 创建教学会话
            session_data = multi_user_teaching_manager.create_teaching_session(
                user_id, int(course_id), token
            )
            
            new_session_state = {
                "active": True,
                "session_key": session_data["session_key"],
                "course": session_data["course_info"]
            }
            
            # 课程信息
            course_info_md = f"""
            ## 📖 {session_data['course_info']['name']}
            
            **学科**: {session_data['course_info']['subject']}  
            **难度**: {session_data['course_info']['difficulty_level']}/5  
            **描述**: {session_data['course_info'].get('description', 'N/A')}
            
            🎯 **个性化教学已启用**
            """
            
            # 初始对话
            initial_chat = [("👩‍🏫 AI老师", session_data["welcome_message"])]
            
            # 学习状态
            status_md = f"""
            ## 📊 学习状态
            
            ✅ **会话已启动**  
            📚 课程: {session_data['course_info']['name']}  
            👤 学习者: {session_data['user_info']['username']}  
            ⏰ 开始时间: {time.strftime('%H:%M:%S')}
            """
            
            return (
                new_session_state,
                course_info_md,
                initial_chat,
                status_md,
                gr.update(selected=2)  # 切换到教学标签页
            )
            
        except Exception as e:
            logger.error(f"Start learning error: {e}")
            return (session_state, f"❌ 启动失败：{str(e)}", [], "启动失败", gr.update())
    
    def _send_message(self, message: str, user_state: Dict, session_state: Dict) -> Tuple:
        """发送消息"""
        try:
            if not session_state.get("active") or not message.strip():
                return (gr.update(), "", gr.update(), gr.update())
            
            user_id = user_state["user"]["id"]
            session_key = session_state["session_key"]
            
            # 处理消息
            response_data = multi_user_teaching_manager.process_user_message(
                user_id, message, session_key
            )
            
            # 构建对话历史
            chat_history = []
            for msg in response_data["chat_history"]:
                if msg["role"] == "human":
                    chat_history.append((msg["content"], None))
                elif msg["role"] == "avatar":
                    if chat_history and chat_history[-1][1] is None:
                        chat_history[-1] = (chat_history[-1][0], msg["content"])
                    else:
                        chat_history.append((None, msg["content"]))
            
            # 学习状态更新
            session_info = response_data["session_info"]
            status_md = f"""
            ## 📊 学习状态
            
            ✅ **对话进行中**  
            💬 消息数: {session_info['message_count']}  
            ⏱️ 时长: {session_info['duration'] // 60}分{session_info['duration'] % 60}秒  
            🚀 响应: {response_data['response_time']:.0f}ms
            """
            
            # 相关课程
            related_md = "## 🎯 相关课程\n\n暂无推荐"
            
            return (chat_history, "", status_md, related_md)
            
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return (gr.update(), message, gr.update(), gr.update())


# 创建全局实例
integrated_frontend = IntegratedFrontend()


def create_integrated_interface():
    """创建融合界面"""
    return integrated_frontend.create_interface() 