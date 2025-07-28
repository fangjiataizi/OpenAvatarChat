#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台 - 统一后端业务逻辑
负责处理教学相关的所有业务逻辑、数据处理和ChatEngine集成
整合了主动教学系统、数据存储、实时通信等功能
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
from dotenv import load_dotenv

# 确保在模块加载时就加载环境变量
load_dotenv()

from engine_utils.directory_info import DirectoryInfo
from src.chat_engine.chat_engine import ChatEngine
from src.chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel

# 导入存储服务 - 临时禁用避免SQLite创建
try:
    # from src.storage.services import learning_session_service, user_service
    STORAGE_AVAILABLE = False  # 强制禁用存储服务
    logger.info("Storage services temporarily disabled to prevent SQLite creation")
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
        
        # 用户认证支持
        self.auth_manager = None
        self.require_auth = True
        self.current_user_id = 1  # 临时设置为1（演示用户）
        
        # AI主动教学相关
        self.current_course = None
        self.current_difficulty = None
        self.current_goal = None
        self.has_greeted = False
        self.webrtc_connected = False
        self.used_teaching_contents = set()  # 追踪已使用的教学内容
        self.teaching_step = 0  # 教学步骤计数器
        
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
        
        # 会话状态管理
        self.session_state = {
            "course": None,
            "difficulty": None, 
            "goal": None,
            "stage": "init",
            "ai_teaching_active": False,
            "last_user_activity": time.time(),
            "message_count": 0
        }
        
        # 添加消息更新触发器
        self.message_update_trigger = 0
        
        # 数据存储相关
        self.current_session_key = None
        self.current_user_id = 1
        self.storage_available = STORAGE_AVAILABLE
    
    def initialize_chat_engine(self, engine_config, app, demo, rtc_container):
        """初始化ChatEngine和AI LLM配置"""
        try:
            # 提取LLM配置用于直接API调用
            if engine_config and hasattr(engine_config, 'handler_configs'):
                logger.info(f"Found handler_configs: {list(engine_config.handler_configs.keys())}")
                for handler_name, handler_config in engine_config.handler_configs.items():
                    logger.info(f"Checking handler: {handler_name}, enabled: {handler_config.get('enabled', False)}")
                    if 'LLM' in handler_name and handler_config.get('enabled', False):
                        self.llm_config = handler_config
                        self.use_real_ai = True
                        logger.info(f"✅ Real AI LLM configured successfully: {handler_name}")
                        logger.info(f"LLM Config: model={handler_config.get('model_name')}, api_url={handler_config.get('api_url')}")
                        break
                else:
                    logger.warning("No enabled LLM handler found in config")
            else:
                logger.warning("No handler_configs found in engine config")
            
            # 强制启用Real AI（用于教学平台）
            if not self.use_real_ai:
                logger.info("🔧 Force enabling Real AI for teaching platform")
                # 尝试使用环境变量API密钥
                api_key = os.getenv('DASHSCOPE_API_KEY')
                if api_key:
                    self.llm_config = {
                        'model_name': 'qwen-vl-plus',
                        'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                        'api_key': api_key,
                        'enabled': True
                    }
                    self.use_real_ai = True
                    logger.info("✅ Real AI enabled with environment API key")
                else:
                    logger.warning("❌ No DASHSCOPE_API_KEY found, using fallback content")
            
            # 尝试初始化ChatEngine（用于WebRTC等功能）
            try:
                if engine_config:
                    self.chat_engine = ChatEngine()
                    self.chat_engine.initialize(engine_config, app=app, ui=demo, parent_block=rtc_container)
                    logger.info("ChatEngine initialized successfully with WebRTC container")
                    
                    # 设置学员消息监听器
                    self._setup_student_message_listener()
                else:
                    logger.warning("No engine_config found, using AI LLM only")
            except Exception as chat_engine_error:
                logger.warning(f"ChatEngine initialization failed: {chat_engine_error}, using AI LLM only")
                
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ChatEngine: {e}")
            # 记录最终的AI状态
            self.log_ai_status()
            return self.use_real_ai
    
    def log_ai_status(self):
        """记录AI配置状态"""
        logger.info("=" * 50)
        logger.info("🤖 AI Teaching Configuration Status")
        logger.info("=" * 50)
        logger.info(f"Real AI Enabled: {'✅ YES' if self.use_real_ai else '❌ NO'}")
        
        if self.use_real_ai and self.llm_config:
            logger.info(f"Model: {self.llm_config.get('model_name', 'Unknown')}")
            logger.info(f"API URL: {self.llm_config.get('api_url', 'Unknown')}")
            api_key = os.getenv('DASHSCOPE_API_KEY') or self.llm_config.get('api_key', '')
            logger.info(f"API Key: {'✅ Configured' if api_key else '❌ Missing'}")
            logger.info("📝 Teaching content will be generated by AI LLM")
        else:
            logger.info("📝 Teaching content will use fallback fixed templates")
            
        logger.info("=" * 50)
    
    def force_enable_real_ai(self):
        """强制启用Real AI（调试用）"""
        api_key = os.getenv('DASHSCOPE_API_KEY')
        if api_key:
            self.llm_config = {
                'model_name': 'qwen-vl-plus',
                'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                'api_key': api_key,
                'enabled': True
            }
            self.use_real_ai = True
            logger.info("🔧 Force enabled Real AI with environment API key")
            self.log_ai_status()
            return True
        else:
            logger.error("❌ Cannot force enable Real AI: DASHSCOPE_API_KEY not found")
            return False
    
    def initialize_auth(self):
        """初始化用户认证系统"""
        try:
            from src.auth.user_auth import auth_manager
            self.auth_manager = auth_manager
            logger.info("User authentication system initialized")
            return True
        except ImportError as e:
            logger.warning(f"Auth system not available: {e}")
            self.require_auth = False
            return False
    
    def get_current_user_info(self) -> Dict:
        """获取当前用户信息"""
        if not self.auth_manager or not self.auth_manager.is_authenticated():
            return {"username": "游客", "role": "guest", "authenticated": False}
        
        user_data = self.auth_manager.get_current_user()
        return {
            "username": user_data.get('username', '用户'),
            "role": user_data.get('role', 'student'),
            "authenticated": True,
            "display_name": self.auth_manager.get_user_display_name()
        }
    
    def check_auth_required(self, action: str = "learning") -> bool:
        """检查是否需要认证才能执行指定操作"""
        if not self.require_auth:
            return True
        
        if not self.auth_manager:
            return False
            
        return self.auth_manager.is_authenticated()
    
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
            if not os.path.exists(log_file_path):
                os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
                with open(log_file_path, 'w') as f:
                    pass
            
            with open(log_file_path, 'r', encoding='utf-8') as file:
                file.seek(0, 2)
                current_position = file.tell()
            
            while self.log_monitor_running:
                try:
                    with open(log_file_path, 'r', encoding='utf-8') as file:
                        file.seek(current_position)
                        
                        for line in file:
                            line = line.strip()
                            
                            if not line or 'monitor_chat_logs' in line:
                                continue
                            
                            # 检查LLM输入 (用户说话)
                            if 'llm input' in line:
                                user_text = self._extract_llm_input(line)
                                if user_text:
                                    self._add_real_chat_message('human', user_text.strip())
                                    self._handle_webrtc_connection()
                            
                            # 检查AI回复 (current sentence)
                            elif 'current sentence' in line:
                                ai_text = self._extract_current_sentence(line)
                                if ai_text:
                                    self._add_real_chat_message('avatar', ai_text.strip())
                                    
                            # 检查avatar启动事件
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
                        
                        current_position = file.tell()
                    
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
            llm_input_index = line.find('llm input')
            if llm_input_index != -1:
                text_part = line[llm_input_index + len('llm input'):].strip()
                words = text_part.split()
                if len(words) > 1:
                    user_text = ' '.join(words[1:])
                    if user_text and len(user_text.strip()) > 0:
                        return user_text
        except Exception:
            pass
        return None
    
    def _extract_current_sentence(self, line: str) -> Optional[str]:
        """从日志行中提取AI回复文本"""
        try:
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
        
        cleaned_content = self._clean_message_content(content)
        logger.debug(f"🔍 Cleaned content: '{cleaned_content}'")
        
        if not cleaned_content or len(cleaned_content.strip()) < 1:
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
                'role': role,
                'content': cleaned_content.strip(),
                'timestamp': time.time()
            }
            self.real_chat_queue.put(message)
            logger.info(f"✅ Added real chat message - {role}: {cleaned_content[:50]}...")
            
            self.message_update_trigger += 1
            logger.debug(f"🔄 Message update trigger incremented to {self.message_update_trigger}")
            
            # 保存到数据库
            db_message = {
                "role": role,
                "content": cleaned_content.strip(),
                "timestamp": message['timestamp'],
                "type": "proactive" if role == "avatar" else "normal"
            }
            self._save_message_to_database(db_message)
            
            # 如果是AI主动消息，立即触发前端更新
            if role == "avatar" and self.frontend_update_callback:
                try:
                    self.frontend_update_callback()
                    logger.debug("🔄 AI message triggered immediate frontend update")
                except Exception as e:
                    logger.error(f"Frontend update error: {e}")
            else:
                logger.debug("🔄 Message added to queue, frontend will auto-refresh")
            
            return True
        else:
            logger.debug(f"🔍 Duplicate message found, skipping")
        
        return False
    
    def _clean_message_content(self, content: str) -> str:
        """清理消息内容，确保只返回纯文本"""
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
        """获取所有对话消息（包括队列和列表中的）"""
        all_messages = []
        
        # 获取队列中的消息（不清空队列）
        temp_messages = []
        while not self.real_chat_queue.empty():
            try:
                msg = self.real_chat_queue.get_nowait()
                temp_messages.append(msg)
            except queue.Empty:
                break
        
        # 把消息放回队列
        for msg in temp_messages:
            self.real_chat_queue.put(msg)
        
        # 合并列表中的消息和队列中的消息
        all_messages.extend(self.real_chat_messages)
        all_messages.extend(temp_messages)
        
        # 按时间戳排序（如果有的话）
        all_messages.sort(key=lambda x: x.get('timestamp', 0))
        
        logger.debug(f"🔍 Total chat messages: {len(all_messages)} (list: {len(self.real_chat_messages)}, queue: {len(temp_messages)})")
        
        return all_messages
    
    def clear_chat_messages(self):
        """清空对话消息队列和列表"""
        while not self.real_chat_queue.empty():
            try:
                self.real_chat_queue.get_nowait()
            except queue.Empty:
                break
        
        # 同时清空消息列表
        self.real_chat_messages.clear()
        logger.info("✅ All chat messages cleared")
    
    def call_llm_api(self, messages: List[Dict], temperature: float = 0.7) -> Optional[str]:
        """调用真实的AI LLM API"""
        if not self.use_real_ai or not self.llm_config:
            logger.warning("Real AI not enabled or no LLM config")
            return None
            
        try:
            api_base = self.llm_config.get('api_url', '')
            api_key = os.getenv('DASHSCOPE_API_KEY') or self.llm_config.get('api_key', '')
            model = self.llm_config.get('model_name', 'qwen-vl-plus')
            
            # 调试信息
            logger.debug(f"LLM API Call - Model: {model}, API Base: {api_base}")
            logger.debug(f"API Key configured: {'Yes' if api_key else 'No'}")
            logger.debug(f"Messages count: {len(messages)}")
            
            if not api_key or api_key == '${DASHSCOPE_API_KEY}':
                logger.error("❌ API key not configured properly! Please set DASHSCOPE_API_KEY environment variable")
                return None
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # 转换消息格式
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
            logger.info("WebRTC connection established - audio stream ready")
            # WebRTC连接建立，但问候已在Avatar就绪时启动
    
    def _handle_avatar_start(self):
        """处理Avatar处理器启动事件"""
        logger.info("Avatar processor started, waiting for WebRTC connection")
        # 不再在这里启动问候，等待WebRTC连接
        
    def _handle_avatar_ready(self):
        """处理Avatar处理器完全就绪事件"""
        logger.info("Avatar processor is fully ready, starting AI greeting")
        # Avatar就绪后立即开始AI问候（此时TTS应该可以工作）
        if self.current_course and not self.has_greeted:
            timer = threading.Timer(3.0, self._start_ai_greeting)
            self._add_timer(timer)
            timer.start()
            logger.info("🎯 AI greeting timer started (3 seconds after Avatar ready)")
    
    def _start_proactive_teaching(self):
        """开始主动教学内容讲授"""
        logger.info(f"🎯 _start_proactive_teaching called - course: {self.current_course}, teaching_active: {self.teaching_active}")
        if not self.current_course or not self.teaching_active:
            logger.warning(f"❌ Proactive teaching blocked - course: {self.current_course}, teaching_active: {self.teaching_active}")
            return
            
        teaching_content = self._generate_teaching_content()
        
        logger.info(f"🎓 AI Teacher Starting Lesson: {teaching_content[:50]}...")
        
        # AI主动教学内容仅走显示+TTS路径，不触发LLM
        success = self._add_real_chat_message('avatar', teaching_content)
        
        # 发送教学内容和TTS
        if success:
            tts_success = self._send_to_tts_only(teaching_content)
            if tts_success:
                logger.info("✅ AI proactive teaching content with TTS sent successfully")
            else:
                logger.warning("TTS failed for teaching content, but text message sent successfully")
        else:
            logger.info("Teaching message was duplicate, skipping TTS")
            
        # 无论TTS是否成功，都继续定期发送教学内容 (30-45秒间隔)
        if self.teaching_active:
            next_delay = random.uniform(30.0, 45.0)
            timer = threading.Timer(next_delay, self._continue_teaching)
            self._add_timer(timer)
            timer.start()
            logger.info(f"🎓 Next teaching content scheduled in {next_delay:.1f} seconds")
        
    def _continue_teaching(self):
        """继续教学内容"""
        if not self.current_course or not self.teaching_active:
            return
            
        next_content = self._generate_next_teaching_content()
        
        if next_content:
            logger.info(f"🎓 AI Teacher Continue: {next_content[:50]}...")
            
            success = self._add_real_chat_message('avatar', next_content)
            
            # 发送教学内容和TTS
            if success:
                tts_success = self._send_to_tts_only(next_content)
                if tts_success:
                    logger.info("✅ AI continue teaching content with TTS sent successfully")
                else:
                    logger.warning("TTS failed for continue teaching content, but text message sent successfully")
            else:
                logger.info("Message was duplicate, skipping TTS")
                
        # 无论如何都继续循环教学 (30-45秒间隔)
        if self.teaching_active:
            next_delay = random.uniform(30.0, 45.0)
            timer = threading.Timer(next_delay, self._continue_teaching)
            self._add_timer(timer)
            timer.start()
            logger.info(f"🎓 Next continue teaching scheduled in {next_delay:.1f} seconds")
    
    def _generate_teaching_content(self) -> str:
        """使用LLM生成教学内容"""
        # 如果有真实AI，使用LLM生成教学内容
        if self.use_real_ai:
            course = self.current_course or "雅思英语"
            difficulty = self.current_difficulty or "初级"
            goal = self.current_goal or ""
            
            # 构建教学内容生成的系统提示
            system_prompt = f"""你是一位专业的AI雅思英语教师，名叫小慧老师。请生成第一段主动教学内容。

要求：
1. 用专业但亲切的语气
2. 针对具体课程提供实用的知识点
3. 根据难度级别调整内容深度
4. 包含一个启发式的问题引导学生思考
5. 体现雅思考试的实用性
6. 保持简洁，每次不超过3句话

直接生成教学内容，不要加解释。"""
            
            # 构建用户请求
            user_request = f"请为'{course}'课程（{difficulty}难度）生成开场教学内容。学习目标：{goal if goal else '提高雅思成绩'}"
            
            # 添加对话历史上下文
            if hasattr(self, 'real_chat_messages') and self.real_chat_messages:
                recent_messages = self.real_chat_messages[-3:] if len(self.real_chat_messages) > 3 else self.real_chat_messages
                context = "之前的对话内容：\n"
                for msg in recent_messages:
                    context += f"- {msg.get('role', 'unknown')}: {msg.get('content', '')[:50]}...\n"
                user_request += f"\n\n{context}\n请基于以上对话历史，生成接下来的教学内容。"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request}
            ]
            
            ai_content = self.call_llm_api(messages, temperature=0.7)
            if ai_content:
                logger.info("Generated AI teaching content successfully")
                return ai_content
            else:
                logger.warning("Failed to generate AI teaching content, using fallback")
        
        # 回退到基础的教学内容
        course = self.current_course or "雅思"
        difficulty = self.current_difficulty or "初级"
        
        fallback_contents = [
            f"现在让我们开始{course}的学习。这是一个很重要的知识点，你有什么想了解的吗？",
            f"在{difficulty}级别的学习中，我们要掌握一些基础概念。你准备好了吗？",
            f"让我为你介绍{course}的核心内容。有什么问题可以随时提出来。"
        ]
        
        import random
        return random.choice(fallback_contents)
    
    def _generate_next_teaching_content(self) -> str:
        """使用LLM生成下一段教学内容"""
        # 如果有真实AI，使用LLM生成持续教学内容
        if self.use_real_ai:
            course = self.current_course or "雅思英语"
            difficulty = self.current_difficulty or "初级"
            
            # 递增教学步骤用于上下文
            self.teaching_step += 1
            
            # 构建持续教学的系统提示
            system_prompt = f"""你是一位专业的AI雅思英语教师，名叫小慧老师。请生成持续教学内容。

教学要求：
1. 用亲切、专业的语气
2. 提供具体的知识点或技巧
3. 根据难度调整内容
4. 包含互动性问题或练习建议
5. 体现雅思考试的实用性
6. 保持简洁，2-3句话即可
7. 与之前内容有所递进，避免重复

请根据教学步骤生成相应内容：
- 第1-2轮：介绍核心概念
- 第3-4轮：提供练习和互动
- 第5-6轮：深入技巧和应用
- 第7轮以上：总结复习和新话题

直接生成教学内容，不要加解释。"""
            
            # 构建用户请求
            user_request = f"请为'{course}'课程（{difficulty}难度）生成第{self.teaching_step}轮持续教学内容。"
            
            # 添加对话历史上下文
            if hasattr(self, 'real_chat_messages') and self.real_chat_messages:
                recent_messages = self.real_chat_messages[-5:] if len(self.real_chat_messages) > 5 else self.real_chat_messages
                context = "最近的对话内容：\n"
                for msg in recent_messages:
                    if msg.get('role') in ['avatar', 'human']:
                        role_name = '老师' if msg.get('role') == 'avatar' else '学生'
                        context += f"- {role_name}: {msg.get('content', '')[:80]}...\n"
                user_request += f"\n\n{context}\n请基于以上对话，生成有针对性的下一段教学内容。"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request}
            ]
            
            ai_content = self.call_llm_api(messages, temperature=0.8)
            if ai_content:
                logger.info(f"Generated AI next teaching content (step {self.teaching_step})")
                return ai_content
            else:
                logger.warning("Failed to generate AI next teaching content, using fallback")
        
        # 回退到简化的步骤式内容
        course = self.current_course or "雅思"
        self.teaching_step += 1
        
        if self.teaching_step <= 2:
            content = f"让我为你介绍{course}的一个重要概念。你有什么想特别了解的吗？"
        elif self.teaching_step <= 4:
            content = "我们来做个小练习吧。这样能帮助你更好地掌握刚才的内容。"
        elif self.teaching_step <= 6:
            content = "很好！现在让我分享一些实用的雅思应试技巧。"
        else:
            # 重置步骤
            self.teaching_step = 1
            content = "我们已经学了不少内容了。有什么问题想问吗？或者继续学习新的知识点？"
        
        return content
    
    def set_current_session_info(self, course: str, difficulty: str, goal: str):
        """设置当前学习会话信息"""
        # 先停止之前的教学活动
        self._stop_ai_teaching()
        
        # 设置新的会话信息
        self.current_course = course
        self.current_difficulty = difficulty
        self.current_goal = goal
        self.has_greeted = False
        self.webrtc_connected = False
        self.teaching_active = False
        self.used_teaching_contents.clear()  # 清空已使用内容
        self.teaching_step = 0  # 重置教学步骤
        
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
        
        # 立即显示准备就绪提示，等待用户点击Record后再问候
        logger.info("🎯 Showing ready prompt, waiting for WebRTC connection for AI greeting")
        ready_prompt = "您的专属AI教师已经准备就绪，请点击获取摄像头权限然后点击record后进行学习。"
        self._add_real_chat_message('system', ready_prompt)
        logger.info(f"📝 Ready prompt displayed: {ready_prompt}")
    
    def _start_ai_greeting(self):
        """AI主动问候学生"""
        if not self.current_course or self.has_greeted:
            logger.debug(f"🔍 Greeting skipped - course: {self.current_course}, greeted: {self.has_greeted}")
            return
        
        # 防止重复问候的双重检查
        if self.has_greeted:
            logger.debug("🔍 Already greeted, skipping duplicate greeting")
            return
            
        # 先设置已问候状态，防止并发调用
        self.has_greeted = True
        
        # 生成个性化问候内容
        greeting = self._generate_greeting_content()
        
        logger.info(f"🤖 AI Teacher Greeting: {greeting[:50]}...")
        
        # 发送问候消息
        success = self._add_real_chat_message('avatar', greeting)
        
        # 只有在消息成功添加时才启动教学流程
        if success:
            # 尝试发送TTS，但不依赖TTS成功
            tts_success = self._send_to_tts_only(greeting)
            if tts_success:
                logger.info("✅ AI greeting with TTS sent successfully")
            else:
                logger.warning("AI greeting TTS failed, but text message sent successfully")
            
            # 无论TTS是否成功，都启动主动教学
            self.teaching_active = True
            
            # 15秒后开始主动教学
            teaching_timer = threading.Timer(15.0, self._start_proactive_teaching)
            self._add_timer(teaching_timer)
            teaching_timer.start()
            logger.info("🎓 Main teaching timer started (15 seconds)")
        else:
            logger.info("Greeting message was duplicate, skipping TTS")
    
    def _generate_greeting_content(self) -> str:
        """使用LLM生成个性化问候内容"""
        # 如果有真实AI，使用LLM生成个性化问候
        if self.use_real_ai:
            course = self.current_course or "雅思英语"
            difficulty = self.current_difficulty or "初级"
            goal = self.current_goal or ""
            
            # 构建问候生成的系统提示
            system_prompt = f"""你是一位专业的AI雅思英语教师，名叫小慧老师。请用亲切、热情的语气生成个性化问候。

要求：
1. 介绍自己是小慧老师
2. 提到具体的课程和难度
3. 如果有学习目标，要体现对目标的关注
4. 表达对开始教学的期待
5. 保持简洁，2-3句话即可

直接生成问候内容，不要加任何解释。"""
            
            user_prompt = f"请为选择了'{course}'课程（{difficulty}难度）的新学生生成个性化问候。学习目标：{goal if goal else '未指定'}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            ai_greeting = self.call_llm_api(messages, temperature=0.8)
            if ai_greeting:
                logger.info("Generated AI greeting successfully")
                return ai_greeting
            else:
                logger.warning("Failed to generate AI greeting, using fallback")
        
        # 回退到简化的固定问候
        course = self.current_course or "课程"
        difficulty = self.current_difficulty or "难度"
        goal = self.current_goal or ""
        
        fallback_greeting = f"你好！我是小慧老师，欢迎来到{course}的学习！我会根据{difficulty}难度为你提供个性化指导。"
        if goal and goal.strip():
            fallback_greeting += f"我注意到你的目标是：{goal}，我们一起努力实现它！"
        fallback_greeting += "准备好开始学习了吗？"
        
        return fallback_greeting

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
                    continue
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
        
        # 回退到基于规则的回复
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
        
        # 基于课程内容的回复
        elif contains_keyword:
            examples = current_course["examples"]
            if examples:
                example = random.choice(examples)
                return f"很好的问题！关于{student_message}，让我来详细解释。例如：{example}。您觉得这样理解对吗？"
            return f"这是{course}中的重要概念。让我为您详细分析一下这个雅思知识点..."
        
        # 通用回复
        else:
            responses = [
                f"我明白您的意思。在{course}的学习中，这个问题很常见。",
                f"让我们一起来分析您提到的'{student_message}'这个雅思相关的内容。",
                f"根据{difficulty}难度，我来为您详细解释一下这个雅思概念。"
            ]
            
            teaching_tips = [
                "您还有其他雅思相关的疑问吗？",
                "要不要我出个相关的雅思练习题？",
                "我们可以通过实际的雅思例子来加深理解。"
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
    
    def _stop_ai_teaching(self):
        """停止AI教学活动"""
        logger.info("🛑 Stopping AI teaching activities...")
        
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
        self.active_timers = [t for t in self.active_timers if t.is_alive()]
    
    def set_frontend_update_callback(self, callback_func):
        """设置前端更新回调函数"""
        self.frontend_update_callback = callback_func
    
    
    def _setup_student_message_listener(self):
        """设置学员消息监听器"""
        try:
            # 方法1: 直接从ChatEngine获取消息 (推荐)
            if hasattr(self, 'chat_engine') and self.chat_engine:
                self._setup_chatengine_message_listener()
            
            # 方法2: 通过日志文件监听 (备用)
            self.last_asr_check_time = time.time()
            self.student_message_listener_active = True
            
            # 启动学员消息监听线程
            if not hasattr(self, 'student_listener_thread') or not self.student_listener_thread.is_alive():
                self.student_listener_thread = threading.Thread(target=self._student_message_listener_loop, daemon=True)
                self.student_listener_thread.start()
                logger.info("🎧 Student message listener started")
        except Exception as e:
            logger.error(f"Failed to setup student message listener: {e}")
    
    def _setup_chatengine_message_listener(self):
        """设置ChatEngine消息监听器"""
        try:
            # 创建一个模拟会话来监听ASR输出
            from chat_engine.data_models.session_info_data import SessionInfoData
            from chat_engine.data_models.chat_data_type import ChatDataType
            import queue
            
            session_info = SessionInfoData(session_id="student_listener")
            
            # 创建输出队列来接收ASR结果
            output_queues = {
                ChatDataType.TEXT: queue.Queue()  # 接收ASR文本输出
            }
            
            # 创建监听会话
            session = self.chat_engine._create_session(session_info, {}, output_queues)
            
            # 启动监听线程
            listener_thread = threading.Thread(target=self._chatengine_message_listener, 
                                             args=(output_queues[ChatDataType.TEXT],), daemon=True)
            listener_thread.start()
            
            logger.info("✅ ChatEngine message listener setup completed")
            
        except Exception as e:
            logger.warning(f"ChatEngine message listener setup failed: {e}, falling back to log monitoring")
    
    def _chatengine_message_listener(self, text_queue):
        """ChatEngine消息监听器"""
        while getattr(self, 'student_message_listener_active', False):
            try:
                if not text_queue.empty():
                    chat_data = text_queue.get_nowait()
                    if hasattr(chat_data, 'data') and hasattr(chat_data.data, 'text'):
                        student_text = chat_data.data.text.strip()
                        if student_text:
                            logger.info(f"🎧 ChatEngine captured student message: {student_text}")
                            self._process_student_message(student_text)
                time.sleep(0.1)  # 100ms检查间隔
            except Exception as e:
                logger.debug(f"ChatEngine message listener error: {e}")
                time.sleep(1)
    
    def _student_message_listener_loop(self):
        """学员消息监听循环"""
        while getattr(self, 'student_message_listener_active', False):
            try:
                # 检查最近的ASR输出
                self._check_recent_asr_output()
                time.sleep(1)  # 每秒检查一次
            except Exception as e:
                logger.error(f"Error in student message listener: {e}")
                time.sleep(5)
    
    def _check_recent_asr_output(self):
        """检查最近的ASR输出"""
        try:
            log_file = "/home/OpenAvatarChat/logs/teaching_platform.log"
            if not os.path.exists(log_file):
                return
                
            # 读取最近的日志行
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, 2)  # 移到文件末尾
                file_size = f.tell()
                
                # 只读取最后1000个字符
                start_pos = max(0, file_size - 1000)
                f.seek(start_pos)
                lines = f.readlines()
                
                # 查找ASR输出
                for line in lines:
                    if 'ASR text:' in line or 'Recognized:' in line:
                        # 提取学员说的话
                        if 'ASR text:' in line:
                            parts = line.split('ASR text:')
                            if len(parts) > 1:
                                student_text = parts[1].strip()
                                self._process_student_message(student_text)
                        elif 'Recognized:' in line:
                            parts = line.split('Recognized:')
                            if len(parts) > 1:
                                student_text = parts[1].strip()
                                self._process_student_message(student_text)
        except Exception as e:
            logger.debug(f"Error checking ASR output: {e}")
    
    def _process_student_message(self, text: str):
        """处理学员消息"""
        try:
            if len(text.strip()) < 2:
                return
                
            # 清理文本
            cleaned_text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text.strip())
            if len(cleaned_text) < 2:
                return
                
            logger.info(f"🧑‍🎓 Student said: {cleaned_text}")
            
            # 添加到对话历史
            success = self._add_real_chat_message('human', cleaned_text)
            if success:
                logger.info("✅ Student message added to chat history")
                
                # 生成AI教师回复
                ai_response = self._generate_ai_response_to_student(cleaned_text)
                if ai_response:
                    logger.info(f"🤖 AI Teacher Response: {ai_response[:50]}...")
                    
                    # 添加AI回复到聊天历史
                    response_success = self._add_real_chat_message('avatar', ai_response)
                    if response_success:
                        # 发送AI回复的TTS
                        self._send_to_tts_only(ai_response)
                        logger.info("✅ AI response to student sent successfully")
                
                # 触发前端更新
                if self.frontend_update_callback:
                    try:
                        self.frontend_update_callback()
                    except:
                        pass
            else:
                logger.debug("Student message was duplicate, skipping")
                
        except Exception as e:
            logger.error(f"Error processing student message: {e}")
    
    def _generate_ai_response_to_student(self, student_message: str) -> str:
        """生成AI教师对学员打断的回复"""
        try:
            if not self.use_real_ai:
                # 如果没有AI，使用简单回复
                return f"我理解您的问题：'{student_message}'。让我继续为您详细讲解相关内容。"
            
            # 构建系统提示
            course = self.current_course or "雅思英语"
            difficulty = self.current_difficulty or "初级"
            
            system_prompt = f"""你是一位专业的AI雅思英语教师，名叫小慧老师。学生刚刚打断了你的教学并说："{student_message}"

教学环境：
- 课程：{course}
- 难度：{difficulty}
- 当前在进行主动教学

请你：
1. 针对学生的话语给出恰当的回应
2. 保持亲切、耐心的教学语气
3. 如果是问题，请详细解答
4. 如果是评论，请给予鼓励和引导
5. 回答控制在2-3句话内
6. 然后自然地表示将继续教学

直接回复学生，不要重复学生的话。"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": student_message}
            ]
            
            # 调用LLM API
            ai_response = self.call_llm_api(messages, temperature=0.7)
            
            if ai_response:
                return ai_response
            else:
                logger.warning("Failed to generate AI response to student, using fallback")
                return f"谢谢您的问题！关于'{student_message}'，这确实是{course}中很重要的一个点，让我详细为您解释一下。"
                
        except Exception as e:
            logger.error(f"Error generating AI response to student: {e}")
            return f"我明白您的意思。让我针对您提到的内容继续为您讲解。"
    
    def _send_to_tts_only(self, text: str) -> bool:
        """仅发送到TTS管道，不触发LLM"""
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
            
            # 仅发送AVATAR_TEXT数据到TTS，不通过TEXT通道
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
                
        except Exception as e:
            logger.warning(f"Failed to send avatar text to TTS: {e}")
    
    # 数据存储方法
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
        # 临时禁用数据库存储，避免外键约束问题
        logger.info("Database session creation temporarily disabled")
        
        # 生成临时会话key用于内存管理
        import secrets
        session_key = f"session_{secrets.token_hex(16)}"
        self.current_session_key = session_key
        logger.info(f"Memory session created: {session_key}")
        return session_key
    
    def stop_log_monitor(self):
        """停止日志监听"""
        self.log_monitor_running = False
        if self.log_monitor_thread:
            self.log_monitor_thread.join(timeout=1)
        logger.info("Log monitor stopped")


# 全局后端实例
teaching_backend = TeachingBackend()