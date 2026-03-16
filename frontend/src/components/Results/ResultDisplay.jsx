/**
 * 結果顯示組件 - 展示處理結果
 */
import React, { useState } from 'react';
import {
  CheckCircle,
  Download,
  Copy,
  FileText,
  Clock,
  ChevronDown,
  ChevronUp,
  Brain,
  Mic
} from 'lucide-react';

const ResultDisplay = ({
  result,
  processingMode,
  originalText = null,
  type = 'audio'
}) => {
  const [showOriginal, setShowOriginal] = useState(false);
  const [showAISummary, setShowAISummary] = useState(true);
  const [copiedSection, setCopiedSection] = useState(null);

  if (!result) {
    return (
      <div className="result-display">
        <div className="no-result">
          <p>沒有可顯示的結果數據</p>
        </div>
      </div>
    );
  }

  const handleCopy = async (text, section) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(section);
      setTimeout(() => setCopiedSection(null), 2000);
    } catch (err) {
      // 複製失敗，靜默處理
    }
  };

  const handleDownload = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatTimestamp = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="result-display">
      <div className="result-header">
        <div className="success-indicator">
          <CheckCircle className="success-icon" size={24} />
          <h3>處理完成</h3>
        </div>
        
        <div className="result-actions">
          <button
            className="action-btn"
            onClick={() => handleDownload(
              result.ai_summary || result.processed_text || result.organized_text,
              `processed_${type}_${Date.now()}.txt`
            )}
          >
            <Download size={16} />
            下載
          </button>
          
          <button
            className={`action-btn ${copiedSection === 'all' ? 'copied' : ''}`}
            onClick={() => handleCopy(result.ai_summary || result.processed_text || result.organized_text, 'all')}
          >
            <Copy size={16} />
            {copiedSection === 'all' ? '已複製' : '複製'}
          </button>
        </div>
      </div>

      {/* 處理摘要 */}
      <div className="processing-summary">
        <div className="summary-item">
          <span className="summary-label">處理模式:</span>
          <span className="summary-value">
            {processingMode === 'meeting' ? '會議記錄' : 
             processingMode === 'lecture' ? '講座筆記' : '通用模式'}
          </span>
        </div>

        {result.processing_time && (
          <div className="summary-item">
            <Clock size={14} />
            <span className="summary-value">
              處理時間: {result.processing_time}秒
            </span>
          </div>
        )}
      </div>

      {/* 區塊1: AI智能摘要 */}
      <div className="result-section ai-summary">
        <div className="section-header">
          <button
            className="section-toggle main-toggle"
            onClick={() => setShowAISummary(!showAISummary)}
          >
            <Brain size={18} />
            <h4>AI智能摘要</h4>
            {showAISummary ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          
          {showAISummary && (
            <div className="section-actions">
              <button
                className={`copy-section-btn ${copiedSection === 'ai_summary' ? 'copied' : ''}`}
                onClick={() => handleCopy(result.ai_summary || result.processed_text || result.organized_text || '無AI摘要結果', 'ai_summary')}
              >
                <Copy size={14} />
                {copiedSection === 'ai_summary' ? '已複製' : '複製'}
              </button>
              <button
                className="download-btn"
                onClick={() => handleDownload(
                  result.ai_summary || result.processed_text || result.organized_text || '無AI摘要結果',
                  `ai_summary_${Date.now()}.txt`
                )}
              >
                <Download size={14} />
                下載
              </button>
            </div>
          )}
        </div>
        
        {showAISummary && (
          <div className="section-content">
            <div className="content-text ai-text">
              {result.ai_summary || result.processed_text || result.organized_text || '無AI摘要結果'}
            </div>
          </div>
        )}
      </div>

      {/* 區塊2: 原始資料 */}
      <div className="result-section original-data">
        <div className="section-header">
          <button
            className="section-toggle main-toggle"
            onClick={() => setShowOriginal(!showOriginal)}
          >
            <Mic size={18} />
            <h4>原始資料</h4>
            {showOriginal ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          
          {showOriginal && (
            <div className="section-actions">
              <button
                className={`copy-section-btn ${copiedSection === 'original' ? 'copied' : ''}`}
                onClick={() => handleCopy(result.transcription || result.text || originalText || '無原始資料', 'original')}
              >
                <Copy size={14} />
                {copiedSection === 'original' ? '已複製' : '複製'}
              </button>
              <button
                className="download-btn"
                onClick={() => handleDownload(
                  result.transcription || result.text || originalText || '無原始資料',
                  `original_transcription_${Date.now()}.txt`
                )}
              >
                <Download size={14} />
                下載
              </button>
            </div>
          )}
        </div>
        
        {showOriginal && (
          <div className="section-content">
            <div className="content-text original-text">
              {result.transcription || result.text || originalText || '無原始資料'}
            </div>
            
            {result.text_with_timestamps && (
              <details className="timestamps-section">
                <summary>時間戳版本</summary>
                <div className="content-text timestamp-text">
                  {result.text_with_timestamps}
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      {/* 文字比較（僅文字處理） */}
      {type === 'text' && originalText && (
        <div className="text-comparison">
          <button
            className="section-toggle"
            onClick={() => setShowOriginal(!showOriginal)}
          >
            <FileText size={16} />
            <span>原始文字</span>
            {showOriginal ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          
          {showOriginal && (
            <div className="collapsible-content">
              <div className="section-actions">
                <button
                  className={`copy-section-btn ${copiedSection === 'original' ? 'copied' : ''}`}
                  onClick={() => handleCopy(originalText, 'original')}
                >
                  {copiedSection === 'original' ? '已複製' : '複製'}
                </button>
              </div>
              
              <div className="result-content">
                <pre className="original-text">
                  {originalText}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 統計信息 */}
      {(result.word_count || result.char_count) && (
        <div className="result-stats">
          {result.word_count && (
            <div className="stat-item">
              <span className="stat-label">詞數:</span>
              <span className="stat-value">{result.word_count}</span>
            </div>
          )}
          
          {result.char_count && (
            <div className="stat-item">
              <span className="stat-label">字數:</span>
              <span className="stat-value">{result.char_count}</span>
            </div>
          )}
          
          {result.audio_duration && (
            <div className="stat-item">
              <span className="stat-label">音頻時長:</span>
              <span className="stat-value">{formatTimestamp(result.audio_duration)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ResultDisplay;