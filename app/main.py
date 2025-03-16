import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path
import tempfile
import uuid

from fastapi import FastAPI, File, UploadFile, Form, WebSocket, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import torch

from .transcriber import WhisperTranscriber
from .diarization import SpeakerDiarization
from .youtube import YouTubeDownloader
from .models import (
    TranscriptionResponse, 
    DiarizedTranscriptionResponse, 
    DiarizationSegment,
    WebSocketMessage,
    ErrorResponse
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Whisper STT API",
    description="基于Whisper的语音转文字API，兼容OpenAI API格式",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# 设置模板
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# 创建转录器和说话者识别实例
transcriber = WhisperTranscriber(model_name="small")

# 创建说话者识别实例 (WhisperX 不需要令牌)
diarization = SpeakerDiarization()

# 创建YouTube下载器实例
youtube_downloader = YouTubeDownloader()

# 存储WebSocket连接
websocket_connections = {}

# 依赖项：获取临时目录
def get_temp_dir():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        # 清理临时目录
        try:
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"清理临时目录时出错: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """返回Web UI首页"""
    return templates.TemplateResponse("index.html", {"request": {}})

@app.post("/v1/audio/transcriptions", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("whisper-small"),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
    language: Optional[str] = Form(None),
    temp_dir: str = Depends(get_temp_dir)
):
    """
    兼容OpenAI API的音频转录端点
    """
    try:
        # 检查文件格式
        if not transcriber.is_format_supported(file.filename):
            return JSONResponse(
                status_code=400,
                content={"error": "不支持的文件格式", "detail": f"支持的格式: {', '.join(transcriber.SUPPORTED_FORMATS)}"}
            )
        
        # 保存上传的文件
        temp_path = os.path.join(temp_dir, file.filename)
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        # 重置文件指针
        await file.seek(0)
        
        # 转录音频
        result = await transcriber.transcribe_file(
            temp_path,
            language=language,
            prompt=prompt,
            temperature=temperature
        )
        
        # 格式化结果
        formatted_result = transcriber.format_result(result, format_type=response_format)
        
        # 如果是json格式，返回完整结果
        if response_format == "json":
            return {"text": formatted_result["text"]}
        # 否则返回纯文本
        else:
            return {"text": formatted_result}
            
    except Exception as e:
        logger.error(f"转录过程中出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe", response_model=DiarizedTranscriptionResponse)
async def transcribe_with_diarization(
    file: UploadFile = File(...),
    enable_diarization: bool = Form(True),
    language: Optional[str] = Form(None),
    temp_dir: str = Depends(get_temp_dir)
):
    """
    带有说话者识别的音频转录端点
    """
    try:
        # 检查文件格式
        if not transcriber.is_format_supported(file.filename):
            return JSONResponse(
                status_code=400,
                content={"error": "不支持的文件格式", "detail": f"支持的格式: {', '.join(transcriber.SUPPORTED_FORMATS)}"}
            )
        
        # 保存上传的文件
        temp_path = os.path.join(temp_dir, file.filename)
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        segments = []
        
        # 如果启用说话者识别，直接使用 WhisperX
        if enable_diarization:
            try:
                # 使用 WhisperX 进行转录和说话者识别
                logger.info("使用 WhisperX 进行转录和说话者识别...")
                diarization_result = await diarization.diarize(temp_path)
                
                # 提取文本和段落
                full_text = " ".join([segment.get("text", "") for segment in diarization_result.get("segments", [])])
                
                # 转换为API响应格式
                for segment in diarization_result.get("segments", []):
                    segments.append(DiarizationSegment(
                        speaker=segment.get("speaker", "UNKNOWN"),
                        start=segment.get("start", 0),
                        end=segment.get("end", 0),
                        text=segment.get("text", "")
                    ))
                
                # 生成 SRT 格式内容
                srt_content = transcriber.format_segments_to_srt(diarization_result.get("segments", []))
                
                return {
                    "text": full_text,
                    "segments": segments,
                    "srt": srt_content
                }
                
            except Exception as e:
                logger.error(f"WhisperX 处理过程中出错: {str(e)}")
                logger.info("回退到普通 Whisper 转录...")
                enable_diarization = False
        
        # 如果不使用说话者识别或 WhisperX 失败，使用普通 Whisper
        if not enable_diarization:
            # 转录音频
            logger.info("使用普通 Whisper 进行转录...")
            transcription = await transcriber.transcribe_file(
                temp_path,
                language=language
            )
            
            # 不使用说话者识别，使用原始转录段落
            for segment in transcription.get("segments", []):
                segments.append(DiarizationSegment(
                    speaker="UNKNOWN",
                    start=segment["start"],
                    end=segment["end"],
                    text=segment["text"]
                ))
            
            # 生成 SRT 格式内容
            srt_content = transcriber.format_result(transcription, format_type="srt")
            
            return {
                "text": transcription["text"],
                "segments": segments,
                "srt": srt_content
            }
                
    except Exception as e:
        logger.error(f"转录过程中出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            logger.error(f"清理临时文件时出错: {str(e)}")

@app.post("/api/transcribe/youtube", response_model=DiarizedTranscriptionResponse)
async def transcribe_youtube(
    url: str = Form(...),
    enable_diarization: bool = Form(True),
    language: Optional[str] = Form(None)
):
    """
    從YouTube視頻URL轉錄音頻
    """
    try:
        # 验证YouTube URL
        if not youtube_downloader.is_valid_youtube_url(url):
            return JSONResponse(
                status_code=400,
                content={"error": "无效的YouTube URL", "detail": "请提供有效的YouTube视频链接"}
            )
        
        # 下载音频
        temp_audio_path = await youtube_downloader.download_audio(url)
        if not temp_audio_path:
            return JSONResponse(
                status_code=500,
                content={"error": "下载YouTube音频失败", "detail": "无法从提供的URL下载音频"}
            )
        
        try:
            # 转录音频
            transcription = await transcriber.transcribe_file(
                temp_audio_path,
                language=language
            )
            
            segments = []
            
            # 不使用說話者識別，使用原始轉錄段落
            for segment in transcription.get("segments", []):
                segments.append(DiarizationSegment(
                    speaker="UNKNOWN",
                    start=segment["start"],
                    end=segment["end"],
                    text=segment["text"]
                ))
            
            # 生成 SRT 格式內容
            srt_content = transcriber.format_result(transcription, format_type="srt")
            
            # 返回結果
            return {
                "text": transcription["text"],
                "segments": segments,
                "srt": srt_content
            }
                
        finally:
            # 清理臨時文件
            try:
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                os.rmdir(os.path.dirname(temp_audio_path))
            except Exception as e:
                logger.error(f"清理臨時文件時出錯: {str(e)}")
                
    except Exception as e:
        logger.error(f"YouTube轉錄過程中出錯: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/api/transcribe/ws/{client_id}")
async def transcribe_websocket(websocket: WebSocket, client_id: str):
    """
    WebSocket端点，用于实时转录
    """
    await websocket.accept()
    
    # 存储WebSocket连接
    websocket_connections[client_id] = websocket
    
    try:
        # 等待客户端发送音频文件
        while True:
            # 接收上传的文件
            data = await websocket.receive_bytes()
            
            # 创建临时文件
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, f"audio_{uuid.uuid4()}.wav")
            
            try:
                # 保存文件
                with open(temp_path, "wb") as f:
                    f.write(data)
                
                # 定义进度回调
                async def progress_callback(progress: float):
                    await websocket.send_json({
                        "type": "progress",
                        "data": {"progress": progress}
                    })
                
                # 定义段落回调
                async def segment_callback(segment: Dict[str, Any]):
                    await websocket.send_json({
                        "type": "segment",
                        "data": {
                            "text": segment["text"],
                            "start": segment["start"],
                            "end": segment["end"]
                        }
                    })
                
                # 转录音频
                result = await transcriber.transcribe_file(
                    temp_path,
                    progress_callback=progress_callback
                )
                
                # 发送完整结果
                await websocket.send_json({
                    "type": "complete",
                    "data": {
                        "text": result["text"],
                        "segments": result.get("segments", [])
                    }
                })
                
            except Exception as e:
                logger.error(f"WebSocket转录过程中出错: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "data": {"error": str(e)}
                })
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    os.rmdir(temp_dir)
                except Exception as e:
                    logger.error(f"清理临时文件时出错: {str(e)}")
    
    except Exception as e:
        logger.error(f"WebSocket连接出错: {str(e)}")
    finally:
        # 移除WebSocket连接
        if client_id in websocket_connections:
            del websocket_connections[client_id]

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"全局异常: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": str(exc)}
    )

@app.get("/api/test-cuda")
async def test_cuda():
    """测试 CUDA 环境是否正常工作"""
    try:
        if not torch.cuda.is_available():
            return {"status": "warning", "message": "CUDA 不可用，将使用 CPU 模式"}
            
        # 测试基本 CUDA 操作
        x = torch.rand(10, 10).cuda()
        y = torch.rand(10, 10).cuda()
        z = x @ y  # 矩阵乘法
        z.cpu()  # 将结果移回 CPU
        
        # 测试 cuDNN
        if torch.backends.cudnn.is_available():
            # 创建一个简单的卷积网络测试 cuDNN
            conv = torch.nn.Conv2d(3, 3, 3).cuda()
            input_tensor = torch.rand(1, 3, 10, 10).cuda()
            output = conv(input_tensor)
            output.cpu()
            cudnn_status = "可用"
        else:
            cudnn_status = "不可用"
            
        # 获取 CUDA 设备信息
        device_count = torch.cuda.device_count()
        device_name = torch.cuda.get_device_name(0) if device_count > 0 else "无"
        
        return {
            "status": "success",
            "message": "CUDA 环境测试通过",
            "cuda_available": torch.cuda.is_available(),
            "cudnn_available": torch.backends.cudnn.is_available(),
            "cudnn_status": cudnn_status,
            "device_count": device_count,
            "device_name": device_name,
            "cuda_version": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else "不可用"
        }
    except Exception as e:
        return {"status": "error", "message": f"CUDA 测试失败: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 