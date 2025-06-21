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
        
        # AI LLM配置
        self.llm_config = None
        self.use_real_ai = False
        
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
                    self.chat_engine.initialize(engine_config, app, demo, rtc_container)
                    logger.info("ChatEngine initialized successfully")
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
                            
                            # 检查AI回复 (current sentence)
                            elif 'current sentence' in line:
                                ai_text = self._extract_current_sentence(line)
                                if ai_text:
                                    self._add_real_chat_message('avatar', ai_text.strip())
                        
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
        # 清理内容格式
        cleaned_content = self._clean_message_content(content)
        
        if not cleaned_content or len(cleaned_content.strip()) < 2:
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
            return True
        
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
    
    def create_learning_session(self, course: str, difficulty: str, goal: str) -> Dict:
        """创建学习会话"""
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
        
        return {
            "course": course,
            "difficulty": difficulty,
            "goal": goal,
            "system_prompt": system_prompt,
            "welcome_message": welcome_message,
            "chat_history": initial_history
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


# 全局后端实例
teaching_backend = TeachingBackend() 