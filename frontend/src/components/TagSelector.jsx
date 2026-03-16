import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Tag, Check, Info, X } from 'lucide-react';

const TagSelector = ({
  theme,
  selectedTags,
  onTagsChange,
  processingMode,
  customPrompt,
  onCustomPromptChange
}) => {
  const [availableTags, setAvailableTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTooltip, setActiveTooltip] = useState(null);
  const [isMobile, setIsMobile] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const triggerRefs = useRef({});
  const tooltipRef = useRef(null);

  // 檢測手機版
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768 || 'ontouchstart' in window);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 計算 tooltip 位置
  const calculatePosition = useCallback((tagId) => {
    const triggerEl = triggerRefs.current[tagId];
    if (!triggerEl || isMobile) return;
    const rect = triggerEl.getBoundingClientRect();
    const tooltipWidth = 256;
    const tooltipHeight = 80;
    const margin = 8;
    // 顯示在元素上方
    let top = rect.top - tooltipHeight - margin;
    let left = rect.left + rect.width / 2 - tooltipWidth / 2;
    // 如果上方空間不足，顯示在下方
    if (top < 16) {
      top = rect.bottom + margin;
    }
    // 確保不超出邊界
    left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16));
    setTooltipPosition({ top, left });
  }, [isMobile]);

  // 當 tooltip 顯示時計算位置
  useEffect(() => {
    if (activeTooltip && !isMobile) {
      calculatePosition(activeTooltip);
    }
  }, [activeTooltip, isMobile, calculatePosition]);

  // 點擊外部關閉 tooltip
  useEffect(() => {
    if (!activeTooltip) return;
    const handleClickOutside = (e) => {
      const triggerEl = triggerRefs.current[activeTooltip];
      if (triggerEl && !triggerEl.contains(e.target) &&
        tooltipRef.current && !tooltipRef.current.contains(e.target)) {
        setActiveTooltip(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [activeTooltip]);

  // Theme-aware colors
  const tagTitleColor = theme === 'dark' ? 'text-white' : 'text-slate-900';
  const tagTitleHoverColor = theme === 'dark' ? 'group-hover:text-white' : 'group-hover:text-slate-900';
  const tagDescColor = theme === 'dark' ? 'text-slate-300' : 'text-slate-700';
  const tagDescHoverColor = theme === 'dark' ? 'group-hover:text-slate-200' : 'group-hover:text-slate-800';
  const tagBgInactive = theme === 'dark' ? 'bg-glass-100' : 'bg-white/80';
  const tagBgHover = theme === 'dark' ? 'hover:bg-glass-200' : 'hover:bg-slate-100';
  const tagBorderInactive = theme === 'dark' ? 'border-glass-border' : 'border-slate-300';
  const tagBorderHover = theme === 'dark' ? 'hover:border-white/30' : 'hover:border-slate-400';

  const loadAvailableTags = useCallback(async () => {
    try {
      const response = await fetch('/api/text/tags');
      if (response.ok) {
        const data = await response.json();
        setAvailableTags(data.data.tags || []);
      } else {
        setError('無法載入標籤');
      }
    } catch (err) {
      setError('載入標籤時發生錯誤');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleTagToggle = (tagId) => {
    // 如果選擇 custom，清除其他標籤
    if (tagId === 'custom') {
      if (selectedTags.includes('custom')) {
        onTagsChange([]);
      } else {
        onTagsChange(['custom']);
      }
      return;
    }

    // 如果已選擇 custom，先清除
    const currentTags = selectedTags.filter(id => id !== 'custom');

    const newSelectedTags = currentTags.includes(tagId)
      ? currentTags.filter(id => id !== tagId)
      : [...currentTags, tagId];
    onTagsChange(newSelectedTags);
  };

  const clearAllTags = () => {
    onTagsChange([]);
  };

  const handleTooltipToggle = (e, tagId) => {
    e.preventDefault();
    e.stopPropagation();
    setActiveTooltip(activeTooltip === tagId ? null : tagId);
  };

  useEffect(() => {
    loadAvailableTags();
  }, [loadAvailableTags]);

  if (loading) {
    return (
      <div className={`glass-panel p-6 flex justify-center ${theme === 'dark' ? '' : 'border-slate-300'}`}>
        <div className={`text-sm animate-pulse ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>載入標籤中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`glass-panel p-6 ${theme === 'dark'
          ? 'border-red-500/30 bg-red-500/5'
          : 'border-2 border-red-400 bg-red-50'
        }`}>
        <div className={`text-sm ${theme === 'dark' ? 'text-red-400' : 'text-red-600'}`}>{error}</div>
      </div>
    );
  }

  const isTagSelected = (tagId) => selectedTags.includes(tagId);

  // 標籤功能詳細介紹
  const tagTooltips = {
    'bulleted_list': '將內容整理成清晰的項目符號列表，方便快速瀏覽重點。適合需要快速掌握要點的場景。',
    'summary': '將內容整理成連貫的摘要文章，使用標題分段，保持閱讀流暢性。適合需要完整概述的場景。',
    'meeting_notes': '整理成完整的會議記錄格式，包含：會議摘要、討論議題、決策事項、待辦事項清單（含負責人和期限）。',
    'detailed_analysis': '深入分析每個論點，提供背景說明和影響評估。適合需要深度理解內容的場景。',
    'custom': '使用您自定義的指令來處理內容，完全由您掌控輸出格式和重點。'
  };

  return (
    <div className={`glass-panel overflow-hidden ${theme === 'dark' ? '' : 'border-slate-300'}`}>
      {/* Header */}
      <div className={`px-8 py-5 border-b ${theme === 'dark'
          ? 'border-white/10 bg-white/5'
          : 'border-slate-300 bg-slate-50/80'
        }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-2 sm:p-2.5 rounded-lg text-brand-primary ${theme === 'dark' ? 'bg-brand-primary/10' : 'bg-brand-primary/10 border border-brand-primary/20'}`}>
              <Tag size={18} className="sm:w-5 sm:h-5" />
            </div>
            <span className={`text-lg font-medium ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              輸出格式
              {selectedTags.length > 0 && <span className={`ml-2 text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>({selectedTags.length} 已選)</span>}
            </span>
          </div>
          {selectedTags.length > 0 && (
            <button
              type="button"
              onClick={clearAllTags}
              className={`text-sm px-3 py-1.5 rounded-lg transition-all ${theme === 'dark'
                  ? 'text-slate-300 hover:text-white hover:bg-white/5'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
            >
              清除
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-8 py-6">
        {/* Custom Prompt */}
        {selectedTags.includes('custom') && (
          <div className="mb-6 animate-in fade-in slide-in-from-top-2">
            <label className={`text-sm font-semibold mb-3 block ${theme === 'dark' ? 'text-brand-secondary' : 'text-brand-primary'
              }`}>
              自定義指令
            </label>
            <textarea
              value={customPrompt || ''}
              onChange={(e) => onCustomPromptChange && onCustomPromptChange(e.target.value)}
              placeholder="請輸入您的自定義處理指令..."
              rows={4}
              className="glass-input w-full resize-none text-sm leading-relaxed"
            />
          </div>
        )}

        {/* Tags Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {availableTags.map((tag) => {
            const isSelected = isTagSelected(tag.id);

            return (
              <div
                key={tag.id}
                ref={(el) => { triggerRefs.current[tag.id] = el; }}
                className="relative"
                onMouseEnter={() => !isMobile && setActiveTooltip(tag.id)}
                onMouseLeave={() => !isMobile && setActiveTooltip(null)}
              >
                {/* Tag card - 使用 div + onClick 避免 button 嵌套 */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => handleTagToggle(tag.id)}
                  onKeyDown={(e) => e.key === 'Enter' && handleTagToggle(tag.id)}
                  className={`w-full relative text-sm px-5 py-4 rounded-xl border transition-all duration-300 text-left h-[90px] flex items-center overflow-hidden cursor-pointer ${tagBgInactive} ${tagBgHover}`}
                  style={{
                    borderColor: isSelected
                      ? '#3b82f6'
                      : (theme === 'dark' ? '#ffffff' : '#cbd5e1')
                  }}
                >
                  {/* Tag content */}
                  <div className="flex-1 pr-6">
                    <div className={`font-semibold leading-relaxed flex items-center gap-2.5 mb-1 transition-colors ${tagTitleColor} ${tagTitleHoverColor}`}>
                      <span className="text-xl">{tag.icon}</span>
                      <span>{tag.name}</span>
                    </div>
                    <div className={`text-xs leading-relaxed transition-colors ${tagDescColor} ${tagDescHoverColor}`}>
                      {tag.description}
                    </div>
                  </div>

                  {/* Info button */}
                  <button
                    type="button"
                    onClick={(e) => handleTooltipToggle(e, tag.id)}
                    className={`absolute top-3 right-3 p-1 rounded-full transition-all z-10
                      ${theme === 'dark'
                        ? 'text-slate-400 hover:text-slate-300 hover:bg-white/10'
                        : 'text-slate-400 hover:text-slate-600 hover:bg-slate-200/50'
                      }
                    `}
                  >
                    <Info size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Tooltip - 使用 fixed 定位，渲染在 grid 外部確保不被裁切 */}
        {activeTooltip && (
          <>
            {isMobile && (
              <div
                className="fixed inset-0 bg-black/30 z-[9998]"
                onClick={() => setActiveTooltip(null)}
              />
            )}
            <div
              ref={tooltipRef}
              className={`
                fixed z-[9999]
                px-4 py-3 rounded-xl text-sm leading-relaxed
                pointer-events-auto
                ${theme === 'dark'
                  ? 'bg-slate-800 text-slate-200 border border-slate-600 shadow-xl shadow-black/30'
                  : 'bg-white text-slate-700 border border-slate-200 shadow-lg shadow-slate-200/50'
                }
              `}
              style={isMobile
                ? { left: 16, right: 16, bottom: 80, width: 'auto' }
                : { top: tooltipPosition.top, left: tooltipPosition.left, width: 256 }
              }
            >
              <div className="flex items-start gap-3">
                <Info size={16} className={`flex-shrink-0 mt-0.5 ${theme === 'dark' ? 'text-brand-secondary' : 'text-brand-primary'}`} />
                <span className="flex-1">{tagTooltips[activeTooltip] || availableTags.find(t => t.id === activeTooltip)?.description}</span>
                {isMobile && (
                  <button
                    type="button"
                    onClick={() => setActiveTooltip(null)}
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
    </div>
  );
};

export default TagSelector;
