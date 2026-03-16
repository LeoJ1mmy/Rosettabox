import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Info, X } from 'lucide-react';

/**
 * 可重用的 Tooltip 組件
 * 桌面版：滑鼠懸停顯示（使用 absolute 定位）
 * 手機版：點擊顯示，固定在螢幕底部
 */
const Tooltip = ({ children, content, theme = 'dark', position = 'top' }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const containerRef = useRef(null);
  const tooltipRef = useRef(null);

  // 檢測是否為手機版
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768 || 'ontouchstart' in window);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 點擊外部關閉 tooltip
  useEffect(() => {
    if (!isVisible) return;

    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target) &&
          tooltipRef.current && !tooltipRef.current.contains(event.target)) {
        setIsVisible(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isVisible]);

  const handleMouseEnter = useCallback(() => {
    if (!isMobile) setIsVisible(true);
  }, [isMobile]);

  const handleMouseLeave = useCallback(() => {
    if (!isMobile) setIsVisible(false);
  }, [isMobile]);

  // 手機版點擊觸發
  const handleClick = useCallback((e) => {
    if (isMobile) {
      e.preventDefault();
      e.stopPropagation();
      setIsVisible(!isVisible);
    }
  }, [isMobile, isVisible]);

  // 根據 position 計算 absolute 定位的 className
  const getPositionClass = () => {
    switch (position) {
      case 'bottom':
        return 'top-full mt-2 left-0';
      case 'left':
        return 'right-full mr-2 top-1/2 -translate-y-1/2';
      case 'right':
        return 'left-full ml-2 top-1/2 -translate-y-1/2';
      case 'top':
      default:
        return 'bottom-full mb-2 left-0';
    }
  };

  return (
    <div
      ref={containerRef}
      className="relative inline-flex items-center"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    >
      {children}

      {/* Tooltip */}
      {isVisible && (
        <>
          {/* 手機版背景遮罩 */}
          {isMobile && (
            <div
              className="fixed inset-0 bg-black/30 z-[9998]"
              onClick={(e) => {
                e.stopPropagation();
                setIsVisible(false);
              }}
            />
          )}

          {/* Tooltip 內容 */}
          <div
            ref={tooltipRef}
            className={`
              z-[9999]
              px-4 py-3 rounded-xl text-sm leading-relaxed
              pointer-events-auto
              animate-in fade-in zoom-in-95 duration-200
              ${isMobile
                ? 'fixed left-4 right-4 bottom-20'
                : `absolute ${getPositionClass()} w-72 max-w-[calc(100vw-2rem)]`
              }
              ${theme === 'dark'
                ? 'bg-slate-800 text-slate-200 border border-slate-600 shadow-xl shadow-black/30'
                : 'bg-white text-slate-700 border border-slate-200 shadow-lg shadow-slate-200/50'
              }
            `}
          >
            <div className="flex items-start gap-3">
              <Info size={16} className={`flex-shrink-0 mt-0.5 ${theme === 'dark' ? 'text-brand-secondary' : 'text-brand-primary'}`} />
              <span className="flex-1">{content}</span>

              {/* 手機版關閉按鈕 */}
              {isMobile && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsVisible(false);
                  }}
                  className={`
                    flex-shrink-0 p-1 rounded-full transition-colors
                    ${theme === 'dark'
                      ? 'hover:bg-slate-700 text-slate-300'
                      : 'hover:bg-slate-100 text-slate-500'
                    }
                  `}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Tooltip;
