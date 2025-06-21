#!/bin/bash

# AI在线教学平台启动脚本 - 前后端分离版本
# 使用新的模块化架构，提供更好的可维护性

# 定义PID文件路径
PID_FILE="/tmp/teaching_platform.pid"
LOG_FILE="logs/teaching_platform.log"

# 获取命令
ACTION=${1:-"start"}

case $ACTION in
    "start")
        echo "🚀 启动AI在线教学平台 (前后端分离版本)"
        ;;
    "stop")
        echo "🛑 停止AI在线教学平台"
        ;;
    "restart")
        echo "🔄 重启AI在线教学平台"
        ;;
    *)
        echo "📖 用法: $0 [start|stop|restart] [config_file] [host] [port]"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo ""
        echo "示例:"
        echo "  $0 start                                    # 使用默认配置启动"
        echo "  $0 restart config/custom.yaml 0.0.0.0 8080 # 使用自定义配置重启"
        exit 1
        ;;
esac

echo "================================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

# 检查必要的环境变量
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "⚠️  警告: DASHSCOPE_API_KEY 环境变量未设置"
    echo "   教学平台将以有限模式运行（仅支持文本对话）"
    echo "   如需完整功能，请设置: export DASHSCOPE_API_KEY=your_api_key"
fi

# 停止服务函数
stop_service() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🔄 停止进程 $PID..."
            kill -TERM $PID
            sleep 2
            
            # 如果进程仍在运行，强制杀死
            if ps -p $PID > /dev/null 2>&1; then
                echo "⚠️  强制停止进程 $PID..."
                kill -KILL $PID
            fi
            
            echo "✅ 服务已停止"
        else
            echo "⚠️  PID文件存在但进程未运行，清理PID文件"
        fi
        rm -f "$PID_FILE"
    else
        echo "ℹ️  服务未运行或PID文件不存在"
        # 尝试通过端口杀死可能的僵尸进程
        pkill -f "teaching_demo.py" 2>/dev/null && echo "🧹 清理了可能的僵尸进程"
    fi
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

# 创建日志目录
mkdir -p logs

# 设置默认配置（跳过ACTION参数）
if [ "$ACTION" = "start" ]; then
    CONFIG_FILE=${2:-"config/teaching_basic.yaml"}
    HOST=${3:-"0.0.0.0"}
    PORT=${4:-"8285"}
else
    # restart命令
    CONFIG_FILE=${2:-"config/teaching_basic.yaml"}
    HOST=${3:-"0.0.0.0"}
    PORT=${4:-"8285"}
fi

echo "📁 使用配置文件: $CONFIG_FILE"
echo "🌐 服务地址: http://$HOST:$PORT"
echo ""

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    echo "   请确保配置文件存在，或使用默认配置"
    exit 1
fi

echo "✅ 配置检查完成"
echo ""

# 显示架构信息
echo "🏗️  架构说明:"
echo "   Frontend: src/frontend/teaching_frontend.py (Gradio界面)"
echo "   Backend:  src/backend/teaching_backend.py (业务逻辑)"  
echo "   API:      src/api/teaching_api.py (接口层)"
echo "   Main:     src/teaching_demo.py (主启动文件)"
echo ""

# 检查端口是否被占用
check_port() {
    if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
        echo "⚠️  端口 $PORT 已被占用"
        echo "   请选择其他端口或停止占用该端口的服务"
        exit 1
    fi
}

# 启动教学平台
echo "🎯 启动教学平台..."

# 检查端口占用
check_port

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
echo "🌐 访问地址: http://$HOST:$PORT"
echo ""

# 等待几秒检查启动状态
sleep 3

if ps -p $PLATFORM_PID > /dev/null 2>&1; then
    echo "✅ 教学平台启动成功！"
    echo ""
    echo "📖 管理命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   停止服务: $0 stop"
    echo "   重启服务: $0 restart"
    echo ""
    echo "🎓 打开浏览器访问: http://$HOST:$PORT"
else
    echo "❌ 教学平台启动失败"
    echo "📋 请查看日志: $LOG_FILE"
    
    # 清理PID文件
    rm -f "$PID_FILE"
    exit 1
fi 