import React, { useState, useEffect, useMemo } from 'react';
import { ChevronDown, ChevronRight, Mic, Brain, Files, FileText, Copy, Check, Download, Trash2, Mail, Loader2, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './AISummaryStyles.css';

// 置信度顏色配置 (綠/黃/紅)
const CONFIDENCE_COLORS = {
  high: {   // >= 0.8
    light: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', badge: 'bg-green-100 text-green-700' },
    dark: { bg: 'bg-green-900/20', border: 'border-green-600', text: 'text-green-300', badge: 'bg-green-800/50 text-green-300' }
  },
  medium: { // 0.5 - 0.8
    light: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', badge: 'bg-yellow-100 text-yellow-700' },
    dark: { bg: 'bg-yellow-900/20', border: 'border-yellow-600', text: 'text-yellow-300', badge: 'bg-yellow-800/50 text-yellow-300' }
  },
  low: {    // < 0.5
    light: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', badge: 'bg-red-100 text-red-700' },
    dark: { bg: 'bg-red-900/20', border: 'border-red-600', text: 'text-red-300', badge: 'bg-red-800/50 text-red-300' }
  }
};

// 獲取置信度等級
const getConfidenceLevel = (confidence) => {
  if (confidence >= 0.8) return 'high';
  if (confidence >= 0.5) return 'medium';
  return 'low';
};

// 獲取置信度顏色配置
const getConfidenceColors = (confidence, theme) => {
  const level = getConfidenceLevel(confidence);
  return CONFIDENCE_COLORS[level][theme];
};

// 時間戳格式化
const formatTimestamp = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

// 取得 email 通知資訊 (單檔用 processing_config，批次用 config)
const getEmailInfo = (data) => {
  const config = data?.processing_config || data?.config;
  if (!config) return null;
  if (!config.email_enabled || !config.email_address) return null;
  return { address: config.email_address };
};

// Email 通知狀態橫幅
const EmailNotificationBanner = ({ theme, emailInfo }) => {
  if (!emailInfo) return null;
  return (
    <div className={`flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm mb-4 ${
      theme === 'dark'
        ? 'bg-emerald-900/20 border border-emerald-700/30 text-emerald-300'
        : 'bg-emerald-50 border border-emerald-200 text-emerald-700'
    }`}>
      <Mail size={16} className="flex-shrink-0" />
      <span>
        處理結果已發送至 <span className="font-semibold">{emailInfo.address}</span>
      </span>
    </div>
  );
};

const ResultDisplay = ({
  theme,
  result,
  processing,
  enableLLMProcessing,
  taskProgress,
  onCancel,
  sourceType = 'audio',
}) => {
  const isTextSource = sourceType === 'text' || (result && result.source_type === 'text');
  // 檢測是否為多檔案批次結果
  const isBatchResult = result && (result.files || result.batch_info);
  const isMultipleFiles = isBatchResult && result.files && result.files.length > 1;

  // 摺疊狀態管理
  const [batchSummaryExpanded, setBatchSummaryExpanded] = useState(true);
  const [fileStates, setFileStates] = useState({});

  // 當檢測到多檔案時，自動收起各檔案的詳細內容
  useEffect(() => {
    if (isMultipleFiles && result.files) {
      const initialStates = {};
      result.files.forEach((_, index) => {
        initialStates[index] = {
          expanded: false, // 檔案卡片預設收起
          whisperExpanded: false, // 語音識別預設收起
          aiSummaryExpanded: false, // AI摘要預設收起
        };
      });
      setFileStates(initialStates);
    } else if (!isMultipleFiles && result) {
      // 單檔案時重置狀態
      setFileStates({});
    }
  }, [isMultipleFiles, result]);

  // 單檔案結果的狀態
  const [whisperExpanded, setWhisperExpanded] = useState(false);
  const [aiSummaryExpanded, setAiSummaryExpanded] = useState(true);

  // 複製狀態管理
  const [copiedSection, setCopiedSection] = useState(null);

  // 複製功能
  const handleCopy = async (text, section) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(section);
      setTimeout(() => setCopiedSection(null), 2000);
    } catch (err) {
      // 複製失敗，靜默處理
    }
  };

  if (!result) {
    // Show processing indicator when actively processing
    if (processing) {
      const progress = taskProgress || { stage: '準備中', percentage: 0, message: '' };
      const pct = progress.percentage || 0;
      const isCompleted = pct === 100;

      const AUDIO_STEPS = [
        { name: '音頻預處理', stageMatch: ['音頻預處理'], completeAt: 5 },
        { name: '響度正規化', stageMatch: ['響度正規化'], completeAt: 12 },
        { name: '語音識別', stageMatch: ['語音識別'], completeAt: 58 },
        { name: '文字精煉', stageMatch: ['文字精煉'], completeAt: 75 },
        { name: 'AI 智能整理', stageMatch: ['AI 智能整理'], completeAt: 95 },
        { name: '完成', stageMatch: ['處理完成'], completeAt: 100 },
      ];

      const TEXT_STEPS = [
        { name: '準備處理', stageMatch: ['準備處理文字', '準備中'], completeAt: 10 },
        { name: '文字清理', stageMatch: ['文字清理', '文字精煉'], completeAt: 30 },
        { name: 'AI 智能整理', stageMatch: ['AI 處理中', 'AI 智能整理'], completeAt: 90 },
        { name: '完成', stageMatch: ['處理完成'], completeAt: 100 },
      ];

      const STEPS = isTextSource ? TEXT_STEPS : AUDIO_STEPS;

      return (
        <div className={`glass-panel p-8 min-h-[500px] flex flex-col justify-center ${
          theme === 'dark' ? '' : 'border-slate-300'
        }`}>
          <div className="flex flex-col items-center text-center">
            {/* Spinner or check */}
            {isCompleted ? (
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mb-6">
                <Check size={32} className="text-emerald-400" />
              </div>
            ) : (
              <div className="w-16 h-16 rounded-full bg-brand-primary/20 flex items-center justify-center mb-6">
                <Loader2 size={32} className="text-brand-primary animate-spin" />
              </div>
            )}

            {/* Title */}
            <h3 className={`text-lg font-semibold mb-2 ${
              isCompleted ? 'text-emerald-400' : theme === 'dark' ? 'text-white' : 'text-slate-900'
            }`}>
              {isCompleted ? '處理完成！' : isTextSource ? '處理文字中...' : '處理音頻中...'}
            </h3>

            {/* Stage and percentage */}
            {progress.stage && (
              <p className={`text-sm mb-1 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
                {progress.stage}
                {pct > 0 && <span className="ml-2 font-semibold text-brand-primary">({pct}%)</span>}
              </p>
            )}

            {/* Detail message */}
            {progress.message && progress.message !== progress.stage && (
              <p className={`text-xs mb-4 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-400'}`}>
                {progress.message}
              </p>
            )}

            {/* Progress bar */}
            {pct > 0 && (
              <div className={`w-full max-w-md h-2.5 rounded-full overflow-hidden mb-6 ${
                theme === 'dark' ? 'bg-glass-200' : 'bg-slate-200'
              }`}>
                <div
                  className={`h-full rounded-full ${
                    isCompleted
                      ? 'bg-emerald-500'
                      : 'bg-gradient-to-r from-brand-primary to-brand-secondary'
                  }`}
                  style={{ width: `${pct}%`, transition: 'width 0.8s ease-in-out' }}
                />
              </div>
            )}

            {/* Step timeline */}
            <div className="flex items-center gap-1 sm:gap-2 mb-6 flex-wrap justify-center">
              {STEPS.map((step, i) => {
                const isActive = step.stageMatch.some(s => progress.stage === s);
                const isStepCompleted = pct >= step.completeAt;
                return (
                  <div key={i} className="flex items-center gap-1 sm:gap-2">
                    {i > 0 && (
                      <div className={`w-4 sm:w-6 h-px ${
                        isStepCompleted ? 'bg-emerald-400' : theme === 'dark' ? 'bg-glass-border' : 'bg-slate-300'
                      }`} />
                    )}
                    <div className="flex items-center gap-1.5">
                      <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                        isActive
                          ? 'bg-brand-primary ring-4 ring-brand-primary/20'
                          : isStepCompleted
                            ? 'bg-emerald-400'
                            : theme === 'dark' ? 'bg-glass-300' : 'bg-slate-300'
                      }`} />
                      <span className={`text-xs whitespace-nowrap ${
                        isActive
                          ? 'text-brand-primary font-semibold'
                          : isStepCompleted
                            ? 'text-emerald-400'
                            : theme === 'dark' ? 'text-slate-400' : 'text-slate-400'
                      }`}>
                        {step.name}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Cancel button */}
            {onCancel && pct < 90 && (
              <button
                type="button"
                onClick={onCancel}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  theme === 'dark'
                    ? 'text-slate-300 hover:text-red-400 hover:bg-red-500/10 border border-glass-border hover:border-red-500/30'
                    : 'text-slate-500 hover:text-red-500 hover:bg-red-50 border border-slate-300 hover:border-red-300'
                }`}
              >
                <XCircle size={16} />
                取消處理
              </button>
            )}
          </div>
        </div>
      );
    }

    // Show empty state when not processing
    return (
      <div className={`glass-panel p-16 flex flex-col items-center justify-center text-center min-h-[500px] border-dashed border-2 ${
        theme === 'dark' ? 'border-glass-border bg-glass-100/50' : 'border-slate-300 bg-slate-50/50'
      }`}>
        <div className={`p-8 rounded-full mb-8 animate-pulse-slow ${
          theme === 'dark' ? 'bg-glass-200' : 'bg-slate-200'
        }`}>
          <FileText size={56} className={theme === 'dark' ? 'text-slate-400' : 'text-slate-400'} />
        </div>
        <h3 className={`text-xl font-display font-medium mb-2 ${
          theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
        }`}>等待處理結果</h3>
        <p className={`max-w-xs ${
          theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
        }`}>
          請先在「上傳設定」或「文字處理」頁面上傳檔案或輸入文字並開始處理，結果將會顯示於此處。
        </p>
      </div>
    );
  } // 如果是批次結果，解析批次資料
  if (isBatchResult) {
    const batchInfo = result.batch_info || {};
    const files = result.files || [];

    return (
      <div className={`glass-panel p-8 sm:p-10 lg:p-12 animate-in fade-in slide-in-from-bottom-4 duration-500 ${
        theme === 'dark' ? '' : 'border-slate-300'
      }`}>
        <div className="mb-6 flex items-center justify-between">
          <h3 className={`text-xl font-display font-bold flex items-center gap-3 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            <Files className="text-brand-primary" size={26} />
            批次處理結果
          </h3>
          <div className="px-4 py-2 rounded-full bg-brand-primary/10 text-brand-primary text-sm font-semibold">
            {files.length} 個檔案
          </div>
        </div>

        {/* Email 通知橫幅 */}
        <EmailNotificationBanner theme={theme} emailInfo={getEmailInfo(result)} />

        {/* 批次摘要 */}
        <BatchSummarySection
          theme={theme}
          batchInfo={batchInfo}
          expanded={batchSummaryExpanded}
          setExpanded={setBatchSummaryExpanded}
        />

        {/* 檔案列表 */}
        <div className="space-y-4 mt-6">
          {files.map((fileResult, index) => (
            <FileResultCard
              key={index}
              theme={theme}
              fileResult={fileResult}
              index={index}
              fileStates={fileStates}
              setFileStates={setFileStates}
              enableLLMProcessing={enableLLMProcessing}
              isMultipleFiles={isMultipleFiles}
              handleCopy={handleCopy}
              copiedSection={copiedSection}
            />
          ))}
        </div>
      </div>
    );
  }

  // 單檔案結果處理
  const whisperResult = result.whisper_result || result.transcription || result.original_text;
  const aiSummaryResult = result.ai_summary || result.processed_text || result.organized_text;

  return (
    <div className={`glass-panel p-8 sm:p-10 lg:p-12 animate-in fade-in slide-in-from-bottom-4 duration-500 ${
      theme === 'dark' ? '' : 'border-slate-300'
    }`}>
      <div className="mb-6 flex items-center justify-between">
        <h3 className={`text-xl font-display font-bold flex items-center gap-3 ${
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        }`}>
          <FileText className="text-brand-primary" size={26} />
          處理結果
        </h3>
        <div className="flex gap-2">
           {/* Actions could go here */}
        </div>
      </div>

      {/* Email 通知橫幅 */}
      <EmailNotificationBanner theme={theme} emailInfo={getEmailInfo(result)} />

      <div className="space-y-4">
        {/* 語音識別/原始文字結果 - 始終顯示 */}
        <DrawerSection
          title={isTextSource ? "原始文字" : "語音識別"}
          content={whisperResult}
          icon={isTextSource ? FileText : Mic}
          expanded={whisperExpanded}
          setExpanded={setWhisperExpanded}
          show={true}
          accentColor="blue"
          enableCopy={true}
          copyId="whisper-single"
          handleCopy={handleCopy}
          copiedSection={copiedSection}
          theme={theme}
          segments={isTextSource ? null : result.segments}
          avgConfidence={isTextSource ? null : result.avg_confidence}
          lowConfidenceCount={isTextSource ? null : result.low_confidence_count}
        />

        {/* AI 智能摘要 - 根據開關狀態顯示（文字來源始終顯示），使用 markdown 渲染 */}
        <DrawerSection
          title="AI 智能摘要"
          content={aiSummaryResult}
          icon={Brain}
          expanded={aiSummaryExpanded}
          setExpanded={setAiSummaryExpanded}
          show={isTextSource || enableLLMProcessing}
          accentColor="green"
          isMarkdown={true}
          enableCopy={true}
          copyId="ai-summary-single"
          handleCopy={handleCopy}
          copiedSection={copiedSection}
          theme={theme}
        />

      </div>

      {/* 如果沒有任何結果 */}
      {!whisperResult && !aiSummaryResult && (
        <div className={`text-center py-12 ${
          theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
        }`}>
          <p>暫無結果。</p>
        </div>
      )}
    </div>
  );
};

// 置信度摘要組件
const ConfidenceSummary = ({ segments, avgConfidence, lowConfidenceCount, theme }) => {
  if (!segments || segments.length === 0) return null;

  // 使用傳入的值或自行計算
  const avg = avgConfidence ?? (segments.reduce((sum, s) => sum + (s.confidence || 0), 0) / segments.length);
  const lowCount = lowConfidenceCount ?? segments.filter(s => (s.confidence || 0) < 0.5).length;
  const percentage = Math.round(avg * 100);

  return (
    <div className={`flex flex-wrap items-center gap-4 p-3 rounded-lg mb-4 ${
      theme === 'dark' ? 'bg-glass-100' : 'bg-slate-100'
    }`}>
      <div className="flex items-center gap-2">
        <span className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
          整體信心度:
        </span>
        <span className={`font-semibold text-lg ${
          avg >= 0.8 ? 'text-green-500' :
          avg >= 0.5 ? 'text-yellow-500' : 'text-red-500'
        }`}>
          {percentage}%
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-500"></span>
          <span className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}>高信心 ≥80%</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
          <span className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}>中信心 50-80%</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500"></span>
          <span className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}>低信心 &lt;50%</span>
        </span>
      </div>
      {lowCount > 0 && (
        <div className="text-sm text-red-500 font-medium">
          ⚠️ {lowCount} 個低信心段落需審核
        </div>
      )}
    </div>
  );
};

// 置信度段落列表組件
const ConfidenceSegmentList = ({ segments, theme }) => {
  if (!segments || segments.length === 0) return null;

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {segments.map((segment, index) => {
        const confidence = segment.confidence || 0;
        const colors = getConfidenceColors(confidence, theme);
        const percentage = Math.round(confidence * 100);

        return (
          <div
            key={index}
            className={`p-3 rounded-lg border ${colors.bg} ${colors.border} transition-all hover:shadow-sm`}
          >
            <div className="flex justify-between items-center mb-1">
              <span className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-400'}`}>
                [{formatTimestamp(segment.start || 0)}-{formatTimestamp(segment.end || 0)}]
              </span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${colors.badge}`}>
                {percentage}% 信心度
              </span>
            </div>
            <p className={`text-sm leading-relaxed ${theme === 'dark' ? 'text-slate-200' : 'text-slate-800'}`}>
              {segment.text}
            </p>
          </div>
        );
      })}
    </div>
  );
};

// 抽屜區塊組件
const DrawerSection = ({
  title,
  content,
  icon: Icon,
  expanded,
  setExpanded,
  show = true,
  accentColor = 'blue',
  isMarkdown = false,
  enableCopy = false,
  copyId = null,
  handleCopy = null,
  copiedSection = null,
  theme,
  // 置信度相關參數
  segments = null,
  avgConfidence = null,
  lowConfidenceCount = null
}) => {
  // 置信度視圖切換狀態
  const [showConfidenceView, setShowConfidenceView] = useState(false);
  const hasConfidenceData = segments && segments.length > 0 && segments.some(s => s.confidence !== undefined);

  if (!show || !content) return null;

  const getAccentColor = (color) => {
    switch(color) {
      case 'blue': return 'text-blue-400 bg-blue-400/10';
      case 'green': return 'text-emerald-400 bg-emerald-400/10';
      case 'purple': return 'text-purple-400 bg-purple-400/10';
      default: return 'text-brand-primary bg-brand-primary/10';
    }
  };

  return (
    <div className={`glass-card overflow-hidden transition-all duration-300 ${
      expanded
        ? theme === 'dark' ? 'ring-1 ring-white/10' : 'ring-1 ring-slate-300'
        : theme === 'dark' ? 'hover:bg-white/5' : 'hover:bg-slate-100'
    }`}>
      {/* 抽屜頭部 */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between p-5 cursor-pointer select-none"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-lg ${getAccentColor(accentColor)}`}>
            <Icon size={20} />
          </div>
          <h4 className={`font-semibold text-base ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>{title}</h4>
        </div>

        <div className="flex items-center gap-3">
          {/* 置信度視圖切換按鈕 */}
          {hasConfidenceData && expanded && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowConfidenceView(!showConfidenceView);
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                showConfidenceView
                  ? 'bg-brand-primary/20 text-brand-primary border border-brand-primary/30'
                  : theme === 'dark'
                    ? 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white'
                    : 'bg-slate-100 text-slate-600 border border-slate-300 hover:bg-slate-200 hover:text-slate-900'
              }`}
              title={showConfidenceView ? '顯示純文字' : '顯示信心度分析'}
            >
              <span>{showConfidenceView ? '純文字' : '信心度'}</span>
            </button>
          )}

          {/* 複製按鈕 */}
          {enableCopy && expanded && handleCopy && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleCopy(content, copyId);
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                copiedSection === copyId
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : theme === 'dark'
                    ? 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white'
                    : 'bg-slate-100 text-slate-600 border border-slate-300 hover:bg-slate-200 hover:text-slate-900'
              }`}
              title="複製內容"
            >
              {copiedSection === copyId ? (
                <>
                  <Check size={12} />
                  <span>已複製</span>
                </>
              ) : (
                <>
                  <Copy size={12} />
                  <span>複製</span>
                </>
              )}
            </button>
          )}

          {expanded ? (
            <ChevronDown size={18} className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'} />
          ) : (
            <ChevronRight size={18} className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'} />
          )}
        </div>
      </div>

      {/* 抽屜內容 */}
      {expanded && (
        <div className={`p-6 border-t ${
          theme === 'dark' ? 'border-white/5 bg-black/50' : 'border-slate-200 bg-slate-50/50'
        }`}>
          {isMarkdown ? (
            <div className={`prose prose-sm max-w-none ${theme === 'dark' ? 'prose-invert' : ''}`}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({node, ...props}) => <h1 className={`text-xl font-bold mb-4 mt-6 pb-2 border-b ${
                    theme === 'dark' ? 'text-white border-white/10' : 'text-slate-900 border-slate-300'
                  }`} {...props} />,
                  h2: ({node, ...props}) => <h2 className={`text-lg font-semibold mb-3 mt-5 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`} {...props} />,
                  h3: ({node, ...props}) => <h3 className={`text-base font-medium mb-2 mt-4 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`} {...props} />,
                  p: ({node, ...props}) => <p className={`leading-relaxed mb-4 ${
                    theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                  }`} {...props} />,
                  ul: ({node, ...props}) => <ul className={`list-disc pl-5 space-y-1 mb-4 ${
                    theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                  }`} {...props} />,
                  ol: ({node, ...props}) => <ol className={`list-decimal pl-5 space-y-1 mb-4 ${
                    theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                  }`} {...props} />,
                  li: ({node, ...props}) => <li className="pl-1" {...props} />,
                  blockquote: ({node, ...props}) => <blockquote className={`border-l-4 border-brand-primary/50 pl-4 py-1 my-4 bg-brand-primary/5 rounded-r italic ${
                    theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                  }`} {...props} />,
                  code: ({node, inline, ...props}) => inline
                    ? <code className={`px-1.5 py-0.5 rounded text-brand-secondary font-mono text-xs ${
                        theme === 'dark' ? 'bg-white/10' : 'bg-slate-200'
                      }`} {...props} />
                    : <code className={`block p-4 rounded-lg overflow-x-auto font-mono text-xs my-4 ${
                        theme === 'dark' ? 'bg-black/30 text-slate-300' : 'bg-slate-100 text-slate-800'
                      }`} {...props} />,
                  table: ({node, ...props}) => <div className={`overflow-x-auto my-4 rounded-lg border ${
                    theme === 'dark' ? 'border-white/10' : 'border-slate-300'
                  }`}><table className="w-full text-left text-sm border-collapse" {...props} /></div>,
                  thead: ({node, ...props}) => <thead className={`${
                    theme === 'dark' ? 'bg-white/5' : 'bg-slate-50'
                  }`} {...props} />,
                  tbody: ({node, ...props}) => <tbody {...props} />,
                  tr: ({node, ...props}) => <tr className={`${
                    theme === 'dark' ? 'hover:bg-white/5' : 'hover:bg-slate-50'
                  }`} {...props} />,
                  th: ({node, ...props}) => <th className={`p-3 font-semibold border ${
                    theme === 'dark' ? 'bg-white/10 text-white border-white/10' : 'bg-slate-100 text-slate-900 border-slate-200'
                  }`} {...props} />,
                  td: ({node, ...props}) => <td className={`p-3 border ${
                    theme === 'dark' ? 'border-white/10 text-slate-300' : 'border-slate-200 text-slate-700'
                  }`} {...props} />,
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          ) : hasConfidenceData && showConfidenceView ? (
            // 置信度視圖
            <div>
              <ConfidenceSummary
                segments={segments}
                avgConfidence={avgConfidence}
                lowConfidenceCount={lowConfidenceCount}
                theme={theme}
              />
              <ConfidenceSegmentList segments={segments} theme={theme} />
            </div>
          ) : (
            // 純文字視圖
            <div className={`whitespace-pre-wrap text-sm leading-relaxed font-mono p-5 rounded-lg border ${
              theme === 'dark' ? 'text-slate-300 bg-black/20 border-white/5' : 'text-slate-800 bg-white border-slate-200'
            }`}>
              {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// 批次摘要組件
const BatchSummarySection = ({ theme, batchInfo, expanded, setExpanded }) => {
  return (
    <div className={`glass-card mb-6 overflow-hidden ${
      theme === 'dark' ? '' : 'border-slate-300'
    }`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full flex items-center justify-between p-5 transition-colors ${
          theme === 'dark' ? 'hover:bg-white/5' : 'hover:bg-slate-100'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-blue-500/20 text-blue-400">
            <Files size={20} />
          </div>
          <h4 className={`font-semibold text-base ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>批次摘要</h4>
        </div>
        {expanded ? (
          <ChevronDown size={18} className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'} />
        ) : (
          <ChevronRight size={18} className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'} />
        )}
      </button>

      {expanded && (
        <div className={`p-6 border-t ${
          theme === 'dark' ? 'border-white/5 bg-black/20' : 'border-slate-200 bg-slate-50/50'
        }`}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 text-center">
            <div className={`p-5 rounded-xl ${
              theme === 'dark'
                ? 'bg-white/5 border border-white/5'
                : 'bg-blue-50 border-2 border-blue-200'
            }`}>
              <div className={`text-2xl font-bold mb-1 ${
                theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
              }`}>
                {batchInfo.total_files || 0}
              </div>
              <div className={`text-xs uppercase tracking-wider ${
                theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
              }`}>
                總計
              </div>
            </div>
            <div className={`p-5 rounded-xl ${
              theme === 'dark'
                ? 'bg-emerald-500/10 border border-emerald-500/20'
                : 'bg-emerald-50 border-2 border-emerald-200'
            }`}>
              <div className={`text-2xl font-bold mb-1 ${
                theme === 'dark' ? 'text-emerald-400' : 'text-emerald-600'
              }`}>
                {batchInfo.successful_files || 0}
              </div>
              <div className={`text-xs uppercase tracking-wider ${
                theme === 'dark' ? 'text-emerald-400/70' : 'text-emerald-600/70'
              }`}>
                成功
              </div>
            </div>
            <div className={`p-5 rounded-xl ${
              theme === 'dark'
                ? 'bg-red-500/10 border border-red-500/20'
                : 'bg-red-50 border-2 border-red-200'
            }`}>
              <div className={`text-2xl font-bold mb-1 ${
                theme === 'dark' ? 'text-red-400' : 'text-red-600'
              }`}>
                {batchInfo.failed_files || 0}
              </div>
              <div className={`text-xs uppercase tracking-wider ${
                theme === 'dark' ? 'text-red-400/70' : 'text-red-600/70'
              }`}>
                失敗
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// 單個檔案結果卡片組件
const FileResultCard = ({
  theme,
  fileResult,
  index,
  fileStates,
  setFileStates,
  enableLLMProcessing,
  isMultipleFiles,
  handleCopy,
  copiedSection
}) => {
  const fileState = fileStates[index] || {
    expanded: !isMultipleFiles, // 如果不是多檔案，預設展開
    whisperExpanded: false,
    aiSummaryExpanded: !isMultipleFiles // 如果不是多檔案，AI摘要預設展開
  };

  const updateFileState = (newState) => {
    setFileStates(prev => ({
      ...prev,
      [index]: { ...fileState, ...newState }
    }));
  };

  const hasError = fileResult.error;
  const fileName = fileResult.filename || `File ${index + 1}`;
  const fileSize = fileResult.file_info?.size;

  return (
    <div className={`glass-card overflow-hidden transition-all duration-300 ${
      hasError ? 'border-red-500/30 bg-red-500/5' : ''
    }`}>
      {/* 檔案標題欄 */}
      <button
        onClick={() => updateFileState({ expanded: !fileState.expanded })}
        className="w-full flex items-center justify-between p-5 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3 overflow-hidden">
          <div className={`p-2.5 rounded-lg ${hasError ? 'bg-red-500/20 text-red-400' : 'bg-white/10 text-slate-300'}`}>
            <FileText size={20} />
          </div>
          <div className="text-left min-w-0">
            <h4 className="font-semibold text-base truncate text-white">{fileName}</h4>
            {fileSize && (
              <p className="text-xs text-slate-400">
                {(fileSize / 1024 / 1024).toFixed(2)} MB
              </p>
            )}
          </div>
          {hasError && (
            <span className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/20 ml-2 whitespace-nowrap">
              失敗
            </span>
          )}
        </div>
        {fileState.expanded ? (
          <ChevronDown size={18} className="text-slate-300" />
        ) : (
          <ChevronRight size={18} className="text-slate-300" />
        )}
      </button>

      {/* 檔案內容 */}
      {fileState.expanded && (
        <div className="border-t border-white/5 bg-black/10 p-6 space-y-5">
          {hasError ? (
            <div className="p-5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-200 text-sm">
              <p className="font-medium mb-1">處理錯誤</p>
              <p className="opacity-80">{fileResult.error}</p>
            </div>
          ) : (
            <div className="space-y-5">
              {/* 語音識別結果 */}
              <DrawerSection
                title="語音識別"
                content={fileResult.transcription}
                icon={Mic}
                expanded={fileState.whisperExpanded}
                setExpanded={(expanded) => updateFileState({ whisperExpanded: expanded })}
                show={true}
                accentColor="blue"
                enableCopy={true}
                copyId={`whisper-batch-${index}`}
                handleCopy={handleCopy}
                copiedSection={copiedSection}
                theme={theme}
                segments={fileResult.segments}
                avgConfidence={fileResult.avg_confidence}
                lowConfidenceCount={fileResult.low_confidence_count}
              />

              {/* AI 智能摘要 */}
              <DrawerSection
                title="AI 智能摘要"
                content={fileResult.ai_summary}
                icon={Brain}
                expanded={fileState.aiSummaryExpanded}
                setExpanded={(expanded) => updateFileState({ aiSummaryExpanded: expanded })}
                show={enableLLMProcessing && fileResult.ai_summary}
                accentColor="green"
                isMarkdown={true}
                enableCopy={true}
                copyId={`ai-summary-batch-${index}`}
                handleCopy={handleCopy}
                copiedSection={copiedSection}
                theme={theme}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ResultDisplay;
