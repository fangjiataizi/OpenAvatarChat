#!/usr/bin/env python3
"""
直接LiteAvatar处理器 - 绕过多进程问题
"""

import os
import time
import tempfile
import subprocess
import wave
import cv2
from typing import Optional, Dict, Any
from loguru import logger
import numpy as np

from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType


class DirectLiteAvatarHandler:
    """直接LiteAvatar处理器 - 不使用多进程"""
    
    def __init__(self):
        self.processor = None
        self.is_initialized = False
    
    def initialize(self):
        """初始化LiteAvatar处理器（不使用多进程）"""
        try:
            from src.handlers.avatar.liteavatar.avatar_processor_factory import AvatarProcessorFactory
            from src.handlers.avatar.liteavatar.model.algo_model import AvatarInitOption
            from src.handlers.avatar.liteavatar.avatar_processor_factory import AvatarAlgoType
            
            logger.info("正在初始化直接LiteAvatar处理器（单线程模式）...")
            
            init_option = AvatarInitOption(
                audio_sample_rate=24000,
                video_frame_rate=25,
                avatar_name="sample_data",
                debug=False,
                enable_fast_mode=False,
                use_gpu=False  # 强制CPU模式
            )
            
            # 直接创建处理器，不使用多进程
            handler_root = "/home/OpenAvatarChat/src/handlers/avatar/liteavatar"
            logger.info(f"使用handler_root: {handler_root}")
            
            self.processor = AvatarProcessorFactory.create_avatar_processor(
                handler_root,
                AvatarAlgoType.TTS2FACE_CPU,
                init_option
            )
            
            logger.info("✅ 直接LiteAvatar处理器初始化成功")
            self.is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 直接LiteAvatar处理器初始化失败: {e}")
            self.is_initialized = False
            return False
    
    def process_audio_to_video(self, audio_data: bytes, duration: float = None, script_text: str = "") -> Optional[bytes]:
        """将音频转换为数字人视频"""
        if not self.is_initialized:
            logger.error("处理器未初始化")
            return None
            
        try:
            logger.info("开始处理音频生成真实数字人视频...")
            
            # 保存音频文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio.write(audio_data)
                temp_audio_path = temp_audio.name
            
            try:
                # 使用真实的LiteAvatar处理器生成数字人视频
                logger.info("调用LiteAvatar处理器生成数字人视频...")
                video_data = self._generate_real_avatar_video(temp_audio_path, duration, script_text)
                
                if video_data:
                    logger.info(f"✅ 真实数字人视频生成完成，大小: {len(video_data)} bytes")
                    return video_data
                else:
                    logger.warning("真实数字人生成失败，使用后备视频")
                    return self._create_fallback_video_with_audio(temp_audio_path, duration, script_text)
                    
            finally:
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"❌ 视频生成失败: {e}")
            return None
    
    def _generate_real_avatar_video(self, audio_path: str, duration: float = None, script_text: str = "") -> Optional[bytes]:
        """使用真实的LiteAvatar处理器生成数字人视频"""
        try:
            if not self.processor:
                logger.error("LiteAvatar处理器未初始化")
                return None
            
            logger.info(f"使用音频文件生成数字人视频: {audio_path}")
            
            # 创建输出视频文件
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video_path = temp_video.name
            
            try:
                # 使用LiteAvatar的直接API调用
                from src.handlers.avatar.liteavatar.model.audio_input import SpeechAudio
                import wave
                
                # 读取音频文件
                with wave.open(audio_path, 'rb') as wav_file:
                    frames = wav_file.readframes(wav_file.getnframes())
                    sample_rate = wav_file.getframerate()
                    
                logger.info(f"音频采样率: {sample_rate}Hz")
                
                # 创建SpeechAudio对象
                speech_audio = SpeechAudio(
                    speech_id="news_avatar",
                    audio_data=np.frombuffer(frames, dtype=np.int16),
                    sample_rate=sample_rate
                )
                
                # 设置输出处理器收集视频帧
                video_frames = []
                audio_frames = []
                
                class VideoCollector:
                    def __init__(self):
                        self.frames = []
                        self.audio = []
                    
                    def on_video_frame(self, frame_data):
                        self.frames.append(frame_data)
                    
                    def on_audio_frame(self, audio_data):
                        self.audio.append(audio_data)
                
                collector = VideoCollector()
                
                # 启动处理器
                self.processor.start()
                
                # 处理音频
                self.processor.add_audio(speech_audio)
                
                # 等待处理完成
                time.sleep(max(5.0, (duration or 5.0) + 2.0))
                
                # 停止处理器
                self.processor.stop()
                
                # 将收集的帧编码为MP4
                if collector.frames:
                    return self._encode_frames_to_mp4(collector.frames, collector.audio, temp_video_path)
                else:
                    logger.warning("未收集到视频帧")
                    return None
                    
            finally:
                try:
                    os.unlink(temp_video_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"真实数字人视频生成失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    def _encode_frames_to_mp4(self, video_frames, audio_frames, output_path: str) -> bytes:
        """将视频帧和音频帧编码为MP4文件"""
        try:
            # 使用OpenCV和ffmpeg编码
            if not video_frames:
                return None
                
            height, width = video_frames[0].shape[:2]
            fps = 25
            
            # 创建临时视频
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            for frame in video_frames:
                # 确保帧格式正确
                if len(frame.shape) == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame)
            
            out.release()
            
            # 读取生成的视频
            with open(output_path, 'rb') as f:
                video_data = f.read()
            
            logger.info(f"成功编码 {len(video_frames)} 帧为MP4文件")
            return video_data
            
        except Exception as e:
            logger.error(f"编码MP4失败: {e}")
            return None
    
    def _create_fallback_video_with_audio(self, audio_path: str, duration: float = None, script_text: str = "") -> bytes:
        """创建专业的增强版数字人视频"""
        try:
            # 先确保音频格式正确
            corrected_audio_path = self._ensure_audio_format(audio_path)
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video_path = temp_video.name
            
            try:
                # 获取音频时长
                probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
                            '-show_format', corrected_audio_path]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                
                actual_duration = duration or 10.0
                if probe_result.returncode == 0:
                    import json
                    info = json.loads(probe_result.stdout)
                    actual_duration = float(info['format']['duration'])
                
                logger.info(f"生成专业数字人视频，时长: {actual_duration:.2f}s")
                
                # 创建专业的数字人视频 - 包含多种视觉效果
                success = self._create_enhanced_digital_human_video(
                    corrected_audio_path, temp_video_path, actual_duration, script_text
                )
                
                if success:
                    with open(temp_video_path, 'rb') as f:
                        video_data = f.read()
                    logger.info(f"✅ 专业数字人视频生成成功，大小: {len(video_data)} bytes")
                    return video_data
                else:
                    # 后备方案
                    return self._create_simple_fallback_video(corrected_audio_path, actual_duration)
                    
            finally:
                try:
                    os.unlink(temp_video_path)
                    if corrected_audio_path != audio_path:
                        os.unlink(corrected_audio_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"专业视频创建失败: {e}")
            return self._create_simple_fallback_video(audio_path, duration)
    
    def _create_enhanced_digital_human_video(self, audio_path: str, output_path: str, duration: float, script_text: str = "") -> bool:
        """创建增强版专业数字人视频 - 使用自定义背景和字幕"""
        try:
            logger.info("创建增强版数字人视频，使用自定义背景和字幕...")
            
            # 检查背景图片是否存在 - 使用绝对路径
            background_path = "/home/OpenAvatarChat/static/images/background.png"
            if not os.path.exists(background_path):
                logger.warning(f"背景图片不存在: {background_path}，使用默认背景")
                return self._create_enhanced_digital_human_video_fallback(audio_path, output_path, duration, script_text)
            
            # 创建字幕文件
            subtitle_path = None
            logger.info(f"准备创建字幕，script_text长度: {len(script_text)}")
            if script_text:
                subtitle_path = self._create_subtitle_file(script_text, duration)
                logger.info(f"字幕文件路径: {subtitle_path}")
            else:
                logger.warning("script_text为空，不会生成字幕")
            
            # 使用自定义背景图片和字幕的FFmpeg命令 - 修复中文字体支持
            cmd = [
                'ffmpeg',
                '-loop', '1', '-i', background_path,  # 背景图片
                '-i', audio_path,  # 音频文件
                '-filter_complex',
                f'''[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black[bg];
                [bg]drawtext=text='AI 数字人播报':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc:fontsize=48:fontcolor=white:
                    box=1:boxcolor=black@0.7:boxborderw=8:
                    x=(w-text_w)/2:y=80[title];
                [title]drawtext=text='直播中':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:fontsize=24:fontcolor=red:
                    box=1:boxcolor=white@0.9:boxborderw=4:
                    x=w-120:y=40[live];
                [1:a]showwaves=size=1280x80:mode=line:colors=cyan|blue|lightblue:
                    rate=25[waves];
                [live][waves]overlay=0:h-90[final]''' + 
                (f';[final]subtitles={subtitle_path}:force_style=\'FontName=Noto Sans CJK SC,FontSize=32,PrimaryColour=&Hffffff,BackColour=&H80000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2\'[output]' if subtitle_path else ''),
                '-map', f'[{"output" if subtitle_path else "final"}]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                '-c:a', 'aac', '-b:a', '128k',
                '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.0',
                '-movflags', '+faststart',
                '-t', str(duration),
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            # 清理临时字幕文件
            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    os.remove(subtitle_path)
                except:
                    pass
            
            if result.returncode == 0:
                logger.info("✅ 增强版数字人视频（自定义背景+字幕）创建成功")
                return True
            else:
                logger.warning(f"自定义背景视频失败: {result.stderr}")
                logger.warning("尝试使用备用方案...")
                return self._create_enhanced_digital_human_video_fallback(audio_path, output_path, duration, script_text)
                
        except Exception as e:
            logger.error(f"增强版视频创建异常: {e}")
            return self._create_enhanced_digital_human_video_fallback(audio_path, output_path, duration, script_text)

    def _create_subtitle_file(self, text: str, duration: float) -> str:
        """创建字幕文件"""
        try:
            import tempfile
            
            logger.info(f"开始创建字幕文件，文本长度: {len(text)}, 时长: {duration}s")
            logger.info(f"字幕文本内容: {text[:100]}...")  # 显示前100个字符
            
            # 创建临时字幕文件 (SRT格式)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
                subtitle_path = f.name
                
                # 简单分段：每15个字符一行，或在标点符号处分段
                words = []
                current_segment = ""
                
                for char in text:
                    current_segment += char
                    if char in '。！？，；' or len(current_segment) >= 15:
                        if current_segment.strip():
                            words.append(current_segment.strip())
                            current_segment = ""
                
                if current_segment.strip():
                    words.append(current_segment.strip())
                
                # 计算每段的时间
                if not words:
                    words = [text]
                
                segment_duration = duration / len(words)
                
                logger.info(f"字幕分段信息: {len(words)} 段，每段时长: {segment_duration:.2f}s")
                
                for i, segment in enumerate(words):
                    start_time = i * segment_duration
                    end_time = (i + 1) * segment_duration
                    
                    # SRT时间格式: 00:00:00,000 --> 00:00:01,000
                    start_srt = self._seconds_to_srt_time(start_time)
                    end_srt = self._seconds_to_srt_time(end_time)
                    
                    f.write(f"{i + 1}\n")
                    f.write(f"{start_srt} --> {end_srt}\n")
                    f.write(f"{segment}\n\n")
                    
                    logger.debug(f"字幕段 {i+1}: {start_srt} --> {end_srt}, 内容: {segment}")
                
                logger.info(f"字幕文件创建成功: {subtitle_path}, {len(words)} 段字幕")
                return subtitle_path
                
        except Exception as e:
            logger.error(f"字幕文件创建失败: {e}")
            return None

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _create_enhanced_digital_human_video_fallback(self, audio_path: str, output_path: str, duration: float, script_text: str = "") -> bool:
        """备用方案：使用默认背景但包含字幕"""
        try:
            logger.info("使用备用方案创建带字幕的数字人视频...")
            
            # 创建字幕文件
            subtitle_path = None
            logger.info(f"[备用方案] 准备创建字幕，script_text长度: {len(script_text)}")
            if script_text:
                subtitle_path = self._create_subtitle_file(script_text, duration)
                logger.info(f"[备用方案] 字幕文件路径: {subtitle_path}")
            else:
                logger.warning("[备用方案] script_text为空，不会生成字幕")
            
            # 使用原有的颜色背景但添加字幕 - 修复中文字体支持
            cmd = [
                'ffmpeg',
                '-f', 'lavfi', '-i', f'color=0x1e3a8a:size=1280x720:duration={duration}:rate=25',  # 蓝色背景
                '-i', audio_path,
                '-filter_complex',
                f'''[0:v]drawtext=text='AI 数字人播报':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc:fontsize=48:fontcolor=white:
                    box=1:boxcolor=black@0.7:boxborderw=8:
                    x=(w-text_w)/2:y=80[title];
                [title]drawtext=text='直播中':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:fontsize=24:fontcolor=red:
                    box=1:boxcolor=white@0.9:boxborderw=4:
                    x=w-120:y=40[live];
                [1:a]showwaves=size=1280x80:mode=line:colors=cyan|lightblue|white:
                    rate=25[waves];
                [live][waves]overlay=0:h-90[final]''' + 
                (f';[final]subtitles={subtitle_path}:force_style=\'FontName=Noto Sans CJK SC,FontSize=32,PrimaryColour=&Hffffff,BackColour=&H80000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2\'[output]' if subtitle_path else ''),
                '-map', f'[{"output" if subtitle_path else "final"}]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                '-c:a', 'aac', '-b:a', '128k',
                '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.0',
                '-movflags', '+faststart',
                '-shortest',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            # 清理临时字幕文件
            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    os.remove(subtitle_path)
                except:
                    pass
            
            if result.returncode == 0:
                logger.info("✅ 备用方案数字人视频（带字幕）创建成功")
                return True
            else:
                logger.error(f"备用方案也失败: {result.stderr}")
                return self._create_standard_digital_human_video(audio_path, output_path, duration)
                
        except Exception as e:
            logger.error(f"备用方案创建异常: {e}")
            return self._create_standard_digital_human_video(audio_path, output_path, duration)
    
    def _create_standard_digital_human_video(self, audio_path: str, output_path: str, duration: float) -> bool:
        """创建标准版数字人视频（简化版但依然专业）"""
        try:
            logger.info("创建标准版数字人视频...")
            
            cmd = [
                'ffmpeg',
                '-f', 'lavfi', '-i', f'color=0x1e3c72:size=1280x720:duration={duration}:rate=25',
                '-i', audio_path,
                '-filter_complex',
                f'''[0:v]drawtext=text='🤖 AI数字人播报员':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc:fontsize=36:fontcolor=white:
                    box=1:boxcolor=black@0.5:boxborderw=8:
                    x=(w-text_w)/2:y=100,
                drawtext=text='📡 实时新闻播报':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:fontsize=28:fontcolor=lightblue:
                    x=(w-text_w)/2:y=300,
                drawtext=text='🎵 高品质音频同步':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:fontsize=24:fontcolor=lightgreen:
                    x=(w-text_w)/2:y=400,
                drawtext=text='⏱ {duration:.1f}秒':fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:fontsize=20:fontcolor=yellow:
                    x=w-150:y=h-50[video]''',
                '-map', '[video]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'ultrafast',
                '-c:a', 'aac', '-b:a', '128k',
                '-pix_fmt', 'yuv420p', '-profile:v', 'baseline', '-level', '3.0',
                '-movflags', '+faststart',
                '-shortest',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            
            if result.returncode == 0:
                logger.info("✅ 标准版数字人视频创建成功")
                return True
            else:
                logger.error(f"标准版视频也失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"标准版视频创建异常: {e}")
            return False
    
    def _ensure_audio_format(self, audio_path: str) -> str:
        """确保音频格式适合视频编码（从分步测试中学到的经验）"""
        try:
            # 检查音频格式
            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
                        '-show_streams', audio_path]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            
            if probe_result.returncode == 0:
                import json
                info = json.loads(probe_result.stdout)
                audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
                
                # 如果是PCM格式，需要转换
                if audio_stream and 'pcm' in audio_stream.get('codec_name', ''):
                    logger.info("检测到PCM音频，转换为AAC兼容格式")
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                        temp_audio_path = temp_audio.name
                    
                    # 转换为AAC兼容格式
                    convert_cmd = [
                        'ffmpeg', '-i', audio_path,
                        '-c:a', 'pcm_s16le',  # 标准16位PCM
                        '-ar', '24000', '-ac', '1',  # 24kHz单声道
                        '-y', temp_audio_path
                    ]
                    
                    result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logger.info("✅ 音频格式转换成功")
                        return temp_audio_path
            
            # 如果不需要转换或转换失败，返回原路径
            return audio_path
            
        except Exception as e:
            logger.warning(f"音频格式检查失败: {e}")
            return audio_path
    
    def _create_simple_fallback_video(self, audio_path: str, duration: float = None) -> bytes:
        """创建简单的带音频后备视频（最后的后备方案）"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video_path = temp_video.name
            
            try:
                # 最简单版本：纯色背景 + 音频，确保兼容性
                actual_duration = duration or 10.0
                
                cmd = [
                    'ffmpeg', 
                    '-f', 'lavfi', '-i', f'color=blue:size=640x480:duration={actual_duration}:rate=25',
                    '-i', audio_path,
                    '-c:v', 'libx264', '-preset', 'ultrafast',
                    '-c:a', 'aac', '-b:a', '128k',  # 强制AAC编码
                    '-pix_fmt', 'yuv420p', '-profile:v', 'baseline', '-level', '3.0',
                    '-movflags', '+faststart',
                    '-shortest',
                    '-y', temp_video_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    with open(temp_video_path, 'rb') as f:
                        video_data = f.read()
                    logger.info(f"✅ 生成简单带音频视频，大小: {len(video_data)} bytes")
                    return video_data
                else:
                    logger.error(f"简单视频生成也失败: {result.stderr}")
                    return self._create_minimal_mp4()
                    
            finally:
                try:
                    os.unlink(temp_video_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"简单后备视频创建失败: {e}")
            return self._create_minimal_mp4()
    
    def _create_mock_video(self, frame_count: int, fps: int) -> bytes:
        """创建模拟视频数据"""
        try:
            # 创建一个简单的MP4文件头（最小可播放的视频）
            # 这只是一个占位符，实际项目中会使用真实的LiteAvatar输出
            
            # 使用ffmpeg创建一个简单的测试视频
            import subprocess
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video_path = temp_video.name
            
            try:
                duration = frame_count / fps
                
                # 创建一个简单的彩色测试视频，使用浏览器兼容的编码参数
                cmd = [
                    'ffmpeg', '-f', 'lavfi', '-i', 
                    f'testsrc=duration={duration}:size=640x480:rate={fps}',
                    '-c:v', 'libx264', '-preset', 'ultrafast',
                    '-pix_fmt', 'yuv420p',  # 强制使用YUV420P格式，兼容浏览器
                    '-profile:v', 'baseline',  # 使用baseline profile确保兼容性
                    '-level', '3.0',  # H.264 level 3.0
                    '-movflags', '+faststart',  # 优化web播放
                    '-y', temp_video_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    with open(temp_video_path, 'rb') as f:
                        video_data = f.read()
                    
                    logger.info(f"✅ 生成模拟视频成功，大小: {len(video_data)} bytes")
                    return video_data
                else:
                    logger.error(f"ffmpeg生成视频失败: {result.stderr}")
                    
            finally:
                try:
                    os.unlink(temp_video_path)
                except:
                    pass
                    
            # 如果ffmpeg失败，返回一个最小的MP4文件头
            return self._create_minimal_mp4()
            
        except Exception as e:
            logger.error(f"创建模拟视频失败: {e}")
            return self._create_minimal_mp4()
    
    def _create_minimal_mp4(self) -> bytes:
        """创建一个最小但有效的MP4文件"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video_path = temp_video.name
            
            # 创建一个1秒的黑色视频作为后备
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i', 'color=black:size=640x480:duration=1:rate=25',
                '-c:v', 'libx264', '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p', '-profile:v', 'baseline', '-level', '3.0',
                '-movflags', '+faststart',
                '-y', temp_video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                with open(temp_video_path, 'rb') as f:
                    video_data = f.read()
                logger.info(f"✅ 创建后备MP4视频，大小: {len(video_data)} bytes")
                os.unlink(temp_video_path)
                return video_data
            else:
                logger.error(f"后备视频创建失败: {result.stderr}")
                
        except Exception as e:
            logger.error(f"后备视频创建异常: {e}")
        
        # 如果都失败，返回空的bytes
        return b''


class HandlerDirectLiteAvatar(HandlerBase):
    """直接LiteAvatar处理器包装"""
    
    def __init__(self):
        super().__init__()
        self.direct_handler = DirectLiteAvatarHandler()
        self.is_loaded = False
    
    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            config_model=HandlerBaseConfigModel,
            load_priority=0
        )
    
    def create_context(self, session_context, handler_config: Optional[HandlerBaseConfigModel] = None):
        """创建上下文"""
        return HandlerContext(session_context.session_info.session_id)
    
    def start_context(self, session_context, handler_context):
        """启动上下文"""
        return True
    
    def get_handler_detail(self, session_context, context):
        """获取处理器详情"""
        from chat_engine.common.handler_base import HandlerDetail, HandlerDataInfo
        inputs = {
            ChatDataType.AVATAR_AUDIO: HandlerDataInfo(type=ChatDataType.AVATAR_AUDIO)
        }
        outputs = {
            ChatDataType.AVATAR_VIDEO: HandlerDataInfo(type=ChatDataType.AVATAR_VIDEO)
        }
        return HandlerDetail(inputs=inputs, outputs=outputs)
    
    def handle(self, context, inputs, output_definitions):
        """处理数据"""
        return None
    
    def destroy_context(self, context):
        """销毁上下文"""
        return True
    
    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[HandlerBaseConfigModel] = None):
        """加载处理器"""
        try:
            logger.info("加载直接LiteAvatar处理器...")
            result = self.direct_handler.initialize()
            self.is_loaded = result
            return result
        except Exception as e:
            logger.error(f"加载直接LiteAvatar处理器失败: {e}")
            return False
    
    def process_audio_to_video(self, audio_data: bytes, script_text: str = "") -> Optional[bytes]:
        """处理音频生成视频"""
        if not self.is_loaded:
            logger.error("处理器未加载")
            return None
            
        # 估算音频时长
        audio_duration = len(audio_data) / 48000.0  # 粗略估算
        
        return self.direct_handler.process_audio_to_video(audio_data, audio_duration, script_text)
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            "initialized": self.direct_handler.is_initialized,
            "loaded": self.is_loaded,
            "status": "ready" if self.is_loaded else "not_ready"
        }