#!/usr/bin/env python3
"""
数字人播报新闻服务 - 主启动文件
基于OpenAvatarChat架构，实现完整的新闻播报视频生成流程
"""

import os
import sys
import asyncio
import json
import time
from typing import Dict, Any, Optional
import gradio as gr
from loguru import logger
import nest_asyncio

# 延迟启用嵌套事件循环支持（避免与 Gradio 冲突）
# nest_asyncio.apply()  # 暂时注释掉，在需要时再启用

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chat_engine.chat_engine import ChatEngine
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from src.handlers.news.video_generator.news_video_handler import HandlerNewsVideo, NewsVideoConfig
from src.handlers.news.script_generator.news_script_handler import HandlerNewsScript
from src.handlers.news.voice_synthesizer.news_voice_handler import HandlerNewsVoice
from src.handlers.news.avatar_renderer.news_avatar_handler import HandlerNewsAvatar


class NewsBroadcastService:
    """新闻播报服务"""

    def __init__(self):
        self.chat_engine = None
        self.video_handler = None
        self.current_job = None
        self.processing_status = "idle"

        # 初始化服务
        self._init_service()

    def _init_service(self):
        """初始化服务"""
        try:
            logger.info("正在初始化新闻播报服务...")

            # 加载配置
            config_path = "config/news_broadcast.yaml"
            if not os.path.exists(config_path):
                logger.error(f"配置文件不存在: {config_path}")
                return

            # 创建ChatEngine配置
            chat_engine_config = ChatEngineConfigModel(
                model_root="models",
                handler_search_path=["src/handlers"],
                handler_configs={}
            )

            # 初始化ChatEngine
            self.chat_engine = ChatEngine()
            self.chat_engine.initialize(chat_engine_config)

            # 初始化视频处理器
            video_config = NewsVideoConfig(
                enabled=True,
                output_formats=["mp4", "webm"],
                quality_options=[]
            )

            self.video_handler = HandlerNewsVideo()
            self.video_handler.init_handler(video_config, chat_engine_config)

            logger.info("新闻播报服务初始化完成")

        except Exception as e:
            logger.error(f"服务初始化失败: {str(e)}")
            raise

    def get_available_options(self) -> Dict[str, Any]:
        """获取可用的选项"""
        return {
            "llm_providers": self.video_handler.script_handler.get_available_providers() if self.video_handler.script_handler else [],
            "voice_providers": self.video_handler.voice_handler.get_available_voices() if self.video_handler.voice_handler else [],
            "avatar_providers": self.video_handler.avatar_handler.get_available_avatars() if self.video_handler.avatar_handler else [],
            "video_qualities": self.video_handler.get_available_qualities(),
            "video_formats": self.video_handler.get_available_formats()
        }

    def generate_news_video(self, news_content: str, llm_provider: str, voice_provider: str,
                          avatar_provider: str, category: str, style: str,
                          video_quality: str, video_format: str) -> Dict[str, Any]:
        """生成新闻视频"""
        try:
            if not news_content.strip():
                return {"status": "error", "message": "新闻内容不能为空"}

            if self.processing_status == "processing":
                return {"status": "error", "message": "当前有任务正在处理中，请等待完成"}

            self.processing_status = "processing"

            # 映射中文选项到英文值
            style_mapping = {
                "正式播报": "formal",
                "亲和播报": "friendly",
                "生动播报": "lively"
            }

            category_mapping = {
                "时政新闻": "politics",
                "财经资讯": "finance",
                "科技前沿": "technology",
                "体育赛事": "sports",
                "生活服务": "life"
            }

            # 构建选项
            options = {
                "llm_provider": llm_provider,
                "tts_provider": voice_provider,
                "avatar_provider": avatar_provider,
                "category": category_mapping.get(category, "general"),
                "style": style_mapping.get(style, "formal"),
                "quality": video_quality,
                "format": video_format
            }

            # 创建输入数据 - 使用简单的数据结构
            input_data = ChatData(
                type=ChatDataType.HUMAN_TEXT,
                data={
                    "text": news_content,
                    "options": options
                }
            )

            # 创建上下文
            session_id = f"news_broadcast_{int(time.time())}"
            context = self.video_handler.create_context(session_id)

            logger.info("开始处理视频数据...")
            # 处理数据
            result = self.video_handler.process_data(input_data, context)

            if result:
                logger.info(f"处理结果类型: {result.type}")
                if result.type in [ChatDataType.AVATAR_VIDEO]:
                    video_path = result.data.get("file_path")
                    metadata = result.data.get("metadata", {})

                    logger.info(f"视频生成成功: {video_path}")
                    self.processing_status = "completed"

                    return {
                        "status": "success",
                        "message": "新闻视频生成成功",
                        "video_path": video_path,
                        "job_id": metadata.get("job_id"),
                        "processing_time": metadata.get("processing_time", 0),
                        "script_length": metadata.get("script_length", 0),
                        "metadata": metadata
                    }
                else:
                    logger.warning(f"意外的结果类型: {result.type}, 结果数据: {result.data}")
                    self.processing_status = "error"
                    return {"status": "error", "message": f"意外的结果类型: {result.type}"}
            else:
                logger.error("视频处理器返回空结果")
                self.processing_status = "error"
                return {"status": "error", "message": "视频生成失败，请检查配置或重试"}

        except Exception as e:
            logger.error(f"生成新闻视频失败: {str(e)}", exc_info=True)
            self.processing_status = "error"
            return {"status": "error", "message": f"生成失败: {str(e)}"}

    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        if self.video_handler and self.current_job:
            return self.video_handler.get_processing_status(self.current_job)
        return {"status": self.processing_status, "progress": 0}

    def cancel_current_job(self) -> bool:
        """取消当前作业"""
        if self.video_handler and self.current_job:
            return self.video_handler.cancel_job(self.current_job)
        return False


def create_gradio_interface():
    """创建Gradio用户界面"""

    # 初始化服务
    service = NewsBroadcastService()
    available_options = service.get_available_options()

    # 提取选项列表
    llm_options = [opt["name"] for opt in available_options["llm_providers"]]
    voice_options = [opt["name"] for opt in available_options["voice_providers"]]
    avatar_options = [opt["name"] for opt in available_options["avatar_providers"]]
    quality_options = [opt["name"] for opt in available_options["video_qualities"]]
    format_options = available_options["video_formats"]

    # 默认值
    default_llm = llm_options[0] if llm_options else "qwen-plus"
    default_voice = voice_options[0] if voice_options else "xiaoxiao_zh"
    default_avatar = avatar_options[0] if avatar_options else "xiaohui_teacher"
    default_quality = quality_options[0] if quality_options else "high"
    default_format = format_options[0] if format_options else "mp4"

    def generate_video(news_content, llm_provider, voice_provider, avatar_provider,
                      category, style, video_quality, video_format):
        """生成视频的回调函数"""
        result = service.generate_news_video(
            news_content, llm_provider, voice_provider, avatar_provider,
            category, style, video_quality, video_format
        )

        if result["status"] == "success":
            return (
                f"✅ 生成成功!\n\n"
                f"📁 视频文件: {result['video_path']}\n"
                f"🆔 作业ID: {result['job_id']}\n"
                f"⏱️ 处理时间: {result['processing_time']:.2f}秒\n"
                f"📝 脚本长度: {result['script_length']}字符\n"
                f"🎬 视频已保存，可以下载查看",
                result['video_path']
            )
        else:
            return f"❌ 生成失败: {result['message']}", None

    def get_status():
        """获取状态的回调函数"""
        status = service.get_processing_status()
        return f"当前状态: {status.get('status', 'unknown')}"

    # 创建界面
    with gr.Blocks(title="数字人播报新闻服务", theme=gr.themes.Soft()) as interface:
        gr.Markdown("""
        # 🤖 数字人播报新闻服务

        基于AI技术，自动生成专业的新闻播报视频。支持选择不同的LLM、语音和数字人组合，快速生成高质量的新闻视频内容。

        ## ✨ 主要功能
        - 📝 **智能脚本生成**: 支持多种LLM模型生成专业的播报脚本
        - 🔊 **语音合成选择**: 提供多种TTS引擎和音色选择
        - 🎭 **数字人渲染**: 支持多种数字人形象和风格
        - 🎬 **一键生成视频**: 整合所有组件，生成完整的新闻播报视频
        """)

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("## 📝 输入新闻内容")

                news_input = gr.Textbox(
                    label="新闻内容",
                    placeholder="请输入要播报的新闻内容...",
                    lines=8,
                    show_copy_button=True
                )

                with gr.Row():
                    category_input = gr.Dropdown(
                        label="新闻类型",
                        choices=["时政新闻", "财经资讯", "科技前沿", "体育赛事", "生活服务"],
                        value="时政新闻"
                    )

                    style_input = gr.Dropdown(
                        label="播报风格",
                        choices=["正式播报", "亲和播报", "生动播报"],
                        value="正式播报"
                    )

            with gr.Column(scale=1):
                gr.Markdown("## ⚙️ 配置选项")

                llm_provider = gr.Dropdown(
                    label="🤖 LLM脚本生成",
                    choices=llm_options,
                    value=default_llm,
                    info="选择用于生成播报脚本的AI模型"
                )

                voice_provider = gr.Dropdown(
                    label="🔊 语音合成",
                    choices=voice_options,
                    value=default_voice,
                    info="选择语音合成的音色和引擎"
                )

                avatar_provider = gr.Dropdown(
                    label="🎭 数字人形象",
                    choices=avatar_options,
                    value=default_avatar,
                    info="选择播报视频中的数字人形象"
                )

                with gr.Row():
                    video_quality = gr.Dropdown(
                        label="🎬 视频质量",
                        choices=quality_options if quality_options else ["high", "medium", "low"],
                        value=default_quality
                    )

                    video_format = gr.Dropdown(
                        label="📁 输出格式",
                        choices=format_options,
                        value=default_format
                    )

        with gr.Row():
            generate_btn = gr.Button(
                "🚀 开始生成新闻视频",
                variant="primary",
                size="lg"
            )

            status_btn = gr.Button(
                "📊 查看状态",
                variant="secondary"
            )

        with gr.Row():
            status_output = gr.Textbox(
                label="处理状态",
                interactive=False,
                lines=3
            )

        with gr.Row():
            result_output = gr.Textbox(
                label="生成结果",
                interactive=False,
                lines=6
            )

            video_output = gr.Video(
                label="生成的视频"
            )

        # 绑定事件
        generate_btn.click(
            fn=generate_video,
            inputs=[news_input, llm_provider, voice_provider, avatar_provider,
                   category_input, style_input, video_quality, video_format],
            outputs=[result_output, video_output]
        )

        status_btn.click(
            fn=get_status,
            outputs=[status_output]
        )

        # 示例数据
        gr.Examples(
            examples=[
                ["今天上午，国务院总理李强在人民大会堂会见了来华访问的美国国务卿布林肯。双方就中美关系、台湾问题、朝鲜半岛局势等共同关心的问题进行了深入交流。李强强调，中美作为两个大国，合作是唯一正确的选择，竞争不应走向对抗。布林肯表示，美方愿与中国保持沟通，避免误解误判。", "时政新闻", "正式播报"],
                ["最新数据显示，2024年上半年，中国新能源汽车销量突破500万辆，同比增长近30%。其中，特斯拉中国市场销量创新高，比亚迪、上汽等本土品牌表现抢眼。业内人士表示，随着技术进步和政策支持，中国新能源汽车产业正迎来黄金发展期。", "财经资讯", "正式播报"],
                ["OpenAI宣布，其最新的GPT-5模型已在内部测试中展现出惊人的能力。该模型不仅在语言理解方面大幅提升，还能进行复杂的多模态任务。业内专家预测，这将进一步加速AI技术的商业化应用进程。", "科技前沿", "生动播报"],
                ["在昨晚结束的欧洲杯决赛中，西班牙队凭借精彩的点球大战击败英格兰队，时隔8年再次捧起大力神杯。西班牙球星佩德里打进制胜球，帮助球队在常规时间内扳平比分。这也是西班牙队第4次夺得欧洲杯冠军。", "体育赛事", "生动播报"],
                ["近日，北京市宣布扩大摇号购房人群范围，将包括更多符合条件的非京籍家庭。这一政策调整旨在进一步缓解住房需求，帮助更多家庭实现安居梦想。专家表示，这将对房地产市场产生积极影响。", "生活服务", "亲和播报"]
            ],
            inputs=[news_input, category_input, style_input],
            label="📚 新闻示例"
        )

        gr.Markdown("""
        ## 📋 使用说明

        1. **输入新闻内容**: 在左侧文本框中输入要播报的新闻内容
        2. **选择新闻类型**: 根据内容选择合适的新闻类型，这会影响脚本风格
        3. **配置播报选项**:
           - LLM脚本生成: 选择用于生成播报脚本的AI模型
           - 语音合成: 选择播报语音的音色和引擎
           - 数字人形象: 选择视频中的主持人形象
           - 视频质量: 选择输出视频的质量等级
           - 输出格式: 选择视频文件的格式
        4. **点击生成**: 点击"开始生成新闻视频"按钮开始处理
        5. **查看结果**: 处理完成后可以在右侧查看生成的视频

        ## ⚠️ 注意事项

        - 新闻内容长度建议在200-1000字符之间
        - 首次使用可能需要一些时间来加载模型
        - 生成的视频文件会保存在 `output/news_videos/` 目录中
        - 支持同时处理一个生成任务，避免并发冲突

        ---
        **技术支持**: 基于OpenAvatarChat项目开发 | 数字人播报新闻服务 v1.0
        """)

    return interface


def main():
    """主函数"""
    try:
        logger.info("启动数字人播报新闻服务...")

        # 检查环境变量
        if not os.getenv("DASHSCOPE_API_KEY"):
            logger.warning("未设置DASHSCOPE_API_KEY环境变量，某些功能可能无法使用")

        # 创建并启动界面
        interface = create_gradio_interface()

        # 启动服务，尝试不同端口避免冲突
        ports_to_try = [8444, 8445, 8446, 8447, 8448]
        launched = False
        
        for port in ports_to_try:
            try:
                logger.info(f"尝试在端口 {port} 启动服务...")
                interface.launch(
                    server_name="0.0.0.0",
                    server_port=port,
                    show_api=False,
                    share=False,
                    ssl_verify=False,
                    prevent_thread_lock=True  # 避免线程锁定问题
                )
                logger.info(f"✅ 新闻播报服务启动成功，访问地址: http://localhost:{port}")
                launched = True
                break
            except OSError as e:
                if "Cannot find empty port" in str(e) or "Address already in use" in str(e):
                    logger.warning(f"端口 {port} 被占用，尝试下一个端口")
                    continue
                else:
                    raise e
        
        if not launched:
            raise OSError("所有端口都被占用，无法启动服务")

        logger.info("新闻播报服务启动完成，访问地址: http://localhost:8444")

    except KeyboardInterrupt:
        logger.info("服务被用户中断")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        raise


if __name__ == "__main__":
    main()
