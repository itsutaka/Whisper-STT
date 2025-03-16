# Whisper STT API

基于 OpenAI Whisper 和 FastAPI 的 GPU 加速语音转文字 (STT) API，兼容 OpenAI 的 audio/transcriptions API 格式。

## 功能特点

- 使用 Whisper small 模型进行语音转文字
- 支持 CUDA GPU 加速
- 支持多种音频格式（mp3、wav、m4a、flac、ogg）
- 说话者识别 (Speaker Diarization)
- 实时转录显示（通过 WebSocket）
- 现代化的 Web UI 界面
- 兼容 OpenAI API 格式

## 安装

### 前提条件

- Python 3.8+
- CUDA 支持的 GPU（可选，但推荐用于加速）
- FFmpeg

### 安装步骤

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/whisper-stt-api.git
cd whisper-stt-api
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 设置 HuggingFace 访问令牌（用于说话者识别）：

```bash
# Linux/macOS
export HUGGINGFACE_TOKEN=your_token_here

# Windows
set HUGGINGFACE_TOKEN=your_token_here
```

> 注意：要使用说话者识别功能，需要在 [HuggingFace](https://huggingface.co/) 上创建账号并获取访问令牌。

## 使用方法

### 启动服务器

```bash
python -m app.main
```

服务器将在 http://localhost:8000 上运行。

### Web 界面

打开浏览器访问 http://localhost:8000 即可使用 Web 界面。

### API 使用

#### 兼容 OpenAI 的 API 端点

```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F file=@/path/to/audio.mp3 \
  -F model=whisper-small \
  -F response_format=json
```

#### 带有说话者识别的 API 端点

```bash
curl -X POST http://localhost:8000/api/transcribe \
  -F file=@/path/to/audio.mp3 \
  -F enable_diarization=true
```

## API 文档

启动服务器后，可以在 http://localhost:8000/docs 查看完整的 API 文档。

## 配置

可以通过环境变量配置以下选项：

- `HUGGINGFACE_TOKEN`：HuggingFace 访问令牌，用于说话者识别

## 许可证

MIT

## 致谢

- [OpenAI Whisper](https://github.com/openai/whisper)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pyannote Audio](https://github.com/pyannote/pyannote-audio) 