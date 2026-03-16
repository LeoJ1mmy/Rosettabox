import React, { useEffect, useState } from 'react';
import { X, ChevronLeft, ChevronRight, Check } from 'lucide-react';

// 教學引導組件 - 顯示教學內容和控制按鈕
const TutorialGuide = ({
  step,
  totalSteps,
  onNext,
  onPrev,
  onSkip,
  onFinish,
  theme = 'light'
}) => {
  const [position, setPosition] = useState({ top: '50%', left: '50%' });
  const [arrowDirection, setArrowDirection] = useState('bottom');

  useEffect(() => {
    if (!step || !step.target) {
      // 無目標時顯示在中央
      setPosition({ top: '50%', left: '50%' });
      setArrowDirection('none');
      return;
    }

    const calculatePosition = () => {
      const element = document.querySelector(step.target);
      if (!element) return;

      const rect = element.getBoundingClientRect();
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const guideWidth = Math.min(350, viewportWidth - 40);
      const guideHeight = 280; // 增加高度以適應更多內容

      // 計算元素在視窗中的位置
      const elementCenterX = rect.left + rect.width / 2;
      const elementCenterY = rect.top + rect.height / 2;

      let newPosition = {};
      let direction = step.position || 'bottom';

      // 智能位置調整 - 檢查所有方向的可用空間
      const spaceTop = rect.top;
      const spaceBottom = viewportHeight - rect.bottom;
      const spaceLeft = rect.left;
      const spaceRight = viewportWidth - rect.right;

      // 根據可用空間調整位置
      if (direction === 'bottom' && spaceBottom < guideHeight + 40) {
        if (spaceTop > guideHeight + 40) {
          direction = 'top';
        } else if (spaceRight > guideWidth + 40) {
          direction = 'right';
        } else if (spaceLeft > guideWidth + 40) {
          direction = 'left';
        } else {
          direction = 'center'; // 所有位置都不夠，使用中央
        }
      } else if (direction === 'top' && spaceTop < guideHeight + 40) {
        if (spaceBottom > guideHeight + 40) {
          direction = 'bottom';
        } else if (spaceRight > guideWidth + 40) {
          direction = 'right';
        } else if (spaceLeft > guideWidth + 40) {
          direction = 'left';
        } else {
          direction = 'center';
        }
      }

      switch (direction) {
        case 'top':
          newPosition = {
            top: rect.top + scrollTop - guideHeight - 10,
            left: elementCenterX + scrollLeft - guideWidth / 2
          };
          setArrowDirection('bottom');
          break;
        case 'bottom':
          newPosition = {
            top: rect.bottom + scrollTop + 10,
            left: elementCenterX + scrollLeft - guideWidth / 2
          };
          setArrowDirection('top');
          break;
        case 'left':
          newPosition = {
            top: elementCenterY + scrollTop - guideHeight / 2,
            left: rect.left + scrollLeft - guideWidth - 10
          };
          setArrowDirection('right');
          break;
        case 'right':
          newPosition = {
            top: elementCenterY + scrollTop - guideHeight / 2,
            left: rect.right + scrollLeft + 10
          };
          setArrowDirection('left');
          break;
        case 'center':
        default:
          newPosition = {
            top: scrollTop + viewportHeight / 2 - guideHeight / 2,
            left: viewportWidth / 2 - guideWidth / 2
          };
          setArrowDirection('none');
          break;
      }

      // 智能邊界檢查 - 保持緊貼目標元素，但確保可見性
      const safeMargin = 5; // 更小的安全邊距

      // 水平位置檢查和微調
      if (newPosition.left !== undefined && typeof newPosition.left === 'number') {
        // 檢查是否超出左邊界
        if (newPosition.left < safeMargin) {
          newPosition.left = safeMargin;
        }
        // 檢查是否超出右邊界
        else if (newPosition.left + guideWidth > viewportWidth - safeMargin) {
          newPosition.left = viewportWidth - guideWidth - safeMargin;
        }
      }

      // 垂直位置檢查和微調
      if (newPosition.top !== undefined && typeof newPosition.top === 'number') {
        // 檢查是否超出上邊界
        if (newPosition.top < scrollTop + safeMargin) {
          newPosition.top = scrollTop + safeMargin;
        }
        // 檢查是否超出下邊界
        else if (newPosition.top + guideHeight > scrollTop + viewportHeight - safeMargin) {
          newPosition.top = scrollTop + viewportHeight - guideHeight - safeMargin;
        }
      }

      setPosition(newPosition);
    };

    // 延遲初始計算，確保DOM穩定
    const timeoutId = setTimeout(calculatePosition, 200);

    // 節流的重新計算函數
    let resizeTimeout;
    let scrollTimeout;

    const throttledCalculatePosition = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(calculatePosition, 150);
    };

    const throttledScrollCalculatePosition = () => {
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(calculatePosition, 100);
    };

    window.addEventListener('resize', throttledCalculatePosition);
    window.addEventListener('scroll', throttledScrollCalculatePosition);

    return () => {
      clearTimeout(timeoutId);
      clearTimeout(resizeTimeout);
      clearTimeout(scrollTimeout);
      window.removeEventListener('resize', throttledCalculatePosition);
      window.removeEventListener('scroll', throttledScrollCalculatePosition);
    };
  }, [step]);

  if (!step) return null;

  // 計算樣式 - 使用絕對定位相對於文檔，確保緊貼目標元素
  const guideStyle = {
    position: 'absolute',
    zIndex: 10000,
    maxWidth: `${Math.min(350, window.innerWidth - 40)}px`,
    minWidth: `${Math.min(300, window.innerWidth - 60)}px`,
    width: `${Math.min(350, window.innerWidth - 40)}px`,
    transform: position.top === '50%' ? 'translate(-50%, -50%)' : 'none',
    top: typeof position.top === 'number' ? `${position.top}px` : position.top,
    left: typeof position.left === 'number' ? `${position.left}px` : position.left,
    // 確保教學框不會被其他元素遮蓋
    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
    // 強制顯示在最頂層
    opacity: 1,
    visibility: 'visible'
  };

  return (
    <div
      className="glass-panel p-6 shadow-2xl border border-white/20 backdrop-blur-xl animate-in zoom-in-95 duration-300"
      style={guideStyle}
    >
      {/* 箭頭 */}
      {arrowDirection !== 'none' && (
        <div className={`tutorial-arrow tutorial-arrow-${arrowDirection}`}>
          <div className="arrow-outer border-white/20"></div>
          <div className="arrow-inner bg-black/60 backdrop-blur-xl"></div>
        </div>
      )}

      {/* 步驟指示器和關閉按鈕 */}
      <div className="flex justify-between items-center mb-4">
        <div className="text-xs font-medium text-brand-secondary uppercase tracking-wider">
          步驟 {step.id} / {totalSteps}
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex space-x-1">
            {Array.from({ length: totalSteps }, (_, index) => (
              <div
                key={index}
                className={`w-1.5 h-1.5 rounded-full transition-colors duration-300 ${
                  index < step.id ? 'bg-brand-primary' : 'bg-white/10'
                }`}
              />
            ))}
          </div>
          {/* 關閉按鈕 */}
          <button
            onClick={onSkip}
            className="text-slate-300 hover:text-white transition-colors"
            title="關閉教學"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* 標題 */}
      <h3 className="text-lg font-display font-bold mb-3 text-white">{step.title}</h3>

      {/* 內容 */}
      <p className="mb-6 text-sm leading-relaxed text-slate-300">
        {step.content}
      </p>

      {/* 按鈕區域 */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0">
        <div className="flex space-x-2 order-2 sm:order-1">
          {step.id > 1 && (
            <button
              onClick={onPrev}
              className="glass-button px-3 py-1.5 text-xs flex items-center gap-1 text-slate-300 hover:text-white"
            >
              <ChevronLeft size={14} />
              上一步
            </button>
          )}
          <button
            onClick={onSkip}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors px-2"
          >
            跳過教學
          </button>
        </div>

        <div className="order-1 sm:order-2">
          {step.isFinish ? (
            <button
              onClick={onFinish}
              className="glass-button bg-emerald-500/20 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/30 px-4 py-2 text-sm font-medium flex items-center gap-2"
            >
              <Check size={16} />
              完成教學
            </button>
          ) : (
            <button
              onClick={onNext}
              className="glass-button bg-brand-primary/20 border-brand-primary/30 text-brand-primary hover:bg-brand-primary/30 px-4 py-2 text-sm font-medium flex items-center gap-2"
            >
              下一步
              <ChevronRight size={16} />
            </button>
          )}
        </div>
      </div>

      {/* CSS 樣式 */}
      <style dangerouslySetInnerHTML={{__html: `
        .tutorial-arrow {
          position: absolute;
          pointer-events: none;
        }

        .tutorial-arrow-top {
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%);
        }

        .tutorial-arrow-bottom {
          top: 100%;
          left: 50%;
          transform: translateX(-50%);
        }

        .tutorial-arrow-left {
          right: 100%;
          top: 50%;
          transform: translateY(-50%);
        }

        .tutorial-arrow-right {
          left: 100%;
          top: 50%;
          transform: translateY(-50%);
        }

        .arrow-outer, .arrow-inner {
          position: absolute;
          width: 0;
          height: 0;
        }

        .tutorial-arrow-top .arrow-outer {
          border-left: 12px solid transparent;
          border-right: 12px solid transparent;
          border-bottom: 12px solid rgba(255, 255, 255, 0.2);
        }

        .tutorial-arrow-top .arrow-inner {
          border-left: 10px solid transparent;
          border-right: 10px solid transparent;
          border-bottom: 10px solid rgba(0, 0, 0, 0.6);
          top: 2px;
          left: -10px;
        }

        .tutorial-arrow-bottom .arrow-outer {
          border-left: 12px solid transparent;
          border-right: 12px solid transparent;
          border-top: 12px solid rgba(255, 255, 255, 0.2);
        }

        .tutorial-arrow-bottom .arrow-inner {
          border-left: 10px solid transparent;
          border-right: 10px solid transparent;
          border-top: 10px solid rgba(0, 0, 0, 0.6);
          top: -12px;
          left: -10px;
        }

        .tutorial-arrow-left .arrow-outer {
          border-top: 12px solid transparent;
          border-bottom: 12px solid transparent;
          border-right: 12px solid rgba(255, 255, 255, 0.2);
        }

        .tutorial-arrow-left .arrow-inner {
          border-top: 10px solid transparent;
          border-bottom: 10px solid transparent;
          border-right: 10px solid rgba(0, 0, 0, 0.6);
          top: -10px;
          left: 2px;
        }

        .tutorial-arrow-right .arrow-outer {
          border-top: 12px solid transparent;
          border-bottom: 12px solid transparent;
          border-left: 12px solid rgba(255, 255, 255, 0.2);
        }

        .tutorial-arrow-right .arrow-inner {
          border-top: 10px solid transparent;
          border-bottom: 10px solid transparent;
          border-left: 10px solid rgba(255, 255, 255, 0.6);
          top: -10px;
          left: -12px;
        }
      `}} />
    </div>
  );
};

export default TutorialGuide;
