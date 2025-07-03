# AI在线教学平台用户角色权限设计

## 🎯 产品定位回顾

AI在线教学平台是一个**1对1 AI教师在线教学平台**，核心特色：
- 学生与AI数字人教师实时音视频互动
- 支持多学科（数学、语文、英语等）教学
- 基于WebRTC的低延迟实时通讯
- 个性化AI教学内容生成

## 👥 用户角色体系设计

### 核心角色（3个）

#### 1. **学生 (Student)** - 主要用户群体
**角色定位**：平台的核心用户，学习服务的接受方

**核心权限**：
- ✅ 用户注册登录和个人信息管理
- ✅ 选择年级和学科偏好
- ✅ 浏览和选择课程
- ✅ 进入1对1教学房间
- ✅ 与AI教师进行音视频互动
- ✅ 使用文字聊天辅助功能
- ✅ 查看个人学习记录和进度
- ✅ 接收课程推荐
- ❌ 不能访问其他学生信息
- ❌ 不能修改课程内容
- ❌ 不能进行系统管理操作

**数据字段**：
```python
# 学生特有字段
grade_level: str           # 年级："小学三年级"、"初中一年级"
parent_contact: str        # 家长联系方式
learning_preferences: dict # 学习偏好：{"preferred_subject": "math", "study_time": "evening"}
```

#### 2. **AI教师 (AI Teacher)** - 系统内置角色
**角色定位**：系统内置的数字人教师，提供教学服务

**系统能力**：
- 🤖 ASR语音识别处理学生输入
- 🤖 LLM生成个性化教学内容
- 🤖 TTS合成自然语音输出
- 🤖 驱动数字人表情和动作
- 🤖 根据课程配置调整教学策略
- 🤖 实时响应学生问题和需求

**技术特性**：
- 支持多种数字人模型（MuseTalk、LiteAvatar、LAM）
- 可配置不同学科的专业提示词
- 个性化教学风格调整
- 多模态交互能力

#### 3. **平台管理员 (Platform Admin)** - 运营管理角色
**角色定位**：平台运营和内容管理人员

**核心权限**：
- ✅ 用户账户管理（学生注册审核、状态管理）
- ✅ 课程内容创建和管理
- ✅ AI教师配置和优化
- ✅ 教学素材上传和管理
- ✅ 系统监控和维护
- ✅ 学习数据统计和分析
- ✅ 平台配置和设置
- ✅ 用户反馈处理

**管理功能**：
```python
# 管理员功能示例
create_course()              # 创建课程
update_ai_teacher_prompt()   # 更新AI教师提示词
manage_user_accounts()       # 管理用户账户
view_platform_analytics()   # 查看平台分析
```

### 扩展角色（未来版本）

#### 4. **家长 (Parent)** - 监护角色
**角色定位**：学生家长，关注孩子学习状况

**核心权限**：
- ✅ 查看孩子学习记录和进度报告
- ✅ 接收学习通知和反馈
- ✅ 管理孩子学习时间安排
- ✅ 与AI教师沟通孩子学习情况
- ❌ 不能直接参与教学过程
- ❌ 不能修改课程内容

## 🔐 权限层级设计

### 权限等级
```
系统管理员 (Admin) - Level 3
    ↓ 拥有所有权限
家长 (Parent) - Level 2  
    ↓ 可查看关联学生信息
学生 (Student) - Level 1
    ↓ 只能访问自己的信息
```

### 权限验证逻辑
```python
def check_permission(user_role: str, required_level: str) -> bool:
    role_hierarchy = {
        'student': 1,
        'parent': 2, 
        'admin': 3
    }
    return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_level, 999)
```

## 📚 课程权限设计

### 课程访问权限
- **学生**：只能访问适合自己年级的课程
- **家长**：可查看孩子选择的课程信息
- **管理员**：可管理所有课程内容

### 课程内容权限
```python
class CoursePermission:
    VIEW_COURSE = "view_course"           # 查看课程
    ENTER_CLASSROOM = "enter_classroom"   # 进入教学房间
    MANAGE_COURSE = "manage_course"       # 管理课程内容
    CREATE_COURSE = "create_course"       # 创建课程
```

## 🎨 用户界面权限

### 学生界面功能
```
首页 → 课程选择 → 教学房间 → 学习记录
├── 个人信息管理
├── 课程推荐
├── 学习进度查看
└── 帮助支持
```

### 管理员界面功能
```
管理控制台
├── 用户管理
│   ├── 学生账户管理
│   ├── 用户状态控制
│   └── 注册审核
├── 课程管理  
│   ├── 课程创建/编辑
│   ├── AI教师配置
│   └── 教学素材管理
├── 数据分析
│   ├── 学习统计
│   ├── 课程使用情况
│   └── 平台运营数据
└── 系统设置
    ├── 平台配置
    ├── 性能监控
    └── 日志管理
```

## 🔧 技术实现要点

### 1. 数据库设计
```sql
-- 用户表支持角色
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',  -- student/admin/parent
    grade_level VARCHAR(20),                      -- 学生年级
    parent_contact VARCHAR(100),                  -- 家长联系方式
    learning_preferences JSONB DEFAULT '{}'       -- 学习偏好
);

-- 课程表支持AI教学
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    subject VARCHAR(20) NOT NULL,                 -- math/chinese/english...
    grade_level VARCHAR(20) NOT NULL,             -- 适用年级
    ai_teacher_prompt TEXT,                       -- AI教师提示词
    teaching_objectives JSONB DEFAULT '[]',       -- 教学目标
    knowledge_points JSONB DEFAULT '[]'           -- 知识点
);
```

### 2. 权限检查装饰器
```python
def require_permission(required_role: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_session = get_current_user_session()
            if not check_permission(user_session['role'], required_role):
                raise PermissionError("Insufficient permissions")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# 使用示例
@require_permission('admin')
def create_course(course_data):
    # 只有管理员可以创建课程
    pass
```

### 3. 用户服务API设计
```python
class UserService:
    def create_student()      # 创建学生用户
    def create_admin()        # 创建管理员用户
    def authenticate_user()   # 用户认证
    def check_permission()    # 权限检查
    def get_students_list()   # 获取学生列表（管理员功能）
    def update_student_profile()  # 更新学生档案
```

## 🚀 实施计划

### Phase 1: 基础角色实现（当前）
- ✅ 学生角色和权限系统
- ✅ 基础的管理员功能
- ✅ 用户认证和会话管理
- ✅ 课程基础管理

### Phase 2: 功能完善
- 🔄 完善管理员控制台
- 🔄 学生学习数据统计
- 🔄 课程推荐算法
- 🔄 用户体验优化

### Phase 3: 扩展功能
- ⏳ 家长角色集成
- ⏳ 多租户支持
- ⏳ 高级分析功能
- ⏳ 移动端适配

## 📝 总结

AI在线教学平台的用户角色设计遵循**简单实用**的原则：

1. **核心用户**：学生是平台的主要服务对象
2. **技术角色**：AI教师提供智能化教学服务  
3. **管理角色**：管理员确保平台稳定运营
4. **扩展空间**：为未来的家长角色预留接口

这种设计既满足了当前1对1 AI教学的核心需求，又为未来的功能扩展提供了良好的架构基础。 