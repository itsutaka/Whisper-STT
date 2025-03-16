import os
import tempfile
import logging
import asyncio
from typing import Optional
import yt_dlp

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    """处理YouTube视频下载的类"""
    
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
        }
    
    async def download_audio(self, url: str) -> Optional[str]:
        """
        从YouTube URL下载音频
        
        Args:
            url: YouTube视频URL
            
        Returns:
            临时音频文件的路径
        """
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "audio")  # 移除扩展名
        final_file = f"{temp_file}.mp3"  # 最终文件名
        
        try:
            # 添加更详细的日志
            logger.info(f"开始下载YouTube视频: {url}")
            logger.info(f"临时目录: {temp_dir}")
            
            # 设置下载选项
            download_opts = dict(self.ydl_opts)
            download_opts['outtmpl'] = temp_file  # 不包含扩展名
            download_opts['verbose'] = True
            
            # 异步执行下载
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._download(url, download_opts)
            )
            
            # 检查最终文件是否存在
            if os.path.exists(final_file):
                logger.info(f"成功下载YouTube音频: {url}")
                return final_file
            else:
                # 检查是否有双扩展名的文件
                double_ext_file = f"{temp_file}.mp3.mp3"
                if os.path.exists(double_ext_file):
                    logger.info(f"找到双扩展名文件，重命名为: {final_file}")
                    os.rename(double_ext_file, final_file)
                    return final_file
                
                # 查找目录中的任何mp3文件
                mp3_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
                if mp3_files:
                    found_file = os.path.join(temp_dir, mp3_files[0])
                    logger.info(f"找到其他MP3文件: {found_file}")
                    if found_file != final_file:
                        os.rename(found_file, final_file)
                    return final_file
                
                logger.error(f"下载YouTube音频失败: {url}")
                logger.error(f"临时目录内容: {os.listdir(temp_dir)}")
                return None
                
        except Exception as e:
            logger.error(f"下载YouTube音频时出错: {str(e)}")
            logger.error(f"错误类型: {type(e).__name__}")
            if isinstance(e, yt_dlp.utils.DownloadError):
                logger.error(f"YouTube-DL错误信息: {str(e.msg)}")
            # 清理临时目录
            if os.path.exists(temp_dir):
                try:
                    for file in os.listdir(temp_dir):
                        os.remove(os.path.join(temp_dir, file))
                    os.rmdir(temp_dir)
                except Exception as cleanup_error:
                    logger.error(f"清理临时目录时出错: {str(cleanup_error)}")
            return None
    
    def _download(self, url: str, options: dict):
        """执行实际的下载操作"""
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                ydl.download([url])
            except Exception as e:
                logger.error(f"下载过程中出错: {str(e)}")
                raise
            
    def is_valid_youtube_url(self, url: str) -> bool:
        """检查URL是否为有效的YouTube链接"""
        return "youtube.com" in url or "youtu.be" in url