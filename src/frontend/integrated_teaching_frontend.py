#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融合教学前端 - 整合用户管理和AI教学系统
提供统一的用户界面
"""

import gradio as gr
import time
import json
import requests
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

# 导入现有的前端组件
from .user_frontend import UserFrontend
from .teaching_frontend import TeachingFrontend
from ..storage.services.user_service import user_service
from ..storage.services.course_service import course_service
from ..backend.integrated_teaching_backend import multi_user_teaching_manager


class IntegratedTeachingFrontend:
    """融合的教学前端类"""
    
    def __init__(self):
        self.user_frontend = UserFrontend()
        self.teaching_frontend = TeachingFrontend()
        self.current_user = None
        self.current_session = None
        
        # 主题配置
        self.theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="indigo",
            neutral_hue="slate"
        )
    
    def create_integrated_interface(self):
        """创建融合的用户界面"""
        with gr.Blocks(
            title="🎓 AI个性化教学平台",
            theme=self.theme,
            css=self._get_custom_css()
        ) as interface:
            
            # 状态管理
            user_session_state = gr.State({"user": None, "token": None, "logged_in": False})
            teaching_session_state = gr.State({"session_key": None, "course": None, "active": False})
            
            # 顶部导航栏
            with gr.Row(elem_id="nav-bar"):
                with gr.Column(scale=3):
                    gr.Markdown("# 🎓 AI个性化教学平台", elem_id="title")
                
                with gr.Column(scale=1):
                    user_info_display = gr.Markdown("请登录", elem_id="user-info")
                    with gr.Row():
                        login_logout_btn = gr.Button("登录", size="sm", variant="primary")
                        refresh_btn = gr.Button("🔄", size="sm", variant="secondary")
            
            # 主要内容区域
            with gr.Row():
                # 左侧边栏
                with gr.Column(scale=1, visible=False) as sidebar:
                    gr.Markdown("### 📚 快速导航")
                    
                    nav_course_btn = gr.Button("选择课程", size="lg", variant="outline")
                    nav_teaching_btn = gr.Button("AI教学", size="lg", variant="outline")
                    nav_progress_btn = gr.Button("学习进度", size="lg", variant="outline")
                    nav_profile_btn = gr.Button("个人设置", size="lg", variant="outline")
                    
                    gr.Markdown("---")
                    
                    # 快速统计
                    stats_display = gr.Markdown("### 📊 学习概况\n暂无数据")
                
                # 主内容区域
                with gr.Column(scale=4):
                    # 登录界面
                    with gr.Group(visible=True) as login_section:
                        self._create_login_interface(user_session_state)
                    
                    # 登录后的主界面
                    with gr.Group(visible=False) as main_section:
                        with gr.Tabs() as main_tabs:
                            # 课程选择标签页
                            with gr.Tab("选择课程", id="course_tab") as course_tab:
                                course_selection_components = self._create_course_selection_interface()
                            
                            # AI教学标签页
                            with gr.Tab("AI教学", id="teaching_tab") as teaching_tab:
                                teaching_components = self._create_teaching_interface()
                            
                            # 学习进度标签页
                            with gr.Tab("学习进度", id="progress_tab") as progress_tab:
                                progress_components = self._create_progress_interface()
                            
                            # 个人设置标签页
                            with gr.Tab("个人设置", id="profile_tab") as profile_tab:
                                profile_components = self._create_profile_interface()
            
            # 事件绑定
            self._bind_events(
                interface,
                user_session_state,
                teaching_session_state,
                login_section,
                main_section,
                sidebar,
                user_info_display,
                login_logout_btn,
                refresh_btn,
                stats_display,
                course_selection_components,
                teaching_components,
                progress_components,
                profile_components
            )
            
        return interface
    
    def _create_login_interface(self, user_session_state):
        """创建登录界面"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🔐 用户登录")
                
                with gr.Tab("登录"):
                    login_username = gr.Textbox(
                        label="用户名",
                        placeholder="请输入用户名",
                        elem_id="login-username"
                    )
                    login_password = gr.Textbox(
                        label="密码",
                        type="password",
                        placeholder="请输入密码",
                        elem_id="login-password"
                    )
                    login_btn = gr.Button("登录", variant="primary", size="lg")
                    login_message = gr.Markdown("")
                
                with gr.Tab("注册"):
                    reg_username = gr.Textbox(label="用户名", placeholder="3-20个字符")
                    reg_email = gr.Textbox(label="邮箱", placeholder="example@email.com")
                    reg_password = gr.Textbox(label="密码", type="password", placeholder="至少6个字符")
                    reg_confirm_password = gr.Textbox(label="确认密码", type="password")
                    reg_grade = gr.Dropdown(
                        label="年级",
                        choices=["小学一年级", "小学二年级", "小学三年级", "小学四年级", 
                                "小学五年级", "小学六年级", "初中一年级", "初中二年级", "初中三年级"],
                        value="小学三年级"
                    )
                    register_btn = gr.Button("注册", variant="secondary", size="lg")
                    register_message = gr.Markdown("")
            
            with gr.Column():
                gr.Markdown("## 🌟 平台特色")
                gr.Markdown("""
                ### ✨ 个性化AI教学
                - 🎯 根据年级和学习风格定制教学内容
                - 🧠 智能难度调节，循序渐进
                - 💬 实时互动对话，启发式教学
                
                ### 📚 丰富课程体系
                - 📖 数学、语文、英语、科学全覆盖
                - 🎓 适应不同年级学习需求
                - 🏆 课程推荐和学习路径规划
                
                ### 📊 学习进度跟踪
                - 📈 详细学习数据分析
                - 🎖️ 学习成就和里程碑
                - 👨‍👩‍👧‍👦 家长可查看学习报告
                """)
        
        return {
            "login_username": login_username,
            "login_password": login_password,
            "login_btn": login_btn,
            "login_message": login_message,
            "reg_username": reg_username,
            "reg_email": reg_email,
            "reg_password": reg_password,
            "reg_confirm_password": reg_confirm_password,
            "reg_grade": reg_grade,
            "register_btn": register_btn,
            "register_message": register_message
        }
    
    def _create_course_selection_interface(self):
        """创建课程选择界面"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 📚 选择课程")
                
                # 筛选选项
                with gr.Row():
                    grade_filter = gr.Dropdown(
                        label="年级筛选",
                        choices=["全部", "小学一年级", "小学二年级", "小学三年级", 
                                "小学四年级", "小学五年级", "小学六年级",
                                "初中一年级", "初中二年级", "初中三年级"],
                        value="全部"
                    )
                    subject_filter = gr.Dropdown(
                        label="学科筛选",
                        choices=["全部", "数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理"],
                        value="全部"
                    )
                    difficulty_filter = gr.Dropdown(
                        label="难度筛选",
                        choices=["全部", "1级-基础", "2级-初级", "3级-中级", "4级-高级", "5级-专家"],
                        value="全部"
                    )
                
                search_box = gr.Textbox(
                    label="搜索课程",
                    placeholder="输入课程名称或关键词..."
                )
                search_btn = gr.Button("搜索", variant="primary")
                
                # 课程列表
                course_list = gr.DataFrame(
                    headers=["课程名称", "学科", "年级", "难度", "描述"],
                    datatype=["str", "str", "str", "number", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 刷新按钮
                refresh_courses_btn = gr.Button("刷新课程列表", variant="secondary")
            
            with gr.Column():
                # 课程详情
                course_detail = gr.Markdown("## 课程详情\n请从左侧选择课程")
                
                # 个性化推荐
                recommendations = gr.Markdown("## 🎯 为您推荐")
                
                # 开始学习按钮
                start_learning_btn = gr.Button(
                    "开始学习", 
                    variant="primary", 
                    size="lg",
                    visible=False
                )
                
                # 选中的课程ID（隐藏）
                selected_course_id = gr.State(None)
        
        return {
            "grade_filter": grade_filter,
            "subject_filter": subject_filter,
            "difficulty_filter": difficulty_filter,
            "search_box": search_box,
            "search_btn": search_btn,
            "course_list": course_list,
            "refresh_courses_btn": refresh_courses_btn,
            "course_detail": course_detail,
            "recommendations": recommendations,
            "start_learning_btn": start_learning_btn,
            "selected_course_id": selected_course_id
        }
    
    def _create_teaching_interface(self):
        """创建AI教学界面"""
        with gr.Row():
            with gr.Column(scale=2):
                # 课程信息栏
                current_course_info = gr.Markdown("## 📖 当前课程\n请先选择课程")
                
                # 对话历史
                chat_history = gr.Chatbot(
                    label="💬 与AI老师对话",
                    height=400,
                    show_label=True,
                    show_copy_button=True
                )
                
                # 输入区域
                with gr.Row():
                    user_input = gr.Textbox(
                        label="",
                        placeholder="在这里输入您的问题或回答...",
                        lines=2,
                        scale=4
                    )
                    send_btn = gr.Button("发送", variant="primary", scale=1)
                
                # 快捷回复
                with gr.Row():
                    quick_reply_1 = gr.Button("我不明白", size="sm", variant="outline")
                    quick_reply_2 = gr.Button("请再解释一遍", size="sm", variant="outline")
                    quick_reply_3 = gr.Button("下一个问题", size="sm", variant="outline")
                    quick_reply_4 = gr.Button("我学会了", size="sm", variant="outline")
            
            with gr.Column(scale=1):
                # 学习状态
                learning_status = gr.Markdown("## 📊 学习状态\n暂无活跃会话")
                
                # 会话控制
                with gr.Group():
                    pause_session_btn = gr.Button("⏸️ 暂停会话", visible=False)
                    end_session_btn = gr.Button("⏹️ 结束会话", visible=False)
                
                # 推荐课程
                related_courses = gr.Markdown("## 🎯 相关推荐")
                
                # 学习提示
                learning_tips = gr.Markdown("""
                ## 💡 学习小贴士
                - 🎯 专注听讲，积极思考
                - 💬 大胆提问，不要害怕错误
                - 📝 记录重点，定期复习
                - 🏆 坚持练习，循序渐进
                """)
        
        return {
            "current_course_info": current_course_info,
            "chat_history": chat_history,
            "user_input": user_input,
            "send_btn": send_btn,
            "quick_reply_1": quick_reply_1,
            "quick_reply_2": quick_reply_2,
            "quick_reply_3": quick_reply_3,
            "quick_reply_4": quick_reply_4,
            "learning_status": learning_status,
            "pause_session_btn": pause_session_btn,
            "end_session_btn": end_session_btn,
            "related_courses": related_courses,
            "learning_tips": learning_tips
        }
    
    def _create_progress_interface(self):
        """创建学习进度界面"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 📈 学习进度分析")
                
                # 总体统计
                overall_stats = gr.Markdown("### 📊 总体统计\n加载中...")
                
                # 课程进度
                course_progress = gr.DataFrame(
                    headers=["课程名称", "学习次数", "总时长", "完成度", "最后学习"],
                    datatype=["str", "number", "str", "str", "str"],
                    interactive=False
                )
                
                # 学习趋势图
                learning_trend = gr.Plot(label="📈 学习趋势")
                
                refresh_progress_btn = gr.Button("刷新数据", variant="secondary")
            
            with gr.Column():
                # 成就徽章
                achievements = gr.Markdown("## 🏆 学习成就\n暂无成就")
                
                # 学习日历
                learning_calendar = gr.Markdown("## 📅 学习日历\n功能开发中...")
                
                # 推荐课程
                recommended_next = gr.Markdown("## 🎯 推荐继续学习")
        
        return {
            "overall_stats": overall_stats,
            "course_progress": course_progress,
            "learning_trend": learning_trend,
            "refresh_progress_btn": refresh_progress_btn,
            "achievements": achievements,
            "learning_calendar": learning_calendar,
            "recommended_next": recommended_next
        }
    
    def _create_profile_interface(self):
        """创建个人设置界面"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## ⚙️ 个人设置")
                
                # 基本信息
                with gr.Group():
                    gr.Markdown("### 👤 基本信息")
                    profile_username = gr.Textbox(label="用户名", interactive=False)
                    profile_email = gr.Textbox(label="邮箱")
                    profile_grade = gr.Dropdown(
                        label="年级",
                        choices=["小学一年级", "小学二年级", "小学三年级", 
                                "小学四年级", "小学五年级", "小学六年级",
                                "初中一年级", "初中二年级", "初中三年级"]
                    )
                    profile_parent_contact = gr.Textbox(label="家长联系方式")
                
                # 学习偏好
                with gr.Group():
                    gr.Markdown("### 🎯 学习偏好")
                    learning_style = gr.Dropdown(
                        label="学习风格",
                        choices=["视觉型", "听觉型", "动觉型", "混合型"],
                        value="混合型"
                    )
                    difficulty_preference = gr.Slider(
                        label="难度偏好",
                        minimum=1,
                        maximum=5,
                        step=1,
                        value=3
                    )
                    favorite_subjects = gr.CheckboxGroup(
                        label="喜欢的学科",
                        choices=["数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理"],
                        value=["数学"]
                    )
                
                update_profile_btn = gr.Button("更新设置", variant="primary")
                profile_message = gr.Markdown("")
            
            with gr.Column():
                # 密码修改
                with gr.Group():
                    gr.Markdown("### 🔐 修改密码")
                    current_password = gr.Textbox(label="当前密码", type="password")
                    new_password = gr.Textbox(label="新密码", type="password")
                    confirm_new_password = gr.Textbox(label="确认新密码", type="password")
                    change_password_btn = gr.Button("修改密码", variant="secondary")
                    password_message = gr.Markdown("")
                
                # 账户操作
                with gr.Group():
                    gr.Markdown("### 🔧 账户操作")
                    export_data_btn = gr.Button("导出学习数据", variant="outline")
                    delete_account_btn = gr.Button("删除账户", variant="stop")
        
        return {
            "profile_username": profile_username,
            "profile_email": profile_email,
            "profile_grade": profile_grade,
            "profile_parent_contact": profile_parent_contact,
            "learning_style": learning_style,
            "difficulty_preference": difficulty_preference,
            "favorite_subjects": favorite_subjects,
            "update_profile_btn": update_profile_btn,
            "profile_message": profile_message,
            "current_password": current_password,
            "new_password": new_password,
            "confirm_new_password": confirm_new_password,
            "change_password_btn": change_password_btn,
            "password_message": password_message,
            "export_data_btn": export_data_btn,
            "delete_account_btn": delete_account_btn
        }
    
    def _bind_events(self, interface, user_session_state, teaching_session_state, 
                    login_section, main_section, sidebar, user_info_display, 
                    login_logout_btn, refresh_btn, stats_display,
                    course_selection_components, teaching_components, 
                    progress_components, profile_components):
        """绑定界面事件"""
        
        # 登录事件
        login_components = self._get_login_components(login_section)
        
        login_components["login_btn"].click(
            fn=self._handle_login,
            inputs=[
                login_components["login_username"],
                login_components["login_password"],
                user_session_state
            ],
            outputs=[
                user_session_state,
                login_section,
                main_section,
                sidebar,
                user_info_display,
                login_logout_btn,
                login_components["login_message"]
            ]
        )
        
        # 注册事件
        login_components["register_btn"].click(
            fn=self._handle_register,
            inputs=[
                login_components["reg_username"],
                login_components["reg_email"],
                login_components["reg_password"],
                login_components["reg_confirm_password"],
                login_components["reg_grade"]
            ],
            outputs=[login_components["register_message"]]
        )
        
        # 登出事件
        login_logout_btn.click(
            fn=self._handle_logout,
            inputs=[user_session_state],
            outputs=[
                user_session_state,
                login_section,
                main_section,
                sidebar,
                user_info_display,
                login_logout_btn
            ]
        )
        
        # 课程选择事件
        course_selection_components["start_learning_btn"].click(
            fn=self._start_teaching_session,
            inputs=[
                course_selection_components["selected_course_id"],
                user_session_state,
                teaching_session_state
            ],
            outputs=[
                teaching_session_state,
                teaching_components["current_course_info"],
                teaching_components["chat_history"],
                teaching_components["learning_status"]
            ]
        )
        
        # 发送消息事件
        teaching_components["send_btn"].click(
            fn=self._send_teaching_message,
            inputs=[
                teaching_components["user_input"],
                user_session_state,
                teaching_session_state
            ],
            outputs=[
                teaching_components["chat_history"],
                teaching_components["user_input"],
                teaching_components["learning_status"],
                teaching_components["related_courses"]
            ]
        )
    
    def _get_login_components(self, login_section):
        """从登录区域提取组件（需要具体实现）"""
        # 这里需要根据实际的组件结构来提取
        # 暂时返回空字典，在实际实现中需要完善
        return {}
    
    def _handle_login(self, username: str, password: str, session_state: Dict) -> Tuple:
        """处理用户登录"""
        try:
            # 调用用户服务进行认证
            result = user_service.authenticate_user(username, password)
            
            if result["success"]:
                user_data = result["user"]
                token = result["token"]
                
                # 更新会话状态
                new_session_state = {
                    "user": user_data,
                    "token": token,
                    "logged_in": True
                }
                
                # 更新用户信息显示
                user_info = f"👤 {user_data['username']} ({user_data.get('grade_level', 'N/A')})"
                
                return (
                    new_session_state,  # user_session_state
                    gr.update(visible=False),  # login_section
                    gr.update(visible=True),   # main_section
                    gr.update(visible=True),   # sidebar
                    user_info,  # user_info_display
                    gr.update(value="登出", variant="secondary"),  # login_logout_btn
                    "✅ 登录成功！"  # login_message
                )
            else:
                return (
                    session_state,
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    f"❌ 登录失败：{result['message']}"
                )
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return (
                session_state,
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                f"❌ 登录出错：{str(e)}"
            )
    
    def _handle_register(self, username: str, email: str, password: str, 
                        confirm_password: str, grade: str) -> str:
        """处理用户注册"""
        try:
            # 验证输入
            if not username or not email or not password:
                return "❌ 请填写所有必需信息"
            
            if password != confirm_password:
                return "❌ 两次输入的密码不一致"
            
            if len(password) < 6:
                return "❌ 密码长度至少6个字符"
            
            # 调用用户服务进行注册
            result = user_service.create_user({
                "username": username,
                "email": email,
                "password": password,
                "grade_level": grade,
                "role": "student"
            })
            
            if result["success"]:
                return "✅ 注册成功！请使用用户名和密码登录。"
            else:
                return f"❌ 注册失败：{result['message']}"
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return f"❌ 注册出错：{str(e)}"
    
    def _handle_logout(self, session_state: Dict) -> Tuple:
        """处理用户登出"""
        try:
            # 如果有token，调用登出接口
            if session_state.get("token"):
                user_service.logout_user(session_state["token"])
            
            # 重置会话状态
            new_session_state = {"user": None, "token": None, "logged_in": False}
            
            return (
                new_session_state,  # user_session_state
                gr.update(visible=True),   # login_section
                gr.update(visible=False),  # main_section
                gr.update(visible=False),  # sidebar
                "请登录",  # user_info_display
                gr.update(value="登录", variant="primary")  # login_logout_btn
            )
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return (session_state, gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    
    def _start_teaching_session(self, course_id: int, user_session: Dict, 
                               teaching_session: Dict) -> Tuple:
        """启动教学会话"""
        try:
            if not user_session.get("logged_in") or not course_id:
                return (
                    teaching_session,
                    "❌ 请先登录并选择课程",
                    [],
                    "未启动会话"
                )
            
            user_id = user_session["user"]["id"]
            session_token = user_session["token"]
            
            # 创建教学会话
            session_data = multi_user_teaching_manager.create_teaching_session(
                user_id, course_id, session_token
            )
            
            # 更新教学会话状态
            new_teaching_session = {
                "session_key": session_data["session_key"],
                "course": session_data["course_info"],
                "active": True
            }
            
            # 初始化对话历史
            initial_chat = [("系统", session_data["welcome_message"])]
            
            # 课程信息显示
            course_info_md = f"""
            ## 📖 {session_data['course_info']['name']}
            
            **学科**: {session_data['course_info']['subject']}  
            **难度**: {session_data['course_info']['difficulty_level']}/5  
            **描述**: {session_data['course_info'].get('description', 'N/A')}
            
            🎯 **个性化设置已启用**
            """
            
            # 学习状态
            learning_status_md = f"""
            ## 📊 学习状态
            
            ✅ **会话已启动**  
            📚 正在学习: {session_data['course_info']['name']}  
            👤 学习者: {session_data['user_info']['username']}  
            ⏰ 开始时间: {time.strftime('%H:%M:%S')}
            """
            
            return (
                new_teaching_session,
                course_info_md,
                initial_chat,
                learning_status_md
            )
            
        except Exception as e:
            logger.error(f"Start teaching session error: {e}")
            return (
                teaching_session,
                f"❌ 启动会话失败：{str(e)}",
                [],
                "启动失败"
            )
    
    def _send_teaching_message(self, message: str, user_session: Dict, 
                              teaching_session: Dict) -> Tuple:
        """发送教学消息"""
        try:
            if not teaching_session.get("active") or not message.strip():
                return (gr.update(), "", gr.update(), gr.update())
            
            user_id = user_session["user"]["id"]
            session_key = teaching_session["session_key"]
            
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
            
            # 更新学习状态
            session_info = response_data["session_info"]
            learning_status_md = f"""
            ## 📊 学习状态
            
            ✅ **会话进行中**  
            💬 消息数: {session_info['message_count']}  
            ⏱️ 会话时长: {session_info['duration'] // 60}分{session_info['duration'] % 60}秒  
            🚀 响应时间: {response_data['response_time']:.0f}ms
            """
            
            # 推荐课程
            recommendations = response_data.get("recommendations", [])
            related_courses_md = "## 🎯 相关推荐\n\n"
            for rec in recommendations[:3]:
                course = rec["course"]
                related_courses_md += f"- 📚 **{course['name']}** ({rec['reason']})\n"
            
            return (
                chat_history,
                "",  # 清空输入框
                learning_status_md,
                related_courses_md
            )
            
        except Exception as e:
            logger.error(f"Send teaching message error: {e}")
            return (gr.update(), message, gr.update(), gr.update())
    
    def _get_custom_css(self) -> str:
        """获取自定义CSS样式"""
        return """
        #title {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: bold;
            font-size: 2em;
        }
        
        #nav-bar {
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 1rem;
            margin-bottom: 1rem;
        }
        
        #user-info {
            text-align: right;
            color: #6b7280;
        }
        
        .gradio-container {
            max-width: 1400px !important;
        }
        
        .chat-message {
            border-radius: 10px;
            padding: 10px;
            margin: 5px 0;
        }
        
        .user-message {
            background-color: #e3f2fd;
            margin-left: 20%;
        }
        
        .ai-message {
            background-color: #f3e5f5;
            margin-right: 20%;
        }
        """


# 创建全局实例
integrated_frontend = IntegratedTeachingFrontend()


def create_integrated_interface():
    """创建融合界面的工厂函数"""
    return integrated_frontend.create_integrated_interface() 