#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper STT API 启动脚本
"""

import os
import argparse
import uvicorn

def main():
    """主函数，解析命令行参数并启动服务器"""
    parser = argparse.ArgumentParser(description="Whisper STT API 服务器")
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0", 
        help="服务器主机地址 (默认: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="服务器端口 (默认: 8000)"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="启用自动重载 (开发模式)"
    )
    
    args = parser.parse_args()
    
    # 启动服务器
    uvicorn.run(
        "app.main:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload
    )

if __name__ == "__main__":
    main() 