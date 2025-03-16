# Whisper STT API

基於 OpenAI Whisper 和 FastAPI 的 GPU 加速語音轉文字 (STT) API，兼容 OpenAI 的 audio/transcriptions API 格式。

![image](https://github.com/user-attachments/assets/e5570b7b-b20e-42ca-aa89-8d54ec81d2ca)


## 功能特點

- 使用 Whisper small 模型進行語音轉文字
- 支援 CUDA GPU 加速
- 支援多種音訊格式（mp3、wav、m4a、flac、ogg）
- 說話者識別 (Speaker Diarization)
- 即時轉錄顯示（透過 WebSocket）
- 現代化的 Web UI 介面
- 兼容 OpenAI API 格式

## 安裝

### 前提條件

- Python 3.8+
- CUDA 支援的 GPU（可選，但推薦用於加速）
- FFmpeg

### 安裝步驟

1. 克隆倉庫：

```bash
git clone https://github.com/yourusername/whisper-stt-api.git
cd whisper-stt-api
```

2. 安裝依賴：

```bash
pip install -r requirements.txt
```

## 使用方法

### 啟動伺服器

```bash
python .\run.py
```

伺服器將在 http://localhost:8000 上運行。

### Web 介面

打開瀏覽器訪問 http://localhost:8000 即可使用 Web 介面。

### API 使用

#### 兼容 OpenAI 的 API 端點

```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F file=@/path/to/audio.mp3 \
  -F model=whisper-small \
  -F response_format=json
```

#### 帶有說話者識別的 API 端點

```bash
curl -X POST http://localhost:8000/api/transcribe \
  -F file=@/path/to/audio.mp3 \
  -F enable_diarization=true
```

## API 文件

啟動伺服器後，可以在 http://localhost:8000/docs 查看完整的 API 文件。

## 配置

建議 Python 版本 3.11

建議在虛擬環境中安裝：
```
python -m venv venv
```
```
source venv/bin/activate  # Linux/Mac
```
或
```
venv\Scripts\activate  # Windows
```

安裝所有依賴：
```
pip install -r requirements.txt
```

注意事項：
需要預先安裝 FFmpeg
如果使用 GPU，可能需要安裝對應版本的 CUDA
某些套件可能需要額外的系統級依賴，特別是在 Linux 系統上

---
whisper模型分成不同大小，請依照硬體選擇適當大小的模型，更改參數至transcriber.py修改

```
 def __init__(self, model_name: str = "tiny", device: Optional[str] = None):
        """
        初始化Whisper转录器
        
        Args:
            model_name: Whisper模型名称 (tiny, base, small, medium, large)
            device: 运行设备 (cuda, cpu)
```
---

## 許可證

MIT

## 致謝

- [OpenAI Whisper](https://github.com/openai/whisper)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pyannote Audio](https://github.com/pyannote/pyannote-audio)

