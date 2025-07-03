#!/bin/bash

# AI在线教学平台启动脚本 - 支持基础版本和集成版本
# 基础版本: 使用PostgreSQL + Redis + MinIO三层存储架构
# 集成版本: 包含用户管理系统的完整平台

# 定义PID文件路径
PID_FILE="/tmp/teaching_platform_storage.pid"
LOG_FILE="logs/teaching_platform.log"

# 获取命令和版本
ACTION=${1:-"start"}
VERSION=${2:-"basic"}  # basic 或 integrated

# 显示用法
show_usage() {
    echo "📖 用法: $0 [start|stop|restart] [basic|integrated] [config_file] [host] [port]"
    echo "  start   - 启动服务"
    echo "  stop    - 停止服务"
    echo "  restart - 重启服务"
    echo ""
    echo "  basic      - 基础版本 (src/teaching_demo.py)"
    echo "  integrated - 集成版本 (start_integrated_teaching_platform.py)"
    echo ""
    echo "示例:"
    echo "  $0 start basic                                     # 启动基础版本"
    echo "  $0 start integrated                               # 启动集成版本"
    echo "  $0 restart integrated config/custom.yaml          # 重启集成版本"
    exit 1
}

case $ACTION in
    "start")
        echo "🚀 启动AI在线教学平台 ($VERSION 版本)"
        ;;
    "stop")
        echo "🛑 停止AI在线教学平台"
        ;;
    "restart")
        echo "🔄 重启AI在线教学平台 ($VERSION 版本)"
        ;;
    *)
        show_usage
        ;;
esac

echo "================================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

# 检查版本参数
if [ "$VERSION" != "basic" ] && [ "$VERSION" != "integrated" ]; then
    echo "❌ 无效的版本参数: $VERSION"
    echo "   支持的版本: basic, integrated"
    show_usage
fi

# 检查必要的环境变量
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "⚠️  警告: DASHSCOPE_API_KEY 环境变量未设置"
    echo "   教学平台将以有限模式运行（仅支持文本对话）"
    echo "   如需完整功能，请设置: export DASHSCOPE_API_KEY=your_api_key"
fi

# 停止服务函数
stop_service() {
    echo "🧹 开始清理所有相关进程..."
    
    # 1. 停止主进程
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🔄 停止主进程 $PID..."
            kill -TERM $PID
            sleep 3
            
            # 如果进程仍在运行，强制杀死
            if ps -p $PID > /dev/null 2>&1; then
                echo "⚠️  强制停止主进程 $PID..."
                kill -KILL $PID
            fi
            
            echo "✅ 主进程已停止"
        else
            echo "⚠️  PID文件存在但主进程未运行"
        fi
        rm -f "$PID_FILE"
    fi
    
    # 2. 清理所有teaching相关的Python进程
    echo "🧹 清理teaching相关进程..."
    TEACHING_PIDS=$(pgrep -f "teaching_demo.py\|teaching_backend\|teaching_frontend" 2>/dev/null)
    if [ ! -z "$TEACHING_PIDS" ]; then
        echo "发现teaching进程: $TEACHING_PIDS"
        kill -TERM $TEACHING_PIDS 2>/dev/null
        sleep 2
        kill -KILL $TEACHING_PIDS 2>/dev/null
        echo "✅ teaching进程已清理"
    fi
    
    # 3. 清理avatar相关的多进程
    echo "🧹 清理avatar多进程..."
    AVATAR_PIDS=$(pgrep -f "avatar_handler\|liteavatar\|avatar_processor\|AvatarProcessor" 2>/dev/null)
    if [ ! -z "$AVATAR_PIDS" ]; then
        echo "发现avatar进程: $AVATAR_PIDS"
        kill -TERM $AVATAR_PIDS 2>/dev/null
        sleep 2
        kill -KILL $AVATAR_PIDS 2>/dev/null
        echo "✅ avatar进程已清理"
    fi
    
    # 4. 清理multiprocessing相关进程
    echo "🧹 清理multiprocessing进程..."
    
    # 查找所有teaching-platform环境的multiprocessing进程
    MULTI_PIDS=$(ps aux | grep "teaching-platform.*multiprocessing" | grep -v grep | awk '{print $2}')
    if [ ! -z "$MULTI_PIDS" ]; then
        echo "发现teaching-platform multiprocessing进程: $MULTI_PIDS"
        kill -TERM $MULTI_PIDS 2>/dev/null
        sleep 3
        kill -KILL $MULTI_PIDS 2>/dev/null
        echo "✅ teaching-platform multiprocessing进程已清理"
    fi
    
    # 查找所有spawn_main进程
    SPAWN_PIDS=$(ps aux | grep "spawn_main" | grep -v grep | awk '{print $2}')
    if [ ! -z "$SPAWN_PIDS" ]; then
        echo "发现spawn_main进程: $SPAWN_PIDS"
        kill -TERM $SPAWN_PIDS 2>/dev/null
        sleep 3
        kill -KILL $SPAWN_PIDS 2>/dev/null
        echo "✅ spawn_main进程已清理"
    fi
    
    # 查找所有resource_tracker进程
    TRACKER_PIDS=$(ps aux | grep "resource_tracker" | grep -v grep | awk '{print $2}')
    if [ ! -z "$TRACKER_PIDS" ]; then
        echo "发现resource_tracker进程: $TRACKER_PIDS"
        kill -TERM $TRACKER_PIDS 2>/dev/null
        sleep 2
        kill -KILL $TRACKER_PIDS 2>/dev/null
        echo "✅ resource_tracker进程已清理"
    fi
    
    # 5. 清理gradio相关进程
    echo "🧹 清理gradio进程..."
    GRADIO_PIDS=$(pgrep -f "gradio" 2>/dev/null)
    if [ ! -z "$GRADIO_PIDS" ]; then
        echo "发现gradio进程: $GRADIO_PIDS"
        kill -TERM $GRADIO_PIDS 2>/dev/null
        sleep 1
        kill -KILL $GRADIO_PIDS 2>/dev/null
        echo "✅ gradio进程已清理"
    fi
    
    # 6. 清理端口占用
    echo "🧹 检查端口占用..."
    PORT_PIDS=$(lsof -ti:8443 2>/dev/null)
    if [ ! -z "$PORT_PIDS" ]; then
        echo "发现端口8443占用进程: $PORT_PIDS"
        kill -TERM $PORT_PIDS 2>/dev/null
        sleep 1
        kill -KILL $PORT_PIDS 2>/dev/null
        echo "✅ 端口占用已清理"
    fi
    
    # 7. 显示内存使用情况
    echo "📊 当前内存使用情况:"
    free -h | head -2
    
    echo "✅ 所有相关进程已清理完成"
}

# 如果是停止命令，执行停止并退出
if [ "$ACTION" = "stop" ]; then
    stop_service
    exit 0
fi

# 如果是重启命令，先停止服务
if [ "$ACTION" = "restart" ]; then
    echo "🔄 正在停止现有服务..."
    stop_service
    echo ""
fi

# 检查存储服务状态
check_storage_services() {
    echo "🔍 检查存储服务状态..."
    
    # 对于集成版本，PostgreSQL是必需的
    if [ "$VERSION" = "integrated" ]; then
        if ! systemctl is-active --quiet postgresql; then
            echo "❌ PostgreSQL 服务未运行，尝试启动..."
            sudo systemctl start postgresql
            sleep 2
            if ! systemctl is-active --quiet postgresql; then
                echo "❌ PostgreSQL 启动失败，集成版本需要PostgreSQL"
                exit 1
            fi
        fi
        echo "✅ PostgreSQL 运行正常"
        
        # 检查Redis (对集成版本不是必需的)
        if ! systemctl is-active --quiet redis-server; then
            echo "⚠️  Redis 服务未运行，集成版本将使用内存缓存模式"
        else
            echo "✅ Redis 运行正常"
        fi
    else
        # 基础版本的存储检查
        if ! systemctl is-active --quiet postgresql; then
            echo "❌ PostgreSQL 服务未运行，尝试启动..."
            sudo systemctl start postgresql
            sleep 2
            if ! systemctl is-active --quiet postgresql; then
                echo "❌ PostgreSQL 启动失败，请检查配置"
                exit 1
            fi
        fi
        echo "✅ PostgreSQL 运行正常"
        
        if ! systemctl is-active --quiet redis-server; then
            echo "❌ Redis 服务未运行，尝试启动..."
            sudo systemctl start redis-server
            sleep 2
            if ! systemctl is-active --quiet redis-server; then
                echo "❌ Redis 启动失败，请检查配置"
                exit 1
            fi
        fi
        echo "✅ Redis 运行正常"
    fi
    
    # 测试数据库连接
    echo "🔗 测试数据库连接..."
    if ! python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        database='teaching_platform',
        user='teaching_admin',
        password='secure_password_123'
    )
    conn.close()
    print('✅ PostgreSQL 连接测试成功')
except Exception as e:
    print(f'❌ PostgreSQL 连接失败: {e}')
    exit(1)
" 2>/dev/null; then
        echo "⚠️  无法测试PostgreSQL连接（可能需要安装psycopg2）"
        echo "   这不影响启动，程序会自动处理"
    fi
    
    # 测试Redis连接（仅对基础版本）
    if [ "$VERSION" = "basic" ] && command -v redis-cli &> /dev/null; then
        if redis-cli ping | grep -q PONG; then
            echo "✅ Redis 连接测试成功"
        else
            echo "❌ Redis 连接失败"
            exit 1
        fi
    elif [ "$VERSION" = "integrated" ]; then
        echo "ℹ️  集成版本支持内存缓存模式，Redis非必需"
    else
        echo "⚠️  redis-cli 未找到，跳过Redis连接测试"
    fi
    
    echo ""
}

# 创建日志目录
mkdir -p logs

# 设置默认配置（跳过ACTION和VERSION参数）
if [ "$ACTION" = "start" ]; then
    if [ "$VERSION" = "integrated" ]; then
        CONFIG_FILE=${3:-"config/teaching_with_storage.yaml"}
        HOST=${4:-"0.0.0.0"}
        PORT=${5:-"7860"}  # 集成版本默认端口7860
    else
        CONFIG_FILE=${3:-"config/teaching_with_storage.yaml"}
        HOST=${4:-"0.0.0.0"}
        PORT=${5:-"8443"}  # 基础版本默认端口8443
    fi
else
    # restart命令
    if [ "$VERSION" = "integrated" ]; then
        CONFIG_FILE=${3:-"config/teaching_with_storage.yaml"}
        HOST=${4:-"0.0.0.0"}
        PORT=${5:-"7860"}
    else
        CONFIG_FILE=${3:-"config/teaching_with_storage.yaml"}
        HOST=${4:-"0.0.0.0"}
        PORT=${5:-"8443"}
    fi
fi

echo "📁 使用配置文件: $CONFIG_FILE"
if [ "$VERSION" = "integrated" ]; then
    echo "🌐 前端地址: http://$HOST:$PORT"
    echo "🔧 API地址: http://$HOST:8001"
else
    echo "🌐 服务地址: https://$HOST:$PORT"
fi
echo ""

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    echo "   请确保配置文件存在，或使用默认配置"
    exit 1
fi

echo "✅ 配置检查完成"
echo ""

# 检查存储服务
check_storage_services

# 显示架构信息
echo "🏗️  架构说明:"
if [ "$VERSION" = "integrated" ]; then
    echo "   版本:     集成版本 (用户管理 + AI教学)"
    echo "   数据库:   PostgreSQL (用户数据 + 会话数据)"  
    echo "   缓存:     Redis (可选, 支持内存缓存)"
    echo "   前端:     集成界面 (7860端口)"
    echo "   API:      RESTful API (8001端口)"
    echo "   主程序:   start_integrated_teaching_platform.py"
else
    echo "   版本:     基础版本 (AI教学系统)"
    echo "   数据库:   PostgreSQL (结构化数据)"  
    echo "   缓存:     Redis (会话缓存)"
    echo "   对象存储: MinIO (媒体文件) [可选]"
    echo "   前端:     teaching_frontend.py"
    echo "   后端:     teaching_backend_with_storage.py"  
    echo "   API:      teaching_api.py"
    echo "   主程序:   src/teaching_demo.py"
fi
echo ""

# 检查端口是否被占用
check_port() {
    if [ "$VERSION" = "integrated" ]; then
        # 检查前端端口和API端口
        if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
            echo "⚠️  前端端口 $PORT 已被占用"
            exit 1
        fi
        if netstat -tuln 2>/dev/null | grep -q ":8001 "; then
            echo "⚠️  API端口 8001 已被占用"
            exit 1
        fi
    else
        if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
            echo "⚠️  端口 $PORT 已被占用"
            exit 1
        fi
    fi
}

# 启动教学平台
echo "🎯 启动教学平台..."

# 检查端口占用
check_port

# 启动不同版本
if [ "$VERSION" = "integrated" ]; then
    echo "🚀 启动集成版本教学平台..."
    
    # 启动集成版本
    nohup python3 start_integrated_teaching_platform.py > "$LOG_FILE" 2>&1 &
    
    # 获取进程PID
    PLATFORM_PID=$!
    echo $PLATFORM_PID > "$PID_FILE"
    
    echo "📝 进程ID: $PLATFORM_PID"
    echo "📋 日志文件: $LOG_FILE"
    echo "🌐 前端地址: http://$HOST:$PORT"
    echo "🔧 API文档:  http://$HOST:8001/docs"
    echo ""
    
    # 等待几秒检查启动状态
    sleep 8
    
    if ps -p $PLATFORM_PID > /dev/null 2>&1; then
        echo "✅ 集成版教学平台启动成功！"
        echo ""
        echo "🎓 集成版功能说明:"
        echo "   - 用户注册、登录、权限管理"
        echo "   - 个性化AI教学体验"
        echo "   - 学习数据持久化存储"
        echo "   - RESTful API接口"
        echo "   - 实时学习进度跟踪"
        echo ""
        echo "🎯 测试账户:"
        echo "   管理员: admin / admin123"
        echo "   学生:   student1 / 123456"
        echo ""
        echo "📖 管理命令:"
        echo "   查看日志: tail -f $LOG_FILE"
        echo "   停止服务: $0 stop"
        echo "   重启服务: $0 restart integrated"
        echo ""
        echo "🎓 打开浏览器访问:"
        echo "   前端界面: http://$HOST:$PORT"
        echo "   API文档:  http://$HOST:8001/docs"
    else
        echo "❌ 集成版教学平台启动失败"
        echo "📋 请查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
    
else
    echo "🚀 启动基础版本教学平台..."
    
    # 确保SSL证书存在
    if [ ! -f "ssl_certs/cert.pem" ] || [ ! -f "ssl_certs/key.pem" ]; then
        echo "🔐 SSL证书不存在，创建自签名证书..."
        ./scripts/create_ssl_certs.sh
    fi
    
    # 后台启动服务并记录PID
    nohup python3 src/teaching_demo.py \
        --config "$CONFIG_FILE" \
        --host "$HOST" \
        --port "$PORT" > "$LOG_FILE" 2>&1 &
    
    # 获取进程PID
    PLATFORM_PID=$!
    echo $PLATFORM_PID > "$PID_FILE"
    
    echo "📝 进程ID: $PLATFORM_PID"
    echo "📋 日志文件: $LOG_FILE"
    echo "🌐 访问地址: https://$HOST:$PORT"
    echo ""
    
    # 等待几秒检查启动状态
    sleep 5
    
    if ps -p $PLATFORM_PID > /dev/null 2>&1; then
        echo "✅ 基础版教学平台启动成功！"
        echo ""
        echo "🎓 基础版功能说明:"
        echo "   - AI数字人教学"
        echo "   - 实时音视频交互"
        echo "   - 数据存储和缓存"
        echo "   - WebRTC通讯支持"
        echo ""
        echo "📖 管理命令:"
        echo "   查看日志: tail -f $LOG_FILE"
        echo "   停止服务: $0 stop"
        echo "   重启服务: $0 restart basic"
        echo ""
        echo "🎓 打开浏览器访问: https://$HOST:$PORT"
        echo "   (首次访问可能需要接受自签名证书)"
    else
        echo "❌ 基础版教学平台启动失败"
        echo "📋 请查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
fi 