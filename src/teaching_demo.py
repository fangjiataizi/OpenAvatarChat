#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台演示程序
基于OpenAvatarChat项目开发的1v1数字人教学系统
"""

import sys
import gradio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from engine_utils.directory_info import DirectoryInfo
from service.service_utils.logger_utils import config_loggers
from service.service_utils.service_config_loader import load_configs
from service.service_utils.ssl_helpers import create_ssl_context

project_dir = DirectoryInfo.get_project_dir()
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

import argparse
import os

import gradio as gr
from loguru import logger
import threading
import time
import re
import queue
from typing import List, Dict
import json

from src.chat_engine.chat_engine import ChatEngine
from src.chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel
from src.service.service_utils.service_config_loader import load_configs

# 全局变量
global_chat_engine = None
real_chat_queue = queue.Queue()  # 用于存储真实对话内容
log_monitor_thread = None
log_monitor_running = False

def start_log_monitor():
    """启动日志监听线程，从日志中提取真实对话内容"""
    global log_monitor_thread, log_monitor_running
    
    if log_monitor_thread and log_monitor_thread.is_alive():
        return
    
    log_monitor_running = True
    log_monitor_thread = threading.Thread(target=monitor_chat_logs, daemon=True)
    log_monitor_thread.start()
    logger.info("Log monitor thread started")

def monitor_chat_logs():
    """监听聊天日志文件，提取实时对话"""
    global real_chat_queue
    
    log_file_path = "logs/log.log"
    
    try:
        # 如果日志文件不存在，创建它
        if not os.path.exists(log_file_path):
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            with open(log_file_path, 'w') as f:
                pass
        
        # 获取文件当前位置，避免读取旧日志
        with open(log_file_path, 'r', encoding='utf-8') as file:
            file.seek(0, 2)  # 移到文件末尾
            current_position = file.tell()
        
        while True:
            try:
                with open(log_file_path, 'r', encoding='utf-8') as file:
                    file.seek(current_position)
                    
                    for line in file:
                        line = line.strip()
                        
                        # 跳过空行和监听函数自己产生的日志
                        if not line or 'monitor_chat_logs' in line or 'Processing log line' in line:
                            continue
                        
                        # 检查LLM输入 (用户说话)
                        if 'llm input' in line:
                            # 提取用户输入文本
                            # 格式: 2025-06-19 15:43:47.384 | INFO | xxx - llm input qwen-vl-plus yeaht
                            try:
                                # 找到 "llm input" 后面的内容
                                llm_input_index = line.find('llm input')
                                if llm_input_index != -1:
                                    text_part = line[llm_input_index + len('llm input'):].strip()
                                    # 去掉模型名称，提取实际文本
                                    words = text_part.split()
                                    if len(words) > 1:
                                        user_text = ' '.join(words[1:])  # 跳过模型名称 qwen-vl-plus
                                        if user_text and len(user_text.strip()) > 0:
                                            # 只在确实提取到内容时才输出一次日志
                                            print(f"[Chat] User: {user_text}")  # 使用print避免循环
                                            add_real_chat_message('human', user_text.strip())
                            except Exception as e:
                                pass  # 静默处理错误
                        
                        # 检查AI回复 (current sentence)
                        elif 'current sentence' in line:
                            # 提取AI回复文本
                            # 格式: 2025-06-19 15:43:49.317 | INFO | xxx - current sentence你提到的yeaht似乎是在确认某个问题或表达肯定。
                            try:
                                # 找到 "current sentence" 后面的内容
                                sentence_index = line.find('current sentence')
                                if sentence_index != -1:
                                    ai_text = line[sentence_index + len('current sentence'):].strip()
                                    if ai_text and len(ai_text.strip()) > 0:
                                        # 只在确实提取到内容时才输出一次日志
                                        print(f"[Chat] AI: {ai_text}")  # 使用print避免循环
                                        add_real_chat_message('avatar', ai_text.strip())
                            except Exception as e:
                                pass  # 静默处理错误
                    
                    # 更新位置
                    current_position = file.tell()
                
                # 短暂休眠避免CPU占用过高
                time.sleep(0.5)
                
            except (FileNotFoundError, PermissionError):
                # 文件可能正在被重新创建，等待一下
                time.sleep(1)
                continue
            except Exception as e:
                # 其他错误，静默处理
                time.sleep(1)
                continue
                
    except Exception as e:
        print(f"Monitor thread error: {e}")  # 使用print避免循环

def get_real_chat_messages():
    """获取真实对话消息"""
    messages = []
    while not real_chat_queue.empty():
        try:
            message = real_chat_queue.get_nowait()
            messages.append(message)
        except queue.Empty:
            break
    return messages

def add_real_chat_message(role: str, content: str):
    """添加真实对话消息到队列，带去重功能和严格的格式清理"""
    global real_chat_queue
    
    # 严格清理内容格式，确保只保留纯文本
    cleaned_content = clean_message_content(content)
    
    # 如果清理后内容为空或无效，直接返回
    if not cleaned_content or len(cleaned_content.strip()) < 2:
        print(f"[Chat] Skipped invalid content: {content[:50]}...")
        return False
    
    # 检查是否已存在相同内容的消息（防止重复）
    temp_messages = []
    duplicate_found = False
    
    # 检查队列中是否有重复消息
    while not real_chat_queue.empty():
        try:
            existing_msg = real_chat_queue.get_nowait()
            temp_messages.append(existing_msg)
            
            # 检查是否重复（相同角色和内容）
            if (existing_msg['role'] == role and 
                existing_msg['content'].strip() == cleaned_content.strip()):
                duplicate_found = True
                print(f"[Chat] Duplicate message detected, skipping: {role} - {cleaned_content[:30]}...")
        except queue.Empty:
            break
    
    # 将消息放回队列
    for msg in temp_messages:
        real_chat_queue.put(msg)
    
    # 如果没有重复，才添加新消息
    if not duplicate_found:
        message = {
            'role': role,  # 'human' or 'avatar'
            'content': cleaned_content.strip(),
            'timestamp': time.time()
        }
        real_chat_queue.put(message)
        print(f"[Chat] Added: {role} - {cleaned_content[:50]}...")
    
    return not duplicate_found  # 返回是否成功添加

def clean_message_content(content: str) -> str:
    """清理消息内容，确保只返回纯文本"""
    import re
    
    # 如果内容包含数据结构标识符，尝试提取纯文本
    if any(marker in content for marker in ["'role':", "'content':", "'type':", "'text':"]):
        # 尝试提取 'text': '内容' 中的内容
        text_match = re.search(r"'text':\s*'([^']*)'", content)
        if text_match:
            return text_match.group(1).strip()
        
        # 尝试提取 "text": "内容" 中的内容
        text_match = re.search(r'"text":\s*"([^"]*)"', content)
        if text_match:
            return text_match.group(1).strip()
        
        # 如果包含数据结构但无法提取，返回空
        print(f"[Chat] Failed to extract text from data structure: {content[:100]}...")
        return ""
    
    # 移除多余的空白字符
    cleaned = re.sub(r'\s+', ' ', content).strip()
    
    # 确保是有效的中文或英文文本
    if len(cleaned) < 1:
        return ""
    
    return cleaned

def update_real_chat_display():
    """更新真实对话显示 - 显示完整的对话历史"""
    global real_chat_queue
    
    # 收集所有消息，包括队列中的和历史的
    all_messages = []
    
    # 从队列中获取所有消息（保持队列完整）
    temp_messages = []
    queue_copy = queue.Queue()
    
    while not real_chat_queue.empty():
        try:
            msg = real_chat_queue.get_nowait()
            temp_messages.append(msg)
            queue_copy.put(msg)  # 复制到新队列
        except queue.Empty:
            break
    
    # 将消息重新放回原队列
    real_chat_queue = queue_copy
    
    # 添加到总消息列表
    all_messages.extend(temp_messages)
    
    # 如果没有任何真实对话，显示空状态
    if not all_messages:
        return gr.update(value='''
        <div id="real-chat-container" style="height: 400px; overflow-y: auto; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <div style="text-align: center; padding: 20px; color: #666;">
                <p>🎯 开始您的学习之旅</p>
                <p>AI教师将根据您选择的课程进行个性化教学</p>
                <p style="margin-top: 15px; font-size: 12px; color: #999;">
                提示：通过左侧视频进行语音对话，对话内容会实时显示在这里
                </p>
            </div>
        </div>
        ''')
    
    # 构建完整的HTML - 只显示真实的对话历史
    chat_html = ""
    
    # 按时间顺序显示所有消息
    for msg in all_messages:
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
    
    return gr.update(value=f'''
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
    ''')

def test_chat_display():
    """测试对话显示功能"""
    import random
    test_messages = [
        ("human", "你好，小慧老师"),
        ("avatar", "你好！我是小慧老师，很高兴为您服务！有什么数学问题需要帮助吗？"),
        ("human", "我想学习数学"),
        ("avatar", "很好！我们今天学习什么数学内容呢？"),
        ("human", "我想学习加法运算"),
        ("avatar", "加法是数学的基础。让我们从简单的例子开始：2+3等于多少呢？"),
        ("human", "等于5"),
        ("avatar", "非常棒！您答对了。2+3确实等于5。让我们尝试一个稍微难一点的：15+7等于多少？"),
    ]
    
    # 随机选择一对对话
    role, content = random.choice(test_messages)
    add_real_chat_message(role, content)
    logger.info(f"Added test message: {role} - {content}")
    return update_real_chat_display()

def get_debug_info():
    """获取调试信息"""
    global real_chat_queue, log_monitor_running
    
    queue_size = real_chat_queue.qsize()
    monitor_status = "运行中" if log_monitor_running else "已停止"
    
    debug_html = f"""
    <div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 12px;">
        <strong>🔍 调试信息：</strong><br/>
        📊 消息队列大小: {queue_size}<br/>
        🔄 日志监听状态: {monitor_status}<br/>
        📝 日志文件: logs/log.log<br/>
        ⏰ 更新时间: {time.strftime('%H:%M:%S')}
    </div>
    """
    
    return gr.update(value=debug_html)

def refresh_chat_display():
    """刷新对话显示"""
    return update_real_chat_display()

def clear_chat_display():
    """清空对话显示"""
    global real_chat_queue
    # 清空队列
    while not real_chat_queue.empty():
        try:
            real_chat_queue.get_nowait()
        except queue.Empty:
            break
    
    # 返回初始状态
    return gr.update(value='''
    <div id="real-chat-container" style="height: 400px; overflow-y: auto; padding: 15px; background: #f8f9fa; border-radius: 8px;">
        <div style="text-align: center; padding: 20px; color: #666;">
            <p>🎯 开始您的学习之旅</p>
            <p>AI教师将根据您选择的课程进行个性化教学</p>
            <p style="margin-top: 15px; font-size: 12px; color: #999;">
            提示：通过左侧视频进行语音对话，对话内容会实时显示在这里
            </p>
        </div>
    </div>
    ''')

def get_current_chat_display():
    """获取当前对话显示内容（用于定时更新）"""
    messages = get_real_chat_messages()
    if not messages:
        return gr.update()
    
    # 构建完整的HTML，包含所有历史消息
    all_messages = []
    
    # 从队列中获取所有消息（不清空队列）
    temp_messages = []
    while not real_chat_queue.empty():
        try:
            msg = real_chat_queue.get_nowait()
            temp_messages.append(msg)
        except queue.Empty:
            break
    
    # 将消息放回队列
    for msg in temp_messages:
        real_chat_queue.put(msg)
    
    # 如果有新消息，更新显示
    if temp_messages:
        chat_html = ""
        for msg in temp_messages:
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
        
        return gr.update(value=f'''
        <div id="real-chat-container" style="height: 400px; overflow-y: auto; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            {chat_html}
        </div>
        <script>
        const container = document.getElementById('real-chat-container');
        if (container) {{
            container.scrollTop = container.scrollHeight;
        }}
        </script>
        ''')
    
    return gr.update()

def parse_args():
    parser = argparse.ArgumentParser(description="AI在线教学平台")
    parser.add_argument("--host", type=str, help="服务主机地址")
    parser.add_argument("--port", type=int, help="服务端口")
    parser.add_argument("--config", type=str, default="config/teaching_basic.yaml", help="配置文件路径")
    parser.add_argument("--env", type=str, default="default", help="配置环境")
    return parser.parse_args()


def setup_teaching_demo():
    """设置教学演示界面"""
    app = FastAPI(title="AI在线教学平台", description="基于数字人的1v1在线教学系统")
    
    # 全局ChatEngine实例
    global_chat_engine = None

    @app.get("/")
    def get_root():
        return RedirectResponse(url="/ui")

    @app.get("/ui/static/fonts/system-ui/system-ui-Regular.woff2")
    @app.get("/ui/static/fonts/ui-sans-serif/ui-sans-serif-Regular.woff2")
    @app.get("/favicon.ico")
    def get_font():
        # 移除混淆错误
        return {}

    # 教学平台专用CSS样式
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
    """

    with gr.Blocks(css=css, title="AI在线教学平台") as gradio_block:
        # 全局状态管理
        current_page = gr.State("course_selection")
        current_course = gr.State("")
        current_difficulty = gr.State("")
        current_goal = gr.State("")
        chat_history = gr.State([])
        
        # 课程选择页面
        with gr.Group(visible=True) as course_selection_page:
            # 页面标题
            with gr.Row():
                gr.HTML("""
                <div class="teaching-header">
                    <h1>🎓 AI在线教学平台</h1>
                    <p>与专业AI数学教师进行1v1互动学习</p>
                </div>
                """)
            
            # 课程选择区域
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📚 选择课程")
                    
                    # 课程选择
                    course_dropdown = gr.Dropdown(
                        choices=[
                            "小学数学 - 基础运算",
                            "小学数学 - 几何图形", 
                            "初中数学 - 代数基础",
                            "初中数学 - 函数概念",
                            "高中数学 - 三角函数"
                        ],
                        label="课程选择",
                        value="小学数学 - 基础运算",
                        interactive=True
                    )
                    
                    # 难度选择
                    difficulty_radio = gr.Radio(
                        choices=["初级", "中级", "高级"],
                        label="难度等级",
                        value="初级",
                        interactive=True
                    )
                    
                    # 学习目标
                    learning_goal = gr.Textbox(
                        label="学习目标 (可选)",
                        placeholder="例如：掌握两位数加法运算",
                        lines=2
                    )
                    
                    # 开始学习按钮
                    start_button = gr.Button(
                        "🚀 开始学习", 
                        variant="primary",
                        size="lg"
                    )
                    
                    # 连接状态
                    status_display = gr.HTML(
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
                    </div>
                    """)
        
        # AI教师对话页面
        with gr.Group(visible=False) as teacher_chat_page:
            # 返回按钮和课程信息
            with gr.Row():
                back_button = gr.Button("← 返回课程选择", variant="secondary", size="sm")
                with gr.Column():
                    course_info = gr.HTML("")
            
            # 主要对话界面
            with gr.Row(equal_height=True):
                # 左侧：AI教师视频区域
                with gr.Column(scale=1):
                    gr.Markdown("### 👩‍🏫 AI教师 - 小慧老师")
                    
                    # AI教师视频容器 - ChatEngine会在这里创建WebRTC组件
                    with gr.Group(elem_classes="teacher-video-container") as rtc_container:
                        # 添加JavaScript来动态调整视频显示
                        gr.HTML("""
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
                        """)
                    
                    # 教师状态和使用说明
                    teacher_status = gr.HTML(
                        '''<div><span class="status-indicator status-ready"></span>小慧老师已就绪</div>
                        <div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 8px; font-size: 12px;">
                        💡 <strong>使用说明：</strong><br/>
                        1. 点击摄像头图标开始视频对话<br/>
                        2. 允许摄像头和麦克风权限<br/>
                        3. 可以语音提问或使用右侧文字对话<br/>
                        4. <strong>语音对话会自动显示在右侧对话区域</strong>
                        </div>'''
                    )
                
                # 右侧：对话和教学内容区域
                with gr.Column(scale=1):
                    gr.Markdown("### 💬 教学对话")
                    
                    # 实时对话显示区域（用于显示WebRTC真实对话）
                    with gr.Group(elem_classes="chat-container"):
                        real_chat_display = gr.HTML("""
                        <div id="real-chat-container" style="height: 400px; overflow-y: auto; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                            <div style="text-align: center; padding: 20px; color: #666;">
                                <p>🎯 开始您的学习之旅</p>
                                <p>AI教师将根据您选择的课程进行个性化教学</p>
                                <p style="margin-top: 15px; font-size: 12px; color: #999;">
                                提示：通过左侧视频进行语音对话，对话内容会实时显示在这里
                                </p>
                            </div>
                        </div>
                        """)
                        
                        # 测试和控制按钮
                        with gr.Row():
                            test_chat_btn = gr.Button("🧪 测试对话显示", size="sm", variant="secondary")
                            refresh_chat_btn = gr.Button("🔄 刷新对话", size="sm", variant="secondary")
                            clear_chat_btn = gr.Button("🗑️清空对话", size="sm", variant="secondary")
                            debug_btn = gr.Button("🔍 显示调试信息", size="sm", variant="secondary")
                        
                        # 调试信息显示区域
                        debug_info_display = gr.HTML("")
                    
                    # 备用文本输入（当WebRTC不可用时）
                    with gr.Group():
                        gr.Markdown("#### 📝 备用文本输入")
                        with gr.Row():
                            backup_input = gr.Textbox(
                                label="",
                                placeholder="如果语音对话不可用，可以在这里输入文字...",
                                lines=2,
                                scale=4
                            )
                            backup_send = gr.Button("发送", variant="secondary", scale=1)
            
                        # 备用对话显示（用于文本输入的回复）
                        backup_chat_display = gr.HTML("")
                        
                        # 快捷回复按钮
                        with gr.Row():
                            quick_reply_1 = gr.Button("我听懂了", size="sm", variant="secondary")
                            quick_reply_2 = gr.Button("请再解释一遍", size="sm", variant="secondary")
                            quick_reply_3 = gr.Button("我有问题", size="sm", variant="secondary")
                            quick_reply_4 = gr.Button("下一个知识点", size="sm", variant="secondary")
        
        with gr.Row():
            backup_input = gr.Textbox(
                label="",
                placeholder="如果语音对话不可用，可以在这里输入文字...",
                lines=2,
                scale=4
            )
            backup_send = gr.Button("发送", variant="secondary", scale=1)
    
        # 快捷回复按钮
        with gr.Row():
            quick_reply_1 = gr.Button("我听懂了", size="sm", variant="secondary")
            quick_reply_2 = gr.Button("请再解释一遍", size="sm", variant="secondary")
            quick_reply_3 = gr.Button("我有问题", size="sm", variant="secondary")
            quick_reply_4 = gr.Button("下一个知识点", size="sm", variant="secondary")
        
        # 事件处理函数
        def start_learning_session(course, difficulty, goal):
            """开始学习会话 - 切换到AI教师对话界面"""
            # 生成课程信息HTML
            course_info_html = f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                <h3>📚 {course}</h3>
                <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                    <span>📊 难度: {difficulty}</span>
                    <span>🎯 目标: {goal or '系统推荐'}</span>
                </div>
            </div>
            """
            
            # 生成个性化的课程系统提示
            system_prompt = f"""你是一位专业的AI数学教师，名叫小慧老师。
当前教学设置：
- 课程：{course}
- 难度等级：{difficulty}
- 学习目标：{goal or '根据课程内容制定合适目标'}

请按照以下教学原则：
1. 用亲切、耐心的语气进行教学
2. 每次回答控制在2-3句话内，避免过长
3. 注重启发式教学，多用提问引导学生思考
4. 对于数学问题，请先分析思路再给出解答步骤
5. 根据{difficulty}难度调整解释的详细程度
6. 鼓励学生提问，营造轻松的学习氛围

现在开始第一次教学互动。"""
            
            # 初始化对话历史
            welcome_message = f"您好！欢迎来到{course}课程。我是您的专属AI数学教师小慧老师。根据您选择的{difficulty}难度，我会为您量身定制学习内容。让我们开始这次精彩的学习之旅吧！有什么问题随时问我哦~ 😊"
            
            initial_chat = f"""
            <div class="message-teacher">
                <strong>👩‍🏫 小慧老师:</strong><br/>
                {welcome_message}
            </div>
            """
            
            # 初始化聊天历史，包含系统提示
            initial_history = [
                {"role": "system", "content": system_prompt},
                {"role": "teacher", "content": welcome_message}
            ]
            
            return (
                gr.update(visible=False),  # course_selection_page - 隐藏课程选择页面
                gr.update(visible=True),   # teacher_chat_page - 显示教师对话页面
                course_info_html,          # course_info - 更新课程信息
                update_real_chat_display(), # real_chat_display - 显示完整对话历史
                '<div><span class="status-indicator status-ready"></span>小慧老师已就绪</div>',  # teacher_status - 更新教师状态
                course,                    # current_course - 保存当前课程
                difficulty,                # current_difficulty - 保存当前难度
                goal,                      # current_goal - 保存当前目标
                initial_history            # chat_history - 初始化聊天历史
            )
        
        def back_to_course_selection():
            """返回课程选择页面"""
            return (
                gr.update(visible=True),   # 显示课程选择页面
                gr.update(visible=False),  # 隐藏教师对话页面
                "",                        # 清空课程信息
                "",                        # 清空对话显示
                '<div><span class="status-indicator status-ready"></span>系统就绪</div>',  # 重置状态
                "",                        # 清空当前课程
                "",                        # 清空当前难度
                "",                        # 清空当前目标
                []                         # 清空聊天历史
            )
        
        def send_message(message, chat_hist, course, difficulty):
            """发送学生消息并获取AI教师回复"""
            if not message.strip():
                return "", chat_hist, gr.update()
            
            # 添加学生消息到历史
            chat_hist.append({"role": "student", "content": message})
            
            # 生成个性化的AI教师回复
            teacher_response = generate_smart_teaching_response(message, course, difficulty, chat_hist)
            
            # 添加教师回复到历史
            chat_hist.append({"role": "teacher", "content": teacher_response})
            
            # 生成对话HTML
            chat_html = ""
            for msg in chat_hist:
                if msg["role"] == "teacher":
                    chat_html += f'<div class="message-teacher"><strong>👩‍🏫 小慧老师:</strong><br/>{msg["content"]}</div>'
                elif msg["role"] == "student":
                    chat_html += f'<div class="message-student"><strong>🧑‍🎓 您:</strong><br/>{msg["content"]}</div>'
                # 跳过system消息的显示
            
            return "", chat_hist, gr.update(value=chat_html)
        
        def generate_smart_teaching_response(student_message, course, difficulty, chat_history):
            """生成智能教学回复"""
            import random
            
            # 根据课程内容定制回复
            course_content = {
                "小学数学 - 基础运算": {
                    "keywords": ["加法", "减法", "乘法", "除法", "计算", "数字", "运算"],
                    "concepts": ["进位", "借位", "口算", "竖式", "九九乘法表"],
                    "examples": ["5+3=8", "10-4=6", "3×4=12", "15÷3=5"]
                },
                "小学数学 - 几何图形": {
                    "keywords": ["三角形", "正方形", "圆形", "长方形", "面积", "周长"],
                    "concepts": ["边", "角", "顶点", "直角", "锐角", "钝角"],
                    "examples": ["正方形有4条相等的边", "三角形有3个角"]
                },
                "初中数学 - 代数基础": {
                    "keywords": ["方程", "未知数", "代数式", "解方程", "x", "y"],
                    "concepts": ["移项", "合并同类项", "分配律", "因式分解"],
                    "examples": ["2x + 3 = 7", "x = 2"]
                },
                "初中数学 - 函数概念": {
                    "keywords": ["函数", "自变量", "因变量", "图像", "坐标"],
                    "concepts": ["一次函数", "二次函数", "函数图像", "函数关系"],
                    "examples": ["y = 2x + 1", "当x=1时，y=3"]
                },
                "高中数学 - 三角函数": {
                    "keywords": ["正弦", "余弦", "正切", "角度", "弧度", "sin", "cos", "tan"],
                    "concepts": ["单位圆", "三角恒等式", "周期性", "对称性"],
                    "examples": ["sin(30°) = 1/2", "cos(0°) = 1"]
                }
            }
            
            current_course = course_content.get(course, course_content["小学数学 - 基础运算"])
            
            # 分析学生消息类型
            message_lower = student_message.lower()
            
            # 检查是否包含课程关键词
            contains_keyword = any(keyword in message_lower for keyword in current_course["keywords"])
            
            # 根据不同情况生成回复
            if "我听懂了" in student_message:
                responses = [
                    "太好了！看来您已经掌握了这个知识点。让我们继续下一个内容吧！",
                    "很棒！您的理解很到位。我们来看看相关的练习题怎么样？",
                    "excellent！您学得很认真。让我给您出个小题目检验一下吧。"
                ]
                return random.choice(responses)
                
            elif "请再解释一遍" in student_message:
                responses = [
                    f"当然可以！让我用更简单的方式来解释{course}的这个概念。",
                    "没问题，我换个角度来讲解，希望能让您更容易理解。",
                    f"好的，我们重新梳理一下{course}的这个知识点。"
                ]
                return random.choice(responses) + f" 在{difficulty}难度下，我们可以这样理解..."
                
            elif "我有问题" in student_message:
                return "请告诉我您的具体问题，我会耐心为您解答。不要担心，任何问题都是学习过程中的正常现象！"
                
            elif "下一个知识点" in student_message:
                next_concepts = current_course["concepts"]
                if next_concepts:
                    concept = random.choice(next_concepts)
                    return f"好的，让我们学习下一个知识点：{concept}。这在{course}中是很重要的概念..."
                return "让我们继续深入学习下一个重要概念。"
                
            elif contains_keyword:
                # 如果包含课程关键词，给出专业回复
                examples = current_course["examples"]
                if examples:
                    example = random.choice(examples)
                    return f"很好的问题！关于{student_message}，让我来详细解释。例如：{example}。您觉得这样理解对吗？"
                return f"这是{course}中的重要概念。让我为您详细分析一下..."
                
            elif any(word in message_lower for word in ["不懂", "不明白", "难", "困难"]):
                return f"我理解您的困惑，{course}确实需要一步步来理解。让我们从最基础的开始，慢慢建立您的信心。"
                
            elif any(word in message_lower for word in ["简单", "容易", "会了"]):
                return "看起来您掌握得很不错！让我们尝试一些稍微有挑战性的内容，帮您进一步提升。"
                
            elif "?" in student_message or "？" in student_message:
                return f"这是个很好的问题！在{course}学习中，提问是非常重要的。让我来为您解答..."
                
            else:
                # 通用回复
                responses = [
                    f"我明白您的意思。在{course}的学习中，这个问题很常见。",
                    f"让我们一起来分析您提到的'{student_message}'。",
                    f"根据{difficulty}难度，我来为您详细解释一下。",
                    f"这是个很有价值的观点！在{course}中，我们可以这样理解...",
                    f"您的思考很深入！让我们继续探讨这个问题。"
                ]
                
                # 添加一些教学建议
                teaching_tips = [
                    "您还有其他疑问吗？",
                    "要不要我出个相关的练习题？",
                    "我们可以通过例子来加深理解。",
                    "您觉得这样的解释清楚吗？"
                ]
                
                response = random.choice(responses)
                tip = random.choice(teaching_tips)
                return f"{response} {tip}"
        
        def quick_reply(reply_text, chat_hist, course, difficulty):
            """处理快捷回复"""
            return send_message(reply_text, chat_hist, course, difficulty)
        
        # 设置全局ChatEngine引用的函数
        def set_chat_engine(engine):
            nonlocal global_chat_engine
            global_chat_engine = engine
        
        # 绑定事件
        start_button.click(
            fn=start_learning_session,
            inputs=[course_dropdown, difficulty_radio, learning_goal],
            outputs=[
                course_selection_page, teacher_chat_page, course_info, 
                real_chat_display, teacher_status, current_course, 
                current_difficulty, current_goal, chat_history
            ]
        )
        
        back_button.click(
            fn=back_to_course_selection,
            outputs=[
                course_selection_page, teacher_chat_page, course_info,
                real_chat_display, status_display, current_course,
                current_difficulty, current_goal, chat_history
            ]
        )
        
        # 发送消息事件
        backup_send.click(
            fn=send_message,
            inputs=[backup_input, chat_history, current_course, current_difficulty],
            outputs=[backup_input, chat_history, backup_chat_display]
        )
        
        backup_input.submit(
            fn=send_message,
            inputs=[backup_input, chat_history, current_course, current_difficulty],
            outputs=[backup_input, chat_history, backup_chat_display]
        )
        
        # 快捷回复按钮事件
        quick_reply_1.click(
            fn=lambda ch, c, d: quick_reply("我听懂了", ch, c, d),
            inputs=[chat_history, current_course, current_difficulty],
            outputs=[backup_input, chat_history, backup_chat_display]
        )
        
        quick_reply_2.click(
            fn=lambda ch, c, d: quick_reply("请再解释一遍", ch, c, d),
            inputs=[chat_history, current_course, current_difficulty],
            outputs=[backup_input, chat_history, backup_chat_display]
        )
        
        quick_reply_3.click(
            fn=lambda ch, c, d: quick_reply("我有问题", ch, c, d),
            inputs=[chat_history, current_course, current_difficulty],
            outputs=[backup_input, chat_history, backup_chat_display]
        )
        
        quick_reply_4.click(
            fn=lambda ch, c, d: quick_reply("下一个知识点", ch, c, d),
            inputs=[chat_history, current_course, current_difficulty],
            outputs=[backup_input, chat_history, backup_chat_display]
        )
        
        # 真实对话控制按钮事件
        test_chat_btn.click(
            fn=test_chat_display,
            outputs=[real_chat_display]
        )
        
        refresh_chat_btn.click(
            fn=refresh_chat_display,
            outputs=[real_chat_display]
        )
        
        clear_chat_btn.click(
            fn=clear_chat_display,
            outputs=[real_chat_display]
        )
        
        # 调试信息按钮事件
        debug_btn.click(
            fn=get_debug_info,
            outputs=[debug_info_display]
        )
        
        # 定时更新真实对话显示（每3秒检查一次）
        def auto_update_chat():
            return update_real_chat_display()
        
        # 使用gr.Timer实现定时更新（如果支持）
        try:
            # Gradio 4.x 支持定时器
            timer = gr.Timer(3.0)  # 每3秒触发一次
            timer.tick(
                fn=auto_update_chat,
                outputs=[real_chat_display]
            )
        except:
            # 如果不支持Timer，可以使用其他方式
            logger.info("Timer not supported, using alternative update method")
    
    # 启动日志监听
    start_log_monitor()
    
    return app, gradio_block, rtc_container, set_chat_engine


def main():
    """主函数 - 基于原始demo.py的实现"""
    args = parse_args()
    
    # 加载配置
    logger_config, service_config, engine_config = load_configs(args)

    # 创建应用
    app, demo, rtc_container, set_chat_engine = setup_teaching_demo()
    
    # 初始化ChatEngine
    global global_chat_engine
    global_chat_engine = ChatEngine()
    global_chat_engine.initialize(engine_config, app, demo, rtc_container)
    set_chat_engine(global_chat_engine)
    
    # 启动日志监听
    start_log_monitor()
    logger.info("Teaching platform started with real chat monitoring")

    # 启动服务
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        ssl_keyfile=service_config.cert_key if hasattr(service_config, 'cert_key') else None,
        ssl_certfile=service_config.cert_file if hasattr(service_config, 'cert_file') else None,
        ssl_verify=False
    )


if __name__ == "__main__":
    main()