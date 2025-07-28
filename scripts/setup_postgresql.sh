#!/bin/bash

# PostgreSQL数据库初始化脚本

set -e

DB_NAME="teaching_platform"
DB_USER="teaching_admin"
DB_PASSWORD="secure_password_123"
DB_HOST="localhost"
DB_PORT="5432"

echo "🔧 设置PostgreSQL数据库..."

# 检查PostgreSQL是否安装
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL未安装，请先安装PostgreSQL"
    echo "Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "CentOS/RHEL: sudo yum install postgresql-server postgresql-contrib"
    exit 1
fi

# 检查PostgreSQL服务是否运行
if ! sudo systemctl is-active --quiet postgresql; then
    echo "🔄 启动PostgreSQL服务..."
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi

# 创建数据库用户和数据库
echo "📝 创建数据库用户和数据库..."

sudo -u postgres psql <<EOF
-- 创建用户（如果不存在）
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- 创建数据库（如果不存在）
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
EOF

echo "✅ PostgreSQL数据库设置完成"
echo "📊 数据库信息:"
echo "   数据库名: $DB_NAME"
echo "   用户名: $DB_USER"
echo "   主机: $DB_HOST"
echo "   端口: $DB_PORT"
echo ""
echo "🔗 连接字符串:"
echo "   postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"