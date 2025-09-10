#!/usr/bin/env python3
"""
优化的新闻播报前端界面
提供更直观的音频和视频展示，支持批量生成
"""

import os
import gradio as gr
import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

# 导入新闻生成服务
from news_broadcast_demo import NewsBroadcastService

class OptimizedNewsInterface:
    def __init__(self):
        self.service = NewsBroadcastService()
        self.output_base = Path("output/news_broadcast")
        self.output_base.mkdir(parents=True, exist_ok=True)
        
        # 创建分离的存储目录
        self.podcast_dir = self.output_base / "podcasts"
        self.video_dir = self.output_base / "videos"
        self.podcast_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)
    
    def test_existing_files(self) -> Tuple[str, str, str, str, str]:
        """测试函数：返回已存在的文件用于调试Gradio显示"""
        audio_path = self.podcast_dir / "20250910_152942_xiaoxiao_podcast.wav"
        video_path = self.video_dir / "20250910_152942_xiaoxiao_video.mp4"
        
        return (
            "✅ 测试现有文件",
            "这是一个测试播报文稿，用于检查前端显示功能是否正常工作。今天天气不错，适合进行数字人播报测试。感谢您的关注。",
            str(audio_path) if audio_path.exists() else None,
            str(video_path) if video_path.exists() else None,
            f"测试音频: {audio_path.name}\n测试视频: {video_path.name}"
        )
        
    def generate_single_news(self, news_content: str, voice_style: str = "female") -> Tuple[str, str, str, str, str]:
        """生成单个新闻的播报文稿、音频和视频"""
        try:
            if not news_content.strip():
                return "请输入新闻内容", "", None, None, ""
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 使用优化的分离存储结构
            audio_filename = f"{timestamp}_xiaoxiao_podcast.wav"
            video_filename = f"{timestamp}_xiaoxiao_video.mp4"
            
            audio_path = self.podcast_dir / audio_filename
            video_path = self.video_dir / video_filename
            
            # 调用生成服务 - 使用标准接口，现在LiteAvatar应该可以工作了
            result = self.service.generate_news_video(
                news_content=news_content,
                llm_provider="qwen-plus",
                voice_provider="xiaoxiao_zh",
                avatar_provider="xiaohui_teacher",
                category="时政新闻",
                style="正式播报",
                video_quality="high",
                video_format="mp4"
            )
            
            if result.get('status') == 'success':
                # 获取原生成的视频，移动到统一目录结构
                original_video = result.get('video_path')
                logger.info(f"生成服务返回的视频路径: {original_video}")
                
                # 总是查找最新生成的视频文件，因为路径可能不准确
                import shutil
                video_search_paths = [
                    "src/handlers/avatar/liteavatar/algo/liteavatar/output/news_broadcast/videos/",
                    "src/handlers/avatar/liteavatar/algo/liteavatar/output/news_videos/",
                    "output/news_videos/",
                    "output/news_broadcast/videos/"
                ]
                found_video = None
                
                # 首先尝试使用返回的路径
                if original_video and Path(original_video).exists():
                    found_video = Path(original_video)
                    logger.info(f"使用服务返回的视频路径: {found_video}")
                else:
                    logger.warning(f"服务返回的视频路径不存在: {original_video}")
                    # 查找最新生成的视频文件
                    all_video_files = []
                    for search_path in video_search_paths:
                        if Path(search_path).exists():
                            video_files = list(Path(search_path).rglob("*.mp4"))
                            all_video_files.extend(video_files)
                            logger.info(f"在 {search_path} 找到 {len(video_files)} 个视频文件")
                    
                    if all_video_files:
                        # 从所有文件中找到最新的
                        latest_video = max(all_video_files, key=lambda x: x.stat().st_mtime)
                        logger.info(f"找到全局最新视频文件: {latest_video}")
                        found_video = latest_video
                
                if found_video:
                    logger.info(f"复制视频文件从 {found_video} 到 {video_path}")
                    # 确保目标目录存在
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(str(found_video), str(video_path))
                        logger.info(f"✅ 视频文件复制成功: {video_path}")
                    except Exception as copy_error:
                        logger.error(f"视频文件复制失败: {copy_error}")
                else:
                    logger.error("未找到任何视频文件")
                
                # 从metadata中获取TTS生成的音频数据并保存到文件
                metadata = result.get('metadata', {})
                
                # 尝试从生成的音频数据中获取音频
                if hasattr(self.service, '_get_latest_audio_data'):
                    # 这是一个假设的方法，我们需要从服务中获取音频数据
                    pass
                
                # 简化方案：由于TTS音频数据在内存中，我们需要重新生成音频文件
                # 从生成的脚本重新生成音频并保存
                generated_script = ""
                if metadata:
                    script_text = metadata.get('script_text') or metadata.get('generated_script', '')
                    if script_text:
                        generated_script = script_text
                        logger.info(f"使用生成的脚本重新生成音频文件，脚本长度: {len(generated_script)}")
                        
                        # 重新生成音频文件
                        import subprocess
                        import tempfile
                        try:
                            # 创建临时文本文件
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                                f.write(generated_script)
                                text_file = f.name
                            
                            # 确保目标目录存在
                            audio_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # 使用edge-tts生成音频
                            cmd = [
                                'edge-tts',
                                '--voice', 'zh-CN-XiaoxiaoNeural',
                                '--file', text_file,
                                '--write-media', str(audio_path)
                            ]
                            
                            result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                            
                            # 清理临时文件
                            import os
                            os.unlink(text_file)
                            
                            if result_proc.returncode == 0:
                                logger.info("TTS音频文件生成成功")
                            else:
                                logger.error(f"TTS音频生成失败: {result_proc.stderr}")
                                
                        except Exception as e:
                            logger.warning(f"TTS音频生成失败: {e}")
                    else:
                        logger.warning("metadata中未找到播报文稿，无法生成音频")
                
                # 提取生成的播报文稿
                generated_script = ""
                metadata = result.get('metadata', {})
                if metadata:
                    # 从metadata中提取播报文稿
                    script_text = metadata.get('script_text') or metadata.get('generated_script', '')
                    if script_text:
                        generated_script = script_text
                        logger.info(f"成功提取播报文稿，长度: {len(generated_script)} 字符")
                    else:
                        logger.warning("metadata中未找到播报文稿")
                        logger.debug(f"metadata内容: {metadata}")
                
                return (
                    f"✅ 生成成功！",
                    generated_script,
                    str(audio_path) if audio_path.exists() and audio_path.is_file() else None,
                    str(video_path) if video_path.exists() and video_path.is_file() else None, 
                    f"播客音频: {audio_filename}\n数字人视频: {video_filename}"
                )
            else:
                return f"❌ 生成失败: {result.get('message', '未知错误')}", "", None, None, ""
            
        except Exception as e:
            logger.error(f"生成新闻时出错: {e}")
            return f"❌ 生成出错: {str(e)}", "", None, None, ""
    
    def generate_batch_news(self, news_list_text: str, voice_style: str = "female") -> Tuple[str, str]:
        """批量生成新闻列表"""
        try:
            if not news_list_text.strip():
                return "请输入新闻列表", ""
            
            # 解析新闻列表 (按行分割或JSON格式)
            news_items = self._parse_news_list(news_list_text)
            if not news_items:
                return "❌ 无法解析新闻列表", ""
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_id = f"batch_{timestamp}"
            
            results = []
            generated_files = []
            
            for i, news_item in enumerate(news_items):
                try:
                    job_id = f"{batch_id}_item_{i+1:03d}"
                    
                    # 生成音频和视频路径
                    audio_path = self.podcast_dir / f"{job_id}.wav"
                    video_path = self.video_dir / f"{job_id}.mp4"
                    
                    # 调用生成服务
                    result = asyncio.run(self.service.generate_news_video({
                        'title': news_item.get('title', f'新闻{i+1}'),
                        'content': news_item.get('content', news_item.get('text', '')),
                        'voice_style': voice_style,
                        'output_audio': str(audio_path),
                        'output_video': str(video_path)
                    }))
                    
                    if result.get('success'):
                        results.append(f"✅ 第{i+1}条新闻生成成功")
                        if audio_path.exists():
                            generated_files.append(f"音频: {audio_path}")
                        if video_path.exists():
                            generated_files.append(f"视频: {video_path}")
                    else:
                        results.append(f"❌ 第{i+1}条新闻生成失败: {result.get('error', '未知错误')}")
                        
                except Exception as e:
                    results.append(f"❌ 第{i+1}条新闻处理出错: {str(e)}")
            
            summary = f"批量生成完成 (批次ID: {batch_id})\n" + "\n".join(results)
            file_list = "生成的文件:\n" + "\n".join(generated_files) if generated_files else "未生成文件"
            
            return summary, file_list
            
        except Exception as e:
            logger.error(f"批量生成时出错: {e}")
            return f"❌ 批量生成出错: {str(e)}", ""
    
    def _parse_news_list(self, text: str) -> List[Dict[str, str]]:
        """解析新闻列表文本"""
        try:
            # 尝试JSON格式
            data = json.loads(text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'news' in data:
                return data['news']
        except json.JSONDecodeError:
            pass
        
        # 尝试按行分割
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        news_items = []
        
        for i, line in enumerate(lines):
            if line.startswith('{') and line.endswith('}'):
                try:
                    item = json.loads(line)
                    news_items.append(item)
                except json.JSONDecodeError:
                    news_items.append({'title': f'新闻{i+1}', 'content': line})
            else:
                news_items.append({'title': f'新闻{i+1}', 'content': line})
        
        return news_items
    
    def _generate_preview_info(self, job_id: str, content: str) -> str:
        """生成预览信息"""
        return f"""
📝 作业信息:
- ID: {job_id}
- 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 内容长度: {len(content)} 字符
- 存储位置: output/news_broadcast/

🎵 音频文件: audio/podcasts/{job_id}.wav
🎬 视频文件: video/final/{job_id}.mp4
"""
    
    def list_generated_files(self) -> str:
        """列出已生成的文件"""
        try:
            audio_files = list(self.podcast_dir.glob("*.wav"))
            video_files = list(self.video_dir.glob("*.mp4"))
            
            audio_list = "\n".join([f"🎵 {f.name} ({self._get_file_size(f)})" for f in sorted(audio_files, key=lambda x: x.stat().st_mtime, reverse=True)])
            video_list = "\n".join([f"🎬 {f.name} ({self._get_file_size(f)})" for f in sorted(video_files, key=lambda x: x.stat().st_mtime, reverse=True)])
            
            audio_summary = f"音频文件 ({len(audio_files)} 个):\n{audio_list}" if audio_files else "暂无音频文件"
            video_summary = f"视频文件 ({len(video_files)} 个):\n{video_list}" if video_files else "暂无视频文件"
            
            # 返回HTML格式的文件列表
            html_content = f"""
            <div style="padding: 10px;">
                <h3>📁 播客音频文件</h3>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{audio_summary}</pre>
                
                <h3>📽️ 数字人视频文件</h3>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{video_summary}</pre>
            </div>
            """
            return html_content
            
        except Exception as e:
            logger.error(f"列出文件时出错: {e}")
            return "获取文件列表失败", ""
    
    def _get_file_size(self, file_path: Path) -> str:
        """获取文件大小"""
        try:
            size = file_path.stat().st_size
            if size < 1024:
                return f"{size}B"
            elif size < 1024*1024:
                return f"{size/1024:.1f}KB"
            else:
                return f"{size/(1024*1024):.1f}MB"
        except:
            return "未知大小"
    
    def list_generated_files(self) -> str:
        """列出已生成的文件"""
        try:
            html_content = """
            <div style="max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                <h3>📁 已生成的文件</h3>
            """
            
            # 列出播客音频
            html_content += "<h4>🎵 播客音频</h4>"
            if self.podcast_dir.exists():
                podcast_files = sorted(self.podcast_dir.glob("*.wav"), key=lambda x: x.stat().st_mtime, reverse=True)
                if podcast_files:
                    for file_path in podcast_files[:10]:  # 最多显示10个最新文件
                        size = self._get_file_size(file_path)
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        html_content += f"""
                        <div style="margin: 5px 0; padding: 5px; background: #f8f9fa; border-radius: 3px;">
                            📄 {file_path.name}<br>
                            💾 大小: {size} | ⏰ 时间: {mtime}
                        </div>
                        """
                else:
                    html_content += "<p>暂无播客音频文件</p>"
            
            # 列出数字人视频
            html_content += "<h4>🎬 数字人视频</h4>"
            if self.video_dir.exists():
                video_files = sorted(self.video_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
                if video_files:
                    for file_path in video_files[:10]:  # 最多显示10个最新文件
                        size = self._get_file_size(file_path)
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        html_content += f"""
                        <div style="margin: 5px 0; padding: 5px; background: #f8f9fa; border-radius: 3px;">
                            📄 {file_path.name}<br>
                            💾 大小: {size} | ⏰ 时间: {mtime}
                        </div>
                        """
                else:
                    html_content += "<p>暂无数字人视频文件</p>"
            
            html_content += "</div>"
            return html_content
            
        except Exception as e:
            return f"<p>获取文件列表失败: {str(e)}</p>"
    
    def create_interface(self):
        """创建Gradio界面"""
        with gr.Blocks(title="数字人新闻播报系统", theme=gr.themes.Soft()) as demo:
            gr.Markdown("# 🎯 数字人新闻播报系统")
            gr.Markdown("### 📋 输入新闻 → 🤖 LLM生成播报文稿 → 🎵 TTS生成音频 → 🎬 数字人播报视频")
            
            with gr.Tabs():
                # 核心生成流程
                with gr.Tab("📝 新闻播报生成"):
                    # 输入区域
                    with gr.Row():
                        with gr.Column(scale=2):
                            gr.Markdown("## 📋 Step 1: 输入新闻内容")
                            news_input = gr.Textbox(
                                label="新闻原始内容",
                                placeholder="请输入要播报的新闻内容，系统将调用LLM优化为播报文稿...",
                                lines=6
                            )
                            
                            with gr.Row():
                                voice_style = gr.Dropdown(
                                    choices=[("晓晓-中文女声", "xiaoxiao_zh"), ("云健-中文男声", "yunjian_zh"), ("云扬-专业播音", "yunyang_zh")],
                                    value="xiaoxiao_zh",
                                    label="🎵 TTS语音风格"
                                )
                                avatar_style = gr.Dropdown(
                                    choices=[("小慧老师", "xiaohui_teacher"), ("女主播", "news_anchor_female"), ("男主播", "news_anchor_male")],
                                    value="xiaohui_teacher",
                                    label="🎬 数字人形象"
                                )
                            
                            generate_btn = gr.Button("🚀 开始生成播报 (LLM → TTS → 数字人)", variant="primary", size="lg")
                            test_btn = gr.Button("🧪 测试显示现有文件", variant="secondary", size="sm")
                        
                        with gr.Column(scale=1):
                            gr.Markdown("## 📊 生成状态")
                            status_output = gr.Textbox(label="当前进度", interactive=False, lines=3)
                            process_info = gr.HTML("""
                            <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9;">
                                <h4>🔄 生成流程:</h4>
                                <p>1️⃣ LLM优化新闻文稿</p>
                                <p>2️⃣ TTS合成播报音频</p>
                                <p>3️⃣ 数字人渲染播报视频</p>
                            </div>
                            """)
                    
                    # 三个核心输出展示区域
                    gr.Markdown("---")
                    gr.Markdown("## 📤 生成结果")
                    
                    with gr.Row(equal_height=True):
                        with gr.Column():
                            gr.Markdown("### 🤖 Step 2: LLM生成的播报文稿")
                            script_output = gr.Textbox(
                                label="优化后的播报文稿",
                                lines=8,
                                interactive=False,
                                placeholder="LLM将根据输入的新闻内容生成适合播报的专业文稿..."
                            )
                        
                        with gr.Column():
                            gr.Markdown("### 🎵 Step 3: TTS生成的播客音频")
                            audio_output = gr.Audio(
                                label="播客音频文件",
                                interactive=False,
                                show_download_button=True
                            )
                            audio_info = gr.HTML("<div style='padding: 5px; color: #666;'>等待音频生成...</div>")
                        
                        with gr.Column():
                            gr.Markdown("### 🎬 Step 4: 数字人播报视频")
                            video_output = gr.Video(
                                label="数字人播报视频",
                                interactive=False,
                                show_download_button=True
                            )
                            video_info = gr.HTML("<div style='padding: 5px; color: #666;'>等待视频生成...</div>")
                
                # 批量生成
                with gr.Tab("📋 批量生成"):
                    with gr.Row():
                        with gr.Column(scale=2):
                            news_list_input = gr.Textbox(
                                label="新闻列表",
                                placeholder='''请输入新闻列表，支持以下格式:

1. 按行分割:
第一条新闻内容
第二条新闻内容  
第三条新闻内容

2. JSON格式:
[
  {"title": "标题1", "content": "内容1"},
  {"title": "标题2", "content": "内容2"}
]''',
                                lines=12
                            )
                            batch_voice_style = gr.Dropdown(
                                choices=["female", "male", "child"],
                                value="female",
                                label="语音风格"
                            )
                            batch_generate_btn = gr.Button("🎬 批量生成", variant="primary")
                        
                        with gr.Column(scale=1):
                            batch_status = gr.Textbox(label="批量生成状态", lines=8, interactive=False)
                            batch_files = gr.Textbox(label="生成的文件", lines=8, interactive=False)
                
                # 文件管理 - 优化为统一的HTML显示
                with gr.Tab("📁 文件管理"):
                    with gr.Row():
                        refresh_btn = gr.Button("🔄 刷新文件列表", variant="secondary")
                        gr.Markdown("📋 **播客音频**存储在 `output/news_broadcast/podcasts/` | **数字人视频**存储在 `output/news_broadcast/videos/`")
                    
                    files_display = gr.HTML(value=self.list_generated_files(), label="已生成的文件")
            
            # 绑定事件
            generate_btn.click(
                fn=self.generate_single_news,
                inputs=[news_input, voice_style],
                outputs=[status_output, script_output, audio_output, video_output, audio_info]
            )
            
            test_btn.click(
                fn=self.test_existing_files,
                outputs=[status_output, script_output, audio_output, video_output, audio_info]
            )
            
            batch_generate_btn.click(
                fn=self.generate_batch_news,
                inputs=[news_list_input, batch_voice_style],
                outputs=[batch_status, batch_files]
            )
            
            refresh_btn.click(
                fn=self.list_generated_files,
                outputs=[files_display]
            )
            
            # 启动时刷新文件列表
            demo.load(
                fn=self.list_generated_files,
                outputs=[files_display]
            )
        
        return demo

def main():
    """启动优化的前端界面"""
    import os
    
    # 确保输出目录存在
    os.makedirs("output/news_broadcast/podcasts", exist_ok=True)
    os.makedirs("output/news_broadcast/videos", exist_ok=True)
    
    interface = OptimizedNewsInterface()
    demo = interface.create_interface()
    
    # 添加静态文件路径，使Gradio能够访问生成的文件
    demo.launch(
        server_name="0.0.0.0",
        server_port=8444,
        share=False,
        show_error=True,
        allowed_paths=["output/news_broadcast"]  # 允许访问输出目录中的文件
    )

if __name__ == "__main__":
    main()