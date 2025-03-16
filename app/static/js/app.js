document.addEventListener('DOMContentLoaded', () => {
    // 获取DOM元素
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const selectButton = document.getElementById('selectButton');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const removeButton = document.getElementById('removeButton');
    const transcribeButton = document.getElementById('transcribeButton');
    const enableDiarization = document.getElementById('enableDiarization');
    const languageSelect = document.getElementById('languageSelect');
    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const resultSection = document.getElementById('resultSection');
    const resultContent = document.getElementById('resultContent');
    const copyButton = document.getElementById('copyButton');
    const downloadButton = document.getElementById('downloadButton');
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    const youtubeUrl = document.getElementById('youtubeUrl');
    const youtubeButton = document.getElementById('youtubeButton');

    // 当前选择的文件
    let selectedFile = null;
    // WebSocket连接
    let websocket = null;
    // 客户端ID
    const clientId = generateClientId();

    // 初始化拖放区域事件
    initDropArea();
    // 初始化按钮事件
    initButtons();
    // 初始化WebSocket
    initWebSocket();

    /**
     * 初始化拖放区域事件
     */
    function initDropArea() {
        // 点击选择文件按钮
        selectButton.addEventListener('click', () => {
            fileInput.click();
        });

        // 文件选择变化
        fileInput.addEventListener('change', (e) => {
            handleFileSelect(e.target.files);
        });

        // 拖放事件
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });

        // 拖放样式
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => {
                dropArea.classList.add('drag-over');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => {
                dropArea.classList.remove('drag-over');
            }, false);
        });

        // 处理拖放文件
        dropArea.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFileSelect(files);
        }, false);
    }

    /**
     * 初始化按钮事件
     */
    function initButtons() {
        // 移除文件按钮
        removeButton.addEventListener('click', () => {
            resetFileSelection();
        });

        // 转录按钮
        transcribeButton.addEventListener('click', () => {
            startTranscription();
        });

        // YouTube按钮点击事件
        youtubeButton.addEventListener('click', () => {
            const url = youtubeUrl.value.trim();
            if (!url) {
                showToast('請輸入YouTube視頻鏈接');
                return;
            }
            
            if (!isValidYoutubeUrl(url)) {
                showToast('請輸入有效的YouTube視頻鏈接');
                return;
            }
            
            transcribeYoutubeVideo(url);
        });

        // 复制按钮
        copyButton.addEventListener('click', () => {
            copyToClipboard(resultContent.textContent);
            showToast('文本已复制到剪贴板');
        });

        // 下载按钮
        downloadButton.addEventListener('click', (e) => {
            e.stopPropagation(); // 防止事件冒泡
            
            // 检查是否有转录数据
            if (!window.transcriptionData) {
                showToast('沒有可下載的轉錄內容');
                return;
            }
            
            // 创建下拉菜单
            const downloadOptions = document.createElement('div');
            downloadOptions.className = 'download-options';
            downloadOptions.innerHTML = `
                <div class="download-option" data-format="txt">下載文本 (.txt)</div>
                <div class="download-option" data-format="srt">下載字幕 (.srt)</div>
            `;
            
            // 定位并显示选项
            const rect = downloadButton.getBoundingClientRect();
            downloadOptions.style.position = 'absolute';
            downloadOptions.style.top = `${rect.bottom + 5}px`; // 添加一些间距
            downloadOptions.style.left = `${rect.left}px`;
            document.body.appendChild(downloadOptions);
            
            // 添加选项点击事件
            downloadOptions.querySelectorAll('.download-option').forEach(option => {
                option.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const format = option.getAttribute('data-format');
                    downloadTranscription(format);
                    document.body.removeChild(downloadOptions);
                });
            });
            
            // 点击其他地方关闭选项
            function closeOptions(e) {
                if (!downloadOptions.contains(e.target) && e.target !== downloadButton) {
                    if (document.body.contains(downloadOptions)) {
                        document.body.removeChild(downloadOptions);
                    }
                    document.removeEventListener('click', closeOptions);
                }
            }
            
            // 延迟一下再添加点击监听，避免立即触发
            setTimeout(() => {
                document.addEventListener('click', closeOptions);
            }, 0);
        });
    }

    /**
     * 初始化WebSocket连接
     */
    function initWebSocket() {
        // 检查浏览器是否支持WebSocket
        if ('WebSocket' in window) {
            // 创建WebSocket连接
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/transcribe/ws/${clientId}`;
            
            websocket = new WebSocket(wsUrl);
            
            // 连接打开
            websocket.onopen = function() {
                console.log('WebSocket连接已建立');
            };
            
            // 接收消息
            websocket.onmessage = function(event) {
                handleWebSocketMessage(event);
            };
            
            // 连接关闭
            websocket.onclose = function() {
                console.log('WebSocket连接已关闭');
                // 尝试重新连接
                setTimeout(initWebSocket, 2000);
            };
            
            // 连接错误
            websocket.onerror = function(error) {
                console.error('WebSocket错误:', error);
            };
        } else {
            console.error('浏览器不支持WebSocket');
        }
    }

    /**
     * 处理WebSocket消息
     */
    function handleWebSocketMessage(event) {
        const message = JSON.parse(event.data);
        
        switch (message.type) {
            case 'progress':
                updateProgress(message.data.progress);
                break;
                
            case 'segment':
                updateTranscriptionSegment(message.data);
                break;
                
            case 'complete':
                completeTranscription(message.data);
                break;
                
            case 'error':
                handleError(message.data.error);
                break;
        }
    }

    /**
     * 处理文件选择
     */
    function handleFileSelect(files) {
        if (files.length === 0) return;
        
        const file = files[0];
        
        // 检查文件类型
        const validTypes = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', 
                           'audio/mpeg', 'audio/wav', 'audio/x-m4a', 
                           'audio/flac', 'audio/ogg'];
        
        const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        const isValidType = validTypes.some(type => 
            type === fileExtension || type === file.type
        );
        
        if (!isValidType) {
            showToast('不支持的文件格式，请选择音频文件（mp3, wav, m4a, flac, ogg）');
            return;
        }
        
        // 更新UI
        selectedFile = file;
        fileName.textContent = file.name;
        fileInfo.style.display = 'flex';
        dropArea.style.display = 'none';
        transcribeButton.disabled = false;
    }

    /**
     * 重置文件选择
     */
    function resetFileSelection() {
        selectedFile = null;
        fileInput.value = '';
        fileInfo.style.display = 'none';
        dropArea.style.display = 'block';
        transcribeButton.disabled = true;
        progressSection.style.display = 'none';
        resultSection.style.display = 'none';
    }

    /**
     * 开始转录
     */
    function startTranscription() {
        if (!selectedFile) return;
        
        // 显示进度条
        progressSection.style.display = 'block';
        resultSection.style.display = 'none';
        updateProgress(0);
        
        // 准备表单数据
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('enable_diarization', enableDiarization.checked);
        
        const language = languageSelect.value;
        if (language) {
            formData.append('language', language);
        }
        
        // 发送请求
        fetch('/api/transcribe', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.error || '转录失败');
                });
            }
            return response.json();
        })
        .then(data => {
            displayTranscriptionResult(data);
        })
        .catch(error => {
            handleError(error.message);
        });
    }

    /**
     * 更新进度条
     */
    function updateProgress(progress) {
        const percent = Math.round(progress * 100);
        progressBar.style.width = `${percent}%`;
        progressText.textContent = `处理中... ${percent}%`;
    }

    /**
     * 显示转录结果
     */
    function displayTranscriptionResult(data) {
        // 保存完整的转录数据，包括 SRT
        window.transcriptionData = data;
        
        // 只顯示結果區域，不隱藏進度條
        resultSection.style.display = 'block';
        
        // 清空结果内容
        resultContent.innerHTML = '';
        
        // 如果有分段
        if (data.segments && data.segments.length > 0) {
            // 按说话者分组显示
            const segments = data.segments;
            
            for (const segment of segments) {
                const segmentDiv = document.createElement('div');
                segmentDiv.className = 'speaker-segment';
                
                // 只有当说话者不是 UNKNOWN 或者启用了说话者识别时才显示说话者标签
                if (segment.speaker !== "UNKNOWN" || enableDiarization.checked) {
                    const speakerLabel = document.createElement('div');
                    speakerLabel.className = 'speaker-label';
                    speakerLabel.textContent = segment.speaker;
                    segmentDiv.appendChild(speakerLabel);
                }
                
                const speakerText = document.createElement('div');
                speakerText.className = 'speaker-text';
                speakerText.textContent = segment.text;
                
                const timestamp = document.createElement('div');
                timestamp.className = 'timestamp';
                timestamp.textContent = `${formatTime(segment.start)} - ${formatTime(segment.end)}`;
                
                segmentDiv.appendChild(speakerText);
                segmentDiv.appendChild(timestamp);
                
                resultContent.appendChild(segmentDiv);
            }
        } else {
            // 显示完整文本
            resultContent.textContent = data.text;
        }
    }

    /**
     * 更新转录段落（用于WebSocket实时更新）
     */
    function updateTranscriptionSegment(segment) {
        // 只顯示結果區域，不隱藏進度條
        resultSection.style.display = 'block';
        
        // 创建或更新段落
        const segmentId = `segment-${Math.floor(segment.start * 1000)}`;
        let segmentDiv = document.getElementById(segmentId);
        
        if (!segmentDiv) {
            segmentDiv = document.createElement('div');
            segmentDiv.id = segmentId;
            segmentDiv.className = 'speaker-segment';
            resultContent.appendChild(segmentDiv);
        }
        
        segmentDiv.innerHTML = `
            <div class="speaker-text">${segment.text}</div>
            <div class="timestamp">${formatTime(segment.start)} - ${formatTime(segment.end)}</div>
        `;
        
        // 滚动到底部
        resultContent.scrollTop = resultContent.scrollHeight;
    }

    /**
     * 完成转录（用于WebSocket）
     */
    function completeTranscription(data) {
        // 更新进度为100%
        updateProgress(1);
        
        // 如果没有实时更新过，显示完整结果
        if (resultContent.children.length === 0) {
            displayTranscriptionResult(data);
        }
        
        showToast('转录完成');
    }

    /**
     * 处理错误
     */
    function handleError(errorMessage) {
        progressSection.style.display = 'none';
        showToast(`错误: ${errorMessage}`, true);
    }

    /**
     * 复制到剪贴板
     */
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).catch(err => {
            console.error('复制到剪贴板失败:', err);
        });
    }

    /**
     * 下载转录文本
     */
    function downloadTranscription(format = 'txt') {
        let content, filename, mimeType;
        
        if (format === 'srt' && window.transcriptionData && window.transcriptionData.srt) {
            // 下载 SRT 格式
            content = window.transcriptionData.srt;
            filename = `transcription_${new Date().toISOString().slice(0, 10)}.srt`;
        } else {
            // 下载纯文本格式
            content = resultContent.textContent;
            filename = `transcription_${new Date().toISOString().slice(0, 10)}.txt`;
        }
        
        // 设置 MIME 类型
        mimeType = 'text/plain;charset=utf-8';
        
        // 创建 Blob 对象，确保使用正确的编码
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        
        // 创建下载链接
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        
        // 添加到文档并触发点击
        document.body.appendChild(a);
        a.click();
        
        // 清理
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
        
        showToast(`${format === 'srt' ? '字幕' : '文本'}已下载`);
    }

    /**
     * 显示提示消息
     */
    function showToast(message, isError = false) {
        toastMessage.textContent = message;
        
        if (isError) {
            toast.style.backgroundColor = 'var(--error-color)';
            toast.style.color = 'white';
        } else {
            toast.style.backgroundColor = 'var(--card-background)';
            toast.style.color = 'var(--text-color)';
        }
        
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    /**
     * 格式化时间（秒 -> MM:SS）
     */
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * 阻止默认事件
     */
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    /**
     * 生成客户端ID
     */
    function generateClientId() {
        return 'client_' + Math.random().toString(36).substring(2, 15);
    }

    /**
     * 检查是否为有效的YouTube URL
     */
    function isValidYoutubeUrl(url) {
        return url.includes('youtube.com/watch') || url.includes('youtu.be/');
    }

    /**
     * 转录YouTube视频
     */
    function transcribeYoutubeVideo(url) {
        // 显示进度条
        progressSection.style.display = 'block';
        resultSection.style.display = 'none';
        updateProgress(0);
        
        // 准备表单数据
        const formData = new FormData();
        formData.append('url', url);
        formData.append('enable_diarization', enableDiarization.checked);
        
        const language = languageSelect.value;
        if (language) {
            formData.append('language', language);
        }
        
        // 发送请求
        fetch('/api/transcribe/youtube', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.error || '轉錄失敗');
                });
            }
            return response.json();
        })
        .then(data => {
            displayTranscriptionResult(data);
            showToast('YouTube視頻轉錄完成');
        })
        .catch(error => {
            handleError(error.message);
        });
    }
}); 
