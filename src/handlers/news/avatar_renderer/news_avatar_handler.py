import os
import time
import asyncio
import threading
from typing import Dict, Optional, List, Any
from loguru import logger
from pydantic import BaseModel, Field
from abc import ABC
import numpy as np

from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo, HandlerDataInfo, HandlerDetail
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.runtime_data.data_bundle import DataBundle, DataBundleDefinition, DataBundleEntry

# Avatar处理器将在需要时动态导入，避免启动时卡顿
# from src.handlers.avatar.liteavatar.avatar_handler_liteavatar import HandlerTts2Face as LiteAvatarHandler  
# from src.handlers.avatar.liteavatar.avatar_handler_liteavatar import Tts2FaceConfigModel as LiteAvatarConfig
# from src.handlers.avatar.musetalk.avatar_handler_musetalk import HandlerAvatarMusetalk as MuseTalkHandler
# from src.handlers.avatar.musetalk.avatar_handler_musetalk import AvatarMuseTalkConfig as MuseTalkConfig


class AvatarOption(BaseModel):
    name: str
    provider: str
    avatar_name: str = ""
    fps: int = 25
    use_gpu: bool = True
    asset_path: str = ""
    concurrent_limit: int = 1
    description: str = ""


class NewsAvatarConfig(HandlerBaseConfigModel, BaseModel):
    enabled: bool = Field(default=True)
    avatar_options: List[AvatarOption] = Field(default_factory=list)


class NewsAvatarContext(HandlerContext):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.config = None
        self.selected_avatar = None
        self.avatar_handler = None
        self.generated_video = None
        self.video_metadata = {}
        self.processing_status = "idle"  # idle, processing, completed, error


class HandlerNewsAvatar(HandlerBase, ABC):
    def __init__(self):
        super().__init__()
        self.avatar_options = []
        self.current_handler = None
        self.active_handlers = {}  # 存储不同类型的处理器实例

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            name="AvatarRenderer",
            display_name="数字人渲染器",
            description="将语音和脚本渲染为数字人视频，支持多种Avatar引擎",
            version="1.0.0",
            author="News Broadcast Team"
        )

    def get_handler_detail(self) -> HandlerDetail:
        return HandlerDetail(
            input_data_types=[ChatDataType.AUDIO, ChatDataType.HUMAN_TEXT],
            output_data_types=[ChatDataType.VIDEO],
            consume_mode=ChatDataConsumeMode.MULTIPLE
        )

    def get_handler_data_info(self) -> HandlerDataInfo:
        return HandlerDataInfo(
            input_descriptions=["语音音频数据", "脚本文本"],
            output_descriptions=["数字人视频"]
        )

    def create_context(self, session_id: str) -> NewsAvatarContext:
        context = NewsAvatarContext(session_id)
        # 将可用的avatar处理器传递给context
        context.avatar_handlers = getattr(self, 'active_handlers', {})
        return context

    def init_handler(self, handler_config: NewsAvatarConfig, chat_engine_config: ChatEngineConfigModel):
        logger.info("初始化新闻数字人渲染处理器")
        self.avatar_options = handler_config.avatar_options

        # 初始化各个Avatar处理器
        self._init_avatar_handlers(chat_engine_config)

        logger.info(f"已配置 {len(self.avatar_options)} 个Avatar选项")

    def _init_avatar_handlers(self, chat_engine_config: ChatEngineConfigModel):
        """初始化各个Avatar处理器 - 使用惰性加载"""
        try:
            # 存储配置信息，但不立即初始化LiteAvatar（避免启动时卡顿）
            use_gpu_setting = any(option.use_gpu for option in self.avatar_options if option.provider == "liteavatar")
            
            # 存储基础配置信息，供后续动态导入使用
            self.liteavatar_settings = {
                "avatar_name": "sample_data",
                "fps": 25,
                "use_gpu": use_gpu_setting
            }
            self.chat_engine_config = chat_engine_config
            
            # 不立即加载，标记为待加载状态
            self.active_handlers["liteavatar"] = "lazy_load"
            
            logger.info("Avatar 处理器配置完成（惰性加载模式）")
        except Exception as e:
            logger.error(f"Avatar 处理器配置失败: {e}")
            self.active_handlers["liteavatar"] = None

        # MuseTalk处理器 - 暂时禁用，缺少依赖
        # musetalk_config = MuseTalkConfig(
        #     fps=20,
        #     batch_size=2,
        #     avatar_video_path="src/handlers/avatar/musetalk/MuseTalk/data/video/news_anchor.mp4",
        #     avatar_model_dir="models/musetalk/avatar_model",
        #     force_create_avatar=False
        # )
        # musetalk_handler = MuseTalkHandler()
        # # MuseTalk处理器可能不需要init_handler，直接实例化即可
        # # musetalk_handler.init_handler(musetalk_config, chat_engine_config)
        # self.active_handlers["musetalk"] = musetalk_handler

        logger.info(f"已初始化 {len(self.active_handlers)} 个Avatar处理器")

    def select_avatar_provider(self, provider_name: str, context: NewsAvatarContext) -> bool:
        """选择指定的Avatar提供商"""
        for option in self.avatar_options:
            if option.name == provider_name:
                context.selected_avatar = option

                # 获取对应的处理器
                if option.provider in self.active_handlers:
                    context.avatar_handler = self.active_handlers[option.provider]
                    logger.info(f"已选择Avatar提供商: {provider_name} ({option.provider})")
                    return True
                else:
                    logger.error(f"Avatar处理器 {option.provider} 未初始化")
                    return False

        logger.error(f"未找到Avatar提供商: {provider_name}")
        return False

    # def _create_liteavatar_config(self, option: AvatarOption) -> LiteAvatarConfig:
    #     """创建LiteAvatar配置（已废弃，使用直接处理器）"""
    #     return LiteAvatarConfig(
    #         avatar_name=option.avatar_name,
    #         fps=option.fps,
    #         use_gpu=option.use_gpu
    #     )

    def _create_musetalk_config(self, option: AvatarOption):
        """创建MuseTalk配置 - 暂时禁用"""
        # return MuseTalkConfig(
        #     fps=option.fps,
        #     batch_size=2,
        #     avatar_video_path=option.asset_path or "src/handlers/avatar/musetalk/MuseTalk/data/video/news_anchor.mp4",
        #     avatar_model_dir="models/musetalk/avatar_model",
        #     force_create_avatar=False
        # )
        return None

    async def render_video_liteavatar(self, audio_data: bytes, script_text: str,
                                    option: AvatarOption, context: NewsAvatarContext) -> Optional[bytes]:
        """使用LiteAvatar渲染视频"""
        try:
            logger.info(f"使用LiteAvatar渲染视频，Avatar: {option.avatar_name}")

            # 创建处理器配置
            config = self._create_liteavatar_config(option)
            handler = context.avatar_handler

            # 准备音频数据
            audio_chat_data = ChatData(
                data_type=ChatDataType.AUDIO,
                data={
                    "audio": audio_data,
                    "format": "wav",
                    "sample_rate": 24000
                }
            )

            # 处理音频数据生成视频
            handler_context = handler.create_context(context.session_id)
            video_result = await handler.process_data_async(audio_chat_data, handler_context)

            if video_result and video_result.data_type == ChatDataType.VIDEO:
                video_data = video_result.data.get("video", b"")
                logger.info(f"LiteAvatar视频渲染成功，大小: {len(video_data)} bytes")
                return video_data

            return None

        except Exception as e:
            logger.error(f"LiteAvatar视频渲染失败: {str(e)}")
            return None

    async def render_video_musetalk(self, audio_data: bytes, script_text: str,
                                  option: AvatarOption, context: NewsAvatarContext) -> Optional[bytes]:
        """使用MuseTalk渲染视频"""
        try:
            logger.info(f"使用MuseTalk渲染视频，Avatar: {option.avatar_name}")

            # MuseTalk需要音频文件路径，这里需要先保存音频文件
            import tempfile
            import wave
            import audioop

            # 创建临时音频文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio_path = temp_audio.name

                # 将音频数据写入文件
                with wave.open(temp_audio, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # 单声道
                    wav_file.setsampwidth(2)  # 16位
                    wav_file.setframerate(24000)  # 24kHz
                    wav_file.writeframes(audio_data)

            try:
                # 创建处理器配置
                config = self._create_musetalk_config(option)
                handler = context.avatar_handler

                # 准备音频数据
                audio_chat_data = ChatData(
                    data_type=ChatDataType.AUDIO,
                    data={
                        "audio_path": temp_audio_path,
                        "format": "wav",
                        "sample_rate": 24000,
                        "script_text": script_text
                    }
                )

                # 处理音频数据生成视频
                handler_context = handler.create_context(context.session_id)
                video_result = await handler.process_data_async(audio_chat_data, handler_context)

                if video_result and video_result.data_type == ChatDataType.VIDEO:
                    video_data = video_result.data.get("video", b"")
                    logger.info(f"MuseTalk视频渲染成功，大小: {len(video_data)} bytes")
                    return video_data

                return None

            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"MuseTalk视频渲染失败: {str(e)}")
            return None

    async def render_video(self, audio_data: bytes, script_text: str, context: NewsAvatarContext) -> Optional[bytes]:
        """渲染视频"""
        if not context.selected_avatar or not context.avatar_handler:
            logger.error("未选择Avatar提供商或处理器未初始化")
            return None

        try:
            context.processing_status = "processing"
            option = context.selected_avatar
            video_data = None

            if option.provider == "liteavatar":
                video_data = await self.render_video_liteavatar(audio_data, script_text, option, context)
            elif option.provider == "musetalk":
                video_data = await self.render_video_musetalk(audio_data, script_text, option, context)
            else:
                logger.error(f"不支持的Avatar提供商: {option.provider}")
                context.processing_status = "error"
                return None

            if video_data:
                # 保存元数据
                context.video_metadata = {
                    "avatar_provider": option.name,
                    "provider_type": option.provider,
                    "avatar_name": option.avatar_name,
                    "fps": option.fps,
                    "video_size": len(video_data),
                    "generated_at": time.time(),
                    "audio_size": len(audio_data),
                    "script_length": len(script_text)
                }

                context.generated_video = video_data
                context.processing_status = "completed"
                logger.info(f"视频渲染完成，视频大小: {len(video_data)} bytes")
                return video_data
            else:
                context.processing_status = "error"
                return None

        except Exception as e:
            logger.error(f"视频渲染失败: {str(e)}")
            context.processing_status = "error"
            return None

    def process_data(self, data: ChatData, context: NewsAvatarContext) -> Optional[ChatData]:
        """处理输入数据"""
        try:
            if data.type == ChatDataType.AVATAR_AUDIO:
                audio_data = data.data.get("audio", b"")
                script_text = data.data.get("script_text", "")
                avatar_provider = data.data.get("avatar_provider", "xiaohui_teacher")

                if not audio_data:
                    logger.error("输入音频数据为空")
                    return None

                # 选择Avatar提供商
                if not self.select_avatar_provider(avatar_provider, context):
                    return None

                # 渲染视频 (改进异步处理)
                try:
                    # 检查是否有正在运行的事件循环
                    try:
                        asyncio.get_running_loop()
                        # 如果有运行中的循环，尝试使用备用的同步处理
                        logger.warning("检测到运行中的事件循环，尝试备用数字人渲染方案")
                        video_data = self._render_video_sync(audio_data, script_text, context)
                    except RuntimeError:
                        # 没有运行中的循环，可以安全创建新循环
                        async def async_render():
                            return await self.render_video(audio_data, script_text, context)

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        video_data = loop.run_until_complete(async_render())
                        loop.close()
                except Exception as e:
                    logger.error(f"数字人渲染过程中出错: {str(e)}")
                    video_data = None

                if video_data:
                    # 返回视频数据
                    output_data = ChatData(
                        type=ChatDataType.AVATAR_VIDEO,
                        data={
                            "video": video_data,
                            "format": "mp4",
                            "fps": context.selected_avatar.fps,
                            "metadata": context.video_metadata,
                            "script_text": script_text,
                            "processing_status": context.processing_status
                        }
                    )
                    return output_data

            return None

        except Exception as e:
            logger.error(f"新闻Avatar处理器处理数据失败: {str(e)}")
            context.processing_status = "error"
            return None

    def get_available_avatars(self) -> List[Dict[str, Any]]:
        """获取可用的Avatar列表"""
        return [
            {
                "name": option.name,
                "provider": option.provider,
                "avatar_name": option.avatar_name,
                "description": option.description,
                "fps": option.fps,
                "use_gpu": option.use_gpu
            }
            for option in self.avatar_options
        ]

    def get_avatar_by_provider(self, provider: str) -> List[Dict[str, Any]]:
        """根据提供商获取Avatar列表"""
        return [
            {
                "name": option.name,
                "avatar_name": option.avatar_name,
                "description": option.description,
                "fps": option.fps
            }
            for option in self.avatar_options
            if option.provider == provider
        ]

    def get_processing_status(self, context: NewsAvatarContext) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            "status": context.processing_status,
            "selected_avatar": context.selected_avatar.name if context.selected_avatar else None,
            "progress": 100 if context.processing_status == "completed" else 0,
            "metadata": context.video_metadata
        }

    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[HandlerBaseConfigModel] = None):
        """加载处理器"""
        logger.info("加载新闻数字人渲染处理器")
        return True

    def start_context(self, session_context: SessionContext, handler_context: HandlerContext):
        """启动上下文"""
        logger.info(f"启动新闻数字人渲染上下文: {handler_context.session_id}")
        return True

    def handle(self, context: HandlerContext, inputs: ChatData,
              session_context: SessionContext) -> Optional[ChatData]:
        """处理数据"""
        logger.info(f"处理新闻数字人渲染数据: {inputs.data_type}")
        return self.process_data(inputs, context)

    def destroy_context(self, context: HandlerContext):
        """销毁上下文"""
        logger.info(f"销毁新闻数字人渲染上下文: {context.session_id}")
        return True

    def _render_video_sync(self, audio_data: bytes, script_text: str, context: NewsAvatarContext) -> Optional[bytes]:
        """同步数字人渲染方法（用于事件循环冲突时的备用方案）"""
        if not context.selected_avatar:
            logger.error("未选择Avatar提供商")
            return None

        try:
            option = context.selected_avatar

            if option.provider == "liteavatar":
                logger.info("使用LiteAvatar进行数字人渲染")
                return self._render_liteavatar_sync(audio_data, script_text, option, context)
            elif option.provider == "musetalk":
                logger.error("MuseTalk暂时禁用")
                return None
            elif option.provider == "lam":
                logger.info("使用LAM数字人渲染")
                return self._render_lam_sync(audio_data, script_text, option, context)
            else:
                logger.error(f"不支持的Avatar提供商: {option.provider}")
                return None

        except Exception as e:
            logger.error(f"同步数字人渲染失败: {str(e)}")
            return None

    def _render_liteavatar_sync(self, audio_data: bytes, script_text: str, option: AvatarOption, context: NewsAvatarContext) -> Optional[bytes]:
        """同步 LiteAvatar 渲染（使用直接处理器）"""
        try:
            logger.info(f"开始 LiteAvatar 同步渲染，avatar: {option.avatar_name}")
            
            # 使用直接处理器避免多进程问题
            from src.handlers.news.avatar_renderer.direct_liteavatar_handler import HandlerDirectLiteAvatar
            
            direct_handler = HandlerDirectLiteAvatar()
            from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel
            
            if not direct_handler.load(ChatEngineConfigModel()):
                logger.error("直接LiteAvatar处理器加载失败")
                return None
            
            logger.info("✅ 直接LiteAvatar处理器加载成功，开始处理音频...")
            
            # 直接处理音频生成视频
            video_data = direct_handler.process_audio_to_video(audio_data, script_text)
            
            if video_data:
                logger.info(f"✅ LiteAvatar 直接渲染成功，视频大小: {len(video_data)} bytes")
                return video_data
            else:
                logger.error("❌ LiteAvatar 直接渲染失败")
                return None
            
        except Exception as e:
            logger.error(f"LiteAvatar 同步渲染失败: {str(e)}")
            return None

    def _render_musetalk_sync(self, audio_data: bytes, script_text: str, option: AvatarOption, context: NewsAvatarContext) -> Optional[bytes]:
        """同步 MuseTalk 渲染（已禁用）"""
        logger.error("MuseTalk已禁用，无法生成视频")
        return None


    def _render_lam_sync(self, audio_data: bytes, script_text: str, option: AvatarOption, context: NewsAvatarContext) -> Optional[bytes]:
        """同步 LAM 渲染"""
        try:
            logger.info("LAM 同步渲染暂未实现")
            # 这里可以实现实际的 LAM 同步渲染逻辑
            # 暂时返回None以保持失败状态
            return None
        except Exception as e:
            logger.error(f"LAM 同步渲染失败: {str(e)}")
            return None
