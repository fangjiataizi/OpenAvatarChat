#!/usr/bin/env python3
"""
简化版新闻数字人渲染处理器
直接使用LiteAvatar进行实时数字人视频生成
"""

import os
import time
import tempfile
import threading
from typing import Dict, Optional, List, Any
from loguru import logger
from pydantic import BaseModel, Field
import numpy as np
from abc import ABC

from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo, HandlerDetail, HandlerDataInfo
from chat_engine.common.engine_channel_type import EngineChannelType
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.runtime_data.data_bundle import DataBundle, DataBundleDefinition, DataBundleEntry

# 导入LiteAvatar处理器
from src.handlers.avatar.liteavatar.avatar_handler_liteavatar import HandlerTts2Face as LiteAvatarHandler
from src.handlers.avatar.liteavatar.avatar_handler_liteavatar import Tts2FaceConfigModel as LiteAvatarConfig


class SimpleNewsAvatarConfig(HandlerBaseConfigModel, BaseModel):
    """简化配置模型"""
    enabled: bool = Field(default=True)
    avatar_name: str = Field(default="sample_data")
    fps: int = Field(default=25)
    use_gpu: bool = Field(default=False)


class SimpleNewsAvatarContext(HandlerContext):
    """简化上下文"""
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.liteavatar_handler = None
        self.liteavatar_context = None
        self.video_output_queue = None
        self.processing_status = "idle"


class HandlerSimpleNewsAvatar(HandlerBase, ABC):
    """简化的新闻数字人渲染处理器"""

    def __init__(self):
        super().__init__()
        self.liteavatar_handler = None
        self.is_initialized = False

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            config_model=SimpleNewsAvatarConfig,
            load_priority=0
        )
    
    def get_handler_detail(self, session_context: SessionContext, context: HandlerContext) -> HandlerDetail:
        """返回处理器详情"""
        inputs = {
            ChatDataType.AVATAR_AUDIO: HandlerDataInfo(
                type=ChatDataType.AVATAR_AUDIO,
            )
        }
        outputs = {
            ChatDataType.AVATAR_VIDEO: HandlerDataInfo(
                type=ChatDataType.AVATAR_VIDEO,
            )
        }
        return HandlerDetail(inputs=inputs, outputs=outputs)

    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[SimpleNewsAvatarConfig] = None):
        """加载和初始化LiteAvatar处理器"""
        try:
            logger.info("初始化简化新闻数字人处理器...")
            
            if handler_config is None:
                handler_config = SimpleNewsAvatarConfig()
            
            # 创建LiteAvatar配置
            liteavatar_config = LiteAvatarConfig(
                avatar_name=handler_config.avatar_name,
                fps=handler_config.fps,
                use_gpu=handler_config.use_gpu
            )
            
            # 创建并加载LiteAvatar处理器
            self.liteavatar_handler = LiteAvatarHandler()
            self.liteavatar_handler.load(engine_config, liteavatar_config)
            
            self.is_initialized = True
            logger.info("简化新闻数字人处理器初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"简化新闻数字人处理器初始化失败: {e}")
            self.is_initialized = False
            return False

    def create_context(self, session_context: SessionContext, 
                      handler_config: Optional[SimpleNewsAvatarConfig] = None) -> SimpleNewsAvatarContext:
        """创建处理器上下文"""
        context = SimpleNewsAvatarContext(session_context.session_info.session_id)
        
        if self.is_initialized and self.liteavatar_handler:
            try:
                # 创建LiteAvatar的上下文
                context.liteavatar_context = self.liteavatar_handler.create_context(session_context, handler_config)
                logger.info("LiteAvatar上下文创建成功")
            except Exception as e:
                logger.error(f"LiteAvatar上下文创建失败: {e}")
                
        return context

    def start_context(self, session_context: SessionContext, handler_context: SimpleNewsAvatarContext):
        """启动上下文"""
        try:
            if handler_context.liteavatar_context:
                self.liteavatar_handler.start_context(session_context, handler_context.liteavatar_context)
                logger.info("LiteAvatar上下文启动成功")
            return True
        except Exception as e:
            logger.error(f"LiteAvatar上下文启动失败: {e}")
            return False

    def handle(self, context: HandlerContext, inputs: ChatData, 
              output_definitions: Dict[ChatDataType, Any]) -> None:
        """处理音频数据生成视频"""
        if not isinstance(context, SimpleNewsAvatarContext):
            logger.error("上下文类型错误")
            return
        
        if not self.is_initialized or not self.liteavatar_handler:
            logger.error("LiteAvatar处理器未初始化")
            return
        
        if inputs.type != ChatDataType.AVATAR_AUDIO:
            logger.debug(f"跳过非音频数据类型: {inputs.type}")
            return
        
        try:
            logger.info("开始处理音频数据生成数字人视频")
            context.processing_status = "processing"
            
            # 直接传递给LiteAvatar处理器
            self.liteavatar_handler.handle(
                context.liteavatar_context, 
                inputs, 
                output_definitions
            )
            
            context.processing_status = "completed"
            logger.info("音频数据处理完成")
            
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")
            context.processing_status = "error"

    def destroy_context(self, context: HandlerContext):
        """销毁上下文"""
        if isinstance(context, SimpleNewsAvatarContext):
            try:
                if context.liteavatar_context and self.liteavatar_handler:
                    self.liteavatar_handler.destroy_context(context.liteavatar_context)
                logger.info("上下文销毁成功")
            except Exception as e:
                logger.error(f"上下文销毁失败: {e}")

    def render_audio_to_video(self, audio_data: bytes, script_text: str = "") -> Optional[bytes]:
        """直接渲染音频为视频的便捷方法"""
        try:
            if not self.is_initialized:
                logger.error("处理器未初始化")
                return None
            
            # 创建临时音频文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio.write(audio_data)
                temp_audio_path = temp_audio.name
            
            try:
                # 使用scipy读取音频
                from scipy.io import wavfile
                sample_rate, audio_array = wavfile.read(temp_audio_path)
                
                # 处理音频数据
                if len(audio_array.shape) > 1:
                    audio_array = np.mean(audio_array, axis=1)
                
                if audio_array.dtype != np.int16:
                    audio_array = (np.clip(audio_array, -1, 1) * 32767).astype(np.int16)
                
                # 重采样到24kHz
                if sample_rate != 24000:
                    from scipy import signal
                    num_samples = int(len(audio_array) * 24000 / sample_rate)
                    audio_array = signal.resample(audio_array, num_samples).astype(np.int16)
                
                # 创建DataBundle
                data_definition = DataBundleDefinition()
                data_definition.add_entry(DataBundleEntry.create_audio_entry("main", 1, 24000))
                data_definition.lockdown()
                
                data_bundle = DataBundle(data_definition)
                data_bundle.set_main_data(audio_array[np.newaxis, :])
                data_bundle.add_meta("speech_id", "news_speech")
                data_bundle.add_meta("avatar_speech_end", True)
                
                # 创建ChatData
                chat_data = ChatData(
                    type=ChatDataType.AVATAR_AUDIO,
                    data=data_bundle
                )
                
                logger.info("音频数据准备完成，开始生成视频")
                
                # 这里应该通过某种方式获取生成的视频
                # 由于LiteAvatar是异步的，我们需要通过队列或回调获取结果
                # 暂时返回None，表示需要进一步完善
                return None
                
            finally:
                os.unlink(temp_audio_path)
            
        except Exception as e:
            logger.error(f"渲染视频失败: {e}")
            return None

    def get_processing_status(self, context: SimpleNewsAvatarContext) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            "status": context.processing_status,
            "initialized": self.is_initialized,
            "has_liteavatar": self.liteavatar_handler is not None
        }