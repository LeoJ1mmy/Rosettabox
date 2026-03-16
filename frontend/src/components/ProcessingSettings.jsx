import React, { useState, useEffect, memo, useCallback, useRef } from 'react';
import { ChevronDown, ChevronUp, Wand2, Mail, Play, Loader2, Info, X } from 'lucide-react';
import TagSelector from './TagSelector';
import Tooltip from './Tooltip';

// Move SettingSection outside to prevent recreation on every render
const SettingSection = memo(({ title, icon: Icon, children, defaultOpen = true, theme, tooltip }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [showTooltip, setShowTooltip] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const tooltipRef = useRef(null);

  // 檢測手機版
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768 || 'ontouchstart' in window);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 點擊外部關閉
  useEffect(() => {
    if (!showTooltip || !isMobile) return;
    const handleClickOutside = (e) => {
      if (tooltipRef.current && !tooltipRef.current.contains(e.target)) {
        setShowTooltip(false);
      }
    };
    document.addEventListener('touchstart', handleClickOutside);
    return () => document.removeEventListener('touchstart', handleClickOutside);
  }, [showTooltip, isMobile]);

  const textPrimary = theme === 'dark' ? 'text-white' : 'text-slate-900';
  const iconMuted = theme === 'dark' ? 'text-slate-300' : 'text-slate-600';
  const hoverBg = theme === 'dark' ? 'hover:bg-white/5' : 'hover:bg-slate-200/50';

  const sectionBorder = theme === 'dark' ? '' : 'border-slate-300';
  const dividerBorder = theme === 'dark' ? 'border-white/10' : 'border-slate-300';

  const handleTooltipToggle = (e) => {
    if (tooltip && isMobile) {
      e.preventDefault();
      e.stopPropagation();
      setShowTooltip(!showTooltip);
    }
  };

  return (
    <div className={`glass-panel overflow-hidden ${sectionBorder}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full px-4 sm:px-8 py-4 sm:py-5 flex items-center justify-between ${hoverBg} transition-colors ${isOpen ? `border-b ${dividerBorder}` : ''
          }`}
      >
        <div
          ref={tooltipRef}
          className="flex items-center gap-3 sm:gap-4 relative"
          onMouseEnter={() => !isMobile && tooltip && setShowTooltip(true)}
          onMouseLeave={() => !isMobile && setShowTooltip(false)}
        >
          <div className={`p-2 sm:p-2.5 rounded-lg text-brand-primary ${theme === 'dark' ? 'bg-brand-primary/10' : 'bg-brand-primary/10 border border-brand-primary/20'
            }`}>
            <Icon size={18} className="sm:w-5 sm:h-5" />
          </div>
          <span className={`text-lg font-medium flex items-center gap-2 ${textPrimary}`}>
            {title}
            {tooltip && (
              <span
                onClick={handleTooltipToggle}
                className={`${theme === 'dark' ? 'text-slate-400' : 'text-slate-400'} opacity-60 hover:opacity-100 transition-opacity p-1 -m-1`}
              >
                <Info size={14} />
              </span>
            )}
          </span>

          {/* Tooltip - 手機版固定底部，桌面版跟隨元素 */}
          {tooltip && showTooltip && (
            <>
              {isMobile && (
                <div
                  className="fixed inset-0 bg-black/30 z-40"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowTooltip(false);
                  }}
                />
              )}
              <div className={`
                z-50
                ${isMobile
                  ? 'fixed left-4 right-4 bottom-20'
                  : 'absolute left-0 top-full mt-2 w-72 max-w-[calc(100vw-2rem)]'
                }
                px-4 py-3 rounded-xl text-sm leading-relaxed
                animate-in fade-in zoom-in-95 duration-200
                ${theme === 'dark'
                  ? 'bg-slate-800 text-slate-200 border border-slate-600 shadow-xl shadow-black/30'
                  : 'bg-white text-slate-700 border border-slate-200 shadow-lg shadow-slate-200/50'
                }
              `}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-start gap-3">
                  <Info size={16} className={`flex-shrink-0 mt-0.5 ${theme === 'dark' ? 'text-brand-secondary' : 'text-brand-primary'}`} />
                  <span className="flex-1">{tooltip}</span>
                  {isMobile && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowTooltip(false);
                      }}
                      className={`flex-shrink-0 p-1 rounded-full ${theme === 'dark' ? 'hover:bg-slate-700 text-slate-300' : 'hover:bg-slate-100 text-slate-500'}`}
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
        {isOpen ? <ChevronUp size={18} className={iconMuted} /> : <ChevronDown size={18} className={iconMuted} />}
      </button>

      {isOpen && (
        <div className="px-4 sm:px-8 pb-6 sm:pb-8 pt-4 sm:pt-6 space-y-4 sm:space-y-6 animate-in slide-in-from-top-2 duration-200">
          {children}
        </div>
      )}
    </div>
  );
});

SettingSection.displayName = 'SettingSection';

const ProcessingSettings = memo(({
  theme,
  files,
  processing,
  uploading,
  handleFileUpload,
  processingMode,
  setProcessingMode,
  whisperModel,
  setWhisperModel,
  aiModel,
  setAiModel,
  enableLLMProcessing,
  setEnableLLMProcessing,
  availableModels,
  availableAiModels,
  modelLoading,
  ollamaStatus,
  setCustomModalType,
  setShowCustomModal,
  emailEnabled,
  setEmailEnabled,
  emailAddress,
  setEmailAddress,
  emailFeatureEnabled,
  selectedTags,
  setSelectedTags,
  customTagPrompt,
  setCustomTagPrompt,
  sourceType = 'audio',
  textInput = '',
}) => {
  // Theme-aware colors
  const textPrimary = theme === 'dark' ? 'text-white' : 'text-slate-900';
  const textSecondary = theme === 'dark' ? 'text-slate-300' : 'text-slate-700';
  const textMuted = theme === 'dark' ? 'text-slate-300' : 'text-slate-600';
  const iconMuted = theme === 'dark' ? 'text-slate-300' : 'text-slate-600';
  const hoverBg = theme === 'dark' ? 'hover:bg-white/5' : 'hover:bg-slate-200/50';
  const hoverText = theme === 'dark' ? 'hover:text-white' : 'hover:text-slate-900';
  const borderHover = theme === 'dark' ? 'hover:border-white/20' : 'hover:border-slate-400';

  const isTextMode = sourceType === 'text';

  // 當選擇僅轉錄模式時，自動關閉 LLM 處理；文字模式強制開啟
  useEffect(() => {
    if (isTextMode) {
      setEnableLLMProcessing(true);
    } else if (processingMode === 'transcribe') {
      setEnableLLMProcessing(false);
    }
  }, [processingMode, isTextMode, setEnableLLMProcessing]);

  // Memoize email change handler to prevent unnecessary re-renders
  const handleEmailChange = useCallback((e) => {
    setEmailAddress(e.target.value);
  }, [setEmailAddress]);

  const allModes = [
    { id: 'meeting', label: '會議記錄', desc: '結構化會議內容' },
    { id: 'lecture', label: '講座筆記', desc: '學術內容整理' },
    { id: 'default', label: '通用模式', desc: '基本內容整理' },
    { id: 'transcribe', label: '僅轉錄', desc: '不進行 AI 摘要' },
    { id: 'interview', label: '訪談整理', desc: '問答格式整理' },
    { id: 'custom', label: '自定義模式', desc: '完全自定義' }
  ];

  // 文字模式下隱藏「僅轉錄」（已經是文字了，不需要轉錄選項）
  const modes = isTextMode ? allModes.filter(m => m.id !== 'transcribe') : allModes;

  return (
    <div className="space-y-6">
      {/* AI Processing Toggle */}
      <div
        data-tutorial="llm-toggle"
        className={`glass-panel p-6 flex items-center justify-between ${theme === 'dark' ? '' : 'border-slate-300'
          }`}
      >
        <Tooltip
          content="開啟後，AI 會自動將語音轉錄結果進行智能整理、摘要和格式化。關閉則僅輸出原始轉錄文字，適合需要完整逐字稿的場景。"
          theme={theme}
          position="right"
        >
          <div className="flex items-center gap-3 sm:gap-4 cursor-help">
            <div className={`p-2 sm:p-2.5 rounded-lg text-brand-primary ${theme === 'dark' ? 'bg-brand-primary/10' : 'bg-brand-primary/10 border border-brand-primary/20'
              }`}>
              <Wand2 size={18} className="sm:w-5 sm:h-5" />
            </div>
            <div>
              <div className={`text-lg font-medium flex items-center gap-2 ${textPrimary}`}>
                AI 智能整理
                <Info size={14} className={`${theme === 'dark' ? 'text-slate-400' : 'text-slate-400'} opacity-60 hover:opacity-100 transition-opacity`} />
              </div>
              <div className={`text-xs sm:text-sm ${textMuted}`}>
                {isTextMode
                  ? '文字處理模式 - AI 將自動整理和摘要內容'
                  : enableLLMProcessing ? '開啟 - AI 將自動整理和摘要內容' : '關閉 - 僅進行語音轉文字'}
              </div>
            </div>
          </div>
        </Tooltip>
        <button
          type="button"
          onClick={() => setEnableLLMProcessing(!enableLLMProcessing)}
          disabled={processingMode === 'transcribe' || isTextMode}
          className={`
            w-14 h-7 p-0 border-0 rounded-full transition-all duration-200
            relative flex-shrink-0
            ${(processingMode === 'transcribe' || isTextMode) ? 'opacity-50 cursor-not-allowed' : ''}
            ${enableLLMProcessing
              ? theme === 'dark'
                ? 'bg-brand-primary/20 ring-2 ring-brand-primary'
                : 'bg-brand-primary/10 ring-2 ring-brand-primary'
              : theme === 'dark'
                ? 'bg-transparent ring-2 ring-slate-600'
                : 'bg-transparent ring-2 ring-slate-400'}
          `}
          style={{ minHeight: 0, minWidth: 0, borderRadius: '9999px' }}
        >
          <span className={`
            absolute top-1 w-5 h-5 rounded-full transition-all duration-200
            ${enableLLMProcessing
              ? theme === 'dark'
                ? 'left-[30px] bg-brand-primary'
                : 'left-[30px] bg-brand-primary'
              : theme === 'dark'
                ? 'left-1 bg-slate-600'
                : 'left-1 bg-slate-400'}
          `}
          />
        </button>
      </div>

      {/* Primary Settings - 處理模式選擇 */}
      <SettingSection
        title="處理模式"
        icon={Wand2}
        theme={theme}
        tooltip="選擇適合您內容類型的處理模式。不同模式會採用不同的 AI 整理策略：會議記錄會提取決策和待辦事項；講座筆記會整理重點概念；訪談整理會呈現問答格式。"
      >
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3" data-tutorial="processing-mode">
          {modes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => {
                setProcessingMode(mode.id);
                // 選擇非僅轉錄模式時，自動開啟 AI 智能整理
                if (mode.id !== 'transcribe') {
                  setEnableLLMProcessing(true);
                }
                if (mode.id === 'custom') {
                  setCustomModalType('mode');
                  setShowCustomModal(true);
                }
              }}
                className={`
                  relative p-4 rounded-xl border text-left transition-all duration-300
                  ${processingMode === mode.id
                    ? theme === 'dark'
                      ? 'bg-brand-primary/20 border-brand-primary shadow-lg shadow-brand-primary/10'
                      : 'bg-brand-primary/10 border-brand-primary/50 border-2 shadow-md shadow-brand-primary/20'
                    : theme === 'dark'
                      ? `bg-glass-100 border-glass-border hover:bg-glass-200 hover:border-white/20`
                      : `bg-white/50 border-slate-300 hover:bg-slate-100 hover:border-slate-400`}
                `}
              >
                <div
                  className="font-medium mb-1 text-sm"
                  style={{
                    color: processingMode === mode.id
                      ? '#3b82f6'
                      : (theme === 'dark' ? '#94a3b8' : '#475569')
                  }}
                >{mode.label}</div>
                <div
                  className="text-xs"
                  style={{
                    color: processingMode === mode.id
                      ? (theme === 'dark' ? '#93c5fd' : '#2563eb')
                      : (theme === 'dark' ? 'rgba(148,163,184,0.7)' : 'rgba(71,85,105,0.7)')
                  }}
                >{mode.desc}</div>
              </button>
            ))}
          </div>
        </SettingSection>

      {/* Notification Settings - Moved outside advanced */}
      {emailFeatureEnabled && (
        <div data-tutorial="email-notification">
          <SettingSection
            title="通知設定"
            icon={Mail}
            theme={theme}
            tooltip="開啟 Email 通知後，當處理任務完成時系統會自動發送郵件通知您。"
          >
            <div className="space-y-6">
              <div className={`mb-4 flex items-center justify-between p-5 rounded-xl ${theme === 'dark'
                ? 'bg-glass-100/50 border border-glass-border/50'
                : 'bg-slate-50/80 border-2 border-slate-300'
                }`}>
                <div className="mt-2 mb-2 space-y-2">
                  <div className={`font-semibold text-base ${textPrimary}`}>Email 通知</div>
                  <div className={`text-sm ${textMuted}`}>任務完成後發送郵件提醒</div>
                </div>
                <button
                  type="button"
                  onClick={() => setEmailEnabled(!emailEnabled)}
                  className={`
                  w-12 h-6 p-0 border-0 rounded-full transition-all duration-200
                  relative flex-shrink-0
                  ${emailEnabled
                      ? theme === 'dark'
                        ? 'bg-brand-primary/20 ring-2 ring-brand-primary'
                        : 'bg-brand-primary/10 ring-2 ring-brand-primary'
                      : theme === 'dark'
                        ? 'bg-transparent ring-2 ring-slate-600'
                        : 'bg-transparent ring-2 ring-slate-400'}
                `}
                  style={{ minHeight: 0, minWidth: 0, borderRadius: '9999px' }}
                >
                  <span className={`
                  absolute top-1 w-4 h-4 rounded-full transition-all duration-200
                  ${emailEnabled
                      ? theme === 'dark'
                        ? 'left-[26px] bg-brand-primary'
                        : 'left-[26px] bg-brand-primary'
                      : theme === 'dark'
                        ? 'left-1 bg-slate-600'
                        : 'left-1 bg-slate-400'}
                `}
                  />
                </button>
              </div>

              {emailEnabled && (
                <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-3">
                  <label className={`block text-sm font-semibold mb-3 ${textSecondary}`}>Email 地址</label>
                  <input
                    type="email"
                    value={emailAddress}
                    onChange={handleEmailChange}
                    placeholder="請輸入您的 Email 地址"
                    className="glass-input"
                  />
                  <p className={`text-sm mt-3 ${textMuted}`}>處理完成後，系統將自動發送通知到此郵箱</p>
                </div>
              )}
            </div>
          </SettingSection>
        </div>
      )}

      {/* Tag Selector - Visible when AI processing is enabled */}
      {enableLLMProcessing && processingMode !== 'transcribe' && (
        <div className="animate-in fade-in slide-in-from-top-4 duration-300 space-y-6" data-tutorial="tag-selector">
          <TagSelector
            selectedTags={selectedTags}
            onTagsChange={setSelectedTags}
            customPrompt={customTagPrompt}
            onCustomPromptChange={setCustomTagPrompt}
            theme={theme}
            processingMode={processingMode}
          />
        </div>
      )}

      {/* Start Button */}
      <div className="mt-8">
        {(() => {
          const isReady = isTextMode
            ? textInput.trim().length >= 10
            : files.length > 0;
          const isDisabled = processing || uploading || !isReady;

          return (
            <>
              <button
                type="button"
                onClick={handleFileUpload}
                disabled={isDisabled}
                className={`
                  w-full py-4 rounded-xl font-display font-bold text-lg flex items-center justify-center gap-2 transition-all duration-300
                  ${isDisabled
                    ? theme === 'dark'
                      ? `bg-glass-200 border border-white/10 ${textMuted} cursor-not-allowed`
                      : `bg-slate-200 border-2 border-slate-300 ${textMuted} cursor-not-allowed`
                    : theme === 'dark'
                      ? 'bg-gradient-to-r from-brand-primary to-brand-secondary text-white shadow-lg shadow-brand-primary/30 hover:shadow-brand-primary/50 hover:scale-[1.02] active:scale-[0.98] border border-transparent'
                      : 'bg-gradient-to-r from-brand-primary to-brand-secondary text-slate-900 shadow-lg shadow-brand-primary/30 hover:shadow-brand-primary/50 hover:scale-[1.02] active:scale-[0.98]'}
                `}
              >
                {processing || uploading ? (
                  <>
                    <Loader2 size={24} className="animate-spin" />
                    <span>處理中...</span>
                  </>
                ) : (
                  <>
                    <Play size={24} fill="currentColor" />
                    <span>
                      {isTextMode
                        ? `開始處理${textInput.trim().length >= 10 ? ` (${textInput.trim().length.toLocaleString()} 字元)` : ''}`
                        : `開始處理${files.length > 0 ? ` (${files.length} 個檔案)` : ''}`
                      }
                    </span>
                  </>
                )}
              </button>
              {!isReady && !processing && (
                <div className={`text-center mt-2 text-xs animate-pulse ${textMuted}`}>
                  {isTextMode ? '請先輸入文字內容以啟用按鈕' : '請先上傳檔案以啟用按鈕'}
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
});

ProcessingSettings.displayName = 'ProcessingSettings';

export default ProcessingSettings;
