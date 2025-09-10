import io
import os
import time
import asyncio
from typing import Dict, Optional, List, Any
from loguru import logger
from pydantic import BaseModel, Field
from abc import ABC
import edge_tts
from openai import OpenAI
import numpy as np

from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo, HandlerDataInfo, HandlerDetail
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.runtime_data.data_bundle import DataBundle, DataBundleDefinition, DataBundleEntry


class TTSOption(BaseModel):
    name: str
    provider: str
    voice: str = ""
    model_name: str = ""
    sample_rate: int = 24000
    api_key: str = ""
    description: str = ""


class NewsVoiceConfig(HandlerBaseConfigModel, BaseModel):
    enabled: bool = Field(default=True)
    tts_options: List[TTSOption] = Field(default_factory=list)


class NewsVoiceContext(HandlerContext):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.config = None
        self.selected_tts = None
        self.generated_audio = None
        self.audio_metadata = {}
        self.edge_client = None
        self.openai_client = None


class HandlerNewsVoice(HandlerBase, ABC):
    def __init__(self):
        super().__init__()
        self.tts_options = []
        self.current_provider = None

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            name="VoiceSynthesizer",
            display_name="语音合成器",
            description="将新闻脚本转换为语音，支持多种TTS引擎",
            version="1.0.0",
            author="News Broadcast Team"
        )

    def get_handler_detail(self) -> HandlerDetail:
        return HandlerDetail(
            input_data_types=[ChatDataType.AVATAR_TEXT],
            output_data_types=[ChatDataType.AUDIO],
            consume_mode=ChatDataConsumeMode.MULTIPLE
        )

    def get_handler_data_info(self) -> HandlerDataInfo:
        return HandlerDataInfo(
            input_descriptions=["新闻播报脚本文本"],
            output_descriptions=["合成的语音音频"]
        )

    def create_context(self, session_id: str) -> NewsVoiceContext:
        return NewsVoiceContext(session_id)

    def init_handler(self, handler_config: NewsVoiceConfig, chat_engine_config: ChatEngineConfigModel):
        logger.info("初始化新闻语音合成处理器")
        self.tts_options = handler_config.tts_options
        logger.info(f"已配置 {len(self.tts_options)} 个TTS选项")

    def select_tts_provider(self, provider_name: str, context: NewsVoiceContext) -> bool:
        """选择指定的TTS提供商"""
        for option in self.tts_options:
            if option.name == provider_name:
                context.selected_tts = option
                self.current_provider = option

                # 初始化对应客户端
                if option.provider == "edge_tts":
                    # Edge TTS 不需要客户端初始化
                    pass
                elif option.provider == "bailian_cosyvoice":
                    context.openai_client = OpenAI(
                        api_key=option.api_key,
                        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                    )

                logger.info(f"已选择TTS提供商: {provider_name} ({option.provider})")
                return True

        logger.error(f"未找到TTS提供商: {provider_name}")
        return False

    async def generate_edge_tts_audio(self, text: str, voice: str, context: NewsVoiceContext) -> Optional[bytes]:
        """使用Edge TTS生成语音"""
        try:
            logger.info(f"使用Edge TTS生成语音，声音: {voice}")

            communicate = edge_tts.Communicate(text, voice)
            audio_data = b""

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            logger.info(f"Edge TTS语音生成成功，大小: {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"Edge TTS语音生成失败: {str(e)}")
            return None

    def generate_cosyvoice_audio(self, text: str, voice: str, model_name: str,
                               context: NewsVoiceContext) -> Optional[bytes]:
        """使用CosyVoice生成语音"""
        try:
            if not context.openai_client:
                logger.error("CosyVoice客户端未初始化")
                return None

            logger.info(f"使用CosyVoice生成语音，声音: {voice}")

            # 阿里云CosyVoice API调用
            response = context.openai_client.audio.speech.create(
                model=model_name,
                voice=voice,
                input=text,
                response_format="mp3"
            )

            # 获取音频数据
            audio_data = b""
            for chunk in response.iter_bytes():
                audio_data += chunk

            logger.info(f"CosyVoice语音生成成功，大小: {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"CosyVoice语音生成失败: {str(e)}")
            return None

    async def synthesize_speech(self, script_text: str, context: NewsVoiceContext) -> Optional[bytes]:
        """合成语音"""
        if not context.selected_tts:
            logger.error("未选择TTS提供商")
            return None

        try:
            option = context.selected_tts
            audio_data = None

            if option.provider == "edge_tts":
                audio_data = await self.generate_edge_tts_audio(script_text, option.voice, context)
            elif option.provider == "bailian_cosyvoice":
                audio_data = self.generate_cosyvoice_audio(script_text, option.voice, option.model_name, context)
            else:
                logger.error(f"不支持的TTS提供商: {option.provider}")
                return None

            if audio_data:
                # 保存元数据
                context.audio_metadata = {
                    "tts_provider": option.name,
                    "provider_type": option.provider,
                    "voice": option.voice,
                    "sample_rate": option.sample_rate,
                    "audio_size": len(audio_data),
                    "generated_at": time.time(),
                    "text_length": len(script_text)
                }

                context.generated_audio = audio_data
                logger.info(f"语音合成完成，音频大小: {len(audio_data)} bytes")
                return audio_data

            return None

        except Exception as e:
            logger.error(f"语音合成失败: {str(e)}")
            return None

    def process_data(self, data: ChatData, context: NewsVoiceContext) -> Optional[ChatData]:
        """处理输入数据"""
        try:
            if data.type == ChatDataType.AVATAR_TEXT:
                script_text = data.data.get("text", "")
                tts_provider = data.data.get("tts_provider", "xiaoxiao_zh")

                if not script_text:
                    logger.error("输入文本为空")
                    return None

                # 选择TTS提供商
                if not self.select_tts_provider(tts_provider, context):
                    return None

                # 合成语音 (改进异步处理)
                try:
                    # 检查是否有正在运行的事件循环
                    try:
                        asyncio.get_running_loop()
                        # 如果有运行中的循环，尝试使用备用的同步处理
                        logger.warning("检测到运行中的事件循环，尝试备用语音合成方案")
                        audio_data = self._synthesize_speech_sync(script_text, context)
                    except RuntimeError:
                        # 没有运行中的循环，可以安全创建新循环
                        async def async_synthesize():
                            return await self.synthesize_speech(script_text, context)

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        audio_data = loop.run_until_complete(async_synthesize())
                        loop.close()
                except Exception as e:
                    logger.error(f"语音合成过程中出错: {str(e)}")
                    audio_data = None

                if audio_data:
                    # 返回音频数据
                    output_data = ChatData(
                        type=ChatDataType.AVATAR_AUDIO,
                        data={
                            "audio": audio_data,
                            "format": "mp3" if context.selected_tts.provider == "bailian_cosyvoice" else "wav",
                            "sample_rate": context.selected_tts.sample_rate,
                            "metadata": context.audio_metadata,
                            "script_text": script_text
                        }
                    )
                    return output_data

            return None

        except Exception as e:
            logger.error(f"新闻语音处理器处理数据失败: {str(e)}")
            return None

    def _synthesize_speech_sync(self, script_text: str, context: NewsVoiceContext) -> Optional[bytes]:
        """同步语音合成方法（用于事件循环冲突时的备用方案）"""
        if not context.selected_tts:
            logger.error("未选择TTS提供商")
            return None

        try:
            option = context.selected_tts

            if option.provider == "edge_tts":
                # 对于 edge_tts，在事件循环冲突时尝试使用同步方式
                logger.info("使用备用方案进行 edge_tts 语音合成")
                return self._generate_edge_tts_audio_sync(script_text, option.voice, context)
            elif option.provider == "bailian_cosyvoice":
                # cosyvoice 已经是同步的，直接调用
                return self.generate_cosyvoice_audio(script_text, option.voice, option.model_name, context)
            else:
                logger.error(f"不支持的TTS提供商: {option.provider}")
                return None

        except Exception as e:
            logger.error(f"同步语音合成失败: {str(e)}")
            return None

    def _generate_edge_tts_audio_sync(self, text: str, voice: str, context: NewsVoiceContext) -> Optional[bytes]:
        """使用线程池的同步 edge_tts 语音合成（避免事件循环冲突）"""
        try:
            import edge_tts
            import tempfile
            import os
            import concurrent.futures

            logger.info(f"开始线程池语音合成: {voice}")

            def run_edge_tts_in_subprocess():
                """使用子进程运行 edge_tts，完全隔离事件循环"""
                try:
                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        temp_filename = temp_file.name
                    
                    try:
                        # 使用subprocess运行edge-tts命令
                        import subprocess
                        cmd = [
                            'python', '-m', 'edge_tts',
                            '--voice', voice,
                            '--text', text,
                            '--write-media', temp_filename
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                        
                        if result.returncode == 0:
                            # 读取音频文件
                            with open(temp_filename, 'rb') as f:
                                audio_data = f.read()
                            return audio_data
                        else:
                            logger.error(f"EdgeTTS子进程失败: {result.stderr}")
                            return None
                        
                    finally:
                        # 清理临时文件
                        if os.path.exists(temp_filename):
                            os.unlink(temp_filename)
                            
                except Exception as e:
                    logger.error(f"子进程 edge_tts 执行失败: {str(e)}")
                    return None
            
            # 直接在当前线程执行，避免线程池问题
            try:
                logger.info("使用子进程方式执行EdgeTTS")
                audio_data = run_edge_tts_in_subprocess()
                if audio_data:
                    logger.info(f"直接同步语音合成成功，大小: {len(audio_data)} bytes")
                    return audio_data
                else:
                    logger.error("直接同步语音合成返回空数据")
                    return None
            except Exception as e:
                logger.error(f"直接同步语音合成失败: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"同步 edge_tts 语音合成失败: {str(e)}")
            return None

    def get_available_voices(self) -> List[Dict[str, Any]]:
        """获取可用的语音列表"""
        return [
            {
                "name": option.name,
                "provider": option.provider,
                "voice": option.voice,
                "description": option.description,
                "sample_rate": option.sample_rate
            }
            for option in self.tts_options
        ]

    def get_voice_by_provider(self, provider: str) -> List[Dict[str, Any]]:
        """根据提供商获取语音列表"""
        return [
            {
                "name": option.name,
                "voice": option.voice,
                "description": option.description
            }
            for option in self.tts_options
            if option.provider == provider
        ]

    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[HandlerBaseConfigModel] = None):
        """加载处理器"""
        logger.info("加载新闻语音合成处理器")
        return True

    def start_context(self, session_context: SessionContext, handler_context: HandlerContext):
        """启动上下文"""
        logger.info(f"启动新闻语音合成上下文: {handler_context.session_id}")
        return True

    def handle(self, context: HandlerContext, inputs: ChatData,
              session_context: SessionContext) -> Optional[ChatData]:
        """处理数据"""
        logger.info(f"处理新闻语音合成数据: {inputs.data_type}")
        return self.process_data(inputs, context)

    def destroy_context(self, context: HandlerContext):
        """销毁上下文"""
        logger.info(f"销毁新闻语音合成上下文: {context.session_id}")
        return True
