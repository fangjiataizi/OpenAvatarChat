#!/usr/bin/env python3
"""
新闻播报批量生成API
提供RESTful接口支持批量生成播客音频和数字人视频
"""

import os
import sys
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from news_broadcast_demo import NewsBroadcastService

class NewsItem(BaseModel):
    """单个新闻项目"""
    title: str = Field(..., description="新闻标题")
    content: str = Field(..., description="新闻内容") 
    category: Optional[str] = Field(None, description="新闻分类")
    priority: Optional[int] = Field(1, description="优先级")

class BatchGenerationRequest(BaseModel):
    """批量生成请求"""
    news_list: List[NewsItem] = Field(..., description="新闻列表")
    voice_style: str = Field("female", description="语音风格")
    video_quality: str = Field("standard", description="视频质量")
    batch_name: Optional[str] = Field(None, description="批次名称")

class GenerationStatus(BaseModel):
    """生成状态"""
    batch_id: str
    status: str  # pending, processing, completed, failed
    progress: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]] = []

class NewsBroadcastAPI:
    """新闻播报API服务"""
    
    def __init__(self):
        self.service = NewsBroadcastService()
        self.app = FastAPI(
            title="数字人新闻播报API",
            description="批量生成播客音频和数字人视频",
            version="1.0.0"
        )
        self.output_base = Path("output/news_broadcast")
        self.output_base.mkdir(parents=True, exist_ok=True)
        
        # 任务状态存储
        self.job_status: Dict[str, GenerationStatus] = {}
        
        self._setup_routes()
        self._setup_static_files()
    
    def _setup_static_files(self):
        """设置静态文件服务"""
        # 分别挂载播客音频和视频文件服务
        self.app.mount("/files/podcasts", StaticFiles(directory="output/news_broadcast/podcasts"), name="podcasts")
        self.app.mount("/files/videos", StaticFiles(directory="output/news_broadcast/videos"), name="videos")
        self.app.mount("/files", StaticFiles(directory="output/news_broadcast"), name="files")
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.get("/")
        async def root():
            return {"message": "数字人新闻播报API服务", "version": "1.0.0"}
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": datetime.now()}
        
        @self.app.post("/generate/single")
        async def generate_single_news(
            title: str,
            content: str,
            voice_style: str = "female",
            background_tasks: BackgroundTasks = None
        ):
            """生成单个新闻播报"""
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                job_id = f"single_{timestamp}"
                
                # 创建任务状态
                self.job_status[job_id] = GenerationStatus(
                    batch_id=job_id,
                    status="processing",
                    progress={"current": 0, "total": 1},
                    created_at=datetime.now()
                )
                
                # 生成文件路径 - 使用优化的目录结构
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_filename = f"{timestamp}_{voice_style}_podcast.wav"
                video_filename = f"{timestamp}_{voice_style}_video.mp4"
                
                audio_path = self.output_base / "podcasts" / audio_filename
                video_path = self.output_base / "videos" / video_filename
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                video_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 调用生成服务 - 使用原有标准接口
                result = self.service.generate_news_video(
                    news_content=content,
                    llm_provider="qwen-plus",
                    voice_provider=voice_style,
                    avatar_provider="xiaohui_teacher",
                    category="时政新闻",
                    style="正式播报",
                    video_quality="high",
                    video_format="mp4"
                )
                
                if result.get('status') == 'success':
                    # 获取原生成的视频文件
                    original_video = result.get('video_path')
                    if original_video and Path(original_video).exists():
                        # 移动到统一的目录结构
                        import shutil
                        shutil.move(original_video, video_path)
                        
                        # 从视频提取音频
                        try:
                            import subprocess
                            subprocess.run([
                                "ffmpeg", "-i", str(video_path), 
                                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                                str(audio_path), "-y"
                            ], check=True, capture_output=True)
                        except Exception as e:
                            logger.warning(f"音频提取失败: {e}")
                    
                    self.job_status[job_id].status = "completed"
                    self.job_status[job_id].completed_at = datetime.now()
                    self.job_status[job_id].results = [{
                        "title": title,
                        "audio_url": f"/files/podcasts/{audio_filename}" if audio_path.exists() else None,
                        "video_url": f"/files/videos/{video_filename}" if video_path.exists() else None,
                        "success": True
                    }]
                    
                    return JSONResponse({
                        "success": True,
                        "job_id": job_id,
                        "audio_url": f"/files/podcasts/{audio_filename}" if audio_path.exists() else None,
                        "video_url": f"/files/videos/{video_filename}" if video_path.exists() else None
                    })
                else:
                    self.job_status[job_id].status = "failed"
                    raise HTTPException(status_code=500, detail=result.get('error', '生成失败'))
                    
            except Exception as e:
                logger.error(f"生成单个新闻失败: {e}")
                if job_id in self.job_status:
                    self.job_status[job_id].status = "failed"
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/generate/batch")
        async def generate_batch_news(
            request: BatchGenerationRequest,
            background_tasks: BackgroundTasks
        ):
            """批量生成新闻播报"""
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                batch_id = f"batch_{timestamp}"
                if request.batch_name:
                    batch_id = f"batch_{request.batch_name}_{timestamp}"
                
                # 创建任务状态
                self.job_status[batch_id] = GenerationStatus(
                    batch_id=batch_id,
                    status="pending",
                    progress={"current": 0, "total": len(request.news_list)},
                    created_at=datetime.now()
                )
                
                # 添加后台任务
                background_tasks.add_task(
                    self._process_batch_generation,
                    batch_id,
                    request.news_list,
                    request.voice_style,
                    request.video_quality
                )
                
                return JSONResponse({
                    "success": True,
                    "batch_id": batch_id,
                    "status": "pending",
                    "total_items": len(request.news_list),
                    "status_url": f"/status/{batch_id}"
                })
                
            except Exception as e:
                logger.error(f"启动批量生成失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/status/{batch_id}")
        async def get_generation_status(batch_id: str):
            """获取生成状态"""
            if batch_id not in self.job_status:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            status = self.job_status[batch_id]
            return JSONResponse({
                "batch_id": batch_id,
                "status": status.status,
                "progress": status.progress,
                "created_at": status.created_at.isoformat(),
                "completed_at": status.completed_at.isoformat() if status.completed_at else None,
                "results": status.results
            })
        
        @self.app.get("/download/audio/{filename}")
        async def download_audio(filename: str):
            """下载音频文件"""
            file_path = self.output_base / "audio" / "podcasts" / filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            return FileResponse(file_path, media_type="audio/wav")
        
        @self.app.get("/download/video/{filename}")  
        async def download_video(filename: str):
            """下载视频文件"""
            file_path = self.output_base / "video" / "final" / filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            return FileResponse(file_path, media_type="video/mp4")
        
        @self.app.get("/list/files")
        async def list_generated_files():
            """列出已生成的文件"""
            try:
                audio_files = []
                video_files = []
                
                audio_dir = self.output_base / "audio" / "podcasts"
                if audio_dir.exists():
                    for f in audio_dir.glob("*.wav"):
                        stat = f.stat()
                        audio_files.append({
                            "filename": f.name,
                            "size": stat.st_size,
                            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "download_url": f"/download/audio/{f.name}"
                        })
                
                video_dir = self.output_base / "video" / "final"
                if video_dir.exists():
                    for f in video_dir.glob("*.mp4"):
                        stat = f.stat()
                        video_files.append({
                            "filename": f.name,
                            "size": stat.st_size,
                            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "download_url": f"/download/video/{f.name}"
                        })
                
                return JSONResponse({
                    "audio_files": sorted(audio_files, key=lambda x: x["created_at"], reverse=True),
                    "video_files": sorted(video_files, key=lambda x: x["created_at"], reverse=True)
                })
                
            except Exception as e:
                logger.error(f"列出文件失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_batch_generation(
        self,
        batch_id: str,
        news_list: List[NewsItem],
        voice_style: str,
        video_quality: str
    ):
        """处理批量生成任务"""
        try:
            self.job_status[batch_id].status = "processing"
            results = []
            
            for i, news_item in enumerate(news_list):
                try:
                    job_id = f"{batch_id}_item_{i+1:03d}"
                    
                    # 更新进度
                    self.job_status[batch_id].progress["current"] = i
                    
                    # 生成文件路径 - 使用优化的目录结构
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") 
                    audio_filename = f"{timestamp}_{voice_style}_{i+1:03d}_podcast.wav"
                    video_filename = f"{timestamp}_{voice_style}_{i+1:03d}_video.mp4"
                    
                    audio_path = self.output_base / "podcasts" / audio_filename
                    video_path = self.output_base / "videos" / video_filename
                    
                    # 调用生成服务 - 使用标准接口
                    result = self.service.generate_news_video(
                        news_content=news_item.content,
                        llm_provider="qwen-plus",
                        voice_provider=voice_style,
                        avatar_provider="xiaohui_teacher",
                        category="时政新闻",
                        style="正式播报",
                        video_quality="high",
                        video_format="mp4"
                    )
                    
                    # 处理生成结果，移动文件到统一结构
                    success = False
                    if result.get('status') == 'success':
                        original_video = result.get('video_path')
                        if original_video and Path(original_video).exists():
                            import shutil
                            shutil.move(original_video, video_path)
                            
                            # 提取音频
                            try:
                                import subprocess
                                subprocess.run([
                                    "ffmpeg", "-i", str(video_path), 
                                    "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                                    str(audio_path), "-y"
                                ], check=True, capture_output=True)
                                success = True
                            except Exception as e:
                                logger.warning(f"批量生成第{i+1}项音频提取失败: {e}")
                                success = True  # 视频成功就算成功
                    
                    results.append({
                        "item_index": i + 1,
                        "title": news_item.title,
                        "success": success,
                        "audio_url": f"/files/podcasts/{audio_filename}" if audio_path.exists() else None,
                        "video_url": f"/files/videos/{video_filename}" if video_path.exists() else None,
                        "error": result.get('message') if not success else None
                    })
                    
                except Exception as e:
                    logger.error(f"处理第{i+1}条新闻失败: {e}")
                    results.append({
                        "item_index": i + 1,
                        "title": news_item.title,
                        "success": False,
                        "error": str(e)
                    })
            
            # 完成任务
            self.job_status[batch_id].status = "completed"
            self.job_status[batch_id].completed_at = datetime.now()
            self.job_status[batch_id].progress["current"] = len(news_list)
            self.job_status[batch_id].results = results
            
        except Exception as e:
            logger.error(f"批量生成任务失败: {e}")
            self.job_status[batch_id].status = "failed"
            self.job_status[batch_id].results = [{"error": str(e)}]

def create_app():
    """创建FastAPI应用"""
    api = NewsBroadcastAPI()
    return api.app

def main():
    """启动API服务"""
    app = create_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        reload=False
    )

if __name__ == "__main__":
    main()