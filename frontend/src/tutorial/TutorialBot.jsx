import React, { useState, useEffect } from 'react';
import { tutorialMessages, botMenuOptions } from './tutorialData';
import { MessageSquare, PlayCircle, Bug } from 'lucide-react';

// 教學精靈組件 - 擴展原有FeedbackBot功能，新增教學選項菜單
const TutorialBot = ({ onOpenFeedback, onStartTutorial, theme }) => {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [buttonPosition, setButtonPosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const [showBubble, setShowBubble] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const [isTalking, setIsTalking] = useState(false);
  const [bubblePosition, setBubblePosition] = useState('bottom-16'); // 動態調整對話框位置

  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };

    const updateButtonPosition = () => {
      const button = document.getElementById('tutorial-bot');
      if (button) {
        const rect = button.getBoundingClientRect();
        setButtonPosition({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('resize', updateButtonPosition);
    updateButtonPosition();

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', updateButtonPosition);
    };
  }, []);

  // 泡泡訊息輪播邏輯
  useEffect(() => {
    // 頁面載入後3秒顯示第一次
    const initialTimer = setTimeout(() => {
      setShowBubble(true);
      setIsTalking(true);

      // 8秒後隱藏泡泡
      setTimeout(() => {
        setShowBubble(false);
        setIsTalking(false);
        // 切換到下一條訊息
        setCurrentMessageIndex((prev) => (prev + 1) % tutorialMessages.length);
      }, 8000);
    }, 3000);

    // 設定定期顯示
    const bubbleTimer = setInterval(() => {
      setShowBubble(true);
      setIsTalking(true);

      // 6秒後隱藏泡泡
      setTimeout(() => {
        setShowBubble(false);
        setIsTalking(false);
        // 切換到下一條訊息
        setCurrentMessageIndex((prev) => (prev + 1) % tutorialMessages.length);
      }, 6000);

    }, 15000); // 每15秒顯示一次

    return () => {
      clearTimeout(initialTimer);
      clearInterval(bubbleTimer);
    };
  }, []);

  // 檢測並避免與其他UI元素重疊
  useEffect(() => {
    const checkForOverlaps = () => {
      // 檢查是否有處理中的文件或進度條
      const uploadButtons = document.querySelectorAll('.start-button, [class*="upload"], [class*="processing"]');
      const bottomElements = document.querySelectorAll('[class*="fixed"][class*="bottom"], [class*="absolute"][class*="bottom"]');

      let hasBottomElements = false;

      // 檢查上傳按鈕是否在處理狀態
      uploadButtons.forEach(el => {
        if (getComputedStyle(el).display !== 'none') {
          const rect = el.getBoundingClientRect();
          if (rect.bottom > window.innerHeight - 300) { // 如果元素在底部300px內
            hasBottomElements = true;
          }
        }
      });

      // 檢查其他底部元素
      bottomElements.forEach(el => {
        if (el.id !== 'tutorial-bot' && getComputedStyle(el).display !== 'none') {
          const rect = el.getBoundingClientRect();
          if (rect.bottom > window.innerHeight - 250) {
            hasBottomElements = true;
          }
        }
      });

      // 根據是否有底部元素調整對話框位置
      setBubblePosition(hasBottomElements ? 'bottom-20' : 'bottom-16');
    };

    // 定期檢查
    const intervalId = setInterval(checkForOverlaps, 500);

    // 初始檢查
    checkForOverlaps();

    return () => clearInterval(intervalId);
  }, []);

  const calculateEyePosition = () => {
    const dx = mousePosition.x - buttonPosition.x;
    const dy = mousePosition.y - buttonPosition.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const maxDistance = 3;

    if (distance === 0) return { x: 0, y: 0 };

    const normalizedX = (dx / distance) * Math.min(distance / 50, maxDistance);
    const normalizedY = (dy / distance) * Math.min(distance / 50, maxDistance);

    return { x: normalizedX, y: normalizedY };
  };

  const eyePosition = calculateEyePosition();

  // 處理精靈點擊 - 顯示選項菜單
  const handleBotClick = () => {
    setShowMenu(true);
    setShowBubble(false); // 隱藏自動泡泡
  };

  // 處理菜單選項點擊
  const handleMenuOption = (optionId) => {
    setShowMenu(false);

    if (optionId === 'feedback') {
      onOpenFeedback();
    } else if (optionId === 'tutorial') {
      onStartTutorial();
    }
  };

  // 點擊外部關閉菜單
  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      setShowMenu(false);
    }
  };

  return (
    <>
      {/* 在手機版隱藏整個教學精靈 */}
      <div className="fixed bottom-6 right-6 z-[5] hidden md:block">
        {/* 泡泡對話 - 自動輪播顯示 */}
        {showBubble && !showMenu && (
          <div className={`absolute ${bubblePosition} right-0 mb-2 animate-fade-in transition-all duration-300`}>
            {/* 對話框容器 */}
            <div className={`glass-panel p-4 w-72 max-w-sm relative z-[60] max-h-32 overflow-hidden backdrop-blur-xl ${
              theme === 'dark'
                ? 'border border-white/20 shadow-[0_8px_32px_rgba(0,0,0,0.3)]'
                : 'border border-slate-300 shadow-[0_8px_32px_rgba(0,0,0,0.15)] bg-white/95'
            }`}>
              <div className={`text-xs leading-relaxed pr-8 font-medium ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                {tutorialMessages[currentMessageIndex]}
              </div>
              {/* 對話氣泡尾巴 */}
              <div className="absolute bottom-0 right-6 transform translate-y-full z-[61]">
                <div className={`w-0 h-0 border-l-[10px] border-r-[10px] border-t-[12px] border-l-transparent border-r-transparent ${
                  theme === 'dark' ? 'border-t-white/20' : 'border-t-slate-300'
                }`}></div>
                <div className={`absolute top-[-1px] left-1/2 transform -translate-x-1/2 -translate-y-[10px] w-0 h-0 border-l-[8px] border-r-[8px] border-t-[10px] border-l-transparent border-r-transparent ${
                  theme === 'dark' ? 'border-t-black/80' : 'border-t-white/95'
                }`}></div>
              </div>
              {/* 訊息指示器 */}
              <div className="absolute top-2 right-2 flex space-x-1">
                {tutorialMessages.map((_, index) => (
                  <div
                    key={index}
                    className={`w-1.5 h-1.5 rounded-full ${
                      index === currentMessageIndex ? 'bg-brand-primary' : theme === 'dark' ? 'bg-white/20' : 'bg-slate-300'
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 精靈按鈕 */}
        <button
          id="tutorial-bot"
          onClick={handleBotClick}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          className={`w-14 h-14 rounded-2xl backdrop-blur-md border transition-all duration-300 group relative overflow-hidden ${
            theme === 'dark'
              ? 'bg-black/40 border-white/10 hover:border-brand-primary/50 hover:bg-black/60 shadow-[0_0_20px_rgba(0,0,0,0.3)] hover:shadow-[0_0_25px_rgba(59,130,246,0.3)]'
              : 'bg-white/90 border-slate-300 hover:border-brand-primary hover:bg-white shadow-[0_4px_20px_rgba(0,0,0,0.1)] hover:shadow-[0_6px_25px_rgba(6,182,212,0.3)]'
          }`}
          title="故障回報及建議回饋"
        >
          {/* 內部光效 */}
          <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

          <div className="flex flex-col items-center justify-center h-full space-y-2 relative z-10">
            {/* 眼睛區域 */}
            <div className="flex justify-center items-center gap-1.5 mb-1">
              {/* 眼睛 - hover時顯示閉眼效果 */}
              {isHovered ? (
                <>
                  <div className="w-2 h-0.5 bg-brand-primary shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                  <div className="w-2 h-0.5 bg-brand-primary shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                </>
              ) : (
                <>
                  <div
                    className={`w-2 h-2 rounded-full transition-transform duration-100 ${
                      theme === 'dark' ? 'bg-white shadow-[0_0_5px_rgba(255,255,255,0.8)]' : 'bg-slate-900 shadow-[0_0_3px_rgba(0,0,0,0.3)]'
                    }`}
                    style={{
                      transform: `translate(${eyePosition.x}px, ${eyePosition.y}px)`
                    }}
                  />
                  <div
                    className={`w-2 h-2 rounded-full transition-transform duration-100 ${
                      theme === 'dark' ? 'bg-white shadow-[0_0_5px_rgba(255,255,255,0.8)]' : 'bg-slate-900 shadow-[0_0_3px_rgba(0,0,0,0.3)]'
                    }`}
                    style={{
                      transform: `translate(${eyePosition.x}px, ${eyePosition.y}px)`
                    }}
                  />
                </>
              )}
            </div>

            {/* 嘴巴區域 */}
            <div className="flex justify-center">
              {isTalking ? (
                <div className={`w-4 h-2 rounded-full animate-mouth-talk transition-all duration-200 ${
                  theme === 'dark' ? 'bg-white/80' : 'bg-slate-900/80'
                }`} />
              ) : isHovered ? (
                <div className="w-5 h-1 bg-brand-primary rounded-full transition-all duration-200 shadow-[0_0_5px_rgba(59,130,246,0.5)]" />
              ) : (
                <div className={`w-3 h-0.5 rounded-full transition-all duration-200 ${
                  theme === 'dark' ? 'bg-white/50' : 'bg-slate-900/50'
                }`} />
              )}
            </div>
          </div>
        </button>
      </div>

      {/* 選項菜單遮罩 */}
      {showMenu && (
        <div
          className="fixed inset-0 z-[9998] bg-black/60 backdrop-blur-sm flex items-center justify-center animate-in fade-in duration-200"
          onClick={handleOverlayClick}
        >
          {/* 選項菜單 */}
          <div className="glass-panel p-6 max-w-sm w-full mx-4 relative animate-in zoom-in-95 duration-200 shadow-2xl">
            <h3 className={`text-lg font-display font-bold mb-6 text-center ${
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            }`}>需要協助嗎？</h3>
            <div className="space-y-3">
              {botMenuOptions.map((option) => (
                <button
                  key={option.id}
                  onClick={() => handleMenuOption(option.id)}
                  className={`w-full p-4 rounded-xl border transition-all duration-200 text-left group ${
                    theme === 'dark'
                      ? 'border-white/5 bg-white/5 hover:bg-white/10 hover:border-brand-primary/30 hover:shadow-[0_0_15px_rgba(59,130,246,0.1)]'
                      : 'border-slate-200 bg-slate-50/50 hover:bg-slate-100 hover:border-brand-primary/50 hover:shadow-[0_0_15px_rgba(6,182,212,0.15)]'
                  }`}
                >
                  <div className="flex items-center space-x-4">
                    <span className="text-2xl text-brand-primary group-hover:scale-110 transition-transform duration-200">
                      {option.id === 'feedback' ? <Bug size={24} /> : <PlayCircle size={24} />}
                    </span>
                    <div>
                      <div className={`font-medium group-hover:text-brand-primary transition-colors ${
                        theme === 'dark' ? 'text-white' : 'text-slate-900'
                      }`}>{option.label}</div>
                      <div className={`text-sm transition-colors ${
                        theme === 'dark' ? 'text-slate-300 group-hover:text-slate-200' : 'text-slate-600 group-hover:text-slate-700'
                      }`}>
                        {option.description}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowMenu(false)}
              className={`mt-6 w-full py-2.5 text-sm rounded-lg transition-colors ${
                theme === 'dark'
                  ? 'text-slate-300 hover:text-white hover:bg-white/5'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              關閉
            </button>
          </div>
        </div>
      )}

      {/* CSS動畫樣式 */}
      <style>{`
        @keyframes animate-fade-in {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .animate-fade-in {
          animation: animate-fade-in 0.3s ease-out;
        }

        @keyframes animate-mouth-talk {
          0% {
            transform: scaleY(1) scaleX(1);
            width: 1rem;
            height: 0.5rem;
          }
          25% {
            transform: scaleY(0.5) scaleX(1.2);
            width: 1.25rem;
            height: 0.25rem;
          }
          50% {
            transform: scaleY(1.5) scaleX(0.8);
            width: 0.75rem;
            height: 0.75rem;
          }
          75% {
            transform: scaleY(0.8) scaleX(1.1);
            width: 1.1rem;
            height: 0.4rem;
          }
          100% {
            transform: scaleY(1) scaleX(1);
            width: 1rem;
            height: 0.5rem;
          }
        }

        .animate-mouth-talk {
          animation: animate-mouth-talk 0.8s ease-in-out infinite;
        }
      `}</style>
    </>
  );
};

export default TutorialBot;
