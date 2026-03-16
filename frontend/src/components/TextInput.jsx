import React, { useCallback, useState, useRef } from 'react';
import { FileText, Trash2, ClipboardPaste, Loader2, AlertCircle, X, Info } from 'lucide-react';
import Tooltip from './Tooltip';

const MIN_TEXT_LENGTH = 10;
const MAX_TEXT_LENGTH = 100000;

const TextInput = ({
  theme,
  textInput,
  setTextInput,
  processing,
  enableCleanFiller,
  setEnableCleanFiller,
}) => {
  const [charCount, setCharCount] = useState(0);
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  const handleTextChange = useCallback((e) => {
    const value = e.target.value;
    if (value.length > MAX_TEXT_LENGTH) {
      setError(`文字內容超過 ${MAX_TEXT_LENGTH.toLocaleString()} 字元上限`);
      setTimeout(() => setError(null), 3000);
      return;
    }
    setTextInput(value);
    setCharCount(value.length);
  }, [setTextInput]);

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        if (text.length > MAX_TEXT_LENGTH) {
          setError(`剪貼簿內容超過 ${MAX_TEXT_LENGTH.toLocaleString()} 字元上限`);
          setTimeout(() => setError(null), 3000);
          return;
        }
        setTextInput(text);
        setCharCount(text.length);
      }
    } catch {
      // Clipboard API 失敗時靜默處理
    }
  }, [setTextInput]);

  const handleClear = useCallback(() => {
    setTextInput('');
    setCharCount(0);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [setTextInput]);

  const textPrimary = theme === 'dark' ? 'text-white' : 'text-slate-900';
  const textSecondary = theme === 'dark' ? 'text-slate-300' : 'text-slate-600';
  const textMuted = theme === 'dark' ? 'text-slate-300' : 'text-slate-500';

  const isValid = charCount >= MIN_TEXT_LENGTH;
  const isLong = charCount > 50000;

  return (
    <div className={`glass-panel p-6 sm:p-8 transition-all duration-300 hover:shadow-brand-primary/10 ${
      theme === 'dark' ? '' : 'border-slate-300'
    }`}>
      <Tooltip
        content="直接貼上逐字稿或文字內容，跳過音轉文步驟，直接進行 AI 智能摘要處理。支援 10 ~ 100,000 字元。"
        theme={theme}
        position="right"
      >
        <div className={`text-lg font-medium flex items-center gap-4 cursor-help mb-5 ${textPrimary}`}>
          <div className={`p-2 sm:p-2.5 rounded-lg text-brand-primary ${
            theme === 'dark' ? 'bg-brand-primary/10' : 'bg-brand-primary/10 border border-brand-primary/20'
          }`}>
            <FileText size={18} className="sm:w-5 sm:h-5" />
          </div>
          <span className="flex items-center gap-2">
            輸入文字
            <Info size={14} className={`${theme === 'dark' ? 'text-slate-400' : 'text-slate-400'} opacity-60`} />
          </span>
        </div>
      </Tooltip>

      {/* Textarea */}
      <div className={`relative rounded-2xl border-2 transition-all duration-300 ${
        processing ? 'opacity-50 cursor-not-allowed' : ''
      } ${
        charCount > 0
          ? 'border-brand-primary/30 bg-brand-primary/5'
          : theme === 'dark' ? 'border-glass-border' : 'border-slate-300'
      }`}>
        <textarea
          ref={textareaRef}
          value={textInput}
          onChange={handleTextChange}
          disabled={processing}
          placeholder="在此貼上逐字稿或文字內容..."
          rows={12}
          className={`w-full resize-y rounded-2xl px-5 py-4 text-sm leading-relaxed bg-transparent outline-none placeholder:opacity-50 ${
            theme === 'dark'
              ? 'text-slate-200 placeholder:text-slate-500'
              : 'text-slate-800 placeholder:text-slate-400'
          }`}
          style={{ minHeight: '200px', maxHeight: '500px' }}
        />
      </div>

      {/* Action bar */}
      <div className="mt-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {/* Paste button */}
          <button
            type="button"
            onClick={handlePaste}
            disabled={processing}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
              theme === 'dark'
                ? 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white'
                : 'bg-slate-100 text-slate-600 border border-slate-300 hover:bg-slate-200 hover:text-slate-900'
            } ${processing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <ClipboardPaste size={14} />
            貼上
          </button>

          {/* Clear button */}
          {charCount > 0 && !processing && (
            <button
              type="button"
              onClick={handleClear}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                theme === 'dark'
                  ? 'bg-white/5 text-slate-300 border border-white/10 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20'
                  : 'bg-slate-100 text-slate-600 border border-slate-300 hover:bg-red-50 hover:text-red-500 hover:border-red-300'
              }`}
            >
              <Trash2 size={14} />
              清除
            </button>
          )}
        </div>

        {/* Character counter */}
        <div className={`text-xs font-mono ${
          charCount === 0
            ? textMuted
            : charCount < MIN_TEXT_LENGTH
              ? 'text-red-400'
              : isLong
                ? 'text-yellow-400'
                : 'text-emerald-400'
        }`}>
          {charCount.toLocaleString()} / {MAX_TEXT_LENGTH.toLocaleString()} 字元
        </div>
      </div>

      {/* Filler word cleanup toggle */}
      <div className={`mt-4 flex items-center justify-between p-4 rounded-xl ${
        theme === 'dark'
          ? 'bg-glass-100/50 border border-glass-border/50'
          : 'bg-slate-50/80 border-2 border-slate-300'
      }`}>
        <div>
          <div className={`text-sm font-medium ${textPrimary}`}>清理口語贅字</div>
          <div className={`text-xs mt-0.5 ${textMuted}`}>
            移除「嗯」、「啊」、「那個」等口語填充詞
          </div>
        </div>
        <button
          type="button"
          onClick={() => setEnableCleanFiller(!enableCleanFiller)}
          disabled={processing}
          className={`
            w-12 h-6 p-0 border-0 rounded-full transition-all duration-200
            relative flex-shrink-0
            ${processing ? 'opacity-50 cursor-not-allowed' : ''}
            ${enableCleanFiller
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
            ${enableCleanFiller
              ? theme === 'dark'
                ? 'left-[26px] bg-brand-primary'
                : 'left-[26px] bg-brand-primary'
              : theme === 'dark'
                ? 'left-1 bg-slate-600'
                : 'left-1 bg-slate-400'}
          `} />
        </button>
      </div>

      {/* Warnings */}
      {charCount > 0 && charCount < MIN_TEXT_LENGTH && (
        <div className={`mt-3 text-xs ${theme === 'dark' ? 'text-red-400' : 'text-red-500'}`}>
          至少需要 {MIN_TEXT_LENGTH} 個字元才能開始處理
        </div>
      )}

      {isLong && (
        <div className={`mt-3 flex items-center gap-2 text-xs ${
          theme === 'dark' ? 'text-yellow-400' : 'text-yellow-600'
        }`}>
          <AlertCircle size={14} />
          文字較長，將進入任務隊列處理
        </div>
      )}

      {/* Error */}
      {error && (
        <div className={`mt-3 p-3 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-200 ${
          theme === 'dark'
            ? 'bg-red-500/10 border border-red-500/30 text-red-400'
            : 'bg-red-50 border-2 border-red-200 text-red-600'
        }`}>
          <AlertCircle size={16} className="flex-shrink-0" />
          <span className="text-sm">{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className={`ml-auto p-1 rounded-lg transition-colors ${
              theme === 'dark' ? 'hover:bg-red-500/20' : 'hover:bg-red-100'
            }`}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Processing state */}
      {processing && (
        <div className={`mt-4 p-5 rounded-xl flex items-center gap-4 animate-pulse-slow ${
          theme === 'dark'
            ? 'bg-brand-primary/10 border border-brand-primary/20'
            : 'bg-brand-primary/5 border-2 border-brand-primary/30'
        }`}>
          <Loader2 size={22} className="animate-spin text-brand-primary" />
          <span className="text-sm font-semibold text-brand-primary">正在處理文字... 請稍候。</span>
        </div>
      )}
    </div>
  );
};

export default TextInput;
