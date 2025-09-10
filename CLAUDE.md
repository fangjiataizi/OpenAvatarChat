# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenAvatarChat is a modular AI-powered digital human teaching platform that combines real-time video communication with intelligent conversational AI. This is a fork/extension that includes specialized teaching functionality, with both the original OpenAvatarChat framework and a custom teaching platform implementation.

### Key Features
- **AI Digital Human Teaching**: Real-time avatar-based teaching using LiteAvatar, LAM, or MuseTalk
- **Proactive Teaching System**: Automatic content delivery with configurable intervals  
- **Multi-modal AI**: Supports text, audio, video interactions via various LLM backends
- **WebRTC Communication**: Low-latency real-time video/audio streaming
- **Modular Architecture**: Pluggable handlers for ASR, TTS, LLM, Avatar rendering
- **Teaching Content Management**: IELTS curriculum with grammar, vocabulary, writing, speaking

## Architecture

The project uses a modular handler-based architecture:

```
src/
├── handlers/           # Modular components (ASR, TTS, LLM, Avatar, etc.)
│   ├── asr/           # Speech recognition (SenseVoice)
│   ├── tts/           # Text-to-speech (CosyVoice, EdgeTTS)
│   ├── llm/           # Language models (MiniCPM, OpenAI-compatible)
│   ├── avatar/        # Avatar rendering (LiteAvatar, LAM, MuseTalk)
│   ├── vad/           # Voice activity detection
│   └── client/        # WebRTC client handlers
├── chat_engine/       # Core conversation engine
├── service/           # Service layer and data models  
├── storage/           # Database and caching (PostgreSQL, Redis)
├── auth/              # Authentication utilities
└── demo.py            # Main application entry point
```

### Teaching Platform Files
- `teaching_demo.py`: Teaching-specific demo entry point
- `teaching_backend.py`: Core teaching logic with proactive content delivery
- `teaching_frontend.py`: Gradio-based web interface
- `teaching_api.py`: API layer connecting frontend/backend

## Development Commands

### Environment Setup
```bash
# Install UV package manager (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies
uv sync --all-packages

# Install dependencies for specific config only
uv run install.py --uv --config config/teaching.yaml
```

### Running the Application

#### Teaching Platform
```bash
# Start teaching platform (recommended)
./start.sh start

# With custom config
./start.sh start config/teaching.yaml

# With custom host/port  
./start.sh start config/teaching.yaml 0.0.0.0 8443

# Stop/restart services
./start.sh stop
./start.sh restart
```

#### Original OpenAvatarChat Demo
```bash
# Run with default config
uv run src/demo.py

# Run with specific config
uv run src/demo.py --config config/chat_with_minicpm.yaml

# Run with custom parameters
uv run src/demo.py --config config/teaching.yaml --host 0.0.0.0 --port 8443
```

### Development and Testing
```bash
# View logs
tail -f logs/teaching_platform.log

# Check process status  
ps aux | grep teaching

# Check port usage
netstat -tulpn | grep 8443

# Health check
curl https://localhost:8443/health
```

### Database Management
```bash
# Start required services
sudo systemctl start postgresql
sudo systemctl start redis-server

# Check service status
systemctl status postgresql redis-server
```

## Configuration System

The application uses YAML-based configuration with environment-specific overrides.

### Main Config Files
- `config/teaching.yaml`: Teaching platform configuration (recommended)
- `config/chat_with_minicpm.yaml`: MiniCPM-based conversation
- `config/chat_with_openai_compatible.yaml`: OpenAI-compatible LLM
- `config/chat_with_gs.yaml`: LAM/Gaussian Splatting rendering

### Handler Configuration Structure
Each handler is configured in the `handler_configs` section:

```yaml
default:
  chat_engine:
    handler_configs:
      HandlerName:
        module: path/to/handler_module
        enabled: true
        # handler-specific parameters
```

### Environment Variables
Set in `.env` file or environment:
- `DASHSCOPE_API_KEY`: Required for Alibaba Cloud models
- `OPENAI_API_KEY`: For OpenAI-compatible services
- `HF_TOKEN`: Hugging Face access token
- Database and cache connection strings

## Handler System

### Available Handlers

**ASR (Speech Recognition)**
- `asr/sensevoice/asr_handler_sensevoice`: FunASR SenseVoice model

**TTS (Text-to-Speech)**  
- `tts/cosyvoice/tts_handler_cosyvoice`: Local CosyVoice inference
- `tts/bailian_tts/tts_handler_cosyvoice_bailian`: Cloud CosyVoice API
- `tts/edgetts/tts_handler_edgetts`: Microsoft Edge TTS

**LLM (Language Models)**
- `llm/minicpm/llm_handler_minicpm`: MiniCPM-o speech-to-speech
- `llm/openai_compatible/llm_handler_openai_compatible`: OpenAI API format

**Avatar (Digital Human)**
- `avatar/liteavatar/avatar_handler_liteavatar`: 2D avatar rendering
- `avatar/lam/avatar_handler_lam_audio2expression`: 3D Gaussian Splatting
- `avatar/musetalk/avatar_handler_musetalk`: 2D talking head

**Client (WebRTC)**
- `client/rtc_client/client_handler_rtc`: Server-side rendering client
- `client/h5_rendering_client/client_handler_lam`: Client-side LAM rendering

### Installing Handler Dependencies
```bash
# Install dependencies for specific config
uv run install.py --uv --config path/to/config.yaml

# Skip core dependencies (handlers only)
uv run install.py --uv --config path/to/config.yaml --skip-core
```

## Model Management

### Model Storage
Models are stored in `models/` directory with subfolders for each handler:
- `models/MiniCPM-o-2_6/`: MiniCPM multimodal model
- `models/wav2vec2-base-960h/`: Audio feature extraction
- `models/LAM_audio2exp/`: LAM expression generation
- `models/musetalk/`: MuseTalk weights

### Model Download Scripts
```bash
# Download MiniCPM models
scripts/download_MiniCPM-o_2.6.sh
scripts/download_MiniCPM-o_2.6-int4.sh

# Download MuseTalk weights  
scripts/download_musetalk_weights.sh
```

## Teaching Platform Features

### Proactive Teaching System
The teaching platform includes automatic content delivery:
- Initial greeting after 3 seconds
- Teaching content starts after 15 seconds
- Automatic content delivery every 30-45 seconds
- Configurable via `proactive_teaching` section in config

### Course Management
Supports structured IELTS curriculum:
- Grammar fundamentals
- Vocabulary building  
- Writing skills (Task 1 & 2)
- Speaking practice (Part 1-3)
- Multiple difficulty levels per course

### Data Storage
- **PostgreSQL**: User data, learning sessions, course progress
- **Redis**: Session caching, real-time data
- **Local files**: Logs, temporary audio/video files

## SSL Configuration

### Auto-generated Certificates
```bash
# Create self-signed certificates
scripts/create_ssl_certs.sh
```

### Custom Certificates
Place certificates in `ssl_certs/`:
- `ssl_certs/cert.pem`: Certificate file
- `ssl_certs/key.pem`: Private key

## Troubleshooting

### Common Issues

**Port conflicts**: Use `./start.sh stop` to clean up processes

**SSL certificate errors**: Run `scripts/create_ssl_certs.sh` to regenerate

**Model loading failures**: Ensure models are downloaded and paths are correct in config

**API key errors**: Verify environment variables are set correctly

**WebRTC connection issues**: Configure TURN server for NAT traversal:
```bash
scripts/setup_coturn.sh
```

### Log Analysis
```bash
# Real-time logs
tail -f logs/teaching_platform.log

# Search for errors
grep "ERROR" logs/teaching_platform.log

# Monitor AI responses  
grep "current sentence" logs/teaching_platform.log
```

## Development Guidelines

### Code Organization
- Keep handler modules self-contained in their respective directories
- Use configuration files for all customizable parameters
- Follow the existing modular architecture patterns
- Maintain compatibility with the OpenAvatarChat handler interface

### Adding New Handlers
1. Create handler directory under `src/handlers/[type]/[name]/`
2. Implement handler class following existing patterns
3. Add `requirements.txt` or `pyproject.toml` for dependencies
4. Update configuration template
5. Test with existing demo applications

### Configuration Best Practices
- Use environment variables for sensitive data
- Provide reasonable defaults in config files
- Document all configuration parameters
- Support both absolute and relative paths

This codebase combines cutting-edge AI technologies for education and real-time communication. The modular design allows for flexible deployment scenarios from lightweight API-based setups to full local inference stacks.
- 我们在 conda teaching-platform 这个环境下开发
- 用sh脚本进行启动测试
- 用sh脚本进行启动测试
- teaching-platform conda 虚拟环境 ./start_news_broadcast.sh 用这个脚本启动测试,再忘了干死你
- 我不要备用方案,必须用数字人视频给我实现