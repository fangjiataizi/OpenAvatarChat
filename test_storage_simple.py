#!/usr/bin/env python3
"""测试数据存储集成"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.backend.teaching_backend import teaching_backend
import time

def main():
    print("🔍 测试数据存储集成...")
    
    # 检查存储可用性
    print(f"Storage Available: {teaching_backend.storage_available}")
    
    # 创建会话
    print("创建学习会话...")
    session_data = teaching_backend.create_learning_session(
        course="雅思 - 基础语法",
        difficulty="初级",
        goal="学习语法"
    )
    
    session_key = session_data.get('session_key')
    print(f"Session Key: {session_key}")
    
    # 添加测试消息
    print("添加测试消息...")
    teaching_backend._add_real_chat_message("avatar", "欢迎学习！")
    teaching_backend._add_real_chat_message("human", "我想学语法")
    
    time.sleep(2)  # 等待异步保存
    
    # 检查队列
    messages = teaching_backend.get_all_chat_messages()
    print(f"队列消息数: {len(messages)}")
    
    # 获取统计
    if session_key:
        stats = teaching_backend.get_session_statistics()
        print(f"会话统计: {stats}")
    
    print("✅ 测试完成")

if __name__ == "__main__":
    main()
