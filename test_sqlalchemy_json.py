#!/usr/bin/env python3
"""测试SQLAlchemy JSON列更新问题"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.database.connection import db_manager
from src.storage.database.models import LearningSession
from datetime import datetime

def test_json_update():
    print("🔍 测试SQLAlchemy JSON列更新...")
    
    with db_manager.get_session() as session:
        # 获取最新会话
        learning_session = session.query(LearningSession).order_by(LearningSession.id.desc()).first()
        if not learning_session:
            print("❌ 没有找到会话")
            return
        
        print(f"会话ID: {learning_session.id}")
        print(f"当前消息数: {len(learning_session.chat_history)}")
        
        # 尝试方法1: 直接修改
        print("\n方法1: 直接修改chat_history列表...")
        original_count = len(learning_session.chat_history)
        learning_session.chat_history.append({
            'role': 'test',
            'content': '测试消息1',
            'timestamp': datetime.now().isoformat()
        })
        session.commit()
        
        # 重新查询检查
        session.refresh(learning_session)
        new_count1 = len(learning_session.chat_history)
        print(f"方法1结果: {original_count} -> {new_count1}")
        
        # 尝试方法2: 替换整个列表
        print("\n方法2: 替换整个chat_history...")
        old_history = list(learning_session.chat_history)
        old_history.append({
            'role': 'test',
            'content': '测试消息2',
            'timestamp': datetime.now().isoformat()
        })
        learning_session.chat_history = old_history
        session.commit()
        
        # 重新查询检查
        session.refresh(learning_session)
        new_count2 = len(learning_session.chat_history)
        print(f"方法2结果: {new_count1} -> {new_count2}")
        
        # 尝试方法3: 使用flag_modified
        print("\n方法3: 使用flag_modified...")
        from sqlalchemy.orm.attributes import flag_modified
        
        learning_session.chat_history.append({
            'role': 'test',
            'content': '测试消息3',
            'timestamp': datetime.now().isoformat()
        })
        flag_modified(learning_session, 'chat_history')
        session.commit()
        
        # 重新查询检查
        session.refresh(learning_session)
        final_count = len(learning_session.chat_history)
        print(f"方法3结果: {new_count2} -> {final_count}")
        
        print(f"\n最终消息列表:")
        for i, msg in enumerate(learning_session.chat_history):
            print(f"  {i+1}. {msg.get('role')}: {msg.get('content', '')[:30]}...")

if __name__ == "__main__":
    test_json_update()
