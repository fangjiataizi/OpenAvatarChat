#!/bin/bash

# AI在线教学平台 - 重启脚本（带日志输出）
# 确保日志写入logs/log.log供前端实时监听

set -e

echo "🎓 AI在线教学平台 - 重启脚本"
echo "=========================================="
echo "🔐 启用HTTPS支持WebRTC摄像头"
echo "🤖 集成LiteAvatar数字人"
echo "🎤 支持语音对话"
echo "🧠 真实AI教师"
echo "📝 日志输出到logs/log.log"
echo ""

# 停止之前的进程
echo "🔄 检查并停止之前的进程..."
pkill -f "teaching_demo.py" 2>/dev/null || echo "   没有发现运行中的教学进程"
pkill -f "multiprocessing" 2>/dev/null || echo "   清理完成"

# 检查并释放端口
for port in 8286 8443; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  端口$port被占用，正在释放..."
        lsof -Pi :$port -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
done

# 激活conda环境
echo "📦 激活conda环境: teaching-platform"
source /root/anaconda3/etc/profile.d/conda.sh
conda activate teaching-platform

# 检查SSL证书
if [ ! -f "ssl_certs/localhost.crt" ] || [ ! -f "ssl_certs/localhost.key" ]; then
    echo "📜 生成SSL证书..."
    mkdir -p ssl_certs
    openssl req -x509 -newkey rsa:2048 -keyout ssl_certs/localhost.key -out ssl_certs/localhost.crt -days 365 -nodes -subj "/C=CN/ST=Beijing/L=Beijing/O=Teaching/OU=IT/CN=localhost" >/dev/null 2>&1
    echo "✅ SSL证书生成完成"
fi

# 确保日志目录存在
echo "📁 准备日志目录..."
mkdir -p logs

# 清空旧日志（可选）
# > logs/log.log

echo "✅ 环境检查完成!"
echo ""
echo "🚀 启动AI在线教学平台（HTTPS版）..."
echo "📍 HTTPS访问地址: https://localhost:8443/ui"
echo "📍 HTTP访问地址: http://localhost:8286/ui"  
echo "🔐 HTTPS版本支持WebRTC摄像头访问"
echo "📝 日志输出: logs/log.log"
echo "⚠️  首次访问请点击'高级'->'继续访问'信任证书"
echo "⏹️  按Ctrl+C停止服务"
echo ""

# 启动HTTPS版本 - 关键：重定向所有输出到日志文件，同时保持控制台输出
echo "📝 启动服务并写入日志文件..."
python src/teaching_demo.py --config config/teaching_with_liteavatar_https.yaml --host 0.0.0.0 --port 8443 2>&1 | tee logs/log.log

echo "👋 AI在线教学平台已停止" 