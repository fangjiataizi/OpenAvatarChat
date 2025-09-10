#!/usr/bin/env python3
"""
数字人新闻播报系统 - 系统验证脚本
用于验证当前版本的所有核心功能是否正常工作
"""

import sys
import os
import requests
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/home/OpenAvatarChat')
sys.path.insert(0, '/home/OpenAvatarChat/src')
os.chdir('/home/OpenAvatarChat')

def check_service_status():
    """检查服务状态"""
    print("🔍 检查服务状态...")
    try:
        response = requests.get("http://localhost:8444/", timeout=5)
        if response.status_code == 200:
            print("✅ Gradio界面服务正常")
            return True
        else:
            print(f"❌ Gradio界面异常，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        return False

def test_core_generation():
    """测试核心生成功能"""
    print("\n🎯 测试核心生成功能...")
    
    try:
        from optimized_news_interface import OptimizedNewsInterface
        
        interface = OptimizedNewsInterface()
        test_content = "系统验证测试：今天是一个美好的日子。"
        
        print(f"📝 测试内容: {test_content}")
        print("⏳ 开始生成...")
        
        start_time = time.time()
        result = interface.generate_single_news(test_content, 'xiaoxiao_zh')
        end_time = time.time()
        
        status, script, audio_path, video_path, info = result
        
        print(f"📊 生成耗时: {end_time - start_time:.1f}秒")
        print(f"📄 状态: {status}")
        print(f"📝 文稿长度: {len(script) if script else 0}字符")
        print(f"🎵 音频: {'✅' if audio_path else '❌'}")
        print(f"🎬 视频: {'✅' if video_path else '❌'}")
        
        # 检查文件
        files_ok = True
        if audio_path:
            audio_file = Path(audio_path)
            if audio_file.exists():
                size = audio_file.stat().st_size
                print(f"   音频文件: {size:,} bytes")
            else:
                print(f"   ❌ 音频文件不存在: {audio_path}")
                files_ok = False
        
        if video_path:
            video_file = Path(video_path)
            if video_file.exists():
                size = video_file.stat().st_size
                print(f"   视频文件: {size:,} bytes")
            else:
                print(f"   ❌ 视频文件不存在: {video_path}")
                files_ok = False
        
        if "✅ 生成成功" in status and files_ok:
            print("✅ 核心生成功能正常")
            return True
        else:
            print("❌ 核心生成功能异常")
            return False
            
    except Exception as e:
        print(f"❌ 生成测试失败: {e}")
        return False

def check_output_structure():
    """检查输出目录结构"""
    print("\n📁 检查输出目录结构...")
    
    required_dirs = [
        "output/news_broadcast/podcasts",
        "output/news_broadcast/videos"
    ]
    
    all_good = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            files = list(path.glob("*.wav")) + list(path.glob("*.mp4"))
            print(f"✅ {dir_path} ({len(files)} 个文件)")
        else:
            print(f"❌ {dir_path} 不存在")
            all_good = False
    
    return all_good

def check_config_files():
    """检查配置文件"""
    print("\n⚙️ 检查配置文件...")
    
    config_files = [
        "config/news_broadcast.yaml",
        ".env",
        "start_news_broadcast.sh"
    ]
    
    all_good = True
    for file_path in config_files:
        path = Path(file_path)
        if path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} 不存在")
            all_good = False
    
    return all_good

def main():
    """主验证流程"""
    print("🎬 数字人新闻播报系统 - 版本验证")
    print("=" * 50)
    
    checks = [
        ("服务状态", check_service_status),
        ("配置文件", check_config_files),
        ("输出目录", check_output_structure),
        ("核心功能", test_core_generation),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name}检查失败: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("📊 验证结果汇总:")
    
    all_passed = True
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 系统验证通过！所有功能正常工作。")
        print("🌐 可以访问: http://localhost:8444")
        return 0
    else:
        print("⚠️ 系统验证失败，部分功能异常。")
        return 1

if __name__ == "__main__":
    exit(main())
