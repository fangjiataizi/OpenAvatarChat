import os
import time
import asyncio
import uuid
import json
from typing import Dict, Optional, List, Any
from loguru import logger
from pydantic import BaseModel, Field
from abc import ABC
import tempfile
import shutil

from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo, HandlerDataInfo, HandlerDetail
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.runtime_data.data_bundle import DataBundle, DataBundleDefinition, DataBundleEntry

# 导入新闻处理器的各个组件
from src.handlers.news.script_generator.news_script_handler import HandlerNewsScript, NewsScriptConfig
from src.handlers.news.voice_synthesizer.news_voice_handler import HandlerNewsVoice, NewsVoiceConfig
from src.handlers.news.avatar_renderer.news_avatar_handler import HandlerNewsAvatar, NewsAvatarConfig


class VideoQualityOption(BaseModel):
    name: str
    resolution: str
    bitrate: str
    fps: int


class NewsVideoConfig(HandlerBaseConfigModel, BaseModel):
    enabled: bool = Field(default=True)
    output_formats: List[str] = Field(default_factory=lambda: ["mp4", "webm", "avi"])
    quality_options: List[VideoQualityOption] = Field(default_factory=list)


class NewsVideoContext(HandlerContext):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.config = None
        self.job_id = str(uuid.uuid4())
        self.processing_status = "idle"  # idle, script_generating, voice_synthesizing, avatar_rendering, video_encoding, completed, error
        self.progress = 0

        # 各组件处理器
        self.script_handler = None
        self.voice_handler = None
        self.avatar_handler = None

        # 生成的内容
        self.generated_script = ""
        self.generated_audio = None
        self.generated_video = None

        # 元数据
        self.metadata = {}
        self.start_time = None
        self.end_time = None

        # 输出路径
        self.output_dir = ""
        self.final_video_path = ""


class HandlerNewsVideo(HandlerBase, ABC):
    def __init__(self):
        super().__init__()
        self.output_formats = ["mp4", "webm", "avi"]
        self.quality_options = []
        self.script_handler = None
        self.voice_handler = None
        self.avatar_handler = None

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            name="VideoGenerator",
            display_name="新闻视频生成器",
            description="整合脚本生成、语音合成和数字人渲染，生成完整的新闻播报视频",
            version="1.0.0",
            author="News Broadcast Team"
        )

    def get_handler_detail(self) -> HandlerDetail:
        return HandlerDetail(
            input_data_types=[ChatDataType.HUMAN_TEXT],
            output_data_types=[ChatDataType.AVATAR_VIDEO],
            consume_mode=ChatDataConsumeMode.SINGLE
        )

    def get_handler_data_info(self) -> HandlerDataInfo:
        return HandlerDataInfo(
            input_descriptions=["新闻内容文本"],
            output_descriptions=["生成的新闻播报视频文件"]
        )

    def create_context(self, session_id: str) -> NewsVideoContext:
        return NewsVideoContext(session_id)

    def init_handler(self, handler_config: NewsVideoConfig, chat_engine_config: ChatEngineConfigModel):
        logger.info("初始化新闻视频生成处理器")
        self.output_formats = handler_config.output_formats
        self.quality_options = handler_config.quality_options

        # 初始化各组件处理器
        self._init_component_handlers(chat_engine_config)

        logger.info("新闻视频生成处理器初始化完成")

    def _init_component_handlers(self, chat_engine_config: ChatEngineConfigModel):
        """初始化各个组件处理器"""
        try:
            # 脚本生成器配置
            script_config = NewsScriptConfig(
                enabled=True,
                llm_options=[
                    {
                        "name": "qwen-plus",
                        "provider": "bailian",
                        "model_name": "qwen-plus",
                        "system_prompt": "你是一位专业的新闻播报员脚本撰写专家...",
                        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        "api_key": os.getenv("DASHSCOPE_API_KEY", "")
                    }
                ]
            )
            self.script_handler = HandlerNewsScript()
            self.script_handler.init_handler(script_config, chat_engine_config)

            # 语音合成器配置
            voice_config = NewsVoiceConfig(
                enabled=True,
                tts_options=[
                    {
                        "name": "xiaoxiao_zh",
                        "provider": "edge_tts",
                        "voice": "zh-CN-XiaoxiaoNeural",
                        "sample_rate": 24000,
                        "description": "晓晓-中文女声"
                    }
                ]
            )
            self.voice_handler = HandlerNewsVoice()
            self.voice_handler.init_handler(voice_config, chat_engine_config)

            # 数字人渲染器配置 - 从配置文件读取
            avatar_config_data = {
                "enabled": True,
                "avatar_options": [
                    {
                        "name": "xiaohui_teacher",
                        "provider": "liteavatar",
                        "avatar_name": "sample_data",
                        "fps": 25,
                        "use_gpu": True,
                        "description": "小慧老师-教学风格"
                    },
                    {
                        "name": "news_anchor_female",
                        "provider": "liteavatar",
                        "avatar_name": "20250408/female_news_anchor",
                        "fps": 25,
                        "use_gpu": True,
                        "description": "女主播-新闻风格"
                    },
                    {
                        "name": "news_anchor_male",
                        "provider": "liteavatar",
                        "avatar_name": "20250408/male_news_anchor",
                        "fps": 25,
                        "use_gpu": True,
                        "description": "男主播-新闻风格"
                    },
                    {
                        "name": "muse_news_anchor",
                        "provider": "musetalk",
                        "fps": 20,
                        "avatar_name": "news_anchor",
                        "asset_path": "src/handlers/avatar/musetalk/MuseTalk/data/video/news_anchor.mp4",
                        "description": "MuseTalk新闻主播"
                    }
                ]
            }
            avatar_config = NewsAvatarConfig(**avatar_config_data)
            self.avatar_handler = HandlerNewsAvatar()
            self.avatar_handler.init_handler(avatar_config, chat_engine_config)

            logger.info("所有组件处理器初始化完成")

        except Exception as e:
            logger.error(f"组件处理器初始化失败: {str(e)}")

    async def generate_news_video(self, news_content: str, options: Dict[str, Any],
                                context: NewsVideoContext) -> Optional[str]:
        """生成完整的新闻视频"""
        try:
            context.start_time = time.time()
            context.processing_status = "script_generating"
            context.progress = 10

            logger.info(f"开始生成新闻视频，作业ID: {context.job_id}")

            # 1. 生成播报脚本
            logger.info("步骤1: 生成播报脚本")
            script_data = await self._generate_script(news_content, options, context)
            if not script_data:
                context.processing_status = "error"
                return None

            context.processing_status = "voice_synthesizing"
            context.progress = 30

            # 2. 合成语音
            logger.info("步骤2: 合成语音")
            audio_data = await self._synthesize_voice(script_data, options, context)
            if not audio_data:
                context.processing_status = "error"
                return None

            context.processing_status = "avatar_rendering"
            context.progress = 60

            # 3. 渲染数字人视频
            logger.info("步骤3: 渲染数字人视频")
            video_data = await self._render_avatar_video(audio_data, script_data, options, context)
            if not video_data:
                context.processing_status = "error"
                return None

            context.processing_status = "video_encoding"
            context.progress = 90

            # 4. 编码和保存最终视频
            logger.info("步骤4: 编码最终视频")
            final_video_path = await self._encode_final_video(video_data, options, context)

            if final_video_path:
                context.processing_status = "completed"
                context.progress = 100
                context.end_time = time.time()

                # 保存元数据
                context.metadata = {
                    "job_id": context.job_id,
                    "news_content": news_content,
                    "generated_script": context.generated_script,  # 添加完整的播报文稿
                    "generated_audio_path": getattr(context, 'generated_audio_path', None),  # 添加音频路径
                    "options": options,
                    "processing_time": context.end_time - context.start_time,
                    "script_length": len(context.generated_script),
                    "audio_size": len(context.generated_audio) if context.generated_audio else 0,
                    "video_size": len(context.generated_video) if context.generated_video else 0,
                    "final_video_path": final_video_path
                }

                logger.info(f"新闻视频生成完成: {final_video_path}")
                return final_video_path

            context.processing_status = "error"
            return None

        except Exception as e:
            logger.error(f"新闻视频生成失败: {str(e)}")
            context.processing_status = "error"
            return None

    async def _generate_script(self, news_content: str, options: Dict[str, Any],
                             context: NewsVideoContext) -> Optional[ChatData]:
        """生成播报脚本"""
        try:
            script_input = ChatData(
                type=ChatDataType.HUMAN_TEXT,
                data={
                    "text": news_content,
                    "category": options.get("category", "general"),
                    "style": options.get("style", "formal"),
                    "llm_provider": options.get("llm_provider", "qwen-plus")
                }
            )

            script_context = self.script_handler.create_context(context.session_id)
            script_result = self.script_handler.process_data(script_input, script_context)

            if script_result:
                context.generated_script = script_result.data.get("text", "")
                logger.info(f"脚本生成成功: {len(context.generated_script)} 字符")
                return script_result

            return None

        except Exception as e:
            logger.error(f"脚本生成失败: {str(e)}")
            return None

    async def _synthesize_voice(self, script_data: ChatData, options: Dict[str, Any],
                              context: NewsVideoContext) -> Optional[ChatData]:
        """合成语音"""
        try:
            voice_context = self.voice_handler.create_context(context.session_id)
            voice_result = self.voice_handler.process_data(script_data, voice_context)

            if voice_result:
                context.generated_audio = voice_result.data.get("audio", b"")
                # 保存TTS生成的音频文件路径
                audio_file_path = voice_result.data.get("file_path")
                if audio_file_path:
                    context.generated_audio_path = audio_file_path
                    logger.info(f"语音合成成功: {len(context.generated_audio)} bytes, 文件路径: {audio_file_path}")
                else:
                    logger.info(f"语音合成成功: {len(context.generated_audio)} bytes")
                return voice_result

            return None

        except Exception as e:
            logger.error(f"语音合成失败: {str(e)}")
            return None

    async def _render_avatar_video(self, audio_data: ChatData, script_data: ChatData,
                                 options: Dict[str, Any], context: NewsVideoContext) -> Optional[ChatData]:
        """渲染数字人视频"""
        try:
            # 合并音频数据和脚本数据  
            avatar_input_data = ChatData(
                type=ChatDataType.AVATAR_AUDIO,
                data={
                    **audio_data.data,
                    "script_text": script_data.data.get("text", ""),
                    "avatar_provider": options.get("avatar_provider", "xiaohui_teacher")
                }
            )

            avatar_context = self.avatar_handler.create_context(context.session_id)
            avatar_result = self.avatar_handler.process_data(avatar_input_data, avatar_context)

            if avatar_result:
                context.generated_video = avatar_result.data.get("video", b"")
                logger.info(f"数字人视频渲染成功: {len(context.generated_video)} bytes")
                return avatar_result

            return None

        except Exception as e:
            logger.error(f"数字人视频渲染失败: {str(e)}")
            return None

    async def _encode_final_video(self, video_data: ChatData, options: Dict[str, Any],
                                context: NewsVideoContext) -> Optional[str]:
        """编码最终视频文件"""
        try:
            # 创建输出目录
            output_dir = os.path.join("output", "news_videos", context.job_id)
            os.makedirs(output_dir, exist_ok=True)
            context.output_dir = output_dir

            # 确定输出格式和质量
            output_format = options.get("format", "mp4")
            quality = options.get("quality", "high")

            # 构建输出文件名
            timestamp = int(time.time())
            filename = f"news_broadcast_{timestamp}.{output_format}"
            output_path = os.path.join(output_dir, filename)

            # 保存视频文件
            video_bytes = video_data.data.get("video", b"")
            if video_bytes:
                with open(output_path, 'wb') as f:
                    f.write(video_bytes)

                # 保存元数据文件
                metadata_path = os.path.join(output_dir, f"metadata_{timestamp}.json")
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(context.metadata, f, ensure_ascii=False, indent=2)

                context.final_video_path = output_path
                logger.info(f"最终视频文件保存到: {output_path}")
                return output_path

            return None

        except Exception as e:
            logger.error(f"视频编码失败: {str(e)}")
            return None

    def process_data(self, data: ChatData, context: NewsVideoContext) -> Optional[ChatData]:
        """处理输入数据"""
        try:
            logger.info(f"视频处理器收到数据，类型: {data.type}, 数据: {data.data}")
            if data.type == ChatDataType.HUMAN_TEXT:
                news_content = data.data.get("text", "")
                options = data.data.get("options", {})

                if not news_content:
                    logger.error("输入新闻内容为空")
                    return None

                # 生成视频 - 优先使用简化的直接同步流程
                logger.info("开始生成新闻视频...")
                try:
                    # 直接使用工作正常的异步方法
                    video_path = self._generate_video_sync(news_content, options, context)

                    logger.info(f"视频生成完成，路径: {video_path}")
                except Exception as e:
                    logger.error(f"视频生成过程中出错: {str(e)}", exc_info=True)
                    video_path = None

                if video_path:
                    # 返回文件路径
                    try:
                        # 使用与其他地方相同的方式创建ChatData
                        output_data = ChatData()
                        output_data.type = ChatDataType.AVATAR_VIDEO
                        output_data.data = {
                            "file_path": video_path,
                            "file_type": "video",
                            "metadata": context.metadata,
                            "processing_status": context.processing_status,
                            "job_id": context.job_id
                        }
                        return output_data
                    except Exception as e:
                        logger.error(f"创建ChatData时出错: {str(e)}")
                        # 返回最简化版本
                        try:
                            output_data = ChatData()
                            output_data.type = ChatDataType.AVATAR_VIDEO  
                            output_data.data = {"file_path": video_path}
                            return output_data
                        except Exception as e2:
                            logger.error(f"创建简化ChatData时也出错: {str(e2)}")
                            return None

            return None

        except Exception as e:
            logger.error(f"新闻视频处理器处理数据失败: {str(e)}")
            context.processing_status = "error"
            return None

    def _generate_video_sync(self, news_content: str, options: Dict[str, Any], 
                           context: NewsVideoContext) -> Optional[str]:
        """使用线程池同步方式生成视频（完全避免事件循环冲突）"""
        try:
            import concurrent.futures
            import threading
            
            logger.info("使用线程池同步方式生成新闻视频")
            
            def run_async_in_thread():
                """在独立线程中运行异步任务"""
                try:
                    # 在新线程中创建新的事件循环
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            self.generate_news_video(news_content, options, context)
                        )
                    finally:
                        new_loop.close()
                except Exception as e:
                    logger.error(f"线程中异步执行失败: {str(e)}")
                    return None
            
            # 使用线程池执行异步任务
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_async_in_thread)
                    try:
                        # 设置超时时间为5分钟
                        video_path = future.result(timeout=300)
                        logger.info(f"线程池执行完成，视频路径: {video_path}")
                        return video_path
                    except concurrent.futures.TimeoutError:
                        logger.error("视频生成超时")
                        return None
                    except Exception as e:
                        logger.error(f"线程池执行失败: {str(e)}")
                        return None
            except RuntimeError as e:
                if "cannot schedule new futures after interpreter shutdown" in str(e) or "cannot schedule new futures after shutdown" in str(e):
                    logger.warning("应用正在关闭，无法启动新的线程池任务，尝试直接异步调用")
                    # 先尝试直接调用异步方法
                    try:
                        return self._run_async_generation(news_content, options, context)
                    except Exception as e2:
                        logger.error(f"直接异步调用失败: {str(e2)}")
                        return None
                else:
                    logger.error(f"线程池创建失败: {str(e)}，尝试直接异步调用")
                    try:
                        return self._run_async_generation(news_content, options, context)
                    except Exception as e2:
                        logger.error(f"直接异步调用失败: {str(e2)}")
                        return None
            
        except Exception as e:
            logger.error(f"同步视频生成失败: {str(e)}")
            return None

    def _run_async_generation(self, news_content: str, options: Dict[str, Any],
                             context: NewsVideoContext) -> Optional[str]:
        """在新线程中运行异步生成函数"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            video_path = loop.run_until_complete(self.generate_news_video(news_content, options, context))
            loop.close()
            return video_path
        except Exception as e:
            logger.error(f"异步生成失败: {str(e)}", exc_info=True)
            return None
    
    def _run_direct_async(self, news_content: str, options: Dict[str, Any],
                         context: NewsVideoContext) -> Optional[str]:
        """直接在当前线程运行异步生成函数（紧急fallback）"""
        try:
            logger.info("使用直接异步调用方式生成视频")
            # 尝试直接运行，不创建新的事件循环
            try:
                # 检查是否已经在异步上下文中
                current_loop = asyncio.get_running_loop()
                logger.error("检测到运行中的事件循环，无法继续")
                return None
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                logger.info("创建新的事件循环进行直接异步调用")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    video_path = loop.run_until_complete(self.generate_news_video(news_content, options, context))
                    return video_path
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"直接异步调用失败: {str(e)}")
            return None
    
    
    def _create_placeholder_mp4(self, video_path: str, news_content: str, options: Dict[str, Any]):
        """创建简单的MP4占位视频文件"""
        try:
            import cv2
            import numpy as np
            
            # 创建简单的视频（5秒，25fps）
            width, height = 640, 480
            fps = 25
            duration = 5  # 秒
            total_frames = fps * duration
            
            # 创建视频写入对象
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
            
            # 生成简单的渐变背景帧
            for frame_num in range(total_frames):
                # 创建渐变背景
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                
                # 添加渐变色彩
                intensity = int(255 * (frame_num / total_frames))
                frame[:, :] = [intensity % 255, (intensity * 2) % 255, (intensity * 3) % 255]
                
                # 添加文字 (使用OpenCV的putText)
                text = f"News Broadcast - Frame {frame_num}"
                cv2.putText(frame, text, (50, height//2), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.7, (255, 255, 255), 2)
                
                # 写入帧
                out.write(frame)
            
            # 释放资源
            out.release()
            logger.info(f"占位MP4视频创建完成: {video_path}")
            
        except Exception as e:
            logger.error(f"创建占位MP4视频失败: {str(e)}")
            # 不创建空文件，直接抛出异常
            raise

    def _generate_video_direct_sync(self, news_content: str, options: Dict[str, Any], 
                                   context: NewsVideoContext) -> Optional[str]:
        """完全同步的直接视频生成方法（集成所有组件）"""
        try:
            logger.info("使用完全同步直接生成方法（包含数字人和音频）")
            
            # 生成输出路径
            import os
            from datetime import datetime
            output_dir = os.path.join("output", "news_videos", context.job_id)
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = int(datetime.now().timestamp())
            video_filename = f"news_broadcast_{timestamp}.mp4"
            video_path = os.path.join(output_dir, video_filename)
            
            # 步骤1: 生成新闻脚本
            logger.info("第1步: 生成新闻播报脚本")
            script_data = ChatData(
                type=ChatDataType.HUMAN_TEXT,
                data={"text": news_content, "options": options}
            )
            
            # 创建脚本处理器的上下文
            script_context = self.script_handler.create_context(f"video_gen_{context.job_id}")
            script_result = self.script_handler.process_data(script_data, script_context)
            if script_result.type != ChatDataType.AVATAR_TEXT:
                raise Exception("脚本生成失败")
            
            script_content = script_result.data.get("text", news_content)
            logger.info(f"脚本生成成功，长度: {len(script_content)}字符")
            
            # 步骤2: 生成语音
            logger.info("第2步: 生成播报语音")
            voice_data = ChatData(
                type=ChatDataType.AVATAR_TEXT,
                data={"text": script_content, "options": options}
            )
            
            # 创建语音处理器的上下文
            voice_context = self.voice_handler.create_context(f"video_gen_{context.job_id}")
            voice_result = self.voice_handler.process_data(voice_data, voice_context)
            if voice_result is None or voice_result.type != ChatDataType.AVATAR_AUDIO:
                raise Exception("语音生成失败")
            
            audio_path = voice_result.data.get("file_path") if voice_result.data else None
            logger.info(f"语音生成成功: {audio_path}")
            
            if not audio_path:
                raise Exception("语音文件路径为空")
            
            # 保存音频路径到context
            context.generated_audio_path = audio_path
            
            # 步骤3: 生成数字人视频
            logger.info("第3步: 生成数字人视频")
            avatar_data = ChatData(
                type=ChatDataType.AVATAR_AUDIO,
                data={"file_path": audio_path, "text": script_content, "options": options}
            )
            
            # 创建数字人处理器的上下文
            avatar_context = self.avatar_handler.create_context(f"video_gen_{context.job_id}")
            avatar_result = self.avatar_handler.process_data(avatar_data, avatar_context)
            if avatar_result is None or avatar_result.type != ChatDataType.AVATAR_VIDEO:
                raise Exception("数字人视频生成失败")
            
            avatar_video_path = avatar_result.data.get("file_path")
            logger.info(f"数字人视频生成成功: {avatar_video_path}")
            
            # 步骤4: 使用ffmpeg优化最终视频
            logger.info("第4步: 优化视频编码为浏览器兼容格式")
            if self._optimize_video_with_ffmpeg(avatar_video_path, video_path):
                logger.info(f"视频优化成功: {video_path}")
                
                if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                    logger.info(f"完整流程生成成功: {video_path}")
                    return video_path
                else:
                    logger.error("优化后的视频文件不存在或为空")
                    return None
            else:
                logger.warning("视频优化失败，使用原始数字人视频")
                return avatar_video_path
                
        except Exception as e:
            logger.error(f"完整流程生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _optimize_video_with_ffmpeg(self, input_video: str, output_video: str) -> bool:
        """使用ffmpeg优化视频为浏览器兼容格式"""
        try:
            import subprocess
            
            # 检查输入文件
            if not os.path.exists(input_video) or os.path.getsize(input_video) == 0:
                logger.error(f"输入视频文件不存在或为空: {input_video}")
                return False
            
            logger.info(f"开始优化视频: {input_video} -> {output_video}")
            
            # ffmpeg命令：重新编码为浏览器兼容格式
            cmd = [
                'ffmpeg', '-y',  # 覆盖输出文件
                '-i', input_video,  # 输入视频
                '-c:v', 'libx264',  # H.264视频编码器
                '-preset', 'fast',  # 编码速度
                '-profile:v', 'baseline',  # 最大兼容性配置
                '-level', '3.0',  # 兼容性等级
                '-pix_fmt', 'yuv420p',  # 浏览器兼容像素格式
                '-movflags', '+faststart',  # 优化网络播放
                '-c:a', 'aac',  # AAC音频编码器
                '-ar', '44100',  # 音频采样率
                '-ac', '2',  # 双声道
                '-b:a', '128k',  # 音频比特率
                output_video
            ]
            
            logger.info(f"执行ffmpeg命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                if os.path.exists(output_video) and os.path.getsize(output_video) > 0:
                    input_size = os.path.getsize(input_video)
                    output_size = os.path.getsize(output_video)
                    logger.info(f"视频优化成功: {input_size} -> {output_size} bytes")
                    return True
                else:
                    logger.error("优化后的视频文件为空")
                    return False
            else:
                logger.error(f"ffmpeg执行失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg执行超时")
            return False
        except Exception as e:
            logger.error(f"视频优化异常: {str(e)}")
            return False
    
    def _create_news_video_directly(self, video_path: str, text: str, options: Dict[str, Any]):
        """直接创建新闻视频，使用ffmpeg确保浏览器兼容性"""
        try:
            logger.info(f"开始直接创建新闻视频: {video_path}")
            
            # 视频参数
            width, height = 1280, 720
            fps = 25
            duration = max(10, min(30, len(text) // 8))
            
            # 直接使用ffmpeg生成视频，确保浏览器兼容性
            success = self._create_video_with_ffmpeg(video_path, text, width, height, fps, duration)
            
            if not success:
                logger.error("ffmpeg方法失败，视频生成失败")
                raise Exception("无法使用ffmpeg生成视频")
            
            # 验证生成的视频文件
            if os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
                logger.info(f"新闻视频创建完成: {video_path} ({file_size} bytes)")
            else:
                logger.error(f"视频文件创建失败: {video_path}")
                
        except Exception as e:
            logger.error(f"直接创建新闻视频失败: {str(e)}")
            raise
    
    def _create_video_with_ffmpeg(self, video_path: str, text: str, width: int, height: int, fps: int, duration: int) -> bool:
        """使用ffmpeg直接生成浏览器兼容的MP4视频"""
        try:
            import subprocess
            import os
            import tempfile
            
            # 创建临时图片序列
            temp_dir = tempfile.mkdtemp()
            
            # 使用PIL生成图片序列（更可靠）
            success = self._generate_image_sequence(temp_dir, text, width, height, fps, duration)
            if not success:
                return False
            
            # 使用ffmpeg将图片序列转换为MP4
            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', os.path.join(temp_dir, 'frame_%05d.png'),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-pix_fmt', 'yuv420p',  # 确保浏览器兼容性
                '-profile:v', 'baseline',  # 基线配置文件，最大兼容性
                '-level', '3.0',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("ffmpeg视频生成成功")
                
                # 添加音频轨道
                self._add_audio_track(video_path, text, duration)
                
                # 清理临时文件
                import shutil
                shutil.rmtree(temp_dir)
                return True
            else:
                logger.error(f"ffmpeg生成失败: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.warning("ffmpeg未安装")
            return False
        except Exception as e:
            logger.error(f"ffmpeg方法失败: {str(e)}")
            return False
    
    def _generate_image_sequence(self, temp_dir: str, text: str, width: int, height: int, fps: int, duration: int) -> bool:
        """生成图片序列"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
            
            total_frames = fps * duration
            wrapped_text = textwrap.fill(text, width=50)
            lines = wrapped_text.split('\n')[:10]  # 最多10行
            
            for frame_num in range(total_frames):
                # 创建图像
                img = Image.new('RGB', (width, height), color=(60, 80, 120))
                draw = ImageDraw.Draw(img)
                
                # 尝试加载支持中文的字体
                try:
                    # 优先使用Noto CJK字体（支持中英文）
                    title_font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 48)
                    text_font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 28)
                    small_font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 20)
                    logger.info("使用Noto CJK中文字体")
                except:
                    try:
                        # 备选DejaVu字体（仅支持英文）
                        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
                        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                        logger.warning("使用DejaVu字体，中文可能显示异常")
                    except:
                        title_font = ImageFont.load_default()
                        text_font = ImageFont.load_default()
                        small_font = ImageFont.load_default()
                        logger.warning("使用默认字体，可能显示异常")
                
                # 标题栏
                draw.rectangle([(0, 0), (width, 120)], fill=(40, 60, 100))
                draw.rectangle([(0, 115), (width, 120)], fill=(255, 255, 255))
                
                # 标题
                draw.text((50, 40), "AI 新闻播报", font=title_font, fill=(255, 255, 255))
                
                # 时间戳
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                draw.text((width - 300, 25), timestamp, font=small_font, fill=(200, 200, 200))
                
                # 新闻文本
                y_pos = 200
                for line in lines:
                    if line.strip() and y_pos < height - 150:
                        draw.text((80, y_pos), line, font=text_font, fill=(255, 255, 255))
                        y_pos += 50
                
                # 底部信息栏
                draw.rectangle([(0, height - 80), (width, height)], fill=(50, 50, 80))
                
                # 进度条
                progress = frame_num / total_frames
                bar_width = int((width - 200) * progress)
                draw.rectangle([(100, height - 40), (100 + bar_width, height - 25)], fill=(0, 255, 0))
                draw.rectangle([(100, height - 40), (width - 100, height - 25)], outline=(100, 100, 100), width=2)
                
                # 进度文本
                progress_text = f"Progress: {int(progress * 100)}% | Frame {frame_num + 1}/{total_frames}"
                draw.text((100, height - 70), progress_text, font=small_font, fill=(255, 255, 255))
                
                # 保存图片
                frame_path = os.path.join(temp_dir, f'frame_{frame_num:05d}.png')
                img.save(frame_path)
            
            logger.info(f"生成了 {total_frames} 张图片")
            return True
            
        except Exception as e:
            logger.error(f"生成图片序列失败: {str(e)}")
            return False
    
    def _create_news_frame(self, width: int, height: int, frame_num: int, total_frames: int, 
                          lines: list, original_text: str):
        """创建单个新闻视频帧"""
        import cv2
        import numpy as np
        
        # 创建背景
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 背景渐变效果
        progress = frame_num / total_frames
        bg_base = int(40 + 20 * np.sin(progress * np.pi * 2))
        frame[:, :] = [bg_base, bg_base + 20, bg_base + 40]  # 蓝色调
        
        # 标题栏
        cv2.rectangle(frame, (0, 0), (width, 120), (20, 40, 80), -1)
        cv2.rectangle(frame, (0, 115), (width, 120), (255, 255, 255), -1)
        
        # 标题文字
        cv2.putText(frame, "AI NEWS BROADCAST", (50, 70), 
                   cv2.FONT_HERSHEY_DUPLEX, 2.0, (255, 255, 255), 3)
        
        # 时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (width - 300, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        
        # 新闻正文
        y_start = 200
        line_height = 50
        for i, line in enumerate(lines):
            if line.strip():  # 跳过空行
                y_pos = y_start + i * line_height
                if y_pos < height - 150:  # 留出底部空间
                    cv2.putText(frame, line, (80, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        
        # 底部信息栏
        cv2.rectangle(frame, (0, height - 80), (width, height), (30, 30, 60), -1)
        
        # 进度条
        bar_width = int((width - 200) * progress)
        cv2.rectangle(frame, (100, height - 40), (100 + bar_width, height - 25), (0, 255, 0), -1)
        cv2.rectangle(frame, (100, height - 40), (width - 100, height - 25), (100, 100, 100), 2)
        
        # 进度文字
        progress_text = f"Progress: {int(progress * 100)}% | Frame {frame_num + 1}/{total_frames}"
        cv2.putText(frame, progress_text, (100, height - 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return frame
    
    def _add_audio_track(self, video_path: str, text: str, duration: int):
        """为视频添加音频轨道"""
        try:
            import numpy as np
            import wave
            import os
            
            # 创建简单的音频（静音 + 提示音）
            sample_rate = 44100
            audio_data = self._generate_audio_track(text, duration, sample_rate)
            
            # 保存临时音频文件
            temp_audio = video_path.replace('.mp4', '_temp.wav')
            with wave.open(temp_audio, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            # 使用ffmpeg合并视频和音频
            self._merge_video_audio(video_path, temp_audio)
            
            # 清理临时文件
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
                
            logger.info(f"音频轨道添加完成: {video_path}")
            
        except Exception as e:
            logger.warning(f"添加音频轨道失败: {str(e)}，视频将没有声音")
    
    def _generate_audio_track(self, text: str, duration: int, sample_rate: int):
        """生成简单的音频轨道"""
        import numpy as np
        
        total_samples = duration * sample_rate
        audio = np.zeros(total_samples, dtype=np.int16)
        
        # 添加开始提示音（简单的正弦波）
        beep_duration = 0.5  # 0.5秒提示音
        beep_samples = int(beep_duration * sample_rate)
        t = np.linspace(0, beep_duration, beep_samples, False)
        
        # 生成800Hz的提示音
        frequency = 800
        beep = (np.sin(frequency * 2 * np.pi * t) * 0.3 * 32767).astype(np.int16)
        audio[:beep_samples] = beep
        
        # 添加结束提示音
        if total_samples > beep_samples * 2:
            audio[-beep_samples:] = beep
        
        return audio
    
    def _merge_video_audio(self, video_path: str, audio_path: str):
        """使用ffmpeg合并视频和音频"""
        try:
            import subprocess
            
            temp_output = video_path.replace('.mp4', '_with_audio.mp4')
            
            # ffmpeg命令：合并视频和音频
            cmd = [
                'ffmpeg', '-y',  # 覆盖输出文件
                '-i', video_path,  # 输入视频
                '-i', audio_path,  # 输入音频
                '-c:v', 'copy',  # 复制视频流
                '-c:a', 'aac',   # 音频编码为AAC
                '-shortest',     # 以较短的流为准
                temp_output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 替换原文件
                import shutil
                shutil.move(temp_output, video_path)
                logger.info("视频音频合并成功")
            else:
                logger.error(f"ffmpeg合并失败: {result.stderr}")
                
        except FileNotFoundError:
            logger.warning("ffmpeg未安装，跳过音频合并")
        except Exception as e:
            logger.error(f"合并视频音频时出错: {str(e)}")

    def get_available_qualities(self) -> List[Dict[str, Any]]:
        """获取可用的视频质量选项"""
        return [
            {
                "name": option.name,
                "resolution": option.resolution,
                "bitrate": option.bitrate,
                "fps": option.fps
            }
            for option in self.quality_options
        ]

    def get_available_formats(self) -> List[str]:
        """获取可用的输出格式"""
        return self.output_formats

    def get_processing_status(self, context: NewsVideoContext) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            "job_id": context.job_id,
            "status": context.processing_status,
            "progress": context.progress,
            "start_time": context.start_time,
            "end_time": context.end_time,
            "metadata": context.metadata,
            "output_dir": context.output_dir,
            "final_video_path": context.final_video_path
        }

    def cancel_job(self, context: NewsVideoContext) -> bool:
        """取消视频生成作业"""
        try:
            if context.processing_status not in ["completed", "error"]:
                context.processing_status = "cancelled"
                context.end_time = time.time()
                logger.info(f"视频生成作业已取消: {context.job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"取消作业失败: {str(e)}")
            return False

    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[HandlerBaseConfigModel] = None):
        """加载处理器"""
        logger.info("加载新闻视频生成处理器")
        return True

    def start_context(self, session_context: SessionContext, handler_context: HandlerContext):
        """启动上下文"""
        logger.info(f"启动新闻视频生成上下文: {handler_context.session_id}")
        return True

    def handle(self, context: HandlerContext, inputs: ChatData,
              session_context: SessionContext) -> Optional[ChatData]:
        """处理数据"""
        logger.info(f"处理新闻视频生成数据: {inputs.data_type}")
        return self.process_data(inputs, context)

    def destroy_context(self, context: HandlerContext):
        """销毁上下文"""
        logger.info(f"销毁新闻视频生成上下文: {context.session_id}")
        return True
