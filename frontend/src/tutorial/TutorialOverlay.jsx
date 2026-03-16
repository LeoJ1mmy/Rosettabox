import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';

// 教學遮罩組件 - 負責暗化背景和高亮目標區域
const TutorialOverlay = ({
  isActive,
  targetElement,
  highlightStyle = {},
  onOverlayClick
}) => {
  const [highlightRect, setHighlightRect] = useState(null);

  useEffect(() => {
    // 創建新的阻止滾動函數引用，確保可以正確移除
    const preventScrollRef = (e) => {
      // 允許程序化滾動，但阻止用戶手動滾動
      if (e.isTrusted && (e.type === 'wheel' || e.type === 'touchmove')) {
        e.preventDefault();
      }
    };

    if (!isActive || !targetElement) {
      setHighlightRect(null);

      // 完全恢復頁面滾動
      document.body.style.overflow = '';
      document.body.style.overflowY = '';
      document.body.style.overflowX = '';
      document.documentElement.style.overflow = '';

      // 移除所有滾動阻止事件監聽器
      const allElements = [document, document.body, document.documentElement, window];
      allElements.forEach(element => {
        try {
          element.removeEventListener('wheel', preventScrollRef);
          element.removeEventListener('touchmove', preventScrollRef);
        } catch (e) {
          // 忽略移除失敗的錯誤
        }
      });

      return;
    }

    // 暫時啟用滾動以支持自動滾動功能
    document.body.style.overflowY = 'auto';
    document.body.style.overflowX = 'visible';

    // 添加滾動阻止事件監聽器
    document.addEventListener('wheel', preventScrollRef, { passive: false });
    document.addEventListener('touchmove', preventScrollRef, { passive: false });

    const updateHighlight = () => {
      // 添加重試邏輯
      let element = document.querySelector(targetElement);

      // 如果第一次找不到，嘗試延遲查找
      if (!element && targetElement) {
        setTimeout(() => {
          element = document.querySelector(targetElement);
          if (element) {
            updateHighlight();
          }
        }, 100);
        return;
      }

      if (element) {
        // 智能選擇最適合的高亮目標 - 改進版
        let targetRect = element;
        let selectedElement = element;

        // 優先級1: 查找具有 data-tutorial 屬性的元素（向上搜索）
        let currentElement = element;
        let tutorialElement = null;
        let searchDepth = 0;
        const maxDepth = 8;

        while (currentElement && searchDepth < maxDepth) {
          if (currentElement.getAttribute && currentElement.getAttribute('data-tutorial')) {
            tutorialElement = currentElement;
            break;
          }
          currentElement = currentElement.parentElement;
          searchDepth++;
        }

        if (tutorialElement) {
          selectedElement = tutorialElement;
        } else {
          // 優先級2: 查找最適合的視覺容器
          currentElement = element;
          searchDepth = 0;

          while (currentElement.parentElement && searchDepth < maxDepth) {
            const parent = currentElement.parentElement;
            const parentStyle = window.getComputedStyle(parent);

            // 檢查元素尺寸和視覺特徵
            const parentRect = parent.getBoundingClientRect();
            const isReasonableSize = parentRect.width >= 100 && parentRect.height >= 30;

            // 更全面的視覺邊界檢測
            const hasVisualBoundary = (
              // 邊框檢測
              parentStyle.borderWidth !== '0px' ||
              parentStyle.border !== 'none' ||
              parentStyle.border !== '0px none rgba(0, 0, 0, 0)' ||
              // 背景色檢測
              parentStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
              parentStyle.backgroundColor !== 'transparent' ||
              // 陰影效果
              parentStyle.boxShadow !== 'none' ||
              // 內邊距檢測
              parseInt(parentStyle.paddingTop) > 8 ||
              parseInt(parentStyle.paddingLeft) > 8 ||
              parseInt(parentStyle.paddingRight) > 8 ||
              parseInt(parentStyle.paddingBottom) > 8 ||
              // Tailwind CSS 類檢測
              parent.classList.contains('border') ||
              parent.classList.contains('border-2') ||
              parent.classList.contains('border-dashed') ||
              parent.classList.contains('bg-white') ||
              parent.classList.contains('bg-gray-50') ||
              parent.classList.contains('bg-gray-100') ||
              parent.classList.contains('bg-gray-200') ||
              parent.classList.contains('p-4') ||
              parent.classList.contains('p-6') ||
              parent.classList.contains('p-8') ||
              parent.classList.contains('rounded') ||
              parent.classList.contains('shadow') ||
              parent.classList.contains('shadow-lg') ||
              parent.classList.contains('shadow-xl') ||
              // 特定UI組件類
              parent.classList.contains('container') ||
              parent.classList.contains('section') ||
              parent.classList.contains('card') ||
              parent.classList.contains('panel') ||
              parent.classList.contains('form') ||
              parent.classList.contains('upload')
            );

            if (hasVisualBoundary && isReasonableSize) {
              selectedElement = parent;
              break;
            }

            currentElement = parent;
            searchDepth++;

            // 防止選擇過大容器
            if (parent.tagName === 'BODY' || parent.tagName === 'HTML' || parent.tagName === 'MAIN' || parent.id === 'root') {
              break;
            }
          }
        }

        targetRect = selectedElement;

        const rect = targetRect.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

        const padding = parseInt(highlightStyle.padding) || 12; // 增加默認padding
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        // 計算元素在文檔中的絕對位置
        const elementLeft = rect.left + scrollLeft;
        const elementTop = rect.top + scrollTop;
        const elementWidth = rect.width;
        const elementHeight = rect.height;

        // 計算高亮區域 - 確保完全包含目標元素
        const highlightLeft = elementLeft - padding;
        const highlightTop = elementTop - padding;
        const highlightWidth = elementWidth + (padding * 2);
        const highlightHeight = elementHeight + (padding * 2);

        // 邊界保護 - 確保高亮區域在視窗內可見
        const minLeft = Math.max(0, highlightLeft);
        const minTop = Math.max(0, highlightTop);
        const maxRight = Math.min(minLeft + highlightWidth, viewportWidth);
        const maxBottom = Math.min(minTop + highlightHeight, viewportHeight + scrollTop);

        const finalWidth = Math.max(50, maxRight - minLeft); // 確保最小寬度
        const finalHeight = Math.max(30, maxBottom - minTop); // 確保最小高度

        const highlightData = {
          top: minTop,
          left: minLeft,
          width: finalWidth,
          height: finalHeight,
          borderRadius: highlightStyle.borderRadius || '12px'
        };

        setHighlightRect(highlightData);
      } else {
        setHighlightRect(null);
      }
    };

    // 初始計算，延遲以確保DOM穩定
    setTimeout(updateHighlight, 100);

    // 監聽視窗大小變化和滾動，但使用節流避免過度頻繁更新
    let scrollTimeout;
    const throttledUpdateHighlight = () => {
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(updateHighlight, 100);
    };

    window.addEventListener('resize', updateHighlight);
    window.addEventListener('scroll', throttledUpdateHighlight);

    return () => {
      // 清理高亮相關的事件監聽器
      window.removeEventListener('resize', updateHighlight);
      window.removeEventListener('scroll', throttledUpdateHighlight);
      clearTimeout(scrollTimeout);

      // 移除滾動阻止事件監聽器
      try {
        document.removeEventListener('wheel', preventScrollRef);
        document.removeEventListener('touchmove', preventScrollRef);
      } catch (e) {
        // Ignore cleanup errors
      }

      // 強制恢復頁面滾動
      document.body.style.overflow = '';
      document.body.style.overflowY = '';
      document.body.style.overflowX = '';
      document.documentElement.style.overflow = '';
    };
  }, [isActive, targetElement, highlightStyle]);

  if (!isActive) return null;

  // 遮罩樣式
  const overlayStyle = {
    position: 'absolute',
    backgroundColor: 'rgba(0, 0, 0, 0.6)', // 稍微降低不透明度以配合模糊
    backdropFilter: 'blur(4px)', // 添加背景模糊
    cursor: 'pointer',
    transition: 'all 0.3s ease'
  };

  return (
    <div
      className="tutorial-overlay"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 9999,
        pointerEvents: 'auto'
      }}
    >
      {/* 明顯的關閉按鈕 */}
      <button
        onClick={onOverlayClick}
        className="fixed top-6 right-6 p-3 bg-red-500/20 hover:bg-red-500/40 text-red-400 border border-red-500/30 rounded-full flex items-center justify-center shadow-lg backdrop-blur-md transition-all duration-200 hover:scale-110 z-[10001] group"
        title="關閉教學"
      >
        <X className="w-6 h-6 group-hover:text-red-200 transition-colors" />
      </button>

      {highlightRect ? (
        <>
          {/* 四個遮罩區域來圍繞高亮區域 */}
          {/* 上方遮罩 */}
          <div
            onClick={onOverlayClick}
            style={{
              ...overlayStyle,
              top: 0,
              left: 0,
              right: 0,
              height: Math.max(0, highlightRect.top),
            }}
          />

          {/* 下方遮罩 */}
          <div
            onClick={onOverlayClick}
            style={{
              ...overlayStyle,
              top: highlightRect.top + highlightRect.height,
              left: 0,
              right: 0,
              bottom: 0,
            }}
          />

          {/* 左側遮罩 */}
          <div
            onClick={onOverlayClick}
            style={{
              ...overlayStyle,
              top: highlightRect.top,
              left: 0,
              width: Math.max(0, highlightRect.left),
              height: highlightRect.height,
            }}
          />

          {/* 右側遮罩 */}
          <div
            onClick={onOverlayClick}
            style={{
              ...overlayStyle,
              top: highlightRect.top,
              left: highlightRect.left + highlightRect.width,
              right: 0,
              height: highlightRect.height,
            }}
          />

          {/* 高亮邊框 */}
          <div
            className="tutorial-highlight"
            style={{
              position: 'absolute',
              top: highlightRect.top,
              left: highlightRect.left,
              width: highlightRect.width,
              height: highlightRect.height,
              borderRadius: highlightRect.borderRadius,
              boxShadow: `
                0 0 0 2px rgba(255, 255, 255, 0.1),
                0 0 0 4px rgba(56, 189, 248, 0.3),
                0 0 20px rgba(56, 189, 248, 0.2),
                inset 0 0 20px rgba(56, 189, 248, 0.1)
              `,
              border: '2px solid rgba(56, 189, 248, 0.6)', // brand-primary color
              backgroundColor: 'rgba(56, 189, 248, 0.05)',
              pointerEvents: 'none',
              animation: 'tutorial-pulse 3s infinite',
              zIndex: 10000
            }}
          />

          {/* 內部指示器 - 簡化為角落標記或更微妙的效果 */}
          <div
            style={{
              position: 'absolute',
              top: highlightRect.top - 4,
              left: highlightRect.left - 4,
              width: highlightRect.width + 8,
              height: highlightRect.height + 8,
              borderRadius: `calc(${highlightRect.borderRadius} + 4px)`,
              border: '1px dashed rgba(255, 255, 255, 0.3)',
              pointerEvents: 'none',
              zIndex: 10000,
              opacity: 0.6
            }}
          />
        </>
      ) : (
        // 沒有高亮區域時，整個螢幕遮罩
        <div
          onClick={onOverlayClick}
          style={{
            ...overlayStyle,
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
          }}
        />
      )}

      {/* CSS動畫定義 */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes tutorial-pulse {
          0% {
            box-shadow:
              0 0 0 2px rgba(255, 255, 255, 0.1),
              0 0 0 4px rgba(56, 189, 248, 0.3),
              0 0 20px rgba(56, 189, 248, 0.2);
            border-color: rgba(56, 189, 248, 0.6);
          }
          50% {
            box-shadow:
              0 0 0 3px rgba(255, 255, 255, 0.2),
              0 0 0 6px rgba(56, 189, 248, 0.5),
              0 0 30px rgba(56, 189, 248, 0.4);
            border-color: rgba(56, 189, 248, 0.9);
          }
          100% {
            box-shadow:
              0 0 0 2px rgba(255, 255, 255, 0.1),
              0 0 0 4px rgba(56, 189, 248, 0.3),
              0 0 20px rgba(56, 189, 248, 0.2);
            border-color: rgba(56, 189, 248, 0.6);
          }
        }

        .tutorial-overlay {
          animation: tutorial-fade-in 0.4s ease-out;
        }

        @keyframes tutorial-fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .tutorial-highlight {
          animation: tutorial-highlight-in 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes tutorial-highlight-in {
          from {
            opacity: 0;
            transform: scale(0.95);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}} />
    </div>
  );
};

export default TutorialOverlay;
