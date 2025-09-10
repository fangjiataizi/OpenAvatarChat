#!/bin/bash

# 数字人播报新闻服务启动脚本
# 基于OpenAvatarChat项目开发

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查Python环境
check_python() {
    log_step "检查Python环境..."
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装，请先安装Python3.8+"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)'; then
        log_info "Python版本: $PYTHON_VERSION ✓"
    else
        log_error "Python版本过低，需要Python 3.8+，当前版本: $PYTHON_VERSION"
        exit 1
    fi
}

# 加载环境变量文件
load_env_file() {
    if [ -f ".env" ]; then
        log_info "从 .env 文件加载环境变量..."
        # 使用 set -a 来自动导出变量
        set -a
        source .env
        set +a
        log_info "环境变量加载完成 ✓"
    else
        log_warn ".env 文件不存在，将使用系统环境变量"
    fi
}

# 检查环境变量
check_environment() {
    log_step "检查环境变量..."

    # 先加载 .env 文件
    load_env_file

    if [ -z "$DASHSCOPE_API_KEY" ]; then
        log_error "DASHSCOPE_API_KEY 环境变量未设置"
        log_error "请在 .env 文件中设置 DASHSCOPE_API_KEY 或手动设置环境变量"
        log_error "示例: export DASHSCOPE_API_KEY=your_api_key"
        exit 1
    else
        log_info "DASHSCOPE_API_KEY 已设置 ✓"
    fi

    if [ -z "$OPENAI_API_KEY" ]; then
        log_warn "OPENAI_API_KEY 环境变量未设置（可选）"
        log_warn "如果要使用GPT模型，请在 .env 文件中设置此变量"
    else
        log_info "OPENAI_API_KEY 已设置 ✓"
    fi
}

# 检查依赖
check_dependencies() {
    log_step "检查项目依赖..."

    if [ ! -f "pyproject.toml" ]; then
        log_error "pyproject.toml 文件不存在"
        exit 1
    fi

    if [ ! -d "src" ]; then
        log_error "src 目录不存在"
        exit 1
    fi

    if [ ! -f "config/news_broadcast.yaml" ]; then
        log_error "config/news_broadcast.yaml 配置文件不存在"
        exit 1
    fi

    log_info "项目文件检查完成 ✓"
}

# 创建输出目录
create_output_dirs() {
    log_step "创建输出目录..."

    mkdir -p output/news_videos
    mkdir -p temp/news_processing
    mkdir -p logs

    log_info "输出目录创建完成 ✓"
}

# 启动服务
start_service() {
    local host=${1:-"0.0.0.0"}
    local port=${2:-"8444"}

    log_step "启动数字人播报新闻服务..."
    log_info "服务地址: http://$host:$port"
    log_info "配置文件: config/news_broadcast.yaml"

    # 检查是否已有进程在运行
    if pgrep -f "news_broadcast_demo.py" > /dev/null; then
        log_warn "检测到新闻播报服务已在运行"
        read -p "是否要停止现有服务并重新启动? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "停止现有服务..."
            pkill -f "news_broadcast_demo.py"
            sleep 2
        else
            log_info "保持现有服务运行"
            exit 0
        fi
    fi

    # 启动服务
    log_info "正在启动服务..."

    # 确保环境变量被传递到子进程
    nohup bash -c "
# 重新加载环境变量
if [ -f '.env' ]; then
    set -a
    source .env
    set +a
fi

conda run -n teaching-platform python -c \"
import sys
import os
sys.path.insert(0, '/home/OpenAvatarChat')
sys.path.insert(0, '/home/OpenAvatarChat/src')
os.chdir('/home/OpenAvatarChat')
from optimized_news_interface import main
main()
\"
" \
        > logs/news_broadcast.log 2>&1 &

    local pid=$!
    echo $pid > news_broadcast.pid

    # 等待服务启动
    sleep 3

    if kill -0 $pid 2>/dev/null; then
        log_info "✅ 新闻播报服务启动成功!"
        log_info "📊 服务PID: $pid"
        log_info "📝 日志文件: logs/news_broadcast.log"
        log_info "🌐 访问地址: http://$host:$port"
        log_info ""
        log_info "按 Ctrl+C 停止服务"
        log_info "或运行: ./start_news_broadcast.sh stop"
    else
        log_error "❌ 服务启动失败，请检查日志文件"
        exit 1
    fi
}

# 停止服务
stop_service() {
    log_step "停止新闻播报服务..."

    if [ -f "news_broadcast.pid" ]; then
        local pid=$(cat news_broadcast.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "正在停止服务 (PID: $pid)..."
            kill $pid
            sleep 2

            if kill -0 $pid 2>/dev/null; then
                log_warn "正常停止失败，强制终止..."
                kill -9 $pid
                sleep 1
            fi
        else
            log_warn "服务进程不存在"
        fi

        rm -f news_broadcast.pid
        log_info "✅ 服务已停止"
    else
        log_warn "未找到PID文件，尝试搜索进程..."
        if pgrep -f "news_broadcast_demo.py" > /dev/null; then
            pkill -f "news_broadcast_demo.py"
            log_info "✅ 服务已停止"
        else
            log_info "未找到运行中的服务"
        fi
    fi
}

# 查看状态
show_status() {
    log_step "查看服务状态..."

    if [ -f "news_broadcast.pid" ]; then
        local pid=$(cat news_broadcast.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "✅ 服务正在运行 (PID: $pid)"

            # 显示端口信息
            if command -v netstat &> /dev/null; then
                local port=$(netstat -tulpn 2>/dev/null | grep ":$pid " | head -1 | awk '{print $4}' | cut -d: -f2)
                if [ -n "$port" ]; then
                    log_info "🌐 服务端口: $port"
                    log_info "🔗 访问地址: http://localhost:$port"
                fi
            fi
        else
            log_warn "❌ 服务进程不存在，但PID文件存在"
            rm -f news_broadcast.pid
        fi
    else
        if pgrep -f "news_broadcast_demo.py" > /dev/null; then
            log_info "✅ 服务正在运行 (PID: $(pgrep -f "news_broadcast_demo.py"))"
        else
            log_info "❌ 服务未运行"
        fi
    fi

    # 显示日志文件
    if [ -f "logs/news_broadcast.log" ]; then
        log_info "📝 最新日志:"
        tail -5 logs/news_broadcast.log | sed 's/^/    /'
    fi
}

# 查看日志
show_logs() {
    local lines=${1:-50}

    if [ -f "logs/news_broadcast.log" ]; then
        log_info "显示最近 $lines 行日志:"
        echo "----------------------------------------"
        tail -$lines logs/news_broadcast.log
        echo "----------------------------------------"
    else
        log_error "日志文件不存在"
    fi
}

# 显示帮助
show_help() {
    echo "数字人播报新闻服务启动脚本"
    echo ""
    echo "用法:"
    echo "  $0 [command] [options]"
    echo ""
    echo "命令:"
    echo "  start [host] [port]    启动服务 (默认: 0.0.0.0:8444)"
    echo "  stop                  停止服务"
    echo "  restart [host] [port] 重启服务"
    echo "  status                查看服务状态"
    echo "  logs [lines]          查看日志 (默认: 50行)"
    echo "  help                  显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start              # 启动服务"
    echo "  $0 start 127.0.0.1 8080  # 指定主机和端口启动"
    echo "  $0 stop               # 停止服务"
    echo "  $0 restart            # 重启服务"
    echo "  $0 status             # 查看状态"
    echo "  $0 logs 100           # 查看最近100行日志"
    echo ""
    echo "环境变量:"
    echo "  DASHSCOPE_API_KEY     阿里云API密钥 (必需)"
    echo "  OPENAI_API_KEY        OpenAI API密钥 (可选)"
    echo ""
    echo "配置文件:"
    echo "  config/news_broadcast.yaml"
    echo ""
}

# 主函数
main() {
    local command=${1:-"start"}

    case $command in
        "start")
            check_python
            check_environment
            check_dependencies
            create_output_dirs
            start_service "${2:-0.0.0.0}" "${3:-8444}"
            ;;
        "stop")
            stop_service
            ;;
        "restart")
            stop_service
            sleep 1
            check_python
            check_environment
            check_dependencies
            create_output_dirs
            start_service "${2:-0.0.0.0}" "${3:-8444}"
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs "${2:-50}"
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
