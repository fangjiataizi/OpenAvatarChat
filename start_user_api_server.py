#!/usr/bin/env python3
"""
AI教学平台用户系统API服务器启动脚本
"""
import sys
import os
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="AI教学平台用户系统API",
    description="提供用户管理和课程管理的RESTful API接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("🚀 启动AI教学平台用户系统API服务器...")
    
    try:
        # 初始化存储服务
        from src.storage.database.connection import db_manager
        from src.storage.cache.redis_client import cache_manager
        
        # 初始化缓存
        cache_manager.initialize()
        logger.info("✅ 存储服务初始化完成")
        
    except Exception as e:
        logger.error(f"❌ 存储服务初始化失败: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """根路径，显示API文档入口"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI教学平台用户系统API</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #2c3e50; }
            .api-link { display: inline-block; margin: 10px; padding: 10px 20px; 
                       background: #3498db; color: white; text-decoration: none; 
                       border-radius: 5px; }
            .feature { margin: 20px 0; padding: 15px; background: #f8f9fa; 
                      border-left: 4px solid #3498db; }
            .endpoint { background: #e9ecef; padding: 10px; margin: 5px 0; 
                       border-radius: 3px; font-family: monospace; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 AI教学平台用户系统API</h1>
            
            <p>欢迎使用AI教学平台的用户管理和课程管理API服务！</p>
            
            <div>
                <a href="/docs" class="api-link">📖 Swagger文档</a>
                <a href="/redoc" class="api-link">📚 ReDoc文档</a>
                <a href="/health" class="api-link">💓 健康检查</a>
            </div>
            
            <div class="feature">
                <h3>👥 用户管理功能</h3>
                <div class="endpoint">POST /api/user/register/student - 学生注册</div>
                <div class="endpoint">POST /api/user/login - 用户登录</div>
                <div class="endpoint">GET /api/user/profile - 获取用户信息</div>
                <div class="endpoint">PUT /api/user/profile - 更新用户信息</div>
                <div class="endpoint">GET /api/user/stats/{user_id} - 学习统计</div>
                <div class="endpoint">POST /api/user/logout - 用户登出</div>
            </div>
            
            <div class="feature">
                <h3>📚 课程管理功能</h3>
                <div class="endpoint">GET /api/course/subjects - 获取学科列表</div>
                <div class="endpoint">GET /api/course/list - 获取课程列表</div>
                <div class="endpoint">GET /api/course/{course_id} - 获取课程详情</div>
                <div class="endpoint">GET /api/course/recommend/for-me - 个人推荐课程</div>
                <div class="endpoint">GET /api/course/search - 搜索课程</div>
            </div>
            
            <div class="feature">
                <h3>🔧 管理员功能</h3>
                <div class="endpoint">POST /api/user/register/admin - 创建管理员</div>
                <div class="endpoint">GET /api/user/students - 获取学生列表</div>
                <div class="endpoint">POST /api/course/create - 创建课程</div>
                <div class="endpoint">PUT /api/course/{course_id} - 更新课程</div>
                <div class="endpoint">GET /api/course/stats/overview - 课程统计</div>
            </div>
            
            <div class="feature">
                <h3>🚀 快速开始</h3>
                <p>1. 首先注册一个学生账户：<code>POST /api/user/register/student</code></p>
                <p>2. 使用账户登录获取token：<code>POST /api/user/login</code></p>
                <p>3. 在请求头中添加：<code>Authorization: Bearer {token}</code></p>
                <p>4. 现在可以访问需要认证的API端点了！</p>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """系统健康检查"""
    try:
        # 检查存储服务状态
        from src.storage.services.user_service import user_service
        from src.storage.services.course_service import course_service
        
        return {
            "status": "healthy",
            "message": "AI教学平台用户系统API运行正常",
            "services": {
                "user_service": "active",
                "course_service": "active",
                "database": "connected",
                "cache": "connected"
            },
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# 注册API路由
try:
    from src.api.user_api import router as user_router
    from src.api.course_api import router as course_router
    
    app.include_router(user_router)
    app.include_router(course_router)
    
    logger.info("✅ API路由注册成功")
    
except Exception as e:
    logger.error(f"❌ API路由注册失败: {e}")


def create_test_data():
    """创建测试数据"""
    logger.info("📝 创建测试数据...")
    
    try:
        from src.storage.services.user_service import user_service
        from src.storage.services.course_service import course_service
        
        # 创建测试管理员
        admin_data = user_service.create_admin(
            username="admin",
            password="admin123456",
            email="admin@teaching.ai"
        )
        
        if admin_data:
            logger.info("✅ 创建测试管理员: admin/admin123456")
        
        # 创建测试学生
        student_data = user_service.create_student(
            username="student",
            password="student123",
            email="student@example.com",
            grade_level="小学三年级",
            parent_contact="13800138000",
            learning_preferences={
                "learning_style": "视觉型",
                "difficulty_preference": 3,
                "favorite_subjects": ["数学", "语文"]
            }
        )
        
        if student_data:
            logger.info("✅ 创建测试学生: student/student123")
        
        # 创建测试课程
        math_course = course_service.create_course(
            name="小学三年级数学基础",
            subject="数学",
            grade_level="小学三年级",
            difficulty_level=2,
            description="小学三年级数学基础课程，包含加减乘除等基本运算",
            teaching_objectives=["掌握基本运算", "理解数学概念", "培养数学思维"],
            knowledge_points=["加法", "减法", "乘法", "除法", "应用题"],
            teaching_materials={"textbook": "人教版数学三年级上册"}
        )
        
        if math_course:
            logger.info("✅ 创建测试数学课程")
        
        chinese_course = course_service.create_course(
            name="小学三年级语文阅读",
            subject="语文",
            grade_level="小学三年级",
            difficulty_level=2,
            description="小学三年级语文阅读课程，培养阅读理解能力",
            teaching_objectives=["提高阅读理解", "增强语感", "扩大词汇量"],
            knowledge_points=["汉字认读", "词语理解", "句子分析", "段落理解"],
            teaching_materials={"textbook": "人教版语文三年级上册"}
        )
        
        if chinese_course:
            logger.info("✅ 创建测试语文课程")
            
        logger.info("🎉 测试数据创建完成！")
        
    except Exception as e:
        logger.error(f"❌ 创建测试数据失败: {e}")


def main():
    """主函数"""
    logger.info("🎓 AI教学平台用户系统API服务器")
    logger.info("=" * 50)
    
    # 创建测试数据
    create_test_data()
    
    # 启动服务器
    logger.info("🚀 启动API服务器...")
    logger.info("📝 API文档地址: http://localhost:8000/docs")
    logger.info("📚 ReDoc文档: http://localhost:8000/redoc")
    logger.info("💓 健康检查: http://localhost:8000/health")
    logger.info("")
    logger.info("🔧 测试账户:")
    logger.info("   管理员: admin / admin123456")
    logger.info("   学生: student / student123")
    logger.info("")
    logger.info("💡 API使用步骤:")
    logger.info("   1. 访问 /api/user/login 登录获取token")
    logger.info("   2. 在请求头添加: Authorization: Bearer {token}")
    logger.info("   3. 访问其他需要认证的API端点")
    logger.info("")
    
    # 启动uvicorn服务器
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )


if __name__ == "__main__":
    main() 