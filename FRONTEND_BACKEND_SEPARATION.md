# AI在线教学平台 - 前后端分离架构

## 架构概述

原有的 `teaching_demo.py` 文件包含了所有功能（界面、业务逻辑、数据处理），代码量超过1100行，难以维护。现在已重构为清晰的前后端分离架构。

## 新架构设计

### 文件结构
```
src/
├── frontend/
│   └── teaching_frontend.py    # 前端界面层 - Gradio UI定义
├── backend/
│   └── teaching_backend.py     # 后端业务层 - 逻辑处理
├── api/
│   └── teaching_api.py         # API接口层 - 前后端连接
└── teaching_demo.py            # 主启动文件 - 精简版
```

### 模块职责

#### 1. Frontend (前端界面层)
**文件**: `src/frontend/teaching_frontend.py`
**职责**:
- Gradio界面组件定义
- CSS样式管理
- UI布局和组件结构
- HTML模板生成
- 前端数据展示格式化

**主要类**:
- `TeachingFrontend`: 前端界面管理类

#### 2. Backend (后端业务层)
**文件**: `src/backend/teaching_backend.py`
**职责**:
- ChatEngine集成和管理
- 日志监听和消息处理
- 教学逻辑和智能回复生成
- 数据存储和状态管理
- 课程内容配置

**主要类**:
- `TeachingBackend`: 后端业务逻辑类

#### 3. API (接口层)
**文件**: `src/api/teaching_api.py`
**职责**:
- 连接前端和后端
- 事件绑定和处理
- 数据格式转换
- 接口统一管理

**主要类**:
- `TeachingAPI`: API接口管理类

#### 4. Main (主启动文件)
**文件**: `src/teaching_demo.py`
**职责**:
- 应用初始化和配置加载
- 模块整合和启动
- 错误处理和优雅退出

## 核心优势

### 1. 可维护性提升
- **单一职责**: 每个模块职责清晰，便于理解和修改
- **代码分离**: 前端UI和后端逻辑完全分离
- **模块化**: 独立的模块可以单独测试和开发

### 2. 扩展性增强
- **插件化**: 新功能可以作为独立模块添加
- **接口标准化**: 统一的API接口便于功能扩展
- **配置化**: 通过配置文件灵活调整功能

### 3. 团队协作
- **并行开发**: 前端和后端可以并行开发
- **技能专精**: UI开发者专注前端，算法开发者专注后端
- **版本控制**: 模块独立，减少代码冲突

## 启动方式

### 使用新的启动脚本
```bash
# 基础启动
./start_teaching_new.sh

# 指定配置文件
./start_teaching_new.sh config/teaching_basic.yaml

# 指定主机和端口
./start_teaching_new.sh config/teaching_basic.yaml 0.0.0.0 8285
```

### 直接Python启动
```bash
python3 src/teaching_demo.py --config config/teaching_basic.yaml --host 0.0.0.0 --port 8285
```

## 配置文件

新架构使用 `config/teaching_basic.yaml` 配置文件，包含：
- 服务器设置
- ChatEngine配置
- 教学特定设置
- 环境变量配置

## 兼容性

### 保持原有功能
- ✅ 所有原有UI功能完全保留
- ✅ 课程选择和教学对话功能不变
- ✅ 实时对话监听和显示功能完整
- ✅ ChatEngine集成和WebRTC支持

### 新增特性
- ✅ 模块化架构，便于维护
- ✅ 标准化API接口
- ✅ 配置文件驱动
- ✅ 更好的错误处理

## 迁移指南

### 从原版本迁移
1. 使用新的启动脚本: `./start_teaching_new.sh`
2. 配置环境变量: `export DASHSCOPE_API_KEY=your_key`
3. 确认配置文件: `config/teaching_basic.yaml`

### 自定义开发
1. **修改UI**: 编辑 `src/frontend/teaching_frontend.py`
2. **修改业务逻辑**: 编辑 `src/backend/teaching_backend.py`
3. **添加新接口**: 编辑 `src/api/teaching_api.py`

## 技术细节

### 数据流
```
用户操作 → Frontend → API → Backend → ChatEngine
         ↑                              ↓
    UI更新 ← API ← Backend ← 响应处理
```

### 关键接口
- `teaching_api.start_learning_session()`: 开始学习会话
- `teaching_api.send_message()`: 发送消息
- `teaching_api.update_real_chat_display()`: 更新实时对话
- `teaching_api.bind_events()`: 绑定UI事件

### 状态管理
- Frontend: UI状态和显示格式
- Backend: 业务状态和数据存储
- API: 状态同步和转换

## 故障排除

### 常见问题
1. **模块导入错误**: 确保项目目录在Python路径中
2. **配置文件错误**: 检查YAML语法和路径
3. **环境变量**: 确保必要的API密钥已设置

### 调试方法
1. 检查日志: `logs/teaching.log`
2. 使用调试按钮: UI中的"显示调试信息"
3. 单独测试模块: 可以独立导入和测试各个模块

## 下一步计划

1. **性能优化**: 前后端数据传输优化
2. **功能扩展**: 添加更多教学模式
3. **测试完善**: 单元测试和集成测试
4. **文档完善**: API文档和开发指南

---

这个新架构为AI在线教学平台提供了更好的可维护性和扩展性，为后续开发奠定了坚实的基础。 