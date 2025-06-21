#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI在线教学平台演示程序 - 主启动文件
基于OpenAvatarChat项目开发的1v1数字人教学系统

采用前后端分离架构：
- Frontend: 负责Gradio界面定义和交互
- Backend: 负责业务逻辑、数据处理和ChatEngine集成  
- API: 负责连接前后端的接口定义
"""

import sys
import argparse
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from loguru import logger

from engine_utils.directory_info import DirectoryInfo
from service.service_utils.service_config_loader import load_configs

# 确保项目目录在路径中
project_dir = DirectoryInfo.get_project_dir()
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# 导入分离后的模块
from src.api.teaching_api import teaching_api


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="AI在线教学平台")
    parser.add_argument("--host", type=str, help="服务主机地址")
    parser.add_argument("--port", type=int, help="服务端口")
    parser.add_argument("--config", type=str, default="config/teaching_basic.yaml", help="配置文件路径")
    parser.add_argument("--env", type=str, default="default", help="配置环境")
    return parser.parse_args()


def create_fastapi_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(title="AI在线教学平台", description="基于数字人的1v1在线教学系统")
    
    @app.get("/")
    def get_root():
        return RedirectResponse(url="/ui")

    @app.get("/ui/static/fonts/system-ui/system-ui-Regular.woff2")
    @app.get("/ui/static/fonts/ui-sans-serif/ui-sans-serif-Regular.woff2")
    @app.get("/favicon.ico")
    def get_font():
        # 移除字体请求错误
        return {}
    
    return app


def setup_teaching_platform():
    """设置教学平台"""
    # 创建FastAPI应用
    app = create_fastapi_app()
    
    # 创建Gradio界面（在这个过程中会自动绑定事件）
    gradio_block, components, rtc_container = teaching_api.frontend.create_gradio_interface()
    
    logger.info("Teaching platform setup completed")
    return app, gradio_block, rtc_container, components


def main():
    """主函数"""
    args = parse_args()
    
    # 加载配置
    logger_config, service_config, engine_config = load_configs(args)
    logger.info("Configuration loaded successfully")

    # 设置教学平台
    app, demo, rtc_container, components = setup_teaching_platform()
    
    # 初始化后端系统
    success = teaching_api.initialize(engine_config, app, demo, rtc_container)
    
    if success:
        logger.info("Teaching platform initialized successfully")
    else:
        logger.warning("Teaching platform initialization failed, running in limited mode")

    # 启动服务
    try:
        demo.launch(
            server_name=args.host,
            server_port=args.port,
            ssl_keyfile=service_config.cert_key if hasattr(service_config, 'cert_key') else None,
            ssl_certfile=service_config.cert_file if hasattr(service_config, 'cert_file') else None,
            ssl_verify=False
        )
    except KeyboardInterrupt:
        logger.info("Shutting down teaching platform...")
        teaching_api.stop()
    except Exception as e:
        logger.error(f"Error starting teaching platform: {e}")
        teaching_api.stop()
        raise


if __name__ == "__main__":
    main()