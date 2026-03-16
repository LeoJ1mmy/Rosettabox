/**
 * 處理狀態組件 - 顯示任務進度和隊列狀態
 * 支援桌面版 hover 和手機版點擊 tooltip
 */
import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Clock, Users, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const ProcessingStatus = ({
  progress,
  queueStatus,
  onCancel,
  type = 'audio'
}) => {
  const [showQueueTooltip, setShowQueueTooltip] = useState(false);
  const [showProcessingTooltip, setShowProcessingTooltip] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const queueTooltipRef = useRef(null);
  const processingTooltipRef = useRef(null);

  // 檢測手機版
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768 || 'ontouchstart' in window);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 點擊外部關閉
  useEffect(() => {
    if (!isMobile) return;
    const handleClickOutside = (e) => {
      if (showQueueTooltip && queueTooltipRef.current && !queueTooltipRef.current.contains(e.target)) {
        setShowQueueTooltip(false);
      }
      if (showProcessingTooltip && processingTooltipRef.current && !processingTooltipRef.current.contains(e.target)) {
        setShowProcessingTooltip(false);
      }
    };
    document.addEventListener('touchstart', handleClickOutside);
    return () => document.removeEventListener('touchstart', handleClickOutside);
  }, [showQueueTooltip, showProcessingTooltip, isMobile]);

  if (!progress && !queueStatus) return null;

  const isInQueue = queueStatus && (queueStatus.status === 'queued' || queueStatus.status === 'pending');
  const isProcessing = progress && (progress.stage || progress.progress > 0);
  const isCompleted = progress && progress.progress === 100;

  // 桌面版 tooltip 樣式
  const desktopTooltipStyle = {
    position: 'absolute',
    zIndex: 50,
    left: 0,
    top: '100%',
    marginTop: '8px',
    padding: '12px 16px',
    borderRadius: '12px',
    fontSize: '14px',
    lineHeight: '1.5',
    width: '280px',
    backgroundColor: '#1e293b',
    color: '#e2e8f0',
    border: '1px solid #475569',
    boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
    animation: 'fadeIn 0.2s ease-out'
  };

  // 手機版 tooltip 樣式
  const mobileTooltipStyle = {
    position: 'fixed',
    zIndex: 50,
    left: '16px',
    right: '16px',
    bottom: '80px',
    padding: '16px',
    borderRadius: '16px',
    fontSize: '14px',
    lineHeight: '1.6',
    backgroundColor: '#1e293b',
    color: '#e2e8f0',
    border: '1px solid #475569',
    boxShadow: '0 10px 40px rgba(0,0,0,0.4)',
    animation: 'slideUp 0.2s ease-out'
  };

  // 手機版遮罩樣式
  const overlayStyle = {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0,0,0,0.3)',
    zIndex: 40
  };

  const handleQueueTooltip = (e) => {
    if (isMobile) {
      e.preventDefault();
      e.stopPropagation();
      setShowQueueTooltip(!showQueueTooltip);
    }
  };

  const handleProcessingTooltip = (e) => {
    if (isMobile) {
      e.preventDefault();
      e.stopPropagation();
      setShowProcessingTooltip(!showProcessingTooltip);
    }
  };

  const renderTooltip = (content, isVisible, onClose) => {
    if (!isVisible) return null;

    return (
      <>
        {isMobile && <div style={overlayStyle} onClick={onClose} />}
        <div style={isMobile ? mobileTooltipStyle : desktopTooltipStyle}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <Info size={16} style={{ flexShrink: 0, marginTop: '2px', color: '#a78bfa' }} />
            <span style={{ flex: 1 }}>{content}</span>
            {isMobile && (
              <button
                type="button"
                onClick={onClose}
                style={{
                  flexShrink: 0,
                  padding: '4px',
                  borderRadius: '50%',
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>
      </>
    );
  };

  return (
    <div className="processing-status">
      {isInQueue && (
        <div className="queue-status">
          <div
            ref={queueTooltipRef}
            className="status-header"
            style={{ position: 'relative', cursor: 'help' }}
            onMouseEnter={() => !isMobile && setShowQueueTooltip(true)}
            onMouseLeave={() => !isMobile && setShowQueueTooltip(false)}
            onClick={handleQueueTooltip}
          >
            <Users className="status-icon" size={20} />
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              任務已排隊
              <Info
                size={14}
                style={{
                  opacity: 0.6,
                  color: '#94a3b8',
                  transition: 'opacity 0.2s'
                }}
                className="hover-opacity-100"
              />
            </h4>
            {renderTooltip(
              '您的任務已加入處理隊列。系統會依序處理每個任務，隊列位置顯示您前方還有多少任務正在等待。處理時間取決於檔案大小和系統負載。',
              showQueueTooltip,
              () => setShowQueueTooltip(false)
            )}
          </div>

          <div className="queue-info">
            <div className="queue-item">
              <Clock size={16} />
              <span>隊列位置: {queueStatus.position || 0}</span>
            </div>

            {queueStatus.estimated_wait_time && (
              <div className="queue-item">
                <Clock size={16} />
                <span>預計等待: {Math.ceil(queueStatus.estimated_wait_time / 60)} 分鐘</span>
              </div>
            )}

            <div className="queue-item">
              <Users size={16} />
              <span>前方還有 {(queueStatus.position || 1) - 1} 個任務</span>
            </div>
          </div>

          {onCancel && (
            <button type="button" className="cancel-queue-btn" onClick={onCancel}>
              <XCircle size={16} />
              取消排隊
            </button>
          )}
        </div>
      )}

      {isProcessing && (
        <div className="processing-status-details">
          <div
            ref={processingTooltipRef}
            className="status-header"
            style={{ position: 'relative', cursor: isCompleted ? 'default' : 'help' }}
            onMouseEnter={() => !isMobile && !isCompleted && setShowProcessingTooltip(true)}
            onMouseLeave={() => !isMobile && setShowProcessingTooltip(false)}
            onClick={!isCompleted ? handleProcessingTooltip : undefined}
          >
            {isCompleted ? (
              <>
                <div className="status-icon completed-check">✓</div>
                <h4 style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  處理完成！
                </h4>
              </>
            ) : (
              <>
                <Loader2 className="status-icon spinning" size={20} />
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {type === 'audio' ? '處理音頻中...' : '整理文字中...'}
                  <Info
                    size={14}
                    style={{
                      opacity: 0.6,
                      color: '#94a3b8',
                      transition: 'opacity 0.2s'
                    }}
                  />
                </h4>
              </>
            )}
            {!isCompleted && renderTooltip(
              '系統正在處理您的檔案。處理流程包括：音頻預處理、語音識別（Whisper）、文字精煉、AI 文字整理。進度條顯示當前處理階段。',
              showProcessingTooltip,
              () => setShowProcessingTooltip(false)
            )}
          </div>

          {progress.stage && (
            <div className="processing-stage">
              <span className="stage-text" style={isCompleted ? { color: '#10b981', fontWeight: 'bold' } : {}}>
                {progress.stage}
              </span>
              {progress.progress > 0 && (
                <span className="stage-progress" style={isCompleted ? { color: '#10b981' } : {}}>
                  ({progress.progress}%)
                </span>
              )}
            </div>
          )}

          {progress.message && progress.message !== progress.stage && (
            <div className="processing-detail" style={{ fontSize: '13px', opacity: 0.7, marginTop: '4px' }}>
              {progress.message}
            </div>
          )}

          {progress.progress > 0 && (
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${progress.progress}%`,
                  backgroundColor: isCompleted ? '#10b981' : undefined,
                  transition: 'width 0.8s ease-in-out'
                }}
              />
            </div>
          )}

          {(() => {
            const STEPS = [
              { name: '音頻預處理', stageMatch: ['音頻預處理'], completeAt: 5 },
              { name: '語音識別', stageMatch: ['語音識別'], completeAt: 58 },
              { name: '文字精煉', stageMatch: ['文字精煉'], completeAt: 75 },
              { name: 'AI 智能整理', stageMatch: ['AI 智能整理'], completeAt: 95 },
              { name: '完成', stageMatch: ['處理完成'], completeAt: 100 },
            ];

            return (
              <div className="processing-steps">
                {STEPS.map((step, i) => {
                  const isActive = step.stageMatch.some(s => progress.stage === s);
                  const isStepCompleted = progress.progress >= step.completeAt;
                  return (
                    <div key={i} className={`step ${isActive ? 'active' : isStepCompleted ? 'completed' : ''}`}>
                      <div className="step-dot" />
                      <span>{step.name}</span>
                    </div>
                  );
                })}
              </div>
            );
          })()}

          {onCancel && progress.progress < 90 && (
            <button type="button" className="cancel-processing-btn" onClick={onCancel}>
              <XCircle size={16} />
              取消處理
            </button>
          )}
        </div>
      )}

      {queueStatus && queueStatus.error && (
        <div className="status-error">
          <AlertTriangle size={16} />
          <span>{queueStatus.error}</span>
        </div>
      )}

      {/* 動畫樣式 */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};

export default ProcessingStatus;
