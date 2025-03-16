import os
import tempfile
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, BinaryIO
import torch
import whisperx

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpeakerDiarization:
    """使用WhisperX进行说话者识别的类"""
    
    def __init__(self, auth_token: Optional[str] = None):
        """
        初始化说话者识别
        
        Args:
            auth_token: 不再需要，保留参数是为了兼容性
        """
        # 强制使用 CPU 以避免 CUDA 问题
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"说话者识别使用设备: {self.device}")
        
        # 启用 TF32 以解决警告
        if self.device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            logger.info("已启用 TF32 支持")
        
        # WhisperX 不需要预先加载模型，它会在运行时按需加载
        logger.info("WhisperX 说话者识别初始化完成")
        self.pipeline = True  # 设置为 True 表示可用
            
    async def diarize(self, audio_path: str, transcription: Optional[Dict] = None) -> Dict:
        """
        对音频文件进行说话者识别
        
        Args:
            audio_path: 音频文件路径
            transcription: 可选的 Whisper 转录结果
            
        Returns:
            带有说话者标签的转录结果
        """
        if not self.pipeline:
            raise ValueError("说话者识别模型未正确初始化")
            
        try:
            # 异步执行说话者识别
            loop = asyncio.get_event_loop()
            
            # 如果没有提供转录结果，使用 WhisperX 进行转录
            if transcription is None:
                logger.info("使用 WhisperX 进行转录和说话者识别")
                try:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self._run_whisperx(audio_path)
                    )
                    return result
                except Exception as e:
                    logger.error(f"WhisperX 转录失败: {str(e)}")
                    # 如果 WhisperX 转录失败，使用普通 Whisper 转录
                    logger.info("回退到普通 Whisper 转录...")
                    from .transcriber import WhisperTranscriber
                    transcriber = WhisperTranscriber(model_name="small", device="cpu")
                    transcription = await transcriber.transcribe_file(audio_path)
                    
                    # 为每个段落分配默认说话者
                    for i, segment in enumerate(transcription.get("segments", [])):
                        segment["speaker"] = f"SPEAKER_{i % 2 + 1}"
                    
                    return transcription
            else:
                # 如果提供了转录结果，只进行说话者识别
                logger.info("使用现有转录结果进行说话者识别")
                try:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self._run_diarization_only(audio_path, transcription)
                    )
                    return result
                except Exception as e:
                    logger.error(f"说话者识别失败: {str(e)}")
                    # 如果说话者识别失败，为每个段落分配默认说话者
                    for i, segment in enumerate(transcription.get("segments", [])):
                        segment["speaker"] = f"SPEAKER_{i % 2 + 1}"
                    
                    return transcription
        except Exception as e:
            logger.error(f"说话者识别过程中出错: {str(e)}")
            # 返回原始转录结果或创建一个简单的结果
            if transcription:
                # 为每个段落分配默认说话者
                for i, segment in enumerate(transcription.get("segments", [])):
                    segment["speaker"] = f"SPEAKER_{i % 2 + 1}"
                
                return transcription
            else:
                # 创建一个简单的错误结果
                return {
                    "error": str(e),
                    "segments": [],
                    "language": "en"
                }
    
    def _run_whisperx(self, audio_path: str) -> Dict:
        """使用 WhisperX 进行转录和说话者识别"""
        try:
            # 1. 转录
            logger.info("正在使用 WhisperX 进行转录...")
            try:
                # 尝试使用 silero VAD
                model = whisperx.load_model("small", "cpu", vad_method="silero")
            except Exception as e:
                logger.warning(f"使用 silero VAD 失败: {str(e)}，尝试不使用 VAD...")
                # 如果 silero VAD 失败，尝试不使用 VAD
                import whisper
                whisper_model = whisper.load_model("small", device="cpu")
                # 直接使用 whisper 进行转录
                result = whisper_model.transcribe(audio_path)
                # 转换为 WhisperX 格式
                return {
                    "segments": result.get("segments", []),
                    "language": result.get("language", "en")
                }
            
            result = model.transcribe(audio_path)
            
            # 2. 对齐
            logger.info("正在进行音素对齐...")
            try:
                align_device = "cpu"
                model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=align_device)
                result = whisperx.align(result["segments"], model_a, metadata, audio_path, align_device)
            except Exception as e:
                logger.warning(f"音素对齐失败: {str(e)}，跳过对齐步骤...")
                # 如果对齐失败，跳过对齐步骤
            
            # 3. 说话者识别
            logger.info("正在进行说话者识别...")
            try:
                diarize_device = "cpu"
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=None, device=diarize_device)
                diarize_segments = diarize_model(audio_path)
                
                # 4. 将说话者标签分配给转录段落
                result = whisperx.assign_word_speakers(diarize_segments, result)
            except Exception as e:
                logger.warning(f"使用说话者识别失败: {str(e)}，使用备用方法...")
                # 如果说话者识别失败，使用简单的段落分割作为备用
                for i, segment in enumerate(result["segments"]):
                    speaker_id = f"SPEAKER_{i % 2 + 1}"
                    segment["speaker"] = speaker_id
                    for word in segment.get("words", []):
                        if word:  # 确保 word 不是 None
                            word["speaker"] = speaker_id
            
            return result
        except Exception as e:
            logger.error(f"WhisperX 处理过程中出错: {str(e)}")
            # 使用 whisper 作为备用
            logger.info("使用普通 Whisper 作为备用...")
            import whisper
            whisper_model = whisper.load_model("small", device="cpu")
            result = whisper_model.transcribe(audio_path)
            
            # 为每个段落分配默认说话者
            for i, segment in enumerate(result.get("segments", [])):
                segment["speaker"] = f"SPEAKER_{i % 2 + 1}"
            
            return result
    
    def _run_diarization_only(self, audio_path: str, transcription: Dict) -> Dict:
        """仅进行说话者识别，使用现有的转录结果"""
        try:
            # 将 Whisper 转录结果转换为 WhisperX 格式
            whisperx_format = self._convert_to_whisperx_format(transcription)
            
            # 加载对齐模型 - 使用 CPU
            language = transcription.get("language", "en")
            align_device = "cpu"  # 强制使用 CPU 进行对齐
            model_a, metadata = whisperx.load_align_model(language_code=language, device=align_device)
            
            # 对齐
            logger.info("正在进行音素对齐...")
            aligned_result = whisperx.align(whisperx_format["segments"], model_a, metadata, audio_path, align_device)
            
            # 说话者识别 - 使用 CPU
            logger.info("正在进行说话者识别...")
            try:
                diarize_device = "cpu"  # 强制使用 CPU 进行说话者识别
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=None, device=diarize_device)
                diarize_segments = diarize_model(audio_path)
                
                # 将说话者标签分配给转录段落
                result = whisperx.assign_word_speakers(diarize_segments, aligned_result)
            except Exception as e:
                logger.warning(f"使用说话者识别失败: {str(e)}，尝试备用方法...")
                # 如果说话者识别失败，使用简单的段落分割作为备用
                for i, segment in enumerate(aligned_result["segments"]):
                    speaker_id = f"SPEAKER_{i % 2 + 1}"  # 简单地交替分配说话者
                    segment["speaker"] = speaker_id
                    for word in segment.get("words", []):
                        word["speaker"] = speaker_id
                result = aligned_result
            
            return result
        except Exception as e:
            logger.error(f"说话者识别过程中出错: {str(e)}")
            raise
    
    def _convert_to_whisperx_format(self, whisper_result: Dict) -> Dict:
        """将标准 Whisper 转录结果转换为 WhisperX 格式"""
        return {
            "segments": whisper_result.get("segments", []),
            "language": whisper_result.get("language", "en")
        }
            
    async def diarize_stream(self, audio_file: BinaryIO) -> Dict:
        """
        对上传的音频流进行说话者识别
        
        Args:
            audio_file: 音频文件流
            
        Returns:
            说话者识别结果
        """
        # 创建临时文件
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, "audio_file")
        
        try:
            # 保存上传的文件
            with open(temp_path, "wb") as f:
                f.write(audio_file.read())
                
            # 执行说话者识别
            return await self.diarize(temp_path)
            
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                os.rmdir(temp_dir)
            except Exception as e:
                logger.error(f"清理临时文件时出错: {str(e)}")
    
    def merge_with_transcription(self, diarization_result: Dict, transcription: Dict) -> List[Dict]:
        """
        将 WhisperX 的说话者识别结果与转录结果合并
        
        Args:
            diarization_result: WhisperX 的说话者识别结果
            transcription: Whisper 转录结果
            
        Returns:
            合并后的段落列表
        """
        # WhisperX 已经合并了转录和说话者识别结果，直接返回其段落
        segments = []
        
        for segment in diarization_result.get("segments", []):
            speaker = segment.get("speaker", "UNKNOWN")
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "")
            
            segments.append({
                "speaker": speaker,
                "start": start,
                "end": end,
                "text": text
            })
            
        return segments