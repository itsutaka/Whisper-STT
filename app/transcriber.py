import os
import tempfile
import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, Callable, Tuple, BinaryIO
import torch
import whisper
import ffmpeg
import numpy as np
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 支持的音频格式
SUPPORTED_FORMATS = ["mp3", "wav", "m4a", "flac", "ogg"]

class WhisperTranscriber:
    """使用Whisper模型进行音频转录的类"""
    
    def __init__(self, model_name: str = "tiny", device: Optional[str] = None):
        """
        初始化Whisper转录器
        
        Args:
            model_name: Whisper模型名称 (tiny, base, small, medium, large)
            device: 运行设备 (cuda, cpu)
        """
        # 确定设备
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"使用设备: {self.device}")
        logger.info(f"加载Whisper模型: {model_name}")
        
        # 加载模型
        self.model = whisper.load_model(model_name, device=self.device)
        logger.info("模型加载完成")
        
    def is_format_supported(self, filename: str) -> bool:
        """检查文件格式是否支持"""
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in SUPPORTED_FORMATS
    
    async def transcribe_file(
        self, 
        file_path: str, 
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        转录音频文件
        
        Args:
            file_path: 音频文件路径
            language: 音频语言代码 (如 'zh', 'en')
            prompt: 提示词，帮助模型理解上下文
            temperature: 采样温度
            progress_callback: 进度回调函数
            
        Returns:
            转录结果字典
        """
        if not self.is_format_supported(file_path):
            raise ValueError(f"不支持的文件格式: {file_path}")
        
        try:
            # 创建转录选项
            transcribe_options = {
                "temperature": temperature,
                "fp16": self.device == "cuda"
            }
            
            if language:
                transcribe_options["language"] = language
                
            if prompt:
                transcribe_options["initial_prompt"] = prompt
                
            # 使用异步执行转录，以便可以报告进度
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.model.transcribe(file_path, **transcribe_options)
            )
            
            # 如果有进度回调，通知完成
            if progress_callback:
                await progress_callback(1.0)
                
            return result
            
        except Exception as e:
            logger.error(f"转录过程中出错: {str(e)}")
            raise
    
    async def transcribe_stream(
        self,
        audio_file: BinaryIO,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        segment_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        转录上传的音频流，支持实时回调
        
        Args:
            audio_file: 音频文件流
            language: 音频语言代码
            prompt: 提示词
            temperature: 采样温度
            segment_callback: 每个片段完成时的回调
            progress_callback: 进度回调
            
        Returns:
            完整的转录结果
        """
        # 创建临时文件
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, "audio_file")
        
        try:
            # 保存上传的文件
            with open(temp_path, "wb") as f:
                f.write(audio_file.read())
            
            # 检查文件格式
            if not self.is_format_supported(audio_file.filename):
                raise ValueError(f"不支持的文件格式: {audio_file.filename}")
            
            # 转录文件
            result = await self.transcribe_file(
                temp_path,
                language=language,
                prompt=prompt,
                temperature=temperature,
                progress_callback=progress_callback
            )
            
            # 如果有段落回调，为每个段落调用
            if segment_callback and "segments" in result:
                for segment in result["segments"]:
                    await segment_callback(segment)
            
            return result
            
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                os.rmdir(temp_dir)
            except Exception as e:
                logger.error(f"清理临时文件时出错: {str(e)}")
                
    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        将秒数转换为 SRT 格式的时间戳 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒数
            
        Returns:
            SRT 格式的时间戳
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    @staticmethod
    def format_result(result: Dict[str, Any], format_type: str = "json") -> Any:
        """
        格式化转录结果
        
        Args:
            result: Whisper转录结果
            format_type: 输出格式 (json, text, srt, vtt)
            
        Returns:
            格式化后的结果
        """
        if format_type == "text":
            return result["text"]
        elif format_type == "json":
            return {
                "text": result["text"],
                "segments": result.get("segments", [])
            }
        elif format_type == "srt":
            # 自定义 SRT 格式转换
            segments = result.get("segments", [])
            srt_content = []
            for i, segment in enumerate(segments, start=1):
                # 转换时间戳为 SRT 格式 (HH:MM:SS,mmm)
                start_time = WhisperTranscriber.format_timestamp(segment["start"])
                end_time = WhisperTranscriber.format_timestamp(segment["end"])
                
                # 添加字幕段落
                srt_content.extend([
                    str(i),  # 字幕序号
                    f"{start_time} --> {end_time}",  # 时间戳
                    segment["text"].strip(),  # 字幕文本
                    ""  # 空行分隔符
                ])
            
            return "\n".join(srt_content)
        elif format_type == "vtt":
            # 暂不支持 VTT 格式
            raise NotImplementedError("VTT format is not supported yet")
        else:
            return result 

    def format_segments_to_srt(self, segments: List[Dict]) -> str:
        """
        将 WhisperX 段落格式化为 SRT 字幕格式
        
        Args:
            segments: WhisperX 段落列表
            
        Returns:
            SRT 格式的字符串
        """
        srt_content = ""
        
        for i, segment in enumerate(segments, start=1):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "")
            speaker = segment.get("speaker", "UNKNOWN")
            
            # 格式化时间
            start_time = self._format_timestamp(start)
            end_time = self._format_timestamp(end)
            
            # 添加说话者标签
            labeled_text = f"[{speaker}] {text}"
            
            # 添加 SRT 条目
            srt_content += f"{i}\n{start_time} --> {end_time}\n{labeled_text}\n\n"
        
        return srt_content

    def _format_timestamp(self, seconds: float) -> str:
        """
        将秒数格式化为 SRT 时间戳格式 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间戳
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}" 
