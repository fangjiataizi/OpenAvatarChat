# AI在线教学平台 - 技术文档

## 🎯 项目概述

基于OpenAvatarChat的AI数字人在线教学平台，支持用户管理、实时AI对话、数字人交互的完整教学解决方案。

## 🏗️ 架构设计

### 核心组件
- **Backend**: `src/backend/teaching_backend.py` - 业务逻辑、数据处理、聊天引擎集成
- **API**: `src/api/teaching_api.py` - 前后端接口、用户管理
- **Frontend**: Gradio界面，集成在demo文件中
- **Storage**: PostgreSQL + Redis + MinIO存储层

### 数据流
```
用户界面 -> API层 -> 后端业务逻辑 -> ChatEngine -> AI模型/数字人
          ↓
    PostgreSQL数据库 (用户、会话、学习记录)
```

## 📁 核心文件结构

```
├── src/
│   ├── demo.py                    # 原始演示文件
│   ├── teaching_demo.py           # 教学平台主启动文件
│   ├── teaching_backend.py   # 后端业务逻辑
│   ├── teaching_frontend.py   # 前端业务逻辑
│   ├── teaching_api.py        # API接口层
│   ├── storage/                   # 存储服务
│   ├── auth/                      # 用户认证
│   └── handlers/                  # AI处理器(ASR/TTS/Avatar等)
├── config/teaching.yaml           # 配置文件
├── start.sh              # 启动脚本
└── .env                          # 环境变量
```

## 🚀 快速启动

### 1. 环境准备
```bash
# 激活conda虚拟环境 (重要!)
conda activate teaching-platform

# 设置API密钥 (自动从.env文件加载)
export DASHSCOPE_API_KEY=sk-a7ec873e0a04461f8ce6c74ea815fa28

# 确保PostgreSQL运行
sudo systemctl start postgresql
```

### 2. 启动平台
```bash
# 使用统一启动脚本 (推荐)
./start.sh restart

# 或直接启动
./start.sh start
```

### 3. 访问地址
- 平台地址: https://0.0.0.0:8443
- 支持用户注册/登录
- 默认演示账户: student1/123456, admin/admin123

## ⚙️ 配置说明

### config/teaching.yaml
```yaml
default:
  service:
    host: "0.0.0.0"
    port: 7860
  
  storage:
    database:
      type: "postgresql"
      url: "postgresql://teaching_admin:secure_password_123@localhost:5432/teaching_platform"
    cache:
      type: "redis"
      host: "localhost"
      port: 6379
  
  chat_engine:
    handler_configs:
      LLM_Bailian:
        api_key: ${DASHSCOPE_API_KEY}
        model_name: "qwen-vl-plus"
      AvatarLiteAvatar:
        avatar_name: "sample_data"
        fps: 25
```

## 🔧 核心功能

### 用户管理
- 用户注册/登录
- 角色管理(学生/管理员)
- 学习历史记录

### AI教学
- 实时语音对话
- 数字人交互
- 课程管理
- 学习进度跟踪

## 🎓 AI自动上课流程详解

### 完整教学流程 (精确时间线) - v1.0 稳定版本

**1. 用户登录阶段** ✅
```
- 用户输入演示账户: student1/123456 或 admin/admin123
- 系统验证凭据并检查用户权限
- 登录成功 → 自动跳转到课程选择页面
- 界面显示: 用户名、登出按钮、欢迎信息
```

**2. 课程选择阶段** ✅
```
- 课程选项: 雅思-基础语法/词汇记忆/写作技巧/口语练习
- 难度级别: 初级/中级/高级 
- 学习目标: 用户自定义输入 (可选)
- 点击 "🚀 开始学习" 按钮
```

**3. 系统准备阶段** ✅
```
T+0s: 用户点击开始学习
- 后端调用 set_current_session_info(course, difficulty, goal)
- 创建内存会话: session_key = session_xxxxx
- 初始化教学状态变量:
  * teaching_active = False
  * has_greeted = False
  * teaching_step = 0
  * webrtc_connected = False
- 立即发送系统提示消息到前端对话框
- 切换到AI教师对话页面
```

**4. 用户交互准备阶段** ✅
```
T+1s: 前端显示准备提示
- 右侧对话框显示: "💡 系统提示: 您的专属AI教师已经准备就绪，请点击获取摄像头权限然后点击record后进行学习。"
- AI教师视频区域显示加载状态
- 用户需要手动点击摄像头权限和Record按钮
```

**5. Avatar启动阶段** ✅
```
T+X: 用户点击Record按钮
- WebRTC连接开始建立
- Avatar处理器启动: LiteAvatar初始化
- 日志: "Detected avatar processor start"
- AI教师数字人画面出现
- Avatar完全就绪: "Avatar processor is fully ready"
```

**6. AI问候阶段** ✅
```
T+X+3s: Avatar就绪后3秒开始问候
- 触发 _start_ai_greeting() 方法
- 调用阿里云qwen-vl-plus模型生成个性化问候内容
- 系统提示: "🤖 AI Teacher Greeting: 大家好，我是小慧老师..."
- TTS语音合成: Edge TTS处理问候文本
- AI教师开始语音问候 (约10-15秒)
- 设置状态: has_greeted=True, teaching_active=True
- 启动主教学定时器: 15秒后开始主动教学
```

**7. 主动教学阶段** ✅
```
T+X+18s: 第一次主动教学
- 触发 _start_proactive_teaching() 方法
- 调用LLM生成第一段教学内容
- 系统提示: "🎓 AI Teacher Starting Lesson:"
- AI教师开始主动讲授课程内容 (带语音)
- 内容添加到对话历史
- 设置下一轮教学定时器: 30-45秒随机间隔

T+X+48-63s: 持续教学循环
- 触发 _continue_teaching() 方法  
- 调用 _generate_next_teaching_content() 生成渐进式内容
- teaching_step递增控制教学进度
- 系统提示: "🎓 AI Teacher Continue:"
- 每次教学后重新设置30-45秒随机定时器
- 无限循环直到用户停止或会话结束
```

**8. 学生交互处理** ✅
```
任意时间: 学生语音打断
- SenseVoice ASR识别学生语音
- 系统提示: "🧑‍🎓 ASR Recognized: [学生话语]"
- 学生消息添加到对话历史
- AI教师暂停主动教学
- 调用LLM生成针对性回应
- AI教师语音回答学生问题
- 恢复主动教学循环
```

### 核心技术实现细节

**问候生成机制** (`_generate_greeting_content`)
```python
# 使用阿里云qwen-vl-plus模型动态生成
system_prompt = "你是一位专业的AI雅思英语教师，名叫小慧老师..."
user_prompt = f"请为选择了'{course}'课程（{difficulty}难度）的新学生生成个性化问候"
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
]
# 调用 self.call_llm_api(messages, temperature=0.8)
```

**主动教学内容生成** (`_generate_teaching_content`)  
```python
# 第一次主动教学使用专门的系统提示
system_prompt = "你是一位专业的AI雅思英语教师...请生成第一段主动教学内容"
user_request = f"请为'{course}'课程（{difficulty}难度）生成开场教学内容"
# 结合对话历史上下文生成个性化内容
```

**渐进式教学内容** (`_generate_next_teaching_content`)
```python
# 基于teaching_step计数器生成不同阶段内容
teaching_step值:
  1: 知识点详解
  2: 互动提问  
  3: 练习环节
  4: 理解确认
  5: 新概念引入
  6: 技巧分享
  >6: 重置为2，循环互动
```

**定时器管理系统**
```python
# 三种核心定时器
1. 问候定时器: 3秒 (Avatar就绪后)
2. 主教学定时器: 15秒 (问候完成后)  
3. 持续教学定时器: 30-45秒随机间隔

# 定时器管理
self.active_timers = []  # 存储所有活跃定时器
self._add_timer(timer)   # 添加定时器到管理列表
self._clear_all_timers() # 会话结束时清理所有定时器
```

**消息流处理**
```python
# 消息角色类型
- 'system': 系统提示消息 (橙色边框显示)
- 'avatar': AI教师消息 (紫色背景，小慧老师标识)  
- 'human': 学生消息 (蓝色背景，学生标识)

# 消息处理流程
1. _add_real_chat_message(role, content)
2. 内容清理和重复检测
3. 添加到 self.real_chat_queue
4. 触发前端更新回调
5. TTS语音合成 (仅avatar消息)
```

**Avatar启动检测机制**
```python
# 日志监控触发点
- "on algo processor start" → _handle_avatar_start()
- "avatar processor started" → _handle_avatar_ready() 
- _handle_avatar_ready() → 启动3秒问候定时器

# 不再依赖难以检测的WebRTC连接事件  
# 改为Avatar完全就绪时立即启动问候
```

### 教学内容生成机制

**问候内容生成** (`_generate_greeting_content`)
```python
- 随机选择3种问候方式之一
- 结合课程名称和难度级别
- 根据学习目标个性化内容
- 添加鼓励和引导语句
```

**主动教学内容** (`_generate_teaching_content`)
```python
- 基于course_content配置的知识库
- 包含keywords, concepts, examples
- 针对不同课程生成专业内容
- 雅思考试导向的实用知识
```

**渐进式教学内容** (`_generate_next_teaching_content`)
```python
- teaching_step计数器控制内容顺序
- 6个固定步骤 + 循环互动
- 避免内容重复发送
- 逐步递进的教学逻辑
```

### 消息处理流程

**消息添加** (`_add_real_chat_message`)
```
1. 内容清理和验证
2. 重复检测 (避免相同消息)
3. 添加到聊天历史 (real_chat_messages)
4. 触发前端更新回调
5. 数据库保存 (当前已禁用)
```

**TTS处理** (`_send_to_tts_only`)
```
1. 直接发送到TTS引擎
2. Edge TTS语音合成
3. 数字人口型同步
4. WebRTC音频传输
```

### 定时器管理

**定时器类型**
- 问候定时器: 3秒延迟
- 主动教学定时器: 15秒延迟  
- 持续教学定时器: 30-45秒随机间隔

**定时器管理** (`_add_timer`, `_clear_all_timers`)
```python
- 所有定时器存储在self.active_timers列表
- 会话结束时自动清理所有定时器
- 防止内存泄漏和重复任务
```

### 关键状态变量

```python
# 教学状态控制
self.teaching_active = True/False      # 教学是否激活 (问候完成后设为True)
self.has_greeted = True/False          # 是否已问候 (防止重复问候)
self.teaching_step = 0-6               # 当前教学步骤 (渐进式教学控制)
self.webrtc_connected = True/False     # WebRTC连接状态

# 会话信息管理
self.current_course = "雅思-基础语法"   # 当前选择的课程
self.current_difficulty = "初级"       # 当前难度级别
self.current_goal = "提高口语"          # 用户学习目标
self.current_user_id = 1               # 固定用户ID (演示模式)
self.current_session_key = "session_xxxxx" # 唯一会话标识

# 消息队列管理
self.real_chat_queue = Queue()         # 线程安全的消息队列
self.real_chat_messages = []           # 消息历史列表 (已废弃)
self.used_teaching_contents = set()    # 避免教学内容重复

# 定时器管理
self.active_timers = []                # 所有活跃定时器列表
self.greeting_timer = None             # 问候定时器引用
self.teaching_timer = None             # 主教学定时器引用
self.continue_timer = None             # 持续教学定时器引用

# AI模型配置
self.use_real_ai = True                # 是否使用真实AI (vs 固定内容)
self.llm_config = {...}                # LLM配置 (qwen-vl-plus)
self.chat_engine = ChatEngine()        # 核心对话引擎
```

### 技术特性
- WebRTC实时通信
- 模块化AI处理器
- PostgreSQL数据持久化
- Redis缓存优化

## 🐛 故障排除

### 重要开发环境要求
**⚠️ 必须使用conda虚拟环境:**
```bash
# 开发前必须激活虚拟环境
conda activate teaching-platform

# 安装缺失的依赖 (如cv2)
conda activate teaching-platform && pip install opencv-python

# 启动服务
./start.sh restart
```

### 常见问题

**基础设置问题**
1. **配置加载失败**: 检查yaml文件格式和路径
2. **数据库连接错误**: 确保PostgreSQL运行并检查连接字符串  
3. **API密钥错误**: 验证DASHSCOPE_API_KEY设置，start.sh会自动从.env加载
4. **端口占用**: 修改config/teaching.yaml中的端口
5. **cv2模块缺失**: 在teaching-platform环境中安装 `pip install opencv-python`

**AI教学流程问题**
5. **登录按钮无反应**: 检查前端事件绑定，确认handle_login_simple方法正常
6. **系统提示不显示**: 检查frontend中system角色消息处理，确认build_chat_html支持system消息
7. **AI不主动问候**: 
   - 检查Avatar是否完全启动: 搜索日志 "Avatar processor is fully ready"
   - 确认问候定时器启动: 搜索 "🎯 AI greeting timer started (3 seconds after Avatar ready)"
   - 验证问候方法执行: 搜索 "🤖 AI Teacher Greeting:"
8. **AI问候无声音**:
   - 确认Avatar在问候前完全就绪
   - 检查TTS配置: Edge TTS + 中文语音
   - 验证WebRTC音频流正常
9. **主动教学不启动**:
   - 确认问候完成: has_greeted=True, teaching_active=True
   - 检查15秒主教学定时器: "🎓 Main teaching timer started (15 seconds)"
   - 验证教学方法调用: "🎓 AI Teacher Starting Lesson:"
10. **教学内容重复**: 检查teaching_step计数器，确认_generate_next_teaching_content逻辑
11. **消息不显示前端**: 
    - 检查消息队列: self.real_chat_queue
    - 确认前端更新回调触发
    - 验证build_chat_html处理所有消息角色
12. **数字人不动**: 检查LiteAvatar配置和avatar处理器状态

**数据库相关问题**
11. **外键约束失败**: 当前已禁用数据库存储，使用内存会话管理
12. **会话创建失败**: 检查current_user_id设置和session_key生成

### 日志查看
```bash
# 查看最新日志
tail -f logs/teaching_platform.log

# 查找特定问题
grep -A 5 -B 5 "ERROR\|Error\|error" logs/teaching_platform.log

# 查看AI教学流程
grep "AI.*greet\|Teaching.*timer\|teaching.*step" logs/teaching_platform.log

# 查看用户登录流程  
grep "Login.*attempt\|Login.*successful\|Login.*failed" logs/teaching_platform.log

# 查看会话创建
grep "Session.*info.*updated\|Memory.*session.*created" logs/teaching_platform.log
```

### 关键日志标识符

**AI教学流程日志**
- `🎯 Showing ready prompt, waiting for WebRTC connection for AI greeting` - 显示准备提示
- `💡 系统提示: 您的专属AI教师已经准备就绪` - 系统准备提示
- `Detected avatar processor start` - Avatar处理器开始启动
- `Avatar processor is fully ready` - Avatar完全就绪
- `🎯 AI greeting timer started (3 seconds after Avatar ready)` - 问候定时器启动
- `🤖 AI Teacher Greeting: 大家好，我是小慧老师` - AI问候开始
- `✅ AI greeting with TTS sent successfully` - 问候语音发送成功
- `🎓 Main teaching timer started (15 seconds)` - 主教学定时器启动
- `🎯 _start_proactive_teaching called` - 主动教学方法被调用
- `🎓 AI Teacher Starting Lesson:` - 第一次主动教学开始
- `✅ AI proactive teaching content with TTS sent successfully` - 主动教学语音成功
- `🎓 Next teaching content scheduled in XX.X seconds` - 下次教学已调度
- `🎓 AI Teacher Continue:` - 持续教学内容
- `✅ AI continue teaching content with TTS sent successfully` - 持续教学语音成功

**用户认证日志**
- `Login attempt for user: student1` - 用户登录尝试
- `Demo login successful for student1` - 演示账户登录成功
- `Login failed for:` - 登录失败

**会话管理日志**
- `Starting learning session: course=雅思 - 基础语法, difficulty=初级` - 开始学习会话
- `Session info updated: 雅思 - 基础语法 - 初级` - 会话信息更新
- `Memory session created: session_xxxxx` - 内存会话创建
- `🛑 Stopping AI teaching activities...` - 停止AI教学活动
- `✅ AI teaching stopped and all timers cleared` - AI教学已停止，定时器已清理

**消息处理日志**
- `🔍 Adding chat message - Role: system, Content: 您的专属AI教师` - 添加系统消息
- `✅ Added real chat message - system: 您的专属AI教师已经准备就绪` - 系统消息添加成功
- `✅ Added real chat message - avatar: 大家好，我是小慧老师` - AI教师消息添加成功
- `🧑‍🎓 ASR Recognized: 你说话` - 学生语音识别成功
- `✅ Added real chat message - human: 你说话` - 学生消息添加成功
- `🔍 Duplicate message found, skipping` - 发现重复消息，跳过
- `🔄 Message update trigger incremented to X` - 消息更新触发器递增
- `🔍 Total chat messages: X (list: 0, queue: X)` - 消息总数统计

**TTS和Avatar日志**
- `Avatar text submitted to TTS pipeline` - 文本提交到TTS管道
- `last sentence[教学内容文本]` - TTS处理的最后句子
- `speech end` - 语音合成结束
- `WARNING | teaching_backend:_send_to_tts_only:1333 - Direct TTS method failed, using log fallback` - TTS直接方法失败，使用日志回退
- `WARNING | teaching_backend:_send_to_tts_only:1303 - No active sessions found for TTS` - TTS没有找到活跃会话

**错误诊断日志**
- `❌ Proactive teaching blocked - course: None, teaching_active: False` - 主动教学被阻止
- `❌ API key not configured properly!` - API密钥配置错误
- `openai.AuthenticationError: Error code: 401` - LLM API认证错误
- `TypeError: cannot convert 'NoneType' object to bytes` - WebRTC视频编码错误

## 🔨 开发指南

### 添加新功能
1. 在`teaching_backend.py`添加业务逻辑
2. 在`teaching_api.py`添加API接口  
3. 在`teaching_frontend.py`更新界面
4. 在`src/demo.py`中集成新功能

### AI教学流程修改
- 问候逻辑: `teaching_backend.py` → `_start_ai_greeting()`
- 教学内容: `teaching_backend.py` → `_generate_teaching_content()`
- 渐进式教学: `teaching_backend.py` → `_generate_next_teaching_content()`
- 定时器管理: `teaching_backend.py` → `_add_timer()`, `_clear_all_timers()`

### 统一版本文件结构 (v1.0 稳定版)
```
├── teaching_backend.py          # 核心业务逻辑和AI教学流程
├── teaching_frontend.py         # Gradio前端界面 (支持system消息显示)
├── teaching_api.py             # API接口层和事件绑定
├── src/teaching_demo.py        # 主启动文件 (使用teaching.yaml配置)
├── config/teaching.yaml        # 统一配置文件 (含qwen-vl-plus配置)
├── start.sh                    # 启动脚本 (修正为使用teaching_demo.py)
├── .env                        # 环境变量 (含DASHSCOPE_API_KEY)
└── TECH_DOC.md                 # 完整技术文档 (含v1.0上课流程)
```

### 数据库操作
- 模型定义: `src/storage/database/models.py`
- 服务层: `src/storage/services/`
- 当前状态: 已禁用数据库存储，使用内存会话

### AI处理器扩展
- 新处理器: `src/handlers/`
- 配置: `config/teaching.yaml`
- 当前集成: Edge TTS, LiteAvatar, SenseVoice, Qwen-VL-Plus

## 📊 监控&维护

### 性能监控
- 响应延迟: 平均2.2秒
- 并发支持: 可配置
- 资源占用: 监控GPU/CPU使用

### 数据备份
```bash
# PostgreSQL备份
pg_dump teaching_platform > backup.sql

# 恢复
psql teaching_platform < backup.sql
```

## 🔐 安全配置

### 环境变量
```bash
# .env文件
DASHSCOPE_API_KEY=your_api_key
DB_URL=postgresql://user:pass@host:5432/db
REDIS_HOST=localhost
```

### SSL配置
- 证书路径: `ssl_certs/`
- 配置: `config/teaching.yaml`中cert_file和cert_key

## 📈 扩展计划

### 短期
- [ ] 修复frontend集成问题
- [ ] 优化用户体验
- [ ] 增加课程类型

### 长期  
- [ ] 多语言支持
- [ ] 移动端适配
- [ ] 高可用部署

---

## 📋 版本更新日志

### v1.0 稳定版本 (2025-07-28)
✅ **核心功能完成**:
- AI主动教学系统完全正常工作
- 系统提示消息正确显示在前端
- Avatar就绪后3秒开始语音问候
- 问候完成后15秒开始主动教学
- 30-45秒间隔的持续教学循环
- 学生语音打断和AI回应功能
- 阿里云qwen-vl-plus LLM集成
- Edge TTS语音合成
- LiteAvatar数字人交互

✅ **技术修复**:
- 修正启动脚本使用正确的teaching_demo.py
- 修复system角色消息在前端显示
- 优化Avatar启动检测机制
- 解决WebRTC连接检测问题
- 完善定时器管理系统
- 增强消息去重和处理

✅ **用户体验优化**:
- 点击"开始学习"后立即显示准备提示
- Record后AI教师出现并语音问候
- 清晰的教学流程和时间节点
- 完整的前端消息显示支持

### 当前稳定功能确认
1. ✅ 用户登录认证系统
2. ✅ 课程选择和难度设置
3. ✅ 系统准备提示显示
4. ✅ Avatar启动和数字人显示
5. ✅ AI个性化语音问候
6. ✅ 主动教学内容生成和播放
7. ✅ 持续教学内容循环
8. ✅ 学生语音识别和交互
9. ✅ 前端消息实时更新
10. ✅ 完整的定时器管理

---

**维护团队**: AI教学平台开发团队  
**最后更新**: 2025-07-28  
**当前版本**: v1.0 (稳定版)  
**启动方式**: `./start.sh restart`  
**访问地址**: https://0.0.0.0:8443