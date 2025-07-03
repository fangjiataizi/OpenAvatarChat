"""
用户管理前端界面 - AI教学平台
"""
import gradio as gr
import logging
from typing import Optional, Dict, List, Any, Tuple
import json
import traceback

from ..storage.services.user_service import user_service
from ..storage.services.course_service import course_service
from ..storage.database.models import SubjectType

logger = logging.getLogger(__name__)


class UserFrontend:
    """用户管理前端界面"""
    
    def __init__(self):
        self.current_user = None
        self.session_token = None
        
    def create_user_interface(self) -> Dict[str, Any]:
        """创建用户管理界面"""
        with gr.Blocks(title="AI教学平台 - 用户管理", theme=gr.themes.Soft()) as interface:
            # 全局状态
            session_state = gr.State({"user": None, "token": None})
            
            # 顶部导航栏
            with gr.Row():
                gr.Markdown("# 🎓 AI教学平台")
                
                with gr.Column(scale=1):
                    user_info_display = gr.Markdown("未登录", elem_id="user-info")
                    with gr.Row():
                        login_btn = gr.Button("登录", size="sm", visible=True)
                        logout_btn = gr.Button("登出", size="sm", visible=False)
            
            # 主要内容区域
            with gr.Tabs() as main_tabs:
                # 登录/注册标签页
                with gr.Tab("登录注册", visible=True) as login_tab:
                    with gr.Row():
                        # 登录表单
                        with gr.Column():
                            gr.Markdown("## 登录")
                            
                            login_username = gr.Textbox(
                                label="用户名",
                                placeholder="请输入用户名"
                            )
                            login_password = gr.Textbox(
                                label="密码",
                                type="password",
                                placeholder="请输入密码"
                            )
                            
                            with gr.Row():
                                login_submit_btn = gr.Button("登录", variant="primary")
                                login_clear_btn = gr.Button("清空")
                            
                            login_message = gr.Markdown("", visible=False)
                        
                        # 注册表单
                        with gr.Column():
                            gr.Markdown("## 学生注册")
                            
                            reg_username = gr.Textbox(
                                label="用户名",
                                placeholder="3-50个字符"
                            )
                            reg_password = gr.Textbox(
                                label="密码",
                                type="password",
                                placeholder="至少6个字符"
                            )
                            reg_email = gr.Textbox(
                                label="邮箱（可选）",
                                placeholder="example@email.com"
                            )
                            reg_grade = gr.Dropdown(
                                label="年级",
                                choices=[
                                    "小学一年级", "小学二年级", "小学三年级", 
                                    "小学四年级", "小学五年级", "小学六年级",
                                    "初中一年级", "初中二年级", "初中三年级",
                                    "高中一年级", "高中二年级", "高中三年级"
                                ],
                                value=None
                            )
                            reg_parent_contact = gr.Textbox(
                                label="家长联系方式（可选）",
                                placeholder="家长手机号或邮箱"
                            )
                            
                            with gr.Row():
                                register_btn = gr.Button("注册", variant="primary")
                                reg_clear_btn = gr.Button("清空")
                            
                            register_message = gr.Markdown("", visible=False)
                
                # 个人资料标签页
                with gr.Tab("个人资料", visible=False) as profile_tab:
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("## 个人信息")
                            
                            profile_username = gr.Textbox(
                                label="用户名",
                                interactive=False
                            )
                            profile_email = gr.Textbox(
                                label="邮箱",
                                interactive=False
                            )
                            profile_role = gr.Textbox(
                                label="角色",
                                interactive=False
                            )
                            profile_created = gr.Textbox(
                                label="注册时间",
                                interactive=False
                            )
                        
                        with gr.Column():
                            gr.Markdown("## 学习设置")
                            
                            profile_grade = gr.Dropdown(
                                label="年级",
                                choices=[
                                    "小学一年级", "小学二年级", "小学三年级", 
                                    "小学四年级", "小学五年级", "小学六年级",
                                    "初中一年级", "初中二年级", "初中三年级",
                                    "高中一年级", "高中二年级", "高中三年级"
                                ]
                            )
                            profile_parent_contact = gr.Textbox(
                                label="家长联系方式"
                            )
                            
                            with gr.Accordion("学习偏好", open=False):
                                learning_style = gr.Dropdown(
                                    label="学习风格",
                                    choices=["视觉型", "听觉型", "动觉型", "混合型"],
                                    value="混合型"
                                )
                                difficulty_preference = gr.Slider(
                                    label="难度偏好",
                                    minimum=1,
                                    maximum=5,
                                    value=3,
                                    step=1
                                )
                                favorite_subjects = gr.CheckboxGroup(
                                    label="喜欢的学科",
                                    choices=[s.value for s in SubjectType]
                                )
                            
                            profile_update_btn = gr.Button("更新资料", variant="primary")
                            profile_message = gr.Markdown("", visible=False)
                
                # 学习统计标签页
                with gr.Tab("学习统计", visible=False) as stats_tab:
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("## 学习概况")
                            
                            stats_display = gr.JSON(
                                label="学习统计",
                                value={}
                            )
                            
                            stats_refresh_btn = gr.Button("刷新统计")
                        
                        with gr.Column():
                            gr.Markdown("## 推荐课程")
                            
                            recommended_courses = gr.DataFrame(
                                headers=["课程名称", "学科", "难度"],
                                datatype=["str", "str", "number"],
                                wrap=True
                            )
                            
                            refresh_recommendations_btn = gr.Button("刷新推荐")
                
                # 管理员标签页
                with gr.Tab("系统管理", visible=False) as admin_tab:
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("## 用户管理")
                            
                            with gr.Row():
                                admin_search_username = gr.Textbox(
                                    label="搜索用户",
                                    placeholder="用户名"
                                )
                                admin_search_btn = gr.Button("搜索")
                            
                            admin_grade_filter = gr.Dropdown(
                                label="年级筛选",
                                choices=["全部"] + [
                                    "小学一年级", "小学二年级", "小学三年级", 
                                    "小学四年级", "小学五年级", "小学六年级",
                                    "初中一年级", "初中二年级", "初中三年级",
                                    "高中一年级", "高中二年级", "高中三年级"
                                ],
                                value="全部"
                            )
                            
                            users_list = gr.DataFrame(
                                headers=["ID", "用户名", "角色", "年级", "创建时间"],
                                datatype=["number", "str", "str", "str", "str"],
                                wrap=True
                            )
                            
                            load_users_btn = gr.Button("加载用户列表")
                        
                        with gr.Column():
                            gr.Markdown("## 创建管理员")
                            
                            admin_new_username = gr.Textbox(
                                label="管理员用户名"
                            )
                            admin_new_password = gr.Textbox(
                                label="管理员密码",
                                type="password"
                            )
                            admin_new_email = gr.Textbox(
                                label="管理员邮箱（可选）"
                            )
                            
                            create_admin_btn = gr.Button("创建管理员", variant="primary")
                            admin_message = gr.Markdown("", visible=False)
            
            # 事件处理函数
            def handle_login(username: str, password: str, session_state: Dict):
                """处理用户登录"""
                try:
                    if not username or not password:
                        return (
                            session_state,
                            gr.update(value="请输入用户名和密码", visible=True),
                            gr.update(visible=True),  # 登录标签页
                            gr.update(visible=False), # 个人资料标签页
                            gr.update(visible=False), # 统计标签页
                            gr.update(visible=False), # 管理员标签页
                            gr.update(value="未登录"),
                            gr.update(visible=True),  # 登录按钮
                            gr.update(visible=False)  # 登出按钮
                        )
                    
                    result = user_service.authenticate_user(username, password)
                    
                    if result:
                        session_state["user"] = result
                        session_state["token"] = result["session_token"]
                        
                        user_info = f"👤 {result['username']} ({result['role']})"
                        
                        # 根据角色显示不同的标签页
                        if result["role"] == "admin":
                            return (
                                session_state,
                                gr.update(value="登录成功！", visible=True),
                                gr.update(visible=False), # 登录标签页
                                gr.update(visible=True),  # 个人资料标签页
                                gr.update(visible=True),  # 统计标签页
                                gr.update(visible=True),  # 管理员标签页
                                gr.update(value=user_info),
                                gr.update(visible=False), # 登录按钮
                                gr.update(visible=True)   # 登出按钮
                            )
                        else:
                            return (
                                session_state,
                                gr.update(value="登录成功！", visible=True),
                                gr.update(visible=False), # 登录标签页
                                gr.update(visible=True),  # 个人资料标签页
                                gr.update(visible=True),  # 统计标签页
                                gr.update(visible=False), # 管理员标签页
                                gr.update(value=user_info),
                                gr.update(visible=False), # 登录按钮
                                gr.update(visible=True)   # 登出按钮
                            )
                    else:
                        return (
                            session_state,
                            gr.update(value="用户名或密码错误", visible=True),
                            gr.update(visible=True),  # 登录标签页
                            gr.update(visible=False), # 个人资料标签页
                            gr.update(visible=False), # 统计标签页
                            gr.update(visible=False), # 管理员标签页
                            gr.update(value="未登录"),
                            gr.update(visible=True),  # 登录按钮
                            gr.update(visible=False)  # 登出按钮
                        )
                        
                except Exception as e:
                    logger.error(f"Login error: {e}")
                    return (
                        session_state,
                        gr.update(value=f"登录失败: {str(e)}", visible=True),
                        gr.update(visible=True),  # 登录标签页
                        gr.update(visible=False), # 个人资料标签页
                        gr.update(visible=False), # 统计标签页
                        gr.update(visible=False), # 管理员标签页
                        gr.update(value="未登录"),
                        gr.update(visible=True),  # 登录按钮
                        gr.update(visible=False)  # 登出按钮
                    )
            
            def handle_logout(session_state: Dict):
                """处理用户登出"""
                try:
                    if session_state.get("token"):
                        user_service.logout_user(session_state["token"])
                    
                    # 重置状态
                    session_state["user"] = None
                    session_state["token"] = None
                    
                    return (
                        session_state,
                        gr.update(visible=True),  # 登录标签页
                        gr.update(visible=False), # 个人资料标签页
                        gr.update(visible=False), # 统计标签页
                        gr.update(visible=False), # 管理员标签页
                        gr.update(value="未登录"),
                        gr.update(visible=True),  # 登录按钮
                        gr.update(visible=False)  # 登出按钮
                    )
                    
                except Exception as e:
                    logger.error(f"Logout error: {e}")
                    return (
                        session_state,
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(value="登出失败"),
                        gr.update(visible=True),
                        gr.update(visible=False)
                    )
            
            def handle_register(username: str, password: str, email: str, 
                              grade: str, parent_contact: str):
                """处理学生注册"""
                try:
                    if not username or not password:
                        return gr.update(value="请输入用户名和密码", visible=True)
                    
                    # 构建学习偏好
                    learning_preferences = {
                        "learning_style": "混合型",
                        "difficulty_preference": 3,
                        "favorite_subjects": []
                    }
                    
                    result = user_service.create_student(
                        username=username,
                        password=password,
                        email=email or None,
                        grade_level=grade or None,
                        parent_contact=parent_contact or None,
                        learning_preferences=learning_preferences
                    )
                    
                    if result:
                        return gr.update(value="注册成功！请登录。", visible=True)
                    else:
                        return gr.update(value="注册失败，用户名可能已存在", visible=True)
                        
                except Exception as e:
                    logger.error(f"Registration error: {e}")
                    return gr.update(value=f"注册失败: {str(e)}", visible=True)
            
            def load_user_profile(session_state: Dict):
                """加载用户资料"""
                try:
                    user = session_state.get("user")
                    if not user:
                        return tuple([gr.update() for _ in range(7)])
                    
                    return (
                        gr.update(value=user.get("username", "")),
                        gr.update(value=user.get("email", "")),
                        gr.update(value=user.get("role", "")),
                        gr.update(value=user.get("created_at", "")),
                        gr.update(value=user.get("grade_level", "")),
                        gr.update(value=user.get("parent_contact", "")),
                        gr.update(visible=False)
                    )
                    
                except Exception as e:
                    logger.error(f"Load profile error: {e}")
                    return tuple([gr.update() for _ in range(7)])
            
            def update_user_profile(session_state: Dict, grade: str, parent_contact: str,
                                  learning_style: str, difficulty: int, subjects: List[str]):
                """更新用户资料"""
                try:
                    user = session_state.get("user")
                    if not user:
                        return gr.update(value="请先登录", visible=True)
                    
                    learning_preferences = {
                        "learning_style": learning_style,
                        "difficulty_preference": difficulty,
                        "favorite_subjects": subjects
                    }
                    
                    success = user_service.update_student_profile(
                        user_id=user["id"],
                        grade_level=grade,
                        parent_contact=parent_contact,
                        learning_preferences=learning_preferences
                    )
                    
                    if success:
                        return gr.update(value="资料更新成功！", visible=True)
                    else:
                        return gr.update(value="资料更新失败", visible=True)
                        
                except Exception as e:
                    logger.error(f"Update profile error: {e}")
                    return gr.update(value=f"更新失败: {str(e)}", visible=True)
            
            def load_learning_stats(session_state: Dict):
                """加载学习统计"""
                try:
                    user = session_state.get("user")
                    if not user:
                        return gr.update(value={})
                    
                    stats = user_service.get_user_learning_stats(user["id"])
                    return gr.update(value=stats)
                    
                except Exception as e:
                    logger.error(f"Load stats error: {e}")
                    return gr.update(value={"error": str(e)})
            
            def load_recommendations(session_state: Dict):
                """加载推荐课程"""
                try:
                    user = session_state.get("user")
                    if not user:
                        return gr.update(value=[])
                    
                    recommendations = course_service.get_recommended_courses(user["id"], 5)
                    
                    # 转换为DataFrame格式
                    data = []
                    for course in recommendations:
                        data.append([
                            course.get("name", ""),
                            course.get("subject", ""),
                            course.get("difficulty_level", 1)
                        ])
                    
                    return gr.update(value=data)
                    
                except Exception as e:
                    logger.error(f"Load recommendations error: {e}")
                    return gr.update(value=[])
            
            def load_users_list(grade_filter: str):
                """加载用户列表（管理员功能）"""
                try:
                    grade = None if grade_filter == "全部" else grade_filter
                    users = user_service.get_students_list(limit=100, grade_level=grade)
                    
                    # 转换为DataFrame格式
                    data = []
                    for user in users:
                        data.append([
                            user.get("id", ""),
                            user.get("username", ""),
                            user.get("role", ""),
                            user.get("grade_level", ""),
                            user.get("created_at", "")
                        ])
                    
                    return gr.update(value=data)
                    
                except Exception as e:
                    logger.error(f"Load users error: {e}")
                    return gr.update(value=[])
            
            def create_admin_user(username: str, password: str, email: str):
                """创建管理员用户"""
                try:
                    if not username or not password:
                        return gr.update(value="请输入用户名和密码", visible=True)
                    
                    result = user_service.create_admin(
                        username=username,
                        password=password,
                        email=email or None
                    )
                    
                    if result:
                        return gr.update(value="管理员创建成功！", visible=True)
                    else:
                        return gr.update(value="创建失败，用户名可能已存在", visible=True)
                        
                except Exception as e:
                    logger.error(f"Create admin error: {e}")
                    return gr.update(value=f"创建失败: {str(e)}", visible=True)
            
            # 绑定事件
            login_submit_btn.click(
                handle_login,
                inputs=[login_username, login_password, session_state],
                outputs=[
                    session_state, login_message, login_tab, profile_tab, 
                    stats_tab, admin_tab, user_info_display, login_btn, logout_btn
                ]
            )
            
            logout_btn.click(
                handle_logout,
                inputs=[session_state],
                outputs=[
                    session_state, login_tab, profile_tab, stats_tab, 
                    admin_tab, user_info_display, login_btn, logout_btn
                ]
            )
            
            register_btn.click(
                handle_register,
                inputs=[reg_username, reg_password, reg_email, reg_grade, reg_parent_contact],
                outputs=[register_message]
            )
            
            # 加载用户资料
            profile_tab.select(
                load_user_profile,
                inputs=[session_state],
                outputs=[
                    profile_username, profile_email, profile_role, profile_created,
                    profile_grade, profile_parent_contact, profile_message
                ]
            )
            
            profile_update_btn.click(
                update_user_profile,
                inputs=[
                    session_state, profile_grade, profile_parent_contact,
                    learning_style, difficulty_preference, favorite_subjects
                ],
                outputs=[profile_message]
            )
            
            stats_refresh_btn.click(
                load_learning_stats,
                inputs=[session_state],
                outputs=[stats_display]
            )
            
            refresh_recommendations_btn.click(
                load_recommendations,
                inputs=[session_state],
                outputs=[recommended_courses]
            )
            
            load_users_btn.click(
                load_users_list,
                inputs=[admin_grade_filter],
                outputs=[users_list]
            )
            
            create_admin_btn.click(
                create_admin_user,
                inputs=[admin_new_username, admin_new_password, admin_new_email],
                outputs=[admin_message]
            )
            
            # 清空按钮
            login_clear_btn.click(
                lambda: ("", ""),
                outputs=[login_username, login_password]
            )
            
            reg_clear_btn.click(
                lambda: ("", "", "", None, ""),
                outputs=[reg_username, reg_password, reg_email, reg_grade, reg_parent_contact]
            )
        
        return interface
    
    def launch(self, **kwargs):
        """启动用户管理界面"""
        interface = self.create_user_interface()
        return interface.launch(**kwargs) 