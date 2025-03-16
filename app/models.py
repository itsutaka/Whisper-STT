from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union


class TranscriptionRequest(BaseModel):
    """兼容OpenAI API的转录请求模型"""
    file: str  # 文件路径
    model: Optional[str] = "whisper-small"
    prompt: Optional[str] = None
    response_format: Optional[str] = "json"
    temperature: Optional[float] = 0.0
    language: Optional[str] = None


class TranscriptionResponse(BaseModel):
    """兼容OpenAI API的转录响应模型"""
    text: str


class DiarizationSegment(BaseModel):
    """说话者分割段"""
    speaker: str
    start: float
    end: float
    text: str


class DiarizedTranscriptionResponse(BaseModel):
    """带有说话者识别的转录响应"""
    text: str
    segments: List[DiarizationSegment]
    srt: Optional[str] = None  # 添加 SRT 字幕内容字段


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""
    type: str  # "progress", "segment", "complete"
    data: Dict[str, Any]


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str
    detail: Optional[str] = None
    status_code: int = 400 