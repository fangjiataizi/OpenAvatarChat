#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台 - 后端业务逻辑
负责处理教学相关的所有业务逻辑、数据处理和ChatEngine集成
"""

import sys
import os
import threading
import time
import re
import queue
import json
import random
import requests
from typing import List, Dict, Tuple, Optional
from loguru import logger

from engine_utils.directory_info import DirectoryInfo
from src.chat_engine.chat_engine import ChatEngine
from src.chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel

# 导入存储服务
try:
    from src.storage.services import learning_session_service, user_service
    STORAGE_AVAILABLE = True
    logger.info("Storage services imported successfully")
except ImportError as e:
    STORAGE_AVAILABLE = False
    logger.warning(f"Storage services not available: {e}")

project_dir = DirectoryInfo.get_project_dir()
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


class TeachingBackend:
    """教学平台后端业务逻辑类"""
    
    def __init__(self):
        self.chat_engine = None
        self.real_chat_queue = queue.Queue()
        self.log_monitor_thread = None
        self.log_monitor_running = False
        self.real_chat_messages = []
        self.all_chat_messages = []
        self.chat_history_lock = threading.Lock()
        
        # AI LLM配置
        self.llm_config = None
        self.use_real_ai = False
        
        # AI主动教学相关
        self.current_course = None
        self.current_difficulty = None
        self.current_goal = None
        self.has_greeted = False  # 是否已经问候过
        self.webrtc_connected = False  # WebRTC是否已连接
        
        # 雅思课程内容配置
        self.course_content = {
            "雅思 - 基础语法": {
                "keywords": ["时态", "语态", "句型", "语法", "动词", "形容词", "副词", "从句"],
                "concepts": ["现在完成时", "被动语态", "复合句", "虚拟语气", "定语从句"],
                "examples": ["I have been studying English for 3 years.", "The book was written by a famous author."]
            },
            "雅思 - 词汇记忆": {
                "keywords": ["词汇", "单词", "记忆", "词根", "词缀", "同义词", "反义词"],
                "concepts": ["词根记忆法", "联想记忆", "语境记忆", "分类记忆"],
                "examples": ["beneficial = benefit + -ial", "significant ≈ important"]
            },
            "雅思 - 写作技巧": {
                "keywords": ["写作", "作文", "段落", "结构", "论证", "观点", "例子"],
                "concepts": ["Task1图表作文", "Task2议论文", "开头段", "主体段", "结尾段"],
                "examples": ["The chart shows that...", "In conclusion, I believe that..."]
            },
            "雅思 - 口语练习": {
                "keywords": ["口语", "发音", "流利度", "话题", "描述", "讨论"],
                "concepts": ["Part1日常话题", "Part2个人陈述", "Part3深度讨论", "语音语调"],
                "examples": ["Could you tell me about your hometown?", "Describe a memorable experience..."]
            }
        }
        
        # 定时器管理
        self.active_timers = []
        self.teaching_active = False
        
        # 前端更新机制
        self.frontend_update_callback = None
        self.frontend_update_timer = None
        self.frontend_update_running = False
        
        # 会话状态管理 - 按照设计文档2.2实现
        self.session_state = {
            "course": None,
            "difficulty": None, 
            "goal": None,
            "stage": "init",  # init, greeting, waiting_user_input, teaching, practice
            "ai_teaching_active": False,
            "last_user_activity": time.time(),
            "message_count": 0
        }
        
        # 添加消息更新触发器 - 用于前端实时更新
        self.message_update_trigger = 0  # 每次消息变更时自增
        
        # 数据存储相关 - 按照设计文档2.7实现
        self.current_session_key = None  # 当前学习会话key
        self.current_user_id = 1  # 默认用户ID (后续支持用户系统)
        self.storage_available = STORAGE_AVAILABLE
    
    def initialize_chat_engine(self, engine_config, app, demo, rtc_container):
        """初始化ChatEngine和AI LLM配置"""
        try:
            # 调试：打印配置信息
            logger.info(f"Engine config type: {type(engine_config)}")
            if engine_config:
                logger.info(f"Engine config attributes: {dir(engine_config)}")
                if hasattr(engine_config, 'chat_engine'):
                    logger.info(f"Chat engine config type: {type(engine_config.chat_engine)}")
                    logger.info(f"Chat engine config attributes: {dir(engine_config.chat_engine)}")
            
            # 提取LLM配置用于直接API调用
            if engine_config and hasattr(engine_config, 'handler_configs'):
                logger.info(f"Found handler_configs: {list(engine_config.handler_configs.keys())}")
                # 查找LLM配置 (LLM_Bailian)
                for handler_name, handler_config in engine_config.handler_configs.items():
                    logger.info(f"Checking handler: {handler_name}, enabled: {handler_config.get('enabled', False)}")
                    if 'LLM' in handler_name and handler_config.get('enabled', False):
                        self.llm_config = handler_config
                        self.use_real_ai = True
                        logger.info(f"Real AI LLM configured successfully: {handler_name}")
                        break
            else:
                logger.warning("No handler_configs found in engine config")
            
            # 尝试初始化ChatEngine（用于WebRTC等功能）
            try:
                if engine_config:
                    self.chat_engine = ChatEngine()
                    # 正确的参数顺序：(engine_config, app, ui, parent_block)
                    self.chat_engine.initialize(engine_config, app=app, ui=demo, parent_block=rtc_container)
                    logger.info("ChatEngine initialized successfully with WebRTC container")
                else:
                    logger.warning("No engine_config found, using AI LLM only")
            except Exception as chat_engine_error:
                logger.warning(f"ChatEngine initialization failed: {chat_engine_error}, using AI LLM only")
                
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ChatEngine: {e}")
            # 即使ChatEngine初始化失败，也让服务继续运行
            return self.use_real_ai  # 如果有AI配置就返回True
    
    def start_log_monitor(self):
        """启动日志监听线程，从日志中提取真实对话内容"""
        if self.log_monitor_thread and self.log_monitor_thread.is_alive():
            return
        
        self.log_monitor_running = True
        self.log_monitor_thread = threading.Thread(target=self._monitor_chat_logs, daemon=True)
        self.log_monitor_thread.start()
        logger.info("Log monitor thread started")
    
    def _monitor_chat_logs(self):
        """监听聊天日志文件，提取实时对话"""
        log_file_path = "logs/teaching_platform.log"
        
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
            
            while self.log_monitor_running:
                try:
                    with open(log_file_path, 'r', encoding='utf-8') as file:
                        file.seek(current_position)
                        
                        for line in file:
                            line = line.strip()
                            
                            # 跳过空行和监听函数自己产生的日志
                            if not line or 'monitor_chat_logs' in line:
                                continue
                            
                            # 检查LLM输入 (用户说话)
                            if 'llm input' in line:
                                user_text = self._extract_llm_input(line)
                                if user_text:
                                    self._add_real_chat_message('human', user_text.strip())
                                    # 检测WebRTC连接建立（用户首次说话）
                                    self._handle_webrtc_connection()
                            
                            # 检查AI回复 (current sentence)
                            elif 'current sentence' in line:
                                ai_text = self._extract_current_sentence(line)
                                if ai_text:
                                    self._add_real_chat_message('avatar', ai_text.strip())
                                    
                            # 检查avatar启动事件 (检测到avatar开始工作)
                            elif 'on algo processor start' in line:
                                logger.info("Detected avatar processor start - triggering AI greeting")
                                self._handle_avatar_start()
                                
                            # 检查avatar processor启动完成
                            elif 'avatar processor started' in line or 'signal2img loop started' in line:
                                logger.info("Detected avatar processor fully started")
                                self._handle_avatar_ready()
                            
                            # 检查停止聊天信号
                            elif 'stop_chat' in line:
                                logger.info("Detected stop_chat signal - stopping AI teaching")
                                self._stop_ai_teaching()
                            
                            # 检查会话结束信号  
                            elif 'session stopped' in line or 'chat session stopped' in line:
                                logger.info("Detected session end - stopping AI teaching")
                                self._stop_ai_teaching()
                        
                        # 更新位置
                        current_position = file.tell()
                    
                    # 短暂休眠避免CPU占用过高
                    time.sleep(0.5)
                    
                except (FileNotFoundError, PermissionError):
                    time.sleep(1)
                    continue
                except Exception as e:
                    time.sleep(1)
                    continue
                    
        except Exception as e:
            logger.error(f"Monitor thread error: {e}")
    
    def _extract_llm_input(self, line: str) -> Optional[str]:
        """从日志行中提取LLM输入文本"""
        try:
            # 格式: 2025-06-19 15:43:47.384 | INFO | xxx - llm input qwen-vl-plus yeaht
            llm_input_index = line.find('llm input')
            if llm_input_index != -1:
                text_part = line[llm_input_index + len('llm input'):].strip()
                words = text_part.split()
                if len(words) > 1:
                    user_text = ' '.join(words[1:])  # 跳过模型名称
                    if user_text and len(user_text.strip()) > 0:
                        return user_text
        except Exception:
            pass
        return None
    
    def _extract_current_sentence(self, line: str) -> Optional[str]:
        """从日志行中提取AI回复文本"""
        try:
            # 格式: 2025-06-19 15:43:49.317 | INFO | xxx - current sentence你提到的yeaht似乎是在确认某个问题或表达肯定。
            sentence_index = line.find('current sentence')
            if sentence_index != -1:
                ai_text = line[sentence_index + len('current sentence'):].strip()
                if ai_text and len(ai_text.strip()) > 0:
                    return ai_text
        except Exception:
            pass
        return None
    
    def _add_real_chat_message(self, role: str, content: str):
        """添加真实对话消息到队列，带去重功能"""
        logger.debug(f"🔍 Adding chat message - Role: {role}, Content: {content[:50]}...")
        
        # 清理内容格式
        cleaned_content = self._clean_message_content(content)
        logger.debug(f"🔍 Cleaned content: '{cleaned_content}'")
        
        # 增加长度检查，避免流式输出的短内容
        if not cleaned_content or len(cleaned_content.strip()) < 3:
            logger.debug(f"🔍 Content too short or empty, skipping. Length: {len(cleaned_content.strip()) if cleaned_content else 0}")
            return False
        
        # 检查重复消息
        temp_messages = []
        duplicate_found = False
        
        while not self.real_chat_queue.empty():
            try:
                existing_msg = self.real_chat_queue.get_nowait()
                temp_messages.append(existing_msg)
                
                if (existing_msg['role'] == role and 
                    existing_msg['content'].strip() == cleaned_content.strip()):
                    duplicate_found = True
            except queue.Empty:
                break
        
        # 将消息放回队列
        for msg in temp_messages:
            self.real_chat_queue.put(msg)
        
        # 如果没有重复，才添加新消息
        if not duplicate_found:
            message = {
                'role': role,  # 'human' or 'avatar'
                'content': cleaned_content.strip(),
                'timestamp': time.time()
            }
            self.real_chat_queue.put(message)
            logger.info(f"✅ Added real chat message - {role}: {cleaned_content[:50]}...")
            
            # 🎯 更新消息触发器，用于状态变化监听
            self.message_update_trigger += 1
            logger.debug(f"🔄 Message update trigger incremented to {self.message_update_trigger}")
            
            # 保存到数据库 - 集成数据持久化
            db_message = {
                "role": role,
                "content": cleaned_content.strip(),
                "timestamp": message['timestamp'],
                "type": "proactive" if role == "avatar" else "normal"
            }
            self._save_message_to_database(db_message)
            
            # 如果是AI主动消息，立即触发前端更新（实现即时显示）
            if role == "avatar" and self.frontend_update_callback:
                try:
                    self.frontend_update_callback()
                    logger.debug("🔄 AI message triggered immediate frontend update")
                except Exception as e:
                    logger.error(f"Frontend update error: {e}")
            else:
                # 用户消息等待前端自动刷新机制处理
                logger.debug("🔄 Message added to queue, frontend will auto-refresh")
            
            return True
        else:
            logger.debug(f"🔍 Duplicate message found, skipping")
        
        return False
    
    def _clean_message_content(self, content: str) -> str:
        """清理消息内容，确保只返回纯文本"""
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
            
            return ""
        
        # 移除多余的空白字符
        cleaned = re.sub(r'\s+', ' ', content).strip()
        return cleaned if len(cleaned) >= 1 else ""
    
    def get_real_chat_messages(self) -> List[Dict]:
        """获取真实对话消息"""
        messages = []
        while not self.real_chat_queue.empty():
            try:
                message = self.real_chat_queue.get_nowait()
                messages.append(message)
            except queue.Empty:
                break
        return messages
    
    def get_all_chat_messages(self) -> List[Dict]:
        """获取所有对话消息（不清空队列）"""
        all_messages = []
        temp_messages = []
        
        # 获取所有消息
        while not self.real_chat_queue.empty():
            try:
                msg = self.real_chat_queue.get_nowait()
                temp_messages.append(msg)
            except queue.Empty:
                break
        
        # 将消息放回队列
        for msg in temp_messages:
            self.real_chat_queue.put(msg)
        
        return temp_messages
    
    def clear_chat_messages(self):
        """清空对话消息队列"""
        while not self.real_chat_queue.empty():
            try:
                self.real_chat_queue.get_nowait()
            except queue.Empty:
                break
    
    def call_llm_api(self, messages: List[Dict], temperature: float = 0.7) -> Optional[str]:
        """调用真实的AI LLM API"""
        if not self.use_real_ai or not self.llm_config:
            return None
            
        try:
            # 获取API配置
            api_base = self.llm_config.get('api_url', '')
            api_key = os.getenv('DASHSCOPE_API_KEY') or self.llm_config.get('api_key', '')
            model = self.llm_config.get('model_name', 'qwen-vl-plus')
            
            if not api_key:
                logger.warning("No API key found, using fallback response")
                return None
            
            # 构建请求
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # 转换消息格式（确保兼容OpenAI格式）
            formatted_messages = []
            for msg in messages:
                if msg['role'] == 'teacher':
                    formatted_messages.append({'role': 'assistant', 'content': msg['content']})
                elif msg['role'] == 'student':
                    formatted_messages.append({'role': 'user', 'content': msg['content']})
                else:
                    formatted_messages.append(msg)
            
            payload = {
                'model': model,
                'messages': formatted_messages,
                'temperature': temperature,
                'max_tokens': self.llm_config.get('max_tokens', 1024),
                'stream': False
            }
            
            # 发起API请求
            response = requests.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    ai_response = result['choices'][0]['message']['content']
                    logger.info(f"AI LLM response received: {ai_response[:100]}...")
                    return ai_response
                else:
                    logger.error(f"Invalid API response format: {result}")
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            
        return None
    
    def _handle_webrtc_connection(self):
        """处理WebRTC连接建立事件"""
        if not self.webrtc_connected:
            self.webrtc_connected = True
            logger.info("WebRTC connection detected, preparing for AI greeting")
            
            # 延迟3秒后发送AI主动问候，确保系统稳定
            threading.Timer(3.0, self._send_ai_greeting).start()
    
    def _handle_avatar_start(self):
        """处理Avatar处理器启动事件"""
        logger.info("Avatar processor started, preparing for AI greeting")
        # 延迟2秒后发送AI主动问候，让avatar完全就绪
        timer = threading.Timer(2.0, self._send_ai_greeting)
        self._add_timer(timer)
        timer.start()
        
    def _handle_avatar_ready(self):
        """处理Avatar处理器完全就绪事件"""
        logger.info("Avatar processor is fully ready")
        # 如果还没有问候过，立即发送问候
        if not self.has_greeted:
            timer = threading.Timer(0.5, self._send_ai_greeting)
            self._add_timer(timer)
            timer.start()
    
    def _send_ai_greeting(self):
        """发送AI主动问候 - 严格按照设计文档2.3实现"""
        if self.has_greeted:
            return
            
        self.has_greeted = True
        self.teaching_active = True
        
        # 生成个性化问候语
        greeting_message = self._generate_greeting_message()
        
        logger.info(f"🎓 AI Teacher Greeting: {greeting_message}")
        
        # ✅ 核心修复：AI主动消息仅走显示+TTS路径，不触发LLM
        # 1. 添加到显示队列 (不触发LLM)
        success = self._add_real_chat_message('avatar', greeting_message)
        
        # 2. 发送到TTS管道 (不通过TEXT通道避免触发LLM)
        tts_success = self._send_to_tts_only(greeting_message)
        
        if success and tts_success:
            logger.info("AI proactive greeting sent and displayed successfully")
        elif not tts_success:
            logger.warning("TTS failed for greeting message")
            
        # 3. 设置状态为等待用户回复
        self.session_state = getattr(self, 'session_state', {})
        self.session_state["stage"] = "waiting_user_input"
        
        # 延迟10秒后开始主动教学内容讲授
        if self.teaching_active:
            timer = threading.Timer(10.0, self._start_proactive_teaching)
            self._add_timer(timer)
            timer.start()
    
    def _trigger_frontend_update(self):
        """触发前端更新的辅助方法"""
        if self.frontend_update_callback:
            try:
                self.frontend_update_callback()
                logger.debug("🔄 Delayed frontend update triggered")
            except Exception as e:
                logger.error(f"Frontend update callback failed: {e}")
    
    def _send_avatar_text_through_engine(self, text: str) -> bool:
        """通过ChatEngine发送Avatar文本数据到TTS和前端显示"""
        try:
            if not self.chat_engine:
                raise Exception("ChatEngine not available")
                
            # 获取当前活跃的会话
            if not hasattr(self.chat_engine, 'sessions') or not self.chat_engine.sessions:
                raise Exception("No active sessions found")
                
            # 通过ChatEngine的会话发送文本数据
            session = next(iter(self.chat_engine.sessions.values()))
            
            # 查找RTC ClientHandler的会话代理
            rtc_handler = None
            for handler_name, handler_record in session.handlers.items():
                if 'Rtc' in handler_name or 'RTC' in handler_name:
                    rtc_handler = handler_record
                    break
            
            if not rtc_handler:
                raise Exception("RTC handler not found")
            
            # 获取RTC客户端会话代理
            rtc_context = rtc_handler.env.context
            if not hasattr(rtc_context, 'client_session_delegate') or not rtc_context.client_session_delegate:
                raise Exception("RTC client session delegate not found")
                
            client_delegate = rtc_context.client_session_delegate
            
            # 方法1：直接发送TEXT数据到聊天通道（用于前端显示）
            self._send_text_to_chat_channel(client_delegate, text)
            
            # 方法2：同时发送AVATAR_TEXT数据到TTS（用于语音合成）
            self._send_avatar_text_to_tts(client_delegate, text, session)
            
            logger.info("Avatar text successfully sent to both chat display and TTS")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to send avatar text through ChatEngine: {e}")
            return False
    
    def _send_text_to_chat_channel(self, client_delegate, text: str):
        """直接发送文本到聊天通道进行显示"""
        try:
            from chat_engine.common.engine_channel_type import EngineChannelType
            
            # 使用与rtc_stream.py相同的方式发送文本到TEXT通道
            # 这样WebRTC的process_chat_history会捕获并发送到前端
            timestamp = client_delegate.get_timestamp()
            
            # 直接调用put_data方法，参考rtc_stream.py第216行的调用方式
            client_delegate.put_data(
                EngineChannelType.TEXT,
                text,
                timestamp,
                loopback=False  # 不回环，让系统处理这个文本作为Avatar输出
            )
            
            logger.info(f"Avatar text sent to TEXT channel for display: {text[:50]}...")
            
        except Exception as e:
            logger.warning(f"Failed to send text to chat channel: {e}")
            # 备用方法：使用loopback=True，让系统把这个当作输入然后处理成输出
            try:
                timestamp = client_delegate.get_timestamp()
                client_delegate.put_data(
                    EngineChannelType.TEXT,
                    text,
                    timestamp,
                    loopback=True  # 回环处理，可能触发LLM生成回应
                )
                logger.info("Backup method: text sent with loopback=True")
                    
            except Exception as backup_e:
                logger.warning(f"Backup method also failed: {backup_e}")
    
    def _send_avatar_text_to_tts(self, client_delegate, text: str, session):
        """发送Avatar文本到TTS进行语音合成"""
        try:
            from chat_engine.data_models.chat_data.chat_data_model import ChatData
            from chat_engine.data_models.chat_data_type import ChatDataType
            from chat_engine.data_models.runtime_data.data_bundle import DataBundle
            from uuid import uuid4
            
            # 创建AVATAR_TEXT数据包用于TTS
            session_context = session.session_context
            definition = session_context.get_input_text_definition("avatar_text")
            data_bundle = DataBundle(definition)
            data_bundle.set_main_data(text)
            data_bundle.add_meta('speech_id', str(uuid4()))
            data_bundle.add_meta('avatar_text_end', True)
            
            chat_data = ChatData(
                source="ai_teacher",
                type=ChatDataType.AVATAR_TEXT,
                data=data_bundle,
                timestamp=session_context.get_timestamp()
            )
            
            # 通过数据提交器直接提交AVATAR_TEXT数据到TTS
            if hasattr(client_delegate, 'data_submitter') and client_delegate.data_submitter:
                client_delegate.data_submitter.submit(chat_data)
                logger.info("Avatar text submitted to TTS pipeline")
            else:
                logger.warning("Data submitter not found, TTS may not work")
                # 不使用put_data_async，因为这个方法可能不存在
                
        except Exception as e:
            logger.warning(f"Failed to send avatar text to TTS: {e}")
    
    def _start_proactive_teaching(self):
        """开始主动教学内容讲授 - 按照设计文档2.5实现"""
        if not self.current_course or not self.teaching_active:
            return
            
        # 根据课程生成教学内容（不使用LLM）
        teaching_content = self._generate_teaching_content()
        
        logger.info(f"🎓 AI Teacher Starting Lesson: {teaching_content[:50]}...")
        
        # ✅ 核心修复：AI主动教学内容仅走显示+TTS路径，不触发LLM
        # 1. 添加到显示队列 (不触发LLM)
        success = self._add_real_chat_message('avatar', teaching_content)
        
        # 2. 发送到TTS管道 (不通过TEXT通道避免触发LLM)
        tts_success = self._send_to_tts_only(teaching_content)
        
        if success and tts_success:
            logger.info("AI proactive teaching content sent successfully")
        elif not tts_success:
            logger.warning("TTS failed for teaching content")
            
        # 继续定期发送教学内容
        if self.teaching_active:
            timer = threading.Timer(30.0, self._continue_teaching)
            self._add_timer(timer)
            timer.start()
        
    def _continue_teaching(self):
        """继续教学内容 - 按照设计文档2.5实现"""
        if not self.current_course or not self.teaching_active:
            return
            
        # 生成下一段教学内容（不使用LLM）
        next_content = self._generate_next_teaching_content()
        
        if next_content:
            logger.info(f"🎓 AI Teacher Continue: {next_content[:50]}...")
            
            # ✅ 核心修复：AI主动教学内容仅走显示+TTS路径，不触发LLM
            # 1. 添加到显示队列 (不触发LLM)
            success = self._add_real_chat_message('avatar', next_content)
            
            # 2. 发送到TTS管道 (不通过TEXT通道避免触发LLM)
            tts_success = self._send_to_tts_only(next_content)
            
            if success and tts_success:
                logger.info("AI continue teaching content sent successfully")
            elif not tts_success:
                logger.warning("TTS failed for continue teaching content")
                
            # 继续循环教学
            if self.teaching_active:
                timer = threading.Timer(25.0, self._continue_teaching)
                self._add_timer(timer)
                timer.start()
    
    def _generate_teaching_content(self) -> str:
        """生成教学内容"""
        course = self.current_course or "雅思 - 基础语法"
        difficulty = self.current_difficulty or "初级"
        
        if "基础语法" in course:
            contents = [
                f"好的，现在让我们开始{course}的学习。首先，我想问一下，你对英语时态掌握得怎么样？我们先来复习一下现在完成时。",
                f"现在完成时的基本结构是：have/has + 过去分词。比如'I have studied English for 3 years'。你能告诉我这个句子表达的是什么意思吗？",
                f"在雅思考试中，现在完成时经常出现在写作和口语部分。让我们来看一个实际的例子..."
            ]
        elif "词汇记忆" in course:
            contents = [
                f"接下来我们学习{course}。词汇是雅思考试的基础，我将教你一些高效的记忆方法。",
                f"首先是词根记忆法。比如'beneficial'这个单词，我们可以分解为'benefit'加上后缀'-ial'。",
                f"你知道'significant'这个词的同义词有哪些吗？在雅思写作中，使用同义词替换非常重要。"
            ]
        elif "写作技巧" in course:
            contents = [
                f"现在我们开始{course}的学习。雅思写作分为Task1和Task2两部分。",
                f"Task1通常是图表作文，开头段的表达很重要。比如'The chart shows that...'是一个常用的开头。",
                f"对于{difficulty}水平的学生，我建议先掌握基本的句型结构，然后再追求语言的多样性。"
            ]
        elif "口语练习" in course:
            contents = [
                f"欢迎来到{course}！口语是很多同学的难点，但不用担心，我会帮助你提高的。",
                f"雅思口语分为三个部分。Part1是日常话题，比如'Could you tell me about your hometown?'",
                f"流利度比准确性更重要。即使有小错误，保持流利的表达也能获得好分数。"
            ]
        else:
            contents = [
                f"让我们开始今天的{course}学习。我会根据你的{difficulty}水平来调整教学内容。",
                f"如果你有任何问题，随时可以打断我。学习是一个互动的过程。",
                f"我们先从基础概念开始，然后逐步深入到更复杂的内容。"
            ]
            
        return random.choice(contents)
    
    def _generate_next_teaching_content(self) -> str:
        """生成下一段教学内容"""
        course = self.current_course or "雅思"
        
        next_contents = [
            "你有什么问题想问我吗？或者我们继续下一个知识点？",
            "让我们来做一个小练习。请试着用刚才学到的知识造一个句子。",
            "很好！现在我们来学习下一个重要概念。在雅思考试中，这个知识点经常出现。",
            "你觉得刚才的内容理解得怎么样？需要我再详细解释一下吗？",
            "我注意到很多学生在这个地方容易出错。让我给你一些实用的技巧。"
        ]
        
        return random.choice(next_contents)
    
    def _generate_greeting_message(self) -> str:
        """生成个性化问候消息"""
        course = self.current_course or "课程"
        difficulty = self.current_difficulty or "适合"
        goal = self.current_goal
        
        greetings = [
            f"你好！我是小慧老师，很高兴为你开始{course}的学习。",
            f"欢迎来到{course}课堂！我是你的专属AI教师小慧。",
            f"你好，同学！我是小慧老师，今天我们一起学习{course}。"
        ]
        
        base_greeting = random.choice(greetings)
        
        # 添加个性化内容
        if goal and goal.strip():
            personal_part = f"我注意到你的学习目标是：{goal}。我会根据这个目标为你制定学习计划。"
        else:
            personal_part = f"我会根据你选择的{difficulty}难度，为你提供个性化的教学指导。"
        
        encouragement = "准备好开始我们的学习之旅了吗？有什么问题随时告诉我！"
        
        return f"{base_greeting}\n\n{personal_part}\n\n{encouragement}"
    
    def set_current_session_info(self, course: str, difficulty: str, goal: str):
        """设置当前学习会话信息 - 按照设计文档2.2实现"""
        # 先停止之前的教学活动
        self._stop_ai_teaching()
        
        # 设置新的会话信息
        self.current_course = course
        self.current_difficulty = difficulty
        self.current_goal = goal
        self.has_greeted = False  # 重置问候状态
        self.webrtc_connected = False  # 重置连接状态
        self.teaching_active = False  # 重置教学状态
        
        # 更新会话状态
        self.session_state.update({
            "course": course,
            "difficulty": difficulty,
            "goal": goal,
            "stage": "waiting_connection",
            "ai_teaching_active": False,
            "last_user_activity": time.time(),
            "message_count": 0
        })
        
        logger.info(f"Session info updated: {course} - {difficulty}")
        logger.info("AI will greet automatically when avatar is ready")

    def create_learning_session(self, course: str, difficulty: str, goal: str) -> Dict:
        """创建学习会话 - 包含数据库持久化"""
        
        # 创建数据库会话
        session_key = self.create_database_session(course, difficulty, goal)
        
        # 生成个性化的课程系统提示
        system_prompt = f"""你是一位专业的AI雅思英语教师，名叫小慧老师。
当前教学设置：
- 课程：{course}
- 难度等级：{difficulty}
- 学习目标：{goal or '根据课程内容制定合适目标'}

请按照以下教学原则：
1. 用亲切、耐心的语气进行教学
2. 每次回答控制在2-3句话内，避免过长
3. 注重启发式教学，多用提问引导学生思考
4. 提供实用的雅思学习技巧和应试策略
5. 根据{difficulty}难度调整解释的详细程度
6. 鼓励学生多练习和提问，营造轻松的学习氛围

现在开始第一次教学互动。"""
        
        # 欢迎消息
        welcome_message = f"您好！欢迎来到{course}课程。我是您的专属AI雅思英语教师小慧老师。根据您选择的{difficulty}难度，我会为您量身定制学习内容。让我们开始这次精彩的学习之旅吧！有什么问题随时问我哦~ 😊"
        
        # 初始化聊天历史
        initial_history = [
            {"role": "system", "content": system_prompt},
            {"role": "teacher", "content": welcome_message}
        ]
        
        # 保存系统提示到数据库
        if session_key:
            self._save_message_to_database({
                "role": "system",
                "content": system_prompt,
                "timestamp": time.time(),
                "type": "system"
            })
        
        return {
            "course": course,
            "difficulty": difficulty,
            "goal": goal,
            "system_prompt": system_prompt,
            "welcome_message": welcome_message,
            "chat_history": initial_history,
            "session_key": session_key,
            "storage_enabled": self.storage_available
        }
    
    def generate_teaching_response(self, student_message: str, course: str, difficulty: str, chat_history: List[Dict]) -> str:
        """生成智能教学回复"""
        # 如果有真实AI配置，优先使用AI LLM
        if self.use_real_ai:
            # 构建完整的对话上下文，包含系统提示
            api_messages = []
            
            # 添加系统提示
            system_prompt = f"""你是一位专业的AI雅思英语教师，名叫小慧老师。
当前教学设置：
- 课程：{course}
- 难度等级：{difficulty}

请按照以下教学原则：
1. 用亲切、耐心的语气进行教学
2. 每次回答控制在2-3句话内，保持简洁
3. 注重启发式教学，多用提问引导学生思考
4. 提供实用的雅思学习技巧和应试策略
5. 根据{difficulty}难度调整解释的详细程度
6. 鼓励学生多练习和提问，营造轻松的学习氛围

请直接回答学生的问题，不要重复学生的话。"""
            
            api_messages.append({"role": "system", "content": system_prompt})
            
            # 添加最近的对话历史（最多保留10轮对话）
            recent_history = chat_history[-20:] if len(chat_history) > 20 else chat_history
            for msg in recent_history:
                if msg['role'] == 'system':
                    continue  # 跳过系统消息，已经添加了新的
                elif msg['role'] == 'student':
                    api_messages.append({"role": "user", "content": msg['content']})
                elif msg['role'] == 'teacher':
                    api_messages.append({"role": "assistant", "content": msg['content']})
            
            # 添加当前学生消息
            api_messages.append({"role": "user", "content": student_message})
            
            # 调用AI API
            ai_response = self.call_llm_api(api_messages, temperature=0.7)
            
            if ai_response:
                logger.info(f"Using AI LLM response for: {student_message[:50]}...")
                return ai_response
            else:
                logger.warning("AI LLM failed, falling back to rule-based response")
        
        # 回退到基于规则的回复（当AI不可用时）
        return self._generate_fallback_response(student_message, course, difficulty)
    
    def _generate_fallback_response(self, student_message: str, course: str, difficulty: str) -> str:
        """生成回退的基于规则的回复"""
        current_course = self.course_content.get(course, self.course_content["雅思 - 基础语法"])
        message_lower = student_message.lower()
        
        # 检查是否包含课程关键词
        contains_keyword = any(keyword in message_lower for keyword in current_course["keywords"])
        
        # 快捷回复处理
        if "我听懂了" in student_message:
            responses = [
                "太好了！看来您已经掌握了这个知识点。让我们继续下一个雅思内容吧！",
                "很棒！您的理解很到位。我们来看看相关的雅思练习题怎么样？",
                "Excellent！您学得很认真。让我给您出个雅思相关的小题目检验一下吧。"
            ]
            return random.choice(responses)
            
        elif "请再解释一遍" in student_message:
            responses = [
                f"当然可以！让我用更简单的方式来解释{course}的这个概念。",
                "没问题，我换个角度来讲解雅思的这个知识点，希望能让您更容易理解。",
                f"好的，我们重新梳理一下{course}的这个重要概念。"
            ]
            return random.choice(responses) + f" 在{difficulty}难度下，我们可以这样理解..."
            
        elif "我有问题" in student_message:
            return "请告诉我您的具体问题，我会耐心为您解答。不要担心，任何问题都是雅思学习过程中的正常现象！"
            
        elif "下一个知识点" in student_message:
            next_concepts = current_course["concepts"]
            if next_concepts:
                concept = random.choice(next_concepts)
                return f"好的，让我们学习下一个知识点：{concept}。这在{course}中是很重要的雅思概念..."
            return "让我们继续深入学习下一个重要的雅思概念。"
        
        # 基于课程内容的回复
        elif contains_keyword:
            examples = current_course["examples"]
            if examples:
                example = random.choice(examples)
                return f"很好的问题！关于{student_message}，让我来详细解释。例如：{example}。您觉得这样理解对吗？"
            return f"这是{course}中的重要概念。让我为您详细分析一下这个雅思知识点..."
        
        # 情感分析回复
        elif any(word in message_lower for word in ["不懂", "不明白", "难", "困难", "hard", "difficult"]):
            return f"我理解您的困惑，{course}确实需要一步步来理解。让我们从最基础的雅思知识开始，慢慢建立您的信心。"
            
        elif any(word in message_lower for word in ["简单", "容易", "会了", "easy", "simple"]):
            return "看起来您掌握得很不错！让我们尝试一些稍微有挑战性的雅思内容，帮您进一步提升。"
            
        elif "?" in student_message or "？" in student_message:
            return f"这是个很好的问题！在{course}学习中，提问是非常重要的。让我来为您解答这个雅思相关的问题..."
        
        # 通用回复
        else:
            responses = [
                f"我明白您的意思。在{course}的学习中，这个问题很常见。",
                f"让我们一起来分析您提到的'{student_message}'这个雅思相关的内容。",
                f"根据{difficulty}难度，我来为您详细解释一下这个雅思概念。",
                f"这是个很有价值的观点！在{course}中，我们可以这样理解...",
                f"您的思考很深入！让我们继续探讨这个雅思问题。"
            ]
            
            teaching_tips = [
                "您还有其他雅思相关的疑问吗？",
                "要不要我出个相关的雅思练习题？",
                "我们可以通过实际的雅思例子来加深理解。",
                "您觉得这样的解释对雅思学习有帮助吗？"
            ]
            
            response = random.choice(responses)
            tip = random.choice(teaching_tips)
            return f"{response} {tip}"
    
    def process_student_message(self, message: str, chat_history: List[Dict], course: str, difficulty: str) -> Tuple[List[Dict], str]:
        """处理学生消息并生成教师回复"""
        if not message.strip():
            return chat_history, ""
        
        # 添加学生消息到历史
        chat_history.append({"role": "student", "content": message})
        
        # 生成教师回复
        teacher_response = self.generate_teaching_response(message, course, difficulty, chat_history)
        
        # 添加教师回复到历史
        chat_history.append({"role": "teacher", "content": teacher_response})
        
        return chat_history, teacher_response
    
    def get_debug_info(self) -> Dict:
        """获取调试信息"""
        return {
            "queue_size": self.real_chat_queue.qsize(),
            "monitor_status": "运行中" if self.log_monitor_running else "已停止",
            "log_file": "logs/log.log",
            "timestamp": time.strftime('%H:%M:%S'),
            "chat_engine_status": "已连接" if self.chat_engine else "未连接"
        }
    
    def add_test_message(self):
        """添加测试消息"""
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
        success = self._add_real_chat_message(role, content)
        if success:
            logger.info(f"Added test message: {role} - {content}")
        return success
    
    def stop_log_monitor(self):
        """停止日志监听"""
        self.log_monitor_running = False
        if self.log_monitor_thread:
            self.log_monitor_thread.join(timeout=1)
        logger.info("Log monitor stopped")
    
    def _stop_ai_teaching(self):
        """停止AI教学活动"""
        logger.info("🛑 Stopping AI teaching activities...")
        
        # 设置停止标志
        self.teaching_active = False
        self.has_greeted = False
        self.webrtc_connected = False
        
        # 取消所有活跃的定时器
        for timer in self.active_timers:
            if timer.is_alive():
                timer.cancel()
                logger.info(f"Cancelled active timer: {timer}")
        
        self.active_timers.clear()
        logger.info("✅ AI teaching stopped and all timers cleared")
    
    def _add_timer(self, timer: threading.Timer):
        """添加定时器到管理列表"""
        self.active_timers.append(timer)
        # 清理已完成的定时器
        self.active_timers = [t for t in self.active_timers if t.is_alive()]
    
    def set_frontend_update_callback(self, callback_func):
        """设置前端更新回调函数"""
        self.frontend_update_callback = callback_func
        
    def start_frontend_auto_update(self):
        """启动前端自动更新"""
        if self.frontend_update_running:
            return
            
        self.frontend_update_running = True
        self._schedule_frontend_update()
        logger.info("Frontend auto-update started")
    
    def stop_frontend_auto_update(self):
        """停止前端自动更新"""
        self.frontend_update_running = False
        if self.frontend_update_timer:
            self.frontend_update_timer.cancel()
        logger.info("Frontend auto-update stopped")
    
    def _schedule_frontend_update(self):
        """安排下次前端更新"""
        if not self.frontend_update_running:
            return
            
        def update_frontend():
            if self.frontend_update_callback and self.frontend_update_running:
                try:
                    # 调用前端更新函数
                    self.frontend_update_callback()
                except Exception as e:
                    logger.error(f"Frontend update error: {e}")
            
            # 安排下次更新
            if self.frontend_update_running:
                self._schedule_frontend_update()
        
        # 3秒后执行更新
        self.frontend_update_timer = threading.Timer(3.0, update_frontend)
        self.frontend_update_timer.start()


    def _add_display_message(self, role: str, content: str, message_type: str = "normal"):
        """统一消息处理 - 按照设计文档2.6实现
        
        Args:
            role: "human" | "avatar" 
            content: 消息内容
            message_type: "normal" | "proactive" | "response"
        """
        try:
            # 1. 内容清理和验证
            cleaned_content = self._clean_message_content(content)
            
            logger.debug(f"🔍 Adding display message - Role: {role}, Type: {message_type}, Content: {cleaned_content[:50]}...")
            
            # 2. 长度检查避免垃圾消息
            if len(cleaned_content) < 3:  # 过滤短消息和流式输出片段，降低阈值以适应测试
                logger.debug(f"🔍 Content too short or empty, skipping. Length: {len(cleaned_content)}")
                return False
                
            # 3. 重复检查
            if self._is_duplicate_message_queue(role, cleaned_content):
                logger.debug(f"🔍 Duplicate message found, skipping")
                return False
                
            # 4. 添加到实时队列
            message = {
                "role": role,
                "content": cleaned_content, 
                "timestamp": time.time(),
                "type": message_type
            }
            
            # 确保队列存在
            if not hasattr(self, 'real_chat_queue'):
                import queue
                self.real_chat_queue = queue.Queue()
                
            self.real_chat_queue.put(message)
            
            # 5. 持久化存储 (异步) - 按照设计文档2.7实现
            self._save_message_to_database(message)
            
            # 6. 触发前端更新 (延迟)
            if self.frontend_update_callback:
                timer = threading.Timer(2.0, self._trigger_frontend_update)
                self._add_timer(timer)
                timer.start()
            
            logger.info(f"✅ Added display message - {role} ({message_type}): {cleaned_content[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding display message: {e}")
            return False
    
    def _is_duplicate_message_queue(self, role: str, content: str) -> bool:
        """检查是否为重复消息（队列版本）"""
        if not hasattr(self, 'real_chat_queue'):
            return False
            
        temp_messages = []
        duplicate_found = False
        
        # 检查队列中的所有消息
        while not self.real_chat_queue.empty():
            try:
                existing_msg = self.real_chat_queue.get_nowait()
                temp_messages.append(existing_msg)
                
                # 检查是否与现有消息重复
                if (existing_msg.get('role') == role and 
                    existing_msg.get('content', '').strip() == content.strip()):
                    duplicate_found = True
                    logger.debug(f"🔍 Found duplicate: '{existing_msg.get('content', '')[:30]}...'")
                    break  # 找到重复就退出
            except:
                break
        
        # 将消息放回队列（按原来的顺序）
        for msg in temp_messages:
            self.real_chat_queue.put(msg)
            
        return duplicate_found
        
    def _send_to_tts_only(self, text: str) -> bool:
        """仅发送到TTS管道，不触发LLM - 按照设计文档2.3实现"""
        try:
            if not self.chat_engine:
                logger.warning("ChatEngine not available for TTS, using fallback method")
                logger.info(f"current sentence{text}")
                return True
                
            # 获取当前活跃的会话
            if not hasattr(self.chat_engine, 'sessions') or not self.chat_engine.sessions:
                logger.warning("No active sessions found for TTS")
                return False
                
            session = next(iter(self.chat_engine.sessions.values()))
            
            # 查找RTC ClientHandler的会话代理
            rtc_handler = None
            for handler_name, handler_record in session.handlers.items():
                if 'Rtc' in handler_name or 'RTC' in handler_name:
                    rtc_handler = handler_record
                    break
            
            if not rtc_handler:
                logger.warning("RTC handler not found for TTS")
                return False
            
            # 获取RTC客户端会话代理
            rtc_context = rtc_handler.env.context
            if not hasattr(rtc_context, 'client_session_delegate') or not rtc_context.client_session_delegate:
                logger.warning("RTC client session delegate not found for TTS")
                return False
                
            client_delegate = rtc_context.client_session_delegate
            
            # ✅ 核心修复：仅发送AVATAR_TEXT数据到TTS，不通过TEXT通道
            success = self._send_avatar_text_to_tts(client_delegate, text, session)
            
            if success:
                logger.info("Avatar text submitted to TTS pipeline successfully")
                return True
            else:
                # 备用方法：使用日志触发TTS
                logger.warning("Direct TTS method failed, using log fallback")
                logger.info(f"current sentence{text}")
                return True
                
        except Exception as e:
            logger.warning(f"Failed to send text to TTS: {e}")
            # 备用方法：使用日志触发TTS
            logger.info(f"current sentence{text}")
            return True
    
    # ==================== 数据存储方法 - 按照设计文档2.7实现 ====================
    
    def _save_message_to_database(self, message: Dict) -> bool:
        """保存消息到数据库 - 异步执行"""
        if not self.storage_available or not self.current_session_key:
            logger.debug("Storage not available or no active session, skipping database save")
            return False
        
        def save_async():
            try:
                success = learning_session_service.add_message_to_session(
                    session_key=self.current_session_key,
                    role=message.get('role'),
                    content=message.get('content'),
                    message_type=message.get('type', 'normal'),
                    metadata={
                        'timestamp': message.get('timestamp'),
                        'source': 'teaching_backend'
                    }
                )
                
                if success:
                    logger.debug(f"Message saved to database: {message.get('role')} - {message.get('content', '')[:30]}...")
                else:
                    logger.warning("Failed to save message to database")
                    
            except Exception as e:
                logger.error(f"Error saving message to database: {e}")
        
        # 异步执行保存操作
        save_thread = threading.Thread(target=save_async, daemon=True)
        save_thread.start()
        return True
    
    def create_database_session(self, course: str, difficulty: str, goal: str) -> Optional[str]:
        """创建数据库学习会话"""
        if not self.storage_available:
            logger.info("Storage not available, using in-memory session only")
            return None
        
        try:
            session_data = learning_session_service.create_session(
                user_id=self.current_user_id,
                course_name=course,
                difficulty=difficulty,
                goal=goal
            )
            
            if session_data:
                session_key = session_data.get('session_key')
                self.current_session_key = session_key
                logger.info(f"Database learning session created: {session_key}")
                return session_key
            else:
                logger.error("Failed to create database session")
                return None
                
        except Exception as e:
            logger.error(f"Error creating database session: {e}")
            return None
    
    def end_database_session(self) -> bool:
        """结束数据库学习会话"""
        if not self.storage_available or not self.current_session_key:
            return False
        
        try:
            success = learning_session_service.end_session(self.current_session_key)
            if success:
                logger.info(f"Database session ended: {self.current_session_key}")
                self.current_session_key = None
                return True
            else:
                logger.warning("Failed to end database session")
                return False
                
        except Exception as e:
            logger.error(f"Error ending database session: {e}")
            return False
    
    def get_session_statistics(self) -> Dict:
        """获取当前会话统计信息"""
        if not self.storage_available or not self.current_session_key:
            return {
                "storage_available": False,
                "session_active": False
            }
        
        try:
            stats = learning_session_service.get_session_statistics(self.current_session_key)
            stats["storage_available"] = True
            stats["session_active"] = True
            stats["session_key"] = self.current_session_key
            return stats
            
        except Exception as e:
            logger.error(f"Error getting session statistics: {e}")
            return {"error": str(e)}
    
    def restore_session_from_database(self, session_key: str) -> bool:
        """从数据库恢复会话状态"""
        if not self.storage_available:
            return False
        
        try:
            session_data = learning_session_service.get_session(session_key)
            if not session_data:
                logger.warning(f"Session not found in database: {session_key}")
                return False
            
            # 恢复会话信息
            self.current_session_key = session_key
            metadata = session_data.get('session_metadata', {})
            
            if metadata:
                self.current_course = metadata.get('course_name')
                self.current_difficulty = metadata.get('difficulty')
                self.current_goal = metadata.get('goal')
            
            # 恢复对话历史到内存队列
            chat_history = session_data.get('chat_history', [])
            for msg in chat_history[-10:]:  # 只恢复最近10条消息
                if 'role' in msg and 'content' in msg:
                    # 添加到内存队列但不触发数据库保存
                    queue_message = {
                        "role": msg['role'],
                        "content": msg['content'],
                        "timestamp": time.time(),
                        "type": msg.get('metadata', {}).get('type', 'normal')
                    }
                    self.real_chat_queue.put(queue_message)
            
            logger.info(f"Session restored from database: {session_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring session from database: {e}")
            return False


# 全局后端实例
teaching_backend = TeachingBackend() 