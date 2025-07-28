#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台演示程序 - 统一版本
基于OpenAvatarChat项目开发的1v1数字人教学系统

功能特色：
- AI数字人教学与实时音视频交互
- 主动教学系统 (开始学习后立即问候，15秒后开始主动教学)
- 丰富的教学内容库 (雅思语法、词汇、写作、口语)
- 数据存储和会话管理
- WebRTC通讯支持
- 响应式前端界面
"""

import sys
import os
import argparse
import time
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from loguru import logger

# 确保项目目录在路径中
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from engine_utils.directory_info import DirectoryInfo
from service.service_utils.service_config_loader import load_configs

# 导入统一的模块
from teaching_api import teaching_api


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="AI在线教学平台 - 统一版本")
    parser.add_argument("--host", type=str, help="服务主机地址")
    parser.add_argument("--port", type=int, help="服务端口")
    parser.add_argument("--config", type=str, default="config/teaching.yaml", help="配置文件路径")
    parser.add_argument("--env", type=str, default="default", help="配置环境")
    return parser.parse_args()


def create_fastapi_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="🎓 AI在线教学平台", 
        description="基于数字人的1v1在线教学系统 - 统一版本",
        version="1.0.0"
    )

    @app.get("/")
    def get_root():
        return RedirectResponse(url="/ui")

    @app.get("/ui/static/fonts/system-ui/system-ui-Regular.woff2")
    @app.get("/ui/static/fonts/ui-sans-serif/ui-sans-serif-Regular.woff2")
    @app.get("/favicon.ico")
    def get_font():
        # 移除字体请求错误
        return {}

    @app.get("/health")
    def health_check():
        """健康检查端点"""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0",
            "features": [
                "AI数字人教学",
                "主动教学系统", 
                "实时音视频交互",
                "数据存储",
                "WebRTC通讯"
            ]
        }

    return app


def setup_teaching_platform():
    """设置教学平台"""
    logger.info("🚀 Setting up Unified Teaching Platform...")
    
    # 创建FastAPI应用
    app = create_fastapi_app()
                
    # 创建Gradio界面（在这个过程中会自动绑定事件）
    gradio_block, components, rtc_container = teaching_api.frontend.create_gradio_interface()
    
    logger.info("✅ Unified Teaching platform setup completed")
    return app, gradio_block, rtc_container, components

def main():
    """主函数"""
    print("🎓 AI在线教学平台 - 统一版本启动中...")
    print("=" * 60)
    
    args = parse_args()
    
    # 加载配置
    logger_config, service_config, engine_config = load_configs(args)
    logger.info("Configuration loaded successfully")

    # 强制启用存储层
    storage_enabled = True
    logger.info("✅ Storage layer enabled for enhanced features")

    # 设置教学平台
    app, demo, rtc_container, components = setup_teaching_platform()

    # 初始化后端系统
    success = teaching_api.initialize(engine_config, app, demo, rtc_container, storage_enabled)
    
    if success:
        logger.info("🎉 Teaching platform initialized successfully")
    else:
        logger.warning("⚠️  Teaching platform initialization failed, running in limited mode")

    # 打印启动信息
    host = args.host or getattr(service_config, 'host', '0.0.0.0')
    port = args.port or getattr(service_config, 'port', 8443)
    
    print("\n🌟 统一版AI在线教学平台启动信息:")
    print(f"📱 访问地址: https://{host}:{port}")
    print("🎓 功能特色:")
    print("   ✅ AI数字人教学 - 智能个性化教学")
    print("   ✅ 主动教学系统 - 开始学习后立即问候和主动教学")
    print("   ✅ 丰富内容库 - 雅思语法、词汇、写作、口语")
    print("   ✅ 实时音视频 - WebRTC高质量通讯")
    print("   ✅ 数据存储 - 学习记录持久化")
    print("   ✅ 响应式界面 - 现代化用户体验")
    print("\n🎯 教学体验:")
    print("   1. 选择课程和难度")
    print("   2. 点击'开始学习'")
    print("   3. AI教师立即个性化问候")
    print("   4. 15秒后开始主动教学")
    print("   5. 每30-45秒发送新教学内容")
    print("=" * 60)

    # 启动服务
    try:
        demo.launch(
            server_name=host,
            server_port=port,
            ssl_keyfile=getattr(service_config, 'cert_key', None),
            ssl_certfile=getattr(service_config, 'cert_file', None),
            ssl_verify=False,
            show_api=False,
            share=False
        )
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down teaching platform...")
        teaching_api.stop()
    except Exception as e:
        logger.error(f"❌ Error starting teaching platform: {e}")
        teaching_api.stop()
        raise


if __name__ == "__main__":
    main()