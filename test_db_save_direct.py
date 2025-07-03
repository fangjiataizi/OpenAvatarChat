#!/usr/bin/env python3
"""直接测试数据库保存功能"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.services.learning_session_service import learning_session_service
import time

def test_direct_save():
    print("🔍 直接测试数据库保存...")
    
    # 获取现有会话
    sessions = learning_session_service.get_user_sessions(user_id=1, limit=1)
    if not sessions:
        print("❌ 没有找到会话")
        return
    
    session_key = sessions[0]['session_key']
    print(f"使用会话: {session_key}")
    
    # 直接添加消息
    print("添加测试消息...")
    success1 = learning_session_service.add_message_to_session(
        session_key=session_key,
        role="avatar",
        content="这是直接保存的AI消息",
        message_type="proactive"
    )
    
    success2 = learning_session_service.add_message_to_session(
        session_key=session_key,
        role="human", 
        content="这是直接保存的用户消息",
        message_type="normal"
    )
    
    print(f"保存结果: avatar={success1}, human={success2}")
    
    # 立即检查
    session_data = learning_session_service.get_session(session_key)
    if session_data:
        print(f"保存后消息数量: {len(session_data.get('chat_history', []))}")
        for i, msg in enumerate(session_data.get('chat_history', [])):
            print(f"  {i+1}. {msg.get('role')}: {msg.get('content', '')[:30]}...")
    
    print("✅ 直接保存测试完成")

if __name__ == "__main__":
    test_direct_save()
