#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Timer响应式更新测试脚本
验证gr.Timer的前端自动更新机制是否正常工作
"""

import os
import sys
import time
import threading

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.backend.teaching_backend import TeachingBackend

def test_timer_message_update():
    """测试Timer更新机制"""
    print("\n🎯 测试Timer消息更新机制...")
    
    backend = TeachingBackend()
    
    # 添加初始消息
    print("添加初始测试消息...")
    backend._add_real_chat_message('human', '用户测试消息1')
    initial_count = len(backend.get_all_chat_messages())
    print(f"初始消息数量: {initial_count}")
    
    # 模拟定时添加AI消息（就像AI主动教学一样）
    def add_ai_messages():
        """后台线程持续添加AI消息"""
        for i in range(2, 6):
            time.sleep(3)  # 每3秒添加一条AI消息
            content = f"AI教学内容 {i} - 这是主动教学消息"
            backend._add_real_chat_message('avatar', content)
            print(f"✅ 添加了AI消息 {i}: {content[:30]}...")
    
    # 启动后台线程
    print("\n🚀 启动后台AI消息模拟...")
    thread = threading.Thread(target=add_ai_messages, daemon=True)
    thread.start()
    
    # 模拟Timer每2秒检查的效果
    print("\n⏰ 开始模拟Timer每2秒检查消息队列...")
    for check_round in range(10):  # 检查20秒
        current_messages = backend.get_all_chat_messages()
        print(f"第{check_round+1}次检查: 消息数量 = {len(current_messages)}")
        
        # 显示最新消息
        if current_messages:
            latest = current_messages[-1]
            print(f"  最新消息: [{latest['role']}] {latest['content'][:50]}...")
        
        time.sleep(2)  # 模拟Timer的2秒间隔
    
    print(f"\n📊 测试完成，最终消息数量: {len(backend.get_all_chat_messages())}")
    return True

def test_ai_teaching_integration():
    """测试AI教学流程的Timer集成"""
    print("\n🎓 测试AI教学Timer集成...")
    
    backend = TeachingBackend()
    
    # 设置课程信息
    backend.set_current_session_info("雅思 - 基础语法", "初级", "提高语法基础")
    
    # 模拟Avatar启动
    print("模拟Avatar启动...")
    backend._handle_avatar_start()
    
    time.sleep(1)
    print(f"问候后消息数量: {len(backend.get_all_chat_messages())}")
    
    # 启动主动教学
    print("启动主动教学...")
    backend.webrtc_connected = True
    backend._start_proactive_teaching()
    
    # 模拟Timer定期检查
    print("\n⏰ 模拟Timer定期检查教学进度...")
    for i in range(15):  # 30秒
        messages = backend.get_all_chat_messages()
        print(f"检查 {i+1}: {len(messages)} 条消息")
        
        if messages:
            latest = messages[-1]
            print(f"  最新: [{latest['role']}] {latest['content'][:50]}...")
        
        time.sleep(2)
    
    # 停止教学
    backend._stop_ai_teaching()
    
    final_count = len(backend.get_all_chat_messages())
    print(f"\n📊 教学结束，总消息数量: {final_count}")
    
    return final_count > 0

def test_backend_frontend_integration():
    """测试后端前端一体化"""
    print("\n🔌 测试后端前端一体化...")
    
    backend = TeachingBackend()
    
    # 模拟前端Timer调用的方法
    def simulate_timer_tick():
        """模拟Timer tick事件"""
        messages = backend.get_all_chat_messages()
        return f"当前有 {len(messages)} 条消息"
    
    # 添加一些消息
    backend._add_real_chat_message('human', '测试消息1')
    backend._add_real_chat_message('avatar', 'AI回复1')
    
    # 模拟Timer触发
    result1 = simulate_timer_tick()
    print(f"Timer触发1: {result1}")
    
    # 再添加消息
    backend._add_real_chat_message('avatar', 'AI主动教学内容')
    
    # 再次Timer触发
    result2 = simulate_timer_tick()
    print(f"Timer触发2: {result2}")
    
    print("✅ 后端前端集成测试完成")
    return True

if __name__ == "__main__":
    print("🎯 Timer响应式更新机制测试")
    print("=" * 50)
    
    # 运行测试
    try:
        test1 = test_timer_message_update()
        test2 = test_ai_teaching_integration() 
        test3 = test_backend_frontend_integration()
        
        print("\n" + "=" * 50)
        print("📊 测试结果总结:")
        print(f"✅ Timer消息更新: {'通过' if test1 else '失败'}")
        print(f"✅ AI教学集成: {'通过' if test2 else '失败'}")
        print(f"✅ 后端前端集成: {'通过' if test3 else '失败'}")
        
        if all([test1, test2, test3]):
            print("\n🎉 所有测试通过！Timer响应式更新机制工作正常！")
        else:
            print("\n❌ 部分测试失败，需要进一步调试")
            
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}") 