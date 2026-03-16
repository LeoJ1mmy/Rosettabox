/**
 * 文件上傳組件 - 模組化的上傳界面
 */
import React, { useState, useCallback } from 'react';
import { Upload, FileAudio, Loader2, AlertCircle, Video, Music } from 'lucide-react';
// 移除音頻提取功能，改為服務器端處理

const FileUpload = ({ onFileSelect, processing, error }) => {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  // 移除音頻提取相關狀態

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      handleFile(droppedFile);
    }
  }, []);

  const handleChange = useCallback((e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  }, []);

  const handleFile = useCallback((selectedFile) => {
    // 檢查文件類型
    const allowedTypes = [
      'audio/', 'video/', 
      'application/octet-stream' // 某些音頻文件可能是這個類型
    ];
    
    const isAllowed = allowedTypes.some(type => 
      selectedFile.type.startsWith(type)
    );

    if (!isAllowed && !selectedFile.name.match(/\.(wav|mp3|m4a|flac|ogg|mp4|avi|mov|mkv)$/i)) {
      alert('請選擇音頻或影片文件');
      return;
    }

    // 檢查文件大小 (500MB)
    if (selectedFile.size > 500 * 1024 * 1024) {
      alert('文件大小不能超過 500MB');
      return;
    }

    setFile(selectedFile);
    if (onFileSelect) {
      onFileSelect(selectedFile);
    }
  }, [onFileSelect]);

  return (
    <div className="upload-container">
      <form
        onDragEnter={handleDrag}
        onSubmit={(e) => e.preventDefault()}
      >
        <input
          type="file"
          id="file-upload"
          accept="audio/*,video/*"
          onChange={handleChange}
          disabled={processing}
          style={{ display: 'none' }}
        />
        
        <label
          htmlFor="file-upload"
          className={`upload-area ${dragActive ? 'drag-active' : ''} ${processing ? 'disabled' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="upload-content">
            {processing ? (
              <>
                <Loader2 className="icon spinning" size={48} />
                <p>處理中...</p>
              </>
            ) : file ? (
              <>
                <FileAudio className="icon" size={48} />
                <p className="file-name">{file.name}</p>
                <p className="file-size">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </p>
                <p className="upload-hint">點擊更換文件</p>
              </>
            ) : (
              <>
                <Upload className="icon" size={48} />
                <p>拖拽文件到這裡或點擊選擇</p>
                <p className="upload-hint">支援音頻和影片格式 (最大 500MB)</p>
              </>
            )}
          </div>
        </label>
      </form>

      {error && (
        <div className="error-message">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};

export default FileUpload;