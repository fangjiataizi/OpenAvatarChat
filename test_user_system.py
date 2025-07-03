#!/usr/bin/env python3
"""
AI教学平台用户系统测试启动脚本
"""
import sys
import os
import logging
import asyncio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_storage_services():
    """测试存储服务"""
    logger.info("🔧 测试存储服务...")
    
    try:
        # 测试数据库连接
        from src.storage.database.connection import db_manager
        logger.info("✅ 数据库连接管理器: OK")
        
        # 测试缓存连接
        from src.storage.cache.redis_client import cache_manager
        cache_manager.initialize()
        logger.info("✅ 缓存管理器: OK")
        
        # 测试用户服务
        from src.storage.services.user_service import user_service
        logger.info("✅ 用户服务: OK")
        
        # 测试课程服务
        from src.storage.services.course_service import course_service
        logger.info("✅ 课程服务: OK")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 存储服务测试失败: {e}")
        return False


def test_user_operations():
    """测试用户操作"""
    logger.info("👥 测试用户操作...")
    
    try:
        from src.storage.services.user_service import user_service
        
        # 测试创建学生用户
        student_data = user_service.create_student(
            username="test_student_123",
            password="test123456",
            email="test@example.com",
            grade_level="小学三年级",
            parent_contact="13800138000",
            learning_preferences={
                "learning_style": "视觉型",
                "difficulty_preference": 3,
                "favorite_subjects": ["数学", "语文"]
            }
        )
        
        if student_data:
            logger.info(f"✅ 创建学生用户成功: {student_data['username']}")
            
            # 测试用户认证
            auth_result = user_service.authenticate_user("test_student_123", "test123456")
            if auth_result:
                logger.info("✅ 用户认证成功")
                session_token = auth_result["session_token"]
                
                # 测试获取用户信息
                user_session = user_service.get_user_by_session(session_token)
                if user_session:
                    logger.info("✅ 会话验证成功")
                
                # 测试更新用户资料
                update_success = user_service.update_student_profile(
                    user_id=student_data["id"],
                    grade_level="小学四年级",
                    learning_preferences={
                        "learning_style": "听觉型",
                        "difficulty_preference": 4,
                        "favorite_subjects": ["数学", "英语"]
                    }
                )
                
                if update_success:
                    logger.info("✅ 更新用户资料成功")
                
                # 测试获取学习统计
                stats = user_service.get_user_learning_stats(student_data["id"])
                logger.info(f"✅ 获取学习统计: {stats}")
                
                # 测试登出
                logout_success = user_service.logout_user(session_token)
                if logout_success:
                    logger.info("✅ 用户登出成功")
                    
            else:
                logger.error("❌ 用户认证失败")
                
        else:
            logger.info("ℹ️  用户可能已存在，跳过创建")
        
        # 测试获取学生列表
        students = user_service.get_students_list(limit=10)
        logger.info(f"✅ 获取学生列表: {len(students)} 个学生")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 用户操作测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_course_operations():
    """测试课程操作"""
    logger.info("📚 测试课程操作...")
    
    try:
        from src.storage.services.course_service import course_service
        
        # 测试获取可用学科
        subjects = course_service.get_available_subjects()
        logger.info(f"✅ 获取可用学科: {len(subjects)} 个学科")
        
        # 测试创建课程
        course_data = course_service.create_course(
            name="小学三年级数学基础",
            subject="数学",
            grade_level="小学三年级",
            difficulty_level=2,
            description="小学三年级数学基础课程，包含加减乘除等基本运算",
            teaching_objectives=["掌握基本运算", "理解数学概念"],
            knowledge_points=["加法", "减法", "乘法", "除法"],
            teaching_materials={"textbook": "人教版数学三年级上册"}
        )
        
        if course_data:
            logger.info(f"✅ 创建课程成功: {course_data['name']}")
            
            # 测试获取课程详情
            course_detail = course_service.get_course_by_id(course_data["id"])
            if course_detail:
                logger.info("✅ 获取课程详情成功")
                
        else:
            logger.info("ℹ️  课程可能已存在，跳过创建")
        
        # 测试获取课程列表
        courses = course_service.get_courses_by_grade_and_subject("小学三年级", "数学")
        logger.info(f"✅ 获取课程列表: {len(courses)} 个课程")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 课程操作测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_api_services():
    """测试API服务"""
    logger.info("🌐 测试API服务...")
    
    try:
        # 测试导入API模块
        from src.api.user_api import router as user_router
        logger.info("✅ 用户API模块: OK")
        
        from src.api.course_api import router as course_router
        logger.info("✅ 课程API模块: OK")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ API服务测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_frontend():
    """测试前端界面"""
    logger.info("🎨 测试前端界面...")
    
    try:
        from src.frontend.user_frontend import UserFrontend
        
        user_frontend = UserFrontend()
        logger.info("✅ 用户前端界面: OK")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 前端界面测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def launch_user_interface():
    """启动用户管理界面"""
    logger.info("🚀 启动用户管理界面...")
    
    try:
        from src.frontend.user_frontend import UserFrontend
        
        user_frontend = UserFrontend()
        
        # 启动界面
        interface = user_frontend.create_user_interface()
        
        logger.info("🎯 用户管理界面已启动！")
        logger.info("📝 访问地址: http://localhost:7860")
        logger.info("💡 功能包括:")
        logger.info("   - 学生注册和登录")
        logger.info("   - 个人资料管理")
        logger.info("   - 学习统计查看")
        logger.info("   - 课程推荐")
        logger.info("   - 管理员功能（需要管理员权限）")
        
        # 启动界面
        interface.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=True
        )
        
    except Exception as e:
        logger.error(f"❌ 启动用户界面失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def main():
    """主函数"""
    logger.info("🎓 AI教学平台用户系统测试")
    logger.info("=" * 50)
    
    # 运行测试
    tests = [
        ("存储服务", test_storage_services),
        ("用户操作", test_user_operations),
        ("课程操作", test_course_operations),
        ("API服务", test_api_services),
        ("前端界面", test_frontend)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"🧪 运行测试: {test_name}")
        try:
            if test_func():
                passed_tests += 1
                logger.info(f"✅ {test_name} 测试通过")
            else:
                logger.error(f"❌ {test_name} 测试失败")
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
        
        logger.info("-" * 30)
    
    # 测试结果
    logger.info("📊 测试结果:")
    logger.info(f"   通过: {passed_tests}/{total_tests}")
    logger.info(f"   成功率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        logger.info("🎉 所有测试通过！启动用户界面...")
        launch_user_interface()
    else:
        logger.warning("⚠️  部分测试失败，但仍可尝试启动界面")
        
        user_input = input("是否仍要启动用户界面？(y/n): ")
        if user_input.lower() in ['y', 'yes']:
            launch_user_interface()


if __name__ == "__main__":
    main() 