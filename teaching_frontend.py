#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台 - 统一前端界面
负责Gradio界面定义、用户交互和UI展示
整合了用户登录、课程选择、教师对话、实时通信等功能
"""

import gradio as gr
import time
from typing import List, Dict, Tuple, Any


class TeachingFrontend:
    """教学平台前端界面类"""
    
    def __init__(self):
        self.css = self._get_custom_css()
        self.course_choices = [
            "雅思 - 基础语法",
            "雅思 - 词汇记忆", 
            "雅思 - 写作技巧",
            "雅思 - 口语练习"
        ]
        self.difficulty_choices = ["初级", "中级", "高级"]
    
    def _get_custom_css(self) -> str:
        """获取自定义CSS样式"""
        return """
        .app {
            @media screen and (max-width: 768px) {
                padding: 8px !important;
            }
        }
        footer {
            display: none !important;
        }
        .teaching-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .course-card {
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            padding: 15px;
            margin: 10px;
            transition: all 0.3s ease;
        }
        .course-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-ready { background-color: #28a745; }
        .status-connecting { background-color: #ffc107; }
        .status-error { background-color: #dc3545; }
        
        /* AI教师对话界面样式 */
        .teacher-video-container {
            border: 2px solid #667eea;
            border-radius: 15px;
            padding: 15px;
            background: linear-gradient(135deg, #f5f7ff 0%, #e8f0ff 100%);
            min-height: 500px;
            height: 500px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* 确保视频组件适当显示，保留头部 */
        .teacher-video-container > div {
            height: 100% !important;
            width: 100% !important;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .teacher-video-container video,
        .teacher-video-container canvas {
            width: 100% !important;
            height: auto !important;
            max-height: 100% !important;
            object-fit: contain !important;
            border-radius: 10px;
            background: #f0f0f0;
        }
        
        /* 如果视频太高，优先显示上半部分（头部） */
        .teacher-video-container video.portrait,
        .teacher-video-container canvas.portrait {
            height: 100% !important;
            width: auto !important;
            object-fit: cover !important;
            object-position: center top !important;
        }
        
        .chat-container {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 15px;
            background: white;
            min-height: 400px;
            max-height: 500px;
            overflow-y: auto;
        }
        .message-teacher {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 15px;
            border-radius: 15px 15px 5px 15px;
            margin: 10px 0;
            max-width: 80%;
        }
        .message-student {
            background: #f1f3f4;
            color: #333;
            padding: 10px 15px;
            border-radius: 15px 15px 15px 5px;
            margin: 10px 0;
            max-width: 80%;
            margin-left: auto;
        }
        .back-button {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1000;
        }
        
        /* 登录页面样式 */
        .login-container {
            max-width: 400px;
            margin: 50px auto;
            padding: 30px;
            border: 2px solid #e1e5e9;
            border-radius: 15px;
            background: white;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        .login-header {
            text-align: center;
            margin-bottom: 25px;
            color: #333;
        }
        .login-form {
            padding: 20px 0;
        }
        .user-info {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            text-align: center;
        }
        """
    
    def create_login_page(self) -> Tuple[gr.Group, Dict[str, Any]]:
        """创建用户登录页面"""
        components = {}
        
        with gr.Group(visible=True) as login_page:
            # 登录页面标题
            with gr.Row():
                gr.HTML("""
                <div class="teaching-header">
                    <h1>🎓 AI在线教学平台</h1>
                    <p>请登录开始您的个性化学习之旅</p>
                </div>
                """)
            
            # 登录表单区域
            with gr.Row():
                with gr.Column(scale=1):
                    pass  # 左侧空白
                with gr.Column(scale=2):
                    with gr.Group():
                        gr.HTML('<div class="login-header"><h2>登录</h2></div>')
                        
                        # 登录表单
                        with gr.Column():
                            components['username'] = gr.Textbox(
                                label="用户名",
                                placeholder="请输入用户名",
                                elem_classes=["login-form"]
                            )
                            components['password'] = gr.Textbox(
                                label="密码",
                                placeholder="请输入密码",
                                type="password",
                                elem_classes=["login-form"]
                            )
                            
                            # 登录和注册按钮
                            with gr.Row():
                                components['login_btn'] = gr.Button(
                                    "🚀 登录",
                                    variant="primary",
                                    size="lg"
                                )
                                components['show_register_btn'] = gr.Button(
                                    "📝 注册新用户",
                                    variant="secondary",
                                    size="lg"
                                )
                            
                            # 登录状态消息
                            components['login_status'] = gr.Markdown(
                                "",
                                visible=True
                            )
                with gr.Column(scale=1):
                    pass  # 右侧空白
            
            # 注册表单区域（默认隐藏）
            with gr.Row(visible=False) as register_section:
                with gr.Column(scale=1):
                    pass  # 左侧空白
                with gr.Column(scale=2):
                    with gr.Group():
                        gr.HTML('<div class="login-header"><h2>用户注册</h2></div>')
                        
                        with gr.Column():
                            components['reg_username'] = gr.Textbox(
                                label="用户名",
                                placeholder="3-20个字符",
                                elem_classes=["login-form"]
                            )
                            components['reg_email'] = gr.Textbox(
                                label="邮箱 (可选)",
                                placeholder="用于找回密码",
                                elem_classes=["login-form"]
                            )
                            components['reg_password'] = gr.Textbox(
                                label="密码",
                                placeholder="至少6位字符",
                                type="password",
                                elem_classes=["login-form"]
                            )
                            components['reg_confirm_password'] = gr.Textbox(
                                label="确认密码",
                                placeholder="请再次输入密码",
                                type="password",
                                elem_classes=["login-form"]
                            )
                            components['reg_grade'] = gr.Dropdown(
                                label="年级 (可选)",
                                choices=["小学", "初中", "高中", "大学", "成人"],
                                elem_classes=["login-form"]
                            )
                            
                            # 注册和返回按钮
                            with gr.Row():
                                components['register_btn'] = gr.Button(
                                    "✅ 注册",
                                    variant="primary",
                                    size="lg"
                                )
                                components['back_to_login_btn'] = gr.Button(
                                    "← 返回登录",
                                    variant="secondary",
                                    size="lg"
                                )
                            
                            # 注册状态消息
                            components['register_status'] = gr.Markdown(
                                "",
                                visible=False
                            )
                with gr.Column(scale=1):
                    pass  # 右侧空白
            
            components['register_section'] = register_section
            
            # 演示账户提示
            with gr.Row():
                with gr.Column():
                    gr.HTML("""
                    <div style="text-align: center; padding: 20px; color: #666; border-top: 1px solid #eee; margin-top: 30px;">
                        <h4>演示账户</h4>
                        <p>学生账户: <code>student1</code> / <code>123456</code></p>
                        <p>管理员: <code>admin</code> / <code>admin123</code></p>
                    </div>
                    """)
        
        return login_page, components
    
    def create_course_selection_page(self) -> Tuple[gr.Group, Dict[str, Any]]:
        """创建课程选择页面"""
        components = {}
        
        with gr.Group(visible=False) as course_selection_page:
            # 用户信息和登出
            with gr.Row():
                with gr.Column(scale=3):
                    components['user_info'] = gr.HTML("""
                    <div class="user-info">
                        <span>👤 用户: 未登录</span>
                    </div>
                    """)
                with gr.Column(scale=1):
                    components['logout_btn'] = gr.Button(
                        "🚪 登出",
                        variant="secondary",
                        size="sm"
                    )
            
            # 页面标题
            with gr.Row():
                gr.HTML("""
                <div class="teaching-header">
                    <h1>🎓 AI在线教学平台</h1>
                    <p>与专业AI雅思教师进行1v1互动学习</p>
                </div>
                """)
            
            # 课程选择区域
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📚 选择课程")
                    
                    # 课程选择
                    components['course_dropdown'] = gr.Dropdown(
                        choices=self.course_choices,
                        label="课程选择",
                        value=self.course_choices[0],
                        interactive=True
                    )
                    
                    # 难度选择
                    components['difficulty_radio'] = gr.Radio(
                        choices=self.difficulty_choices,
                        label="难度等级",
                        value=self.difficulty_choices[0],
                        interactive=True
                    )
                    
                    # 学习目标
                    components['learning_goal'] = gr.Textbox(
                        label="学习目标 (可选)",
                        placeholder="例如：掌握雅思英语基础语法",
                        lines=2
                    )
                    
                    # 开始学习按钮
                    components['start_button'] = gr.Button(
                        "🚀 开始学习", 
                        variant="primary",
                        size="lg"
                    )
                    
                    # 连接状态
                    components['status_display'] = gr.HTML(
                        '<div><span class="status-indicator status-ready"></span>系统就绪</div>'
                    )
                
                with gr.Column(scale=2):
                    gr.Markdown("### 🤖 AI教师预览")
                    
                    # 功能介绍
                    gr.HTML("""
                    <div style="text-align: center; padding: 40px; background: #f8f9fa; border-radius: 10px;">
                        <h3>🎯 学习特色</h3>
                        <div style="display: flex; justify-content: space-around; margin-top: 20px;">
                            <div>
                                <div style="font-size: 2em;">🤖</div>
                                <p><strong>AI数字教师</strong><br/>专业教学经验</p>
                            </div>
                            <div>
                                <div style="font-size: 2em;">🎥</div>
                                <p><strong>视频互动</strong><br/>面对面教学</p>
                            </div>
                            <div>
                                <div style="font-size: 2em;">🎤</div>
                                <p><strong>语音对话</strong><br/>自然交流</p>
                            </div>
                            <div>
                                <div style="font-size: 2em;">📝</div>
                                <p><strong>个性化</strong><br/>因材施教</p>
                            </div>
                        </div>
                        <div style="margin-top: 30px; padding: 20px; background: #fff3cd; border-radius: 8px;">
                            <h4>🌟 主动教学特色</h4>
                            <p>AI教师会在您开始学习后主动进行教学：</p>
                            <ul style="text-align: left; margin: 10px 0;">
                                <li>✅ 开始学习后立即个性化问候</li>
                                <li>✅ 15秒后开始主动教学内容讲授</li>
                                <li>✅ 每30-45秒自动发送新的教学内容</li>
                                <li>✅ 丰富的雅思教学内容库</li>
                                <li>✅ 支持随时语音和文字互动</li>
                            </ul>
                        </div>
                    </div>
                    """)
        
        return course_selection_page, components
    
    def create_teacher_chat_page(self) -> Tuple[gr.Group, Dict[str, Any], gr.Group]:
        """创建AI教师对话页面"""
        components = {}
        
        with gr.Group(visible=False) as teacher_chat_page:
            # 返回按钮和课程信息
            with gr.Row():
                components['back_button'] = gr.Button("← 返回课程选择", variant="secondary", size="sm")
                with gr.Column():
                    components['course_info'] = gr.HTML("")
            
            # 主要对话界面
            with gr.Row(equal_height=True):
                # 左侧：AI教师视频区域
                with gr.Column(scale=1):
                    gr.Markdown("### 👩‍🏫 AI教师 - 小慧老师")
                    
                    # AI教师视频容器 - ChatEngine会在这里创建WebRTC组件
                    with gr.Group(elem_classes="teacher-video-container") as rtc_container:
                        # 视频显示调整JavaScript
                        gr.HTML(self._get_video_adjustment_script())
                    
                    # 教师状态和使用说明
                    components['teacher_status'] = gr.HTML(self._get_teacher_status_html())
                
                # 右侧：对话和教学内容区域
                with gr.Column(scale=1):
                    gr.Markdown("### 💬 教学对话")
                    
                    # 实时对话显示区域
                    with gr.Group(elem_classes="chat-container"):
                        components['real_chat_display'] = gr.HTML(self._get_initial_chat_html())
                        
                        # 测试和控制按钮
                        with gr.Row():
                            components['refresh_chat_btn'] = gr.Button("🔄 刷新对话", size="sm", variant="secondary")
                            components['clear_chat_btn'] = gr.Button("🗑️清空对话", size="sm", variant="secondary")
                            components['auto_toggle_btn'] = gr.Button("🔄 自动刷新: 启用", size="sm", variant="primary")
                        
                        # 调试信息显示区域
                        components['debug_info_display'] = gr.HTML("")
                        
                        # 隐藏的状态组件用于自动刷新
                        components['auto_refresh_state'] = gr.State(True)
                        
                        # Timer定时器
                        components['refresh_timer'] = gr.Timer(value=2, active=True)  # 每2秒检查一次
                  
        
        return teacher_chat_page, components, rtc_container
    
    def _get_video_adjustment_script(self) -> str:
        """获取视频显示调整JavaScript"""
        return """
        <script>
        // 监听视频加载，调整显示方式
        function adjustVideoDisplay() {
            const container = document.querySelector('.teacher-video-container');
            if (!container) return;
            
            const videos = container.querySelectorAll('video, canvas');
            videos.forEach(video => {
                video.addEventListener('loadedmetadata', function() {
                    const aspectRatio = this.videoWidth / this.videoHeight || this.width / this.height;
                    
                    // 如果是竖屏或接近正方形（头像类视频）
                    if (aspectRatio < 1.2) {
                        this.classList.add('portrait');
                        // 使用cover模式，但定位到顶部（显示头部）
                        this.style.objectFit = 'cover';
                        this.style.objectPosition = 'center top';
                        this.style.height = '100%';
                        this.style.width = 'auto';
                    } else {
                        // 横屏视频使用contain模式，完整显示
                        this.classList.remove('portrait');
                        this.style.objectFit = 'contain';
                        this.style.objectPosition = 'center';
                        this.style.width = '100%';
                        this.style.height = 'auto';
                    }
                });
                
                // 如果是canvas，也进行类似处理
                if (video.tagName === 'CANVAS') {
                    const observer = new MutationObserver(() => {
                        const aspectRatio = video.width / video.height;
                        if (aspectRatio < 1.2) {
                            video.classList.add('portrait');
                            video.style.objectFit = 'cover';
                            video.style.objectPosition = 'center top';
                            video.style.height = '100%';
                            video.style.width = 'auto';
                        } else {
                            video.classList.remove('portrait');
                            video.style.objectFit = 'contain';
                            video.style.objectPosition = 'center';
                            video.style.width = '100%';
                            video.style.height = 'auto';
                        }
                    });
                    observer.observe(video, { attributes: true, attributeFilter: ['width', 'height'] });
                }
            });
        }
        
        // 定期检查新添加的视频元素
        setInterval(adjustVideoDisplay, 1000);
        
        // 页面加载完成后立即执行
        document.addEventListener('DOMContentLoaded', adjustVideoDisplay);
        </script>
        """
    
    def _get_teacher_status_html(self) -> str:
        """获取教师状态HTML"""
        return '''<div><span class="status-indicator status-ready"></span>小慧老师已就绪</div>
        <div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 8px; font-size: 12px;">
        💡 <strong>使用说明：</strong><br/>
        1. 点击摄像头图标开始视频对话<br/>
        2. 允许摄像头和麦克风权限<br/>
        3. 可以语音提问或使用右侧文字对话<br/>
        4. <strong>语音对话会自动显示在右侧对话区域</strong><br/>
        5. <strong>AI教师会主动进行教学讲解</strong>
        </div>'''
    
    def _get_initial_chat_html(self) -> str:
        """获取初始对话HTML"""
        return """
        <div id="real-chat-container" style="height: 400px; overflow-y: auto; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <div style="text-align: center; padding: 20px; color: #666;">
                <p>🎯 开始您的学习之旅</p>
                <p>AI教师将根据您选择的课程进行个性化教学</p>
                <p style="margin-top: 15px; font-size: 12px; color: #999;">
                提示：通过左侧视频进行语音对话，对话内容会实时显示在这里<br/>
                AI教师会在开始学习后主动进行教学讲解
                </p>
            </div>
        </div>
        """
    
    def create_state_components(self) -> Dict[str, gr.State]:
        """创建状态管理组件"""
        return {
            'current_page': gr.State("course_selection"),
            'current_course': gr.State(""),
            'current_difficulty': gr.State(""),
            'current_goal': gr.State(""),
            'chat_history': gr.State([])
        }
    
    def build_chat_html(self, messages: List[Dict]) -> str:
        """构建对话HTML"""
        if not messages:
            return self._get_initial_chat_html()
        
        chat_html = ""
        for msg in messages:
            if msg['role'] == 'human':
                chat_html += f'''
                <div style="margin-bottom: 15px;">
                    <div style="background: #e3f2fd; padding: 12px; border-radius: 12px; margin-left: 20px;">
                        <strong>🧑‍🎓 您:</strong><br/>
                        {msg['content']}
                    </div>
                </div>
                '''
            elif msg['role'] == 'avatar':
                chat_html += f'''
                <div style="margin-bottom: 15px;">
                    <div style="background: #f3e5f5; padding: 12px; border-radius: 12px; margin-right: 20px;">
                        <strong>👩‍🏫 小慧老师:</strong><br/>
                        {msg['content']}
                    </div>
                </div>
                '''
            elif msg['role'] == 'system':
                chat_html += f'''
                <div style="margin-bottom: 15px;">
                    <div style="background: #fff3e0; padding: 12px; border-radius: 12px; border-left: 4px solid #ff9800;">
                        <strong>💡 系统提示:</strong><br/>
                        {msg['content']}
                    </div>
                </div>
                '''
        
        return f'''
        <div id="real-chat-container" style="height: 400px; overflow-y: auto; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            {chat_html}
        </div>
        <script>
        // 自动滚动到底部
        setTimeout(function() {{
            const container = document.getElementById('real-chat-container');
            if (container) {{
                container.scrollTop = container.scrollHeight;
            }}
        }}, 100);
        </script>
        '''
    
    def build_backup_chat_html(self, chat_history: List[Dict]) -> str:
        """构建备用对话HTML"""
        chat_html = ""
        for msg in chat_history:
            if msg["role"] == "teacher":
                chat_html += f'<div class="message-teacher"><strong>👩‍🏫 小慧老师:</strong><br/>{msg["content"]}</div>'
            elif msg["role"] == "student":
                chat_html += f'<div class="message-student"><strong>🧑‍🎓 您:</strong><br/>{msg["content"]}</div>'
        return chat_html
    
    def create_course_info_html(self, course: str, difficulty: str, goal: str) -> str:
        """创建课程信息HTML"""
        return f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h3>📚 {course}</h3>
            <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                <span>📊 难度: {difficulty}</span>
                <span>🎯 目标: {goal or '系统推荐'}</span>
            </div>
            <div style="margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; font-size: 12px;">
                💡 <strong>主动教学提示：</strong>AI教师会在您开始学习后主动进行个性化教学，包括问候、知识讲解和练习指导
            </div>
        </div>
        """
    
    def create_debug_info_html(self, debug_info: Dict) -> str:
        """创建调试信息HTML"""
        return f"""
        <div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 12px;">
            <strong>🔍 调试信息：</strong><br/>
            📊 消息队列大小: {debug_info.get('queue_size', 0)}<br/>
            🔄 日志监听状态: {debug_info.get('monitor_status', '未知')}<br/>
            📝 日志文件: {debug_info.get('log_file', 'N/A')}<br/>
            🔗 ChatEngine状态: {debug_info.get('chat_engine_status', '未知')}<br/>
            ⏰ 更新时间: {debug_info.get('timestamp', 'N/A')}
        </div>
        """
    
    def create_gradio_interface(self) -> Tuple[gr.Blocks, Dict[str, Any], gr.Group]:
        """创建完整的Gradio界面"""
        with gr.Blocks(css=self.css, title="AI在线教学平台") as gradio_block:
            # 创建状态组件
            states = self.create_state_components()
            
            # 创建登录页面
            login_page, login_components = self.create_login_page()
            
            # 创建课程选择页面
            course_selection_page, course_components = self.create_course_selection_page()
            
            # 创建AI教师对话页面
            teacher_chat_page, chat_components, rtc_container = self.create_teacher_chat_page()
            
            # 合并所有组件
            all_components = {
                **login_components,
                **course_components,
                **chat_components,
                **states,
                'login_page': login_page,
                'course_selection_page': course_selection_page,
                'teacher_chat_page': teacher_chat_page,
                'gradio_block': gradio_block
            }
            
            # 在Gradio上下文内绑定事件
            self._bind_events_in_context(all_components)
        
        return gradio_block, all_components, rtc_container
    
    def _bind_events_in_context(self, components: Dict[str, Any]):
        """在Gradio上下文内绑定事件"""
        # 延迟导入避免循环依赖
        from teaching_api import teaching_api
        teaching_api.bind_events(components)


# 全局前端实例
teaching_frontend = TeachingFrontend()