#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台 MVP版本
快速可用的1v1数字人教学系统原型
"""

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import datetime
import json
import os

class TeachingMVP:
    """教学平台MVP核心类"""
    
    def __init__(self):
        self.session_data = {}
        self.learning_log = []
        
    def start_learning_session(self, course, difficulty, goal):
        """开始学习会话"""
        session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 存储会话信息
        self.session_data = {
            "session_id": session_id,
            "course": course,
            "difficulty": difficulty,
            "goal": goal or "无特定目标",
            "start_time": datetime.datetime.now(),
            "messages": []
        }
        
        # 模拟AI教师欢迎语
        welcome_msg = self.generate_welcome_message(course, difficulty)
        self.session_data["messages"].append({
            "role": "teacher",
            "content": welcome_msg,
            "timestamp": datetime.datetime.now()
        })
        
        # 更新显示
        session_info = f"课程: {course}\n难度: {difficulty}\n目标: {goal or '无特定目标'}\n会话ID: {session_id}"
        status_html = '<div><span class="status-indicator status-connecting"></span>✅ AI教师已连接</div>'
        log_content = f"[{session_id}] 学习会话开始\n{welcome_msg}\n"
        
        return session_info, status_html, log_content, gr.update(visible=True)
    
    def generate_welcome_message(self, course, difficulty):
        """生成AI教师欢迎消息"""
        course_messages = {
            "小学数学 - 基础运算": f"你好！我是你的数学老师。今天我们来学习基础运算，{difficulty}难度。让我们从简单的加减法开始吧！",
            "小学数学 - 几何图形": f"欢迎来到几何图形的世界！我会帮你认识各种形状，{difficulty}难度。你想先学习哪种图形呢？",
            "初中数学 - 代数基础": f"代数是数学的重要分支，{difficulty}难度。我们会从变量和方程式开始学习。",
            "初中数学 - 函数概念": f"函数是数学中的核心概念！{difficulty}难度。让我们一起探索函数的奥秘吧！",
            "高中数学 - 三角函数": f"三角函数在数学和物理中都很重要，{difficulty}难度。我们从基本的正弦、余弦开始。"
        }
        
        return course_messages.get(course, f"欢迎学习{course}！我是你的AI数学教师，{difficulty}难度。让我们开始吧！")
    
    def handle_student_input(self, user_input):
        """处理学生输入"""
        if not user_input.strip():
            return "", self.get_current_log()
        
        # 记录学生消息
        student_msg = {
            "role": "student", 
            "content": user_input,
            "timestamp": datetime.datetime.now()
        }
        self.session_data["messages"].append(student_msg)
        
        # 生成AI教师回复（MVP版本使用模拟回复）
        teacher_reply = self.generate_teacher_reply(user_input)
        teacher_msg = {
            "role": "teacher",
            "content": teacher_reply,
            "timestamp": datetime.datetime.now()
        }
        self.session_data["messages"].append(teacher_msg)
        
        # 更新日志
        updated_log = self.get_current_log()
        
        return "", updated_log  # 清空输入框，更新日志

    def generate_teacher_reply(self, student_input):
        """生成AI教师回复（MVP版本的模拟回复）"""
        input_lower = student_input.lower()
        
        # 简单的关键词匹配回复系统
        if any(word in input_lower for word in ["你好", "hello", "hi"]):
            return "你好！很高兴和你一起学习数学。有什么问题可以随时问我！"
        
        elif any(word in input_lower for word in ["加法", "加", "+"]):
            return "加法很简单！比如 2 + 3 = 5。你想试试其他的加法题目吗？我可以出题给你练习。"
        
        elif any(word in input_lower for word in ["减法", "减", "-"]):
            return "减法就是从一个数中取走一部分。比如 5 - 2 = 3。让我们多练习几题吧！"
        
        elif any(word in input_lower for word in ["乘法", "乘", "×", "*"]):
            return "乘法可以理解为重复的加法。比如 3 × 4 = 3 + 3 + 3 + 3 = 12。这样理解容易吗？"
        
        elif any(word in input_lower for word in ["除法", "除", "÷", "/"]):
            return "除法是把一个数平均分成几份。比如 12 ÷ 3 = 4，意思是12分成3份，每份是4。"
        
        elif any(word in input_lower for word in ["圆", "圆形"]):
            return "圆形是没有角的图形！圆的周长 = 2πr，面积 = πr²。你知道π大约等于多少吗？"
        
        elif any(word in input_lower for word in ["三角形"]):
            return "三角形有三条边和三个角。三角形内角和等于180度！你想学习哪种三角形呢？"
        
        elif any(word in input_lower for word in ["函数"]):
            return "函数就像一台机器，输入x，输出f(x)。比如f(x) = x + 1，输入2就输出3。理解了吗？"
        
        elif "?" in student_input or "？" in student_input:
            return "这是个很好的问题！让我来帮你分析一下。数学就是要多问为什么，这样才能真正理解。"
        
        elif any(word in input_lower for word in ["不懂", "不会", "难"]):
            return "没关系，学习需要过程！我们可以从更简单的开始，一步一步来。你觉得哪个部分最困难？"
        
        elif any(word in input_lower for word in ["谢谢", "thank"]):
            return "不用谢！帮助你学习数学是我的荣幸。还有其他问题吗？"
        
        else:
            return f"你提到了'{student_input}'，这让我想到可以从基础概念开始讲解。数学需要循序渐进，我们一起努力！有什么具体问题吗？"

    def get_current_log(self):
        """获取当前学习日志"""
        if not self.session_data.get("messages"):
            return "等待开始学习..."
        
        log_lines = []
        for msg in self.session_data["messages"]:
            time_str = msg["timestamp"].strftime("%H:%M:%S")
            role = "🤖 AI教师" if msg["role"] == "teacher" else "👨‍🎓 学生"
            log_lines.append(f"[{time_str}] {role}: {msg['content']}")
        
        return "\n\n".join(log_lines)

def create_teaching_app():
    """创建教学应用"""
    app = FastAPI(title="AI在线教学平台 MVP", description="快速可用的1v1数字人教学系统")
    teaching_mvp = TeachingMVP()

    @app.get("/")
    def get_root():
        return RedirectResponse(url="/ui")

    # 教学平台CSS样式
    css = """
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
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-ready { background-color: #28a745; }
    .status-connecting { background-color: #ffc107; }
    .chat-container {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        background-color: #f9f9f9;
    }
    """

    with gr.Blocks(css=css, title="AI在线教学平台 MVP") as gradio_interface:
        # 页面标题
        gr.HTML("""
        <div class="teaching-header">
            <h1>🎓 AI在线教学平台 MVP</h1>
            <p>与专业AI数学教师进行1v1互动学习（演示版本）</p>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📚 课程设置")
                
                course_dropdown = gr.Dropdown(
                    choices=[
                        "小学数学 - 基础运算",
                        "小学数学 - 几何图形", 
                        "初中数学 - 代数基础",
                        "初中数学 - 函数概念",
                        "高中数学 - 三角函数"
                    ],
                    label="选择课程",
                    value="小学数学 - 基础运算"
                )
                
                difficulty_radio = gr.Radio(
                    choices=["初级", "中级", "高级"],
                    label="难度等级",
                    value="初级"
                )
                
                learning_goal = gr.Textbox(
                    label="学习目标 (可选)",
                    placeholder="例如：掌握两位数加法运算",
                    lines=2
                )
                
                start_button = gr.Button("🚀 开始学习", variant="primary", size="lg")
                
                status_display = gr.HTML(
                    '<div><span class="status-indicator status-ready"></span>系统就绪</div>'
                )
                
                session_info = gr.Textbox(
                    label="本次学习信息", 
                    value="等待开始...",
                    interactive=False,
                    lines=3
                )
            
            with gr.Column(scale=2):
                gr.Markdown("### 🤖 AI教师互动区")
                
                # 学习记录显示区
                learning_log = gr.Textbox(
                    label="师生对话记录",
                    lines=12,
                    interactive=False,
                    placeholder="点击'开始学习'后，与AI教师的对话将显示在这里..."
                )
                
                # 学生输入区（初始隐藏）
                with gr.Group(visible=False) as chat_interface:
                    gr.Markdown("#### 💬 与AI教师对话")
                    with gr.Row():
                        student_input = gr.Textbox(
                            label="你的消息",
                            placeholder="输入你的问题或回答...",
                            lines=2,
                            scale=4
                        )
                        send_button = gr.Button("📤 发送", variant="secondary", scale=1)
        
        # 底部提示
        gr.Markdown("""
        ---
        ### 💡 使用提示
        - **MVP版本**：当前为演示版本，AI回复基于关键词匹配
        - **支持话题**：加减乘除、几何图形、函数等基础数学概念
        - **互动方式**：可以提问、回答、讨论数学问题
        - **未来功能**：语音对话、数字人动画、个性化学习路径
        """)
        
        # 事件绑定
        start_button.click(
            fn=teaching_mvp.start_learning_session,
            inputs=[course_dropdown, difficulty_radio, learning_goal],
            outputs=[session_info, status_display, learning_log, chat_interface]
        )
        
        # 发送消息事件
        def send_message_wrapper(user_input):
            return teaching_mvp.handle_student_input(user_input)
        
        send_button.click(
            fn=send_message_wrapper,
            inputs=[student_input],
            outputs=[student_input, learning_log]
        )
        
        # 回车发送
        student_input.submit(
            fn=send_message_wrapper,
            inputs=[student_input],
            outputs=[student_input, learning_log]
        )

    gr.mount_gradio_app(app, gradio_interface, path="/ui")
    return app

def main():
    """主函数"""
    print("🎓 AI在线教学平台 MVP 启动中...")
    print("📍 访问地址: http://localhost:8285/ui")
    print("⚡ 这是可立即使用的MVP版本！")
    print("🔧 当前为演示模式，AI回复基于关键词匹配")
    print("⏹️  按Ctrl+C停止服务")
    print()
    
    app = create_teaching_app()
    uvicorn.run(app, host="0.0.0.0", port=8285)

if __name__ == "__main__":
    main() 