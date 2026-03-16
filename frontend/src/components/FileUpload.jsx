import React, { useCallback, useState } from 'react';
import { Upload, FileAudio, X, Loader2, AlertCircle, UploadCloud, Info } from 'lucide-react';
import Tooltip from './Tooltip';

// 最大檔案大小限制 (500MB)
const MAX_FILE_SIZE = 500 * 1024 * 1024;

const FileUpload = ({
  theme,
  files,
  setFiles,
  processing,
  uploading,
  uploadProgress,
  uploadSpeed,
  handleFileUpload
}) => {
  const [isDragActive, setIsDragActive] = useState(false);
  const [sizeError, setSizeError] = useState(null);

  // 檢查檔案大小
  const validateFileSize = useCallback((fileList) => {
    const validFiles = [];
    const oversizedFiles = [];

    fileList.forEach(file => {
      if (file.size > MAX_FILE_SIZE) {
        oversizedFiles.push(file.name);
      } else {
        validFiles.push(file);
      }
    });

    if (oversizedFiles.length > 0) {
      setSizeError(`以下檔案超過 500MB 限制：${oversizedFiles.join(', ')}`);
      setTimeout(() => setSizeError(null), 5000);
    }

    return validFiles;
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragActive(false);
    if (processing || uploading) return;

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      const validFiles = validateFileSize(droppedFiles);
      if (validFiles.length > 0) {
        setFiles(prev => [...prev, ...validFiles]);
      }
    }
  }, [processing, uploading, setFiles, validateFileSize]);

  const onDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragActive(true);
  }, []);

  const onDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragActive(false);
  }, []);

  const removeFile = (index) => {
    if (processing || uploading) return;
    const newFiles = [...files];
    newFiles.splice(index, 1);
    setFiles(newFiles);
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      const validFiles = validateFileSize(selectedFiles);

      if (validFiles.length > 0) {
        setFiles(prev => {
          // Filter duplicates based on name and size
          const existingKeys = new Set(prev.map(f => `${f.name}-${f.size}`));
          const uniqueNewFiles = validFiles.filter(f => !existingKeys.has(`${f.name}-${f.size}`));

          if (uniqueNewFiles.length === 0) return prev;
          return [...prev, ...uniqueNewFiles];
        });
      }
      // Reset input value to allow selecting the same file again if needed
      e.target.value = '';
    }
  };

  const textPrimary = theme === 'dark' ? 'text-white' : 'text-slate-900';
  const textSecondary = theme === 'dark' ? 'text-slate-300' : 'text-slate-600';
  const textMuted = theme === 'dark' ? 'text-slate-300' : 'text-slate-500';
  const iconColor = theme === 'dark' ? 'text-slate-300' : 'text-slate-700';

  return (
    <div className={`glass-panel p-6 sm:p-8 transition-all duration-300 hover:shadow-brand-primary/10 ${theme === 'dark' ? '' : 'border-slate-300'
      }`}>
      <Tooltip
        content="支援上傳音訊檔案（MP3、WAV、M4A）和影片檔案（MP4、MOV）。可同時選擇多個檔案進行批次處理，系統會自動提取音軌進行語音轉文字。"
        theme={theme}
        position="right"
      >
        <div className={`text-lg font-medium flex items-center gap-4 cursor-help mb-5 ${textPrimary}`}>
          <div className={`p-2 sm:p-2.5 rounded-lg text-brand-primary ${theme === 'dark' ? 'bg-brand-primary/10' : 'bg-brand-primary/10 border border-brand-primary/20'}`}>
            <Upload size={18} className="sm:w-5 sm:h-5" />
          </div>
          <span className="flex items-center gap-2">
            上傳檔案
            <Info size={14} className={`${theme === 'dark' ? 'text-slate-400' : 'text-slate-400'} opacity-60`} />
          </span>
        </div>
      </Tooltip>

      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => !processing && !uploading && document.getElementById('file-input').click()}
        className={`
          relative border-2 border-dashed rounded-2xl px-8 py-12 lg:py-16 text-center transition-all duration-300
          ${processing || uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-brand-primary/50 hover:bg-brand-primary/5'}
          ${isDragActive ? 'border-brand-primary bg-brand-primary/10 scale-[1.01]' : ''}
          ${files.length > 0 && !isDragActive
            ? 'border-brand-primary/30 bg-brand-primary/5'
            : !isDragActive ? (theme === 'dark' ? 'border-glass-border' : 'border-slate-300') : ''}
        `}
      >
        <input
          id="file-input"
          type="file"
          multiple
          accept="audio/*,video/*,.mp3,.wav,.m4a,.mp4,.mov"
          onChange={handleFileSelect}
          disabled={processing || uploading}
          className="hidden"
        />

        <div className={`inline-flex p-5 rounded-full mb-5 transition-all duration-300 ${isDragActive
          ? 'bg-brand-primary/20 text-brand-primary scale-110'
          : files.length > 0
            ? theme === 'dark'
              ? 'bg-brand-accent/20 text-brand-accent'
              : 'bg-brand-accent/15 text-brand-accent border-2 border-brand-accent/30'
            : theme === 'dark'
              ? `bg-glass-200 ${iconColor}`
              : `bg-slate-200 ${iconColor}`
          }`}>
          {files.length > 0 ? <FileAudio size={36} /> : <UploadCloud size={36} />}
        </div>

        {files.length > 0 ? (
          <div>
            <h3 className={`text-lg font-semibold mb-1 ${textPrimary}`}>已選擇 {files.length} 個檔案</h3>
            <p className={`text-sm ${textSecondary}`}>點擊或拖放以新增更多</p>
          </div>
        ) : (
          <div>
            <h3 className={`text-lg font-semibold mb-1.5 ${textPrimary}`}>
              {isDragActive ? '放開以新增檔案' : '拖放檔案至此或點擊瀏覽'}
            </h3>
            <p className={`text-sm ${textSecondary}`}>
              支援 MP3, WAV, M4A, MP4, MOV (最大 500MB)
            </p>
          </div>
        )}
      </div>

      {/* Size Error Alert */}
      {sizeError && (
        <div className={`mt-4 p-4 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-200 ${theme === 'dark'
          ? 'bg-red-500/10 border border-red-500/30 text-red-400'
          : 'bg-red-50 border-2 border-red-200 text-red-600'
          }`}>
          <AlertCircle size={20} className="flex-shrink-0" />
          <span className="text-sm">{sizeError}</span>
          <button
            type="button"
            onClick={() => setSizeError(null)}
            className={`ml-auto p-1 rounded-lg transition-colors ${theme === 'dark' ? 'hover:bg-red-500/20' : 'hover:bg-red-100'
              }`}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-6 space-y-3">
          <h4 className={`text-sm font-semibold uppercase tracking-wider ${textSecondary}`}>已選檔案 ({files.length})</h4>
          <div className="space-y-2">
            {files.map((file, index) => (
              <div key={index} className={`glass-card p-3 flex items-center justify-between group ${theme === 'dark' ? '' : 'border-slate-300'
                }`}>
                <div className="flex items-center gap-3 overflow-hidden">
                  <div className={`p-2 text-brand-secondary rounded-lg ${theme === 'dark' ? 'bg-brand-secondary/20' : 'bg-brand-secondary/10 border border-brand-secondary/20'
                    }`}>
                    <FileAudio size={18} />
                  </div>
                  <div className="min-w-0">
                    <p className={`text-sm font-medium truncate ${textPrimary}`}>{file.name}</p>
                    <p className={`text-xs mt-0.5 ${textMuted}`}>{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>

                {!processing && !uploading && (
                  <button
                    onClick={() => removeFile(index)}
                    className={`p-1.5 rounded-lg hover:text-red-400 hover:bg-red-400/10 transition-colors ${iconColor}`}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload Progress */}
      {uploading && (
        <div className={`mt-6 p-5 rounded-xl space-y-4 ${theme === 'dark'
          ? 'bg-brand-secondary/10 border border-brand-secondary/20'
          : 'bg-brand-secondary/5 border-2 border-brand-secondary/30'
          }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Loader2 size={20} className="animate-spin text-brand-secondary" />
              <span className={`text-sm font-semibold ${textPrimary}`}>上傳中...</span>
            </div>
            <span className={`text-sm font-bold text-brand-secondary`}>{uploadProgress}%</span>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-2.5 bg-glass-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-brand-secondary to-brand-primary transition-all duration-300 ease-out shadow-lg"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>

          {/* File Info & Transfer Stats */}
          <div className={`flex items-center justify-between text-xs ${textSecondary}`}>
            <div className="flex items-center gap-4">
              <span>
                {files.length} 個檔案 • {(files.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024).toFixed(2)} MB
              </span>
            </div>
            {uploadProgress > 0 && uploadProgress < 100 && uploadSpeed > 0 && (
              <span className="font-mono font-semibold text-brand-secondary">
                {uploadSpeed >= 1024 * 1024
                  ? `${(uploadSpeed / 1024 / 1024).toFixed(2)} MB/s`
                  : `${(uploadSpeed / 1024).toFixed(2)} KB/s`}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Processing State */}
      {processing && (
        <div className={`mt-6 p-5 rounded-xl flex items-center gap-4 animate-pulse-slow ${theme === 'dark'
          ? 'bg-brand-primary/10 border border-brand-primary/20'
          : 'bg-brand-primary/5 border-2 border-brand-primary/30'
          }`}>
          <Loader2 size={22} className="animate-spin text-brand-primary" />
          <span className="text-sm font-semibold text-brand-primary">正在處理音訊... 這可能需要一段時間。</span>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
