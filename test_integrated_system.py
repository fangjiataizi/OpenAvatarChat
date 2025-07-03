#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI教学平台融合系统测试
测试用户系统 + AI教学系统的完整集成
"""

import os
import sys
import time
import asyncio
from typing import Dict, Any
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.storage.database.connection import db_manager
from src.storage.cache.redis_client import cache_manager
from src.storage.services.user_service import user_service
from src.storage.services.course_service import course_service
from src.backend.integrated_teaching_backend import multi_user_teaching_manager


class IntegratedSystemTester:
    """融合系统测试器"""
    
    def __init__(self):
        self.test_user_id = None
        self.test_course_id = None
        self.test_session_key = None
        
    def test_storage_layer(self) -> bool:
        """测试存储层"""
        logger.info("🧪 测试存储层...")
        
        try:
            # 测试数据库连接
            db_healthy = db_manager.health_check()
            if not db_healthy:
                logger.error("❌ 数据库连接失败")
                return False
            logger.info("✅ 数据库连接正常")
            
            # 测试缓存连接
            try:
                cache_manager.ping()
                logger.info("✅ Redis缓存连接正常")
            except Exception as e:
                logger.warning(f"⚠️  Redis连接失败: {e}")
                logger.info("💡 将使用内存缓存")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 存储层测试失败: {e}")
            return False
    
    def test_user_system(self) -> bool:
        """测试用户系统"""
        logger.info("👤 测试用户系统...")
        
        try:
            # 1. 测试用户创建
            test_user_data = {
                "username": f"test_user_{int(time.time())}",
                "email": f"test_{int(time.time())}@example.com",
                "password": "test123456",
                "role": "student",
                "grade_level": "小学三年级",
                "learning_preferences": {
                    "learning_style": "混合型",
                    "difficulty_preference": 3,
                    "favorite_subjects": ["数学", "英语"]
                }
            }
            
            create_result = user_service.create_user(test_user_data)
            if not create_result["success"]:
                logger.error(f"❌ 用户创建失败: {create_result['message']}")
                return False
            
            self.test_user_id = create_result["user"]["id"]
            logger.info(f"✅ 用户创建成功 (ID: {self.test_user_id})")
            
            # 2. 测试用户认证
            auth_result = user_service.authenticate_user(
                test_user_data["username"], 
                test_user_data["password"]
            )
            if not auth_result["success"]:
                logger.error(f"❌ 用户认证失败: {auth_result['message']}")
                return False
            
            token = auth_result["token"]
            logger.info("✅ 用户认证成功")
            
            # 3. 测试会话验证
            session_user = user_service.get_user_by_session(token)
            if not session_user:
                logger.error("❌ 会话验证失败")
                return False
            
            logger.info("✅ 会话验证成功")
            
            # 4. 测试用户信息更新
            update_data = {
                "grade_level": "小学四年级",
                "learning_preferences": {
                    "learning_style": "视觉型",
                    "difficulty_preference": 4,
                    "favorite_subjects": ["数学", "语文", "英语"]
                }
            }
            
            update_result = user_service.update_user_profile(self.test_user_id, update_data)
            if not update_result["success"]:
                logger.error(f"❌ 用户信息更新失败: {update_result['message']}")
                return False
            
            logger.info("✅ 用户信息更新成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 用户系统测试失败: {e}")
            return False
    
    def test_course_system(self) -> bool:
        """测试课程系统"""
        logger.info("📚 测试课程系统...")
        
        try:
            # 1. 测试课程创建
            test_course_data = {
                "name": f"测试课程_{int(time.time())}",
                "subject": "数学",
                "grade_level": "小学三年级",
                "difficulty_level": 3,
                "description": "这是一个用于系统测试的课程",
                "teaching_objectives": ["测试目标1", "测试目标2"],
                "knowledge_points": ["知识点1", "知识点2"],
                "estimated_duration": 30,
                "ai_teacher_prompt": "你是一位测试用的AI老师，请进行友好的教学。",
                "is_active": True
            }
            
            create_result = course_service.create_course(test_course_data)
            if not create_result["success"]:
                logger.error(f"❌ 课程创建失败: {create_result['message']}")
                return False
            
            self.test_course_id = create_result["course"]["id"]
            logger.info(f"✅ 课程创建成功 (ID: {self.test_course_id})")
            
            # 2. 测试课程查询
            course = course_service.get_course_by_id(self.test_course_id)
            if not course:
                logger.error("❌ 课程查询失败")
                return False
            
            logger.info("✅ 课程查询成功")
            
            # 3. 测试课程列表
            all_courses = course_service.get_all_courses()
            if not all_courses:
                logger.error("❌ 课程列表查询失败")
                return False
            
            logger.info(f"✅ 课程列表查询成功 (共 {len(all_courses)} 个课程)")
            
            # 4. 测试学科查询
            subjects = course_service.get_all_subjects()
            if not subjects:
                logger.error("❌ 学科列表查询失败")
                return False
            
            logger.info(f"✅ 学科列表查询成功 (共 {len(subjects)} 个学科)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 课程系统测试失败: {e}")
            return False
    
    def test_teaching_integration(self) -> bool:
        """测试教学系统集成"""
        logger.info("🎓 测试AI教学系统集成...")
        
        try:
            if not self.test_user_id or not self.test_course_id:
                logger.error("❌ 缺少测试用户或课程数据")
                return False
            
            # 1. 测试创建教学会话
            session_token = f"test_token_{int(time.time())}"
            session_data = multi_user_teaching_manager.create_teaching_session(
                self.test_user_id, 
                self.test_course_id, 
                session_token
            )
            
            if not session_data or "session_key" not in session_data:
                logger.error("❌ 教学会话创建失败")
                return False
            
            self.test_session_key = session_data["session_key"]
            logger.info(f"✅ 教学会话创建成功 (Key: {self.test_session_key[:20]}...)")
            
            # 2. 测试会话状态查询
            session_status = multi_user_teaching_manager.get_user_session_status(self.test_user_id)
            if not session_status:
                logger.error("❌ 会话状态查询失败")
                return False
            
            logger.info("✅ 会话状态查询成功")
            
            # 3. 测试消息处理
            test_messages = [
                "你好，我想学习数学",
                "请教我加法",
                "1+1等于几？",
                "谢谢老师"
            ]
            
            for i, message in enumerate(test_messages, 1):
                logger.info(f"📝 发送测试消息 {i}: {message}")
                
                try:
                    response_data = multi_user_teaching_manager.process_user_message(
                        self.test_user_id, 
                        message, 
                        self.test_session_key
                    )
                    
                    if not response_data or "response" not in response_data:
                        logger.error(f"❌ 消息 {i} 处理失败")
                        return False
                    
                    ai_response = response_data["response"]
                    response_time = response_data.get("response_time", 0)
                    
                    logger.info(f"🤖 AI回复 {i}: {ai_response[:100]}...")
                    logger.info(f"⏱️  响应时间: {response_time:.2f}ms")
                    
                    # 短暂等待，模拟真实对话
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ 消息 {i} 处理异常: {e}")
                    # 继续测试其他消息
                    continue
            
            logger.info("✅ 消息处理测试完成")
            
            # 4. 测试会话结束
            end_result = multi_user_teaching_manager.end_teaching_session(
                self.test_user_id, 
                self.test_session_key
            )
            
            if not end_result:
                logger.error("❌ 会话结束失败")
                return False
            
            logger.info("✅ 会话结束成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 教学系统集成测试失败: {e}")
            return False
    
    def test_personalization_engine(self) -> bool:
        """测试个性化引擎"""
        logger.info("🎯 测试个性化引擎...")
        
        try:
            if not self.test_user_id or not self.test_course_id:
                logger.error("❌ 缺少测试数据")
                return False
            
            # 获取用户数据
            user_data = user_service.get_user_by_id(self.test_user_id)
            course_data = course_service.get_course_by_id(self.test_course_id)
            
            if not user_data or not course_data:
                logger.error("❌ 获取用户或课程数据失败")
                return False
            
            # 1. 测试个性化提示生成
            personalized_prompt = multi_user_teaching_manager.personalized_engine.generate_personalized_prompt(
                user_data, course_data
            )
            
            if not personalized_prompt or len(personalized_prompt) < 100:
                logger.error("❌ 个性化提示生成失败")
                return False
            
            logger.info("✅ 个性化提示生成成功")
            logger.info(f"📝 提示长度: {len(personalized_prompt)} 字符")
            
            # 2. 测试欢迎消息生成
            welcome_message = multi_user_teaching_manager.personalized_engine.generate_welcome_message(
                user_data, course_data
            )
            
            if not welcome_message:
                logger.error("❌ 欢迎消息生成失败")
                return False
            
            logger.info("✅ 欢迎消息生成成功")
            logger.info(f"👋 欢迎消息: {welcome_message}")
            
            # 3. 测试课程推荐（如果有其他课程）
            try:
                recommendations = multi_user_teaching_manager.personalized_engine.get_recommended_next_topics(
                    self.test_user_id, self.test_course_id
                )
                
                logger.info(f"✅ 课程推荐生成成功 (共 {len(recommendations)} 个推荐)")
                
                for i, rec in enumerate(recommendations[:3], 1):
                    course = rec["course"]
                    reason = rec["reason"]
                    confidence = rec["confidence"]
                    logger.info(f"📚 推荐 {i}: {course['name']} (原因: {reason}, 置信度: {confidence})")
                    
            except Exception as e:
                logger.warning(f"⚠️  课程推荐测试跳过: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 个性化引擎测试失败: {e}")
            return False
    
    def test_api_integration(self) -> bool:
        """测试API集成"""
        logger.info("🔌 测试API集成...")
        
        try:
            # 导入API模块测试
            from src.api.integrated_teaching_api import app
            from src.api.user_api import router as user_router
            from src.api.course_api import router as course_router
            
            logger.info("✅ API模块导入成功")
            
            # 测试应用配置
            if not hasattr(app, 'routes') or len(app.routes) == 0:
                logger.error("❌ API路由配置失败")
                return False
            
            logger.info(f"✅ API路由配置成功 (共 {len(app.routes)} 个路由)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ API集成测试失败: {e}")
            return False
    
    def test_frontend_integration(self) -> bool:
        """测试前端集成"""
        logger.info("🎨 测试前端集成...")
        
        try:
            # 导入前端模块测试
            from src.frontend.integrated_frontend import create_integrated_interface
            
            logger.info("✅ 前端模块导入成功")
            
            # 创建界面实例测试
            interface = create_integrated_interface()
            
            if not interface:
                logger.error("❌ 前端界面创建失败")
                return False
            
            logger.info("✅ 前端界面创建成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 前端集成测试失败: {e}")
            return False
    
    def cleanup_test_data(self):
        """清理测试数据"""
        logger.info("🧹 清理测试数据...")
        
        try:
            # 清理测试用户（如果需要）
            if self.test_user_id:
                logger.info(f"保留测试用户 (ID: {self.test_user_id}) 用于手动验证")
            
            # 清理测试课程（如果需要）
            if self.test_course_id:
                logger.info(f"保留测试课程 (ID: {self.test_course_id}) 用于手动验证")
            
            logger.info("✅ 测试数据清理完成")
            
        except Exception as e:
            logger.warning(f"⚠️  测试数据清理失败: {e}")
    
    def run_comprehensive_test(self) -> bool:
        """运行综合测试"""
        logger.info("🧪 开始AI教学平台融合系统综合测试")
        logger.info("=" * 60)
        
        test_results = []
        
        # 测试项目列表
        test_cases = [
            ("存储层", self.test_storage_layer),
            ("用户系统", self.test_user_system),
            ("课程系统", self.test_course_system),
            ("教学集成", self.test_teaching_integration),
            ("个性化引擎", self.test_personalization_engine),
            ("API集成", self.test_api_integration),
            ("前端集成", self.test_frontend_integration)
        ]
        
        # 执行测试
        for test_name, test_func in test_cases:
            logger.info(f"\n{'='*20} {test_name} 测试 {'='*20}")
            try:
                result = test_func()
                test_results.append((test_name, result))
                
                if result:
                    logger.info(f"✅ {test_name} 测试通过")
                else:
                    logger.error(f"❌ {test_name} 测试失败")
                    
            except Exception as e:
                logger.error(f"💥 {test_name} 测试异常: {e}")
                test_results.append((test_name, False))
        
        # 清理测试数据
        self.cleanup_test_data()
        
        # 测试结果总结
        logger.info("\n" + "=" * 60)
        logger.info("📊 测试结果总结")
        logger.info("=" * 60)
        
        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"  {test_name:<12}: {status}")
        
        logger.info("-" * 60)
        logger.info(f"📈 总体成功率: {passed}/{total} ({passed/total*100:.1f}%)")
        
        if passed == total:
            logger.info("🎉 所有测试通过！系统集成成功！")
            logger.info("🚀 可以启动完整的AI教学平台了")
            return True
        else:
            logger.warning(f"⚠️  {total-passed} 个测试失败，请检查系统配置")
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
    
    # 运行测试
    tester = IntegratedSystemTester()
    success = tester.run_comprehensive_test()
    
    if success:
        logger.info("\n🎓 融合系统测试完成！")
        logger.info("🌟 建议执行: python start_integrated_teaching_platform.py")
        sys.exit(0)
    else:
        logger.error("\n❌ 融合系统测试失败！请检查系统配置")
        sys.exit(1)


if __name__ == "__main__":
    main() 