#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI教学平台融合系统启动脚本
整合用户管理 + AI教学 + 数据存储的完整平台
"""

import os
import sys
import time
import threading
import subprocess
import uvicorn
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# 导入融合的组件
from src.api.integrated_teaching_api import app as api_app
from src.frontend.integrated_frontend import create_integrated_interface
from src.storage.database.connection import db_manager
from src.storage.cache.redis_client import cache_manager


class IntegratedTeachingPlatform:
    """集成教学平台启动器"""
    
    def __init__(self):
        self.api_port = 8001
        self.frontend_port = 7860
        self.api_process = None
        self.frontend_interface = None
        
    def check_dependencies(self) -> bool:
        """检查系统依赖"""
        logger.info("🔍 检查系统依赖...")
        
        try:
            # 检查PostgreSQL
            db_healthy = db_manager.health_check()
            if db_healthy:
                logger.info("✅ PostgreSQL 数据库连接正常")
            else:
                logger.error("❌ PostgreSQL 数据库连接失败")
                return False
            
            # 检查Redis
            try:
                cache_manager.ping()
                logger.info("✅ Redis 缓存服务正常")
            except Exception as e:
                logger.warning(f"⚠️  Redis 连接失败: {e}")
                logger.info("💡 系统将使用内存缓存模式")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 依赖检查失败: {e}")
            return False
    
    def initialize_database(self):
        """初始化数据库"""
        logger.info("📊 初始化数据库...")
        
        try:
            # 确保数据库表创建
            db_manager.initialize()
            logger.info("✅ 数据库表初始化完成")
            
            # 创建测试数据
            self._create_test_data()
            
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise
    
    def _create_test_data(self):
        """创建测试数据"""
        try:
            from src.storage.services.user_service import user_service
            from src.storage.services.course_service import course_service
            
            # 创建管理员账户
            admin_result = user_service.create_user({
                "username": "admin",
                "email": "admin@teaching.ai",
                "password": "admin123",
                "role": "admin",
                "grade_level": "管理员",
                "is_active": True
            })
            
            if admin_result["success"]:
                logger.info("✅ 管理员账户创建成功 (admin/admin123)")
            
            # 创建学生测试账户
            student_result = user_service.create_user({
                "username": "student1",
                "email": "student1@test.com", 
                "password": "123456",
                "role": "student",
                "grade_level": "小学三年级",
                "learning_preferences": {
                    "learning_style": "混合型",
                    "difficulty_preference": 3,
                    "favorite_subjects": ["数学", "英语"]
                },
                "is_active": True
            })
            
            if student_result["success"]:
                logger.info("✅ 学生测试账户创建成功 (student1/123456)")
            
            # 创建示例课程
            sample_courses = [
                {
                    "name": "小学数学 - 加减法基础",
                    "subject": "数学",
                    "grade_level": "小学三年级",
                    "difficulty_level": 2,
                    "description": "学习两位数以内的加减法运算，培养数学基础思维",
                    "teaching_objectives": ["掌握加减法运算", "理解数的概念", "培养逻辑思维"],
                    "knowledge_points": ["加法运算", "减法运算", "进位借位", "实际应用"],
                    "estimated_duration": 30,
                    "ai_teacher_prompt": "你是一位耐心的小学数学老师，专门教授加减法。用简单易懂的语言，结合生活实例来解释数学概念。",
                    "is_active": True
                },
                {
                    "name": "小学语文 - 汉字识字",
                    "subject": "语文", 
                    "grade_level": "小学三年级",
                    "difficulty_level": 2,
                    "description": "学习常用汉字的识读和书写，掌握基本笔画顺序",
                    "teaching_objectives": ["认识常用汉字", "掌握笔画顺序", "理解字义"],
                    "knowledge_points": ["汉字结构", "笔画顺序", "部首偏旁", "组词造句"],
                    "estimated_duration": 25,
                    "ai_teacher_prompt": "你是一位温和的语文老师，擅长通过故事和图画来教授汉字。注重激发学生的学习兴趣。",
                    "is_active": True
                },
                {
                    "name": "小学英语 - 基础单词",
                    "subject": "英语",
                    "grade_level": "小学三年级", 
                    "difficulty_level": 2,
                    "description": "学习日常生活中的基础英语单词和简单对话",
                    "teaching_objectives": ["掌握基础词汇", "简单英语对话", "正确发音"],
                    "knowledge_points": ["日常词汇", "简单句型", "发音练习", "情景对话"],
                    "estimated_duration": 20,
                    "ai_teacher_prompt": "你是一位活泼的英语老师，善于用游戏和互动的方式教学。多鼓励学生开口说英语。",
                    "is_active": True
                }
            ]
            
            created_count = 0
            for course_data in sample_courses:
                result = course_service.create_course(course_data)
                if result["success"]:
                    created_count += 1
            
            logger.info(f"✅ 创建了 {created_count} 个示例课程")
            
        except Exception as e:
            logger.warning(f"⚠️  测试数据创建失败: {e}")
    
    def start_api_server(self):
        """启动API服务器"""
        logger.info(f"🚀 启动API服务器 (端口: {self.api_port})...")
        
        def run_api():
            uvicorn.run(
                api_app,
                host="0.0.0.0",
                port=self.api_port,
                log_level="info",
                access_log=False  # 减少日志噪音
            )
        
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        
        # 等待API服务器启动
        time.sleep(3)
        logger.info(f"✅ API服务器已启动: http://localhost:{self.api_port}")
        
        return api_thread
    
    def start_frontend(self):
        """启动前端界面"""
        logger.info(f"🎨 启动前端界面 (端口: {self.frontend_port})...")
        
        try:
            # 创建融合界面
            interface = create_integrated_interface()
            
            # 启动Gradio界面
            interface.launch(
                server_name="0.0.0.0",
                server_port=self.frontend_port,
                share=False,
                show_error=True,
                quiet=False,
                show_api=False
            )
            
        except Exception as e:
            logger.error(f"❌ 前端启动失败: {e}")
            raise
    
    def run(self):
        """运行完整平台"""
        logger.info("🎓 启动AI教学平台融合系统...")
        
        try:
            # 1. 检查依赖
            if not self.check_dependencies():
                logger.error("❌ 依赖检查失败，无法启动")
                return False
            
            # 2. 初始化数据库
            self.initialize_database()
            
            # 3. 启动API服务器
            api_thread = self.start_api_server()
            
            # 4. 启动前端界面
            logger.info("🌟 系统启动完成！")
            logger.info("=" * 60)
            logger.info("📱 前端界面: http://localhost:7860")
            logger.info("🔧 API文档:  http://localhost:8001/docs")
            logger.info("🎯 测试账户:")
            logger.info("   管理员: admin / admin123")
            logger.info("   学生:   student1 / 123456")
            logger.info("=" * 60)
            
            self.start_frontend()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("👋 用户中断，正在关闭系统...")
            return True
        except Exception as e:
            logger.error(f"❌ 系统启动失败: {e}")
            return False


def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 启动平台
    platform = IntegratedTeachingPlatform()
    success = platform.run()
    
    if success:
        logger.info("✅ AI教学平台已安全关闭")
    else:
        logger.error("❌ AI教学平台启动失败")
        sys.exit(1)


if __name__ == "__main__":
    main() 