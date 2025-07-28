#!/bin/bash

# AI在线教学平台启动脚本 - 统一版本
# 基于basic版本整合所有功能的简化启动脚本

# 定义PID文件路径
PID_FILE="/tmp/teaching_platform.pid"
LOG_FILE="logs/teaching_platform.log"

# 获取命令
ACTION=${1:-"start"}

# 显示用法
show_usage() {
    echo "📖 用法: $0 [start|stop|restart] [config_file] [host] [port]"
    echo "  start   - 启动服务"
    echo "  stop    - 停止服务"
    echo "  restart - 重启服务"
    echo ""
    echo "示例:"
    echo "  $0 start                                    # 启动教学平台"
    echo "  $0 start config/teaching.yaml              # 使用指定配置启动"
    echo "  $0 restart config/teaching.yaml 0.0.0.0 8443  # 重启并指定参数"
    exit 1
}

case $ACTION in
    "start")
        echo "🚀 启动AI在线教学平台"
        ;;
    "stop")
        echo "🛑 停止AI在线教学平台"
        ;;
    "restart")
        echo "🔄 重启AI在线教学平台"
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

# 加载环境变量
if [ -f ".env" ]; then
    echo "🔧 加载环境变量文件 .env"
    source .env
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# 检查必要的环境变量
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "⚠️  警告: DASHSCOPE_API_KEY 环境变量未设置"
    echo "   教学平台将以有限模式运行（仅支持文本对话）"
    echo "   如需完整功能，请设置: export DASHSCOPE_API_KEY=your_api_key"
else
    echo "✅ DASHSCOPE_API_KEY 环境变量已配置"
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
    
    # 3. 清理端口占用
    echo "🧹 检查端口占用..."
    PORT_PIDS=$(lsof -ti:8443 2>/dev/null)
    if [ ! -z "$PORT_PIDS" ]; then
        echo "发现端口8443占用进程: $PORT_PIDS"
        kill -TERM $PORT_PIDS 2>/dev/null
        sleep 1
        kill -KILL $PORT_PIDS 2>/dev/null
        echo "✅ 端口占用已清理"
    fi
    
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
    
    echo ""
}

# 创建日志目录
mkdir -p logs

# 设置配置参数
CONFIG_FILE=${2:-"config/teaching.yaml"}
HOST=${3:-"0.0.0.0"}
PORT=${4:-"8443"}

echo "📁 使用配置文件: $CONFIG_FILE"
echo "🌐 服务地址: https://$HOST:$PORT"
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
echo "   版本:     统一版本 (主动教学 + AI数字人)"
echo "   数据库:   PostgreSQL (结构化数据)"  
echo "   缓存:     Redis (会话缓存)"
echo "   前端:     teaching_frontend.py"
echo "   后端:     teaching_backend.py (含主动教学)"
echo "   API:      teaching_api.py"
echo "   主程序:   src/demo.py"
echo "   特色:     开始学习后立即问候，15秒后主动教学"
echo ""

# 检查端口是否被占用
check_port() {
    if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
        echo "⚠️  端口 $PORT 已被占用"
        exit 1
    fi
}

# 启动教学平台
echo "🎯 启动教学平台..."

# 检查端口占用
check_port

# 确保SSL证书存在
if [ ! -f "ssl_certs/cert.pem" ] || [ ! -f "ssl_certs/key.pem" ]; then
    echo "🔐 SSL证书不存在，创建自签名证书..."
    ./scripts/create_ssl_certs.sh
fi

echo "🚀 启动统一版本教学平台..."

# 激活conda环境并后台启动服务
nohup bash -c "source .env && export \$(grep -v '^#' .env | grep -v '^$' | xargs) && source /root/anaconda3/etc/profile.d/conda.sh && conda activate teaching-platform && python src/teaching_demo.py \
    --config '$CONFIG_FILE' \
    --host '$HOST' \
    --port '$PORT'" > "$LOG_FILE" 2>&1 &

# 获取进程PID
PLATFORM_PID=$!
echo $PLATFORM_PID > "$PID_FILE"

echo "📝 进程ID: $PLATFORM_PID"
echo "📋 日志文件: $LOG_FILE"
echo "🌐 访问地址: https://$HOST:$PORT"
echo ""

# 等待几秒检查启动状态
sleep 8

if ps -p $PLATFORM_PID > /dev/null 2>&1; then
    echo "✅ 统一版教学平台启动成功！"
    echo ""
    echo "🎓 统一版功能说明:"
    echo "   - AI数字人教学"
    echo "   - 主动教学系统 (开始学习后立即问候)"
    echo "   - 定期教学内容推送 (15秒后开始，30-45秒间隔)"
    echo "   - 实时音视频交互"
    echo "   - 雅思全科目教学内容库"
    echo "   - 数据存储和缓存"
    echo "   - WebRTC通讯支持"
    echo ""
    echo "🎯 教学体验流程:"
    echo "   1. 选择课程和难度级别"
    echo "   2. 点击'🚀 开始学习'"
    echo "   3. AI教师立即个性化问候"
    echo "   4. 15秒后开始主动教学"
    echo "   5. 每30-45秒自动发送新教学内容"
    echo "   6. 支持实时语音和文字交互"
    echo ""
    echo "📖 管理命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   停止服务: $0 stop"
    echo "   重启服务: $0 restart"
    echo ""
    echo "🎓 打开浏览器访问: https://$HOST:$PORT"
    echo "   (首次访问可能需要接受自签名证书)"
else
    echo "❌ 统一版教学平台启动失败"
    echo "📋 请查看日志: $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi