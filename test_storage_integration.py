# -*- coding: utf-8 -*-
"""
测试数据存储集成功能
验证AI教学平台的消息持久化、会话管理等功能
"""

import sys
import os
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.backend.teaching_backend import teaching_backend

def test_storage_integration():
    """测试存储集成功能"""
    print("🚀 AI教学平台数据存储集成测试")
    print("=" * 50)
    
    # 1. 测试存储可用性
    print(f"✓ Storage Available: {teaching_backend.storage_available}")
    print(f"✓ Current User ID: {teaching_backend.current_user_id}")
    
    if not teaching_backend.storage_available:
        print("❌ 存储服务不可用，使用内存模式测试")
    
    # 2. 创建学习会话
    print("\n📚 创建学习会话...")
    session_data = teaching_backend.create_learning_session(
        course="雅思 - 基础语法",
        difficulty="初级", 
        goal="掌握基础语法"
    )
    
    session_key = session_data.get('session_key')
    print(f"✓ Session Key: {session_key}")
    print(f"✓ Storage Enabled: {session_data.get('storage_enabled')}")
    
    # 3. 测试消息添加
    print("\n💬 测试消息添加...")
    test_messages = [
        {"role": "avatar", "content": "欢迎学习雅思语法！"},
        {"role": "human", "content": "我想学习现在完成时"},
        {"role": "avatar", "content": "现在完成时用来表示过去的动作对现在的影响"}
    ]
    
    for i, msg in enumerate(test_messages):
        success = teaching_backend._add_real_chat_message(
            role=msg["role"],
            content=msg["content"]
        )
        print(f"  消息 {i+1}: {'✅' if success else '❌'} {msg['content'][:30]}...")
        time.sleep(0.5)
    
    # 4. 等待异步保存
    print("\n⏳ 等待异步保存完成...")
    time.sleep(2)
    
    # 5. 检查内存队列
    print("\n🔍 检查内存队列...")
    messages = teaching_backend.get_all_chat_messages()
    print(f"✓ 队列消息数: {len(messages)}")
    
    # 6. 获取会话统计
    if session_key:
        print("\n📊 获取会话统计...")
        stats = teaching_backend.get_session_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    print("\n✅ 数据存储集成测试完成")

if __name__ == "__main__":
    test_storage_integration() 
#!/usr/bin/env python3
 