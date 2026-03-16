import React, { useState } from 'react';
import { tutorialSteps } from './tutorialData';
import { useTutorial } from './useTutorial';

// 教學調試組件 - 幫助測試高亮功能
const TutorialDebug = ({ theme }) => {
  const [showDebug, setShowDebug] = useState(false);
  const { isActive, startTutorial, forceClose } = useTutorial();

  const checkElements = () => {
    // 檢查所有可能的選擇器（調試用）
    const alternativeSelectors = [
      { name: 'navigation', selectors: ['[data-tutorial="navigation"]', 'nav', '.mobile-tabs'] },
      { name: 'processing-settings', selectors: ['[data-tutorial="processing-settings"]', '.border.p-6'] },
      { name: 'llm-toggle', selectors: ['[data-tutorial="llm-toggle"]', 'input[type="checkbox"]'] },
      { name: 'processing-mode', selectors: ['[data-tutorial="processing-mode"]', '.grid.grid-cols-3'] },
      { name: 'file-upload', selectors: ['[data-tutorial="file-upload"]', '.border-dashed', 'input[type="file"]'] },
      { name: 'theme-toggle', selectors: ['[data-tutorial="theme-toggle"]', 'button[title*="主題"]'] }
    ];

    // 視覺化標記找到的元素
    alternativeSelectors.forEach(({ selectors }) => {
      selectors.forEach(selector => {
        const element = document.querySelector(selector);
        if (element) {
          element.style.outline = '2px solid green';
          setTimeout(() => { element.style.outline = ''; }, 2000);
        }
      });
    });
  };

  const highlightAllElements = () => {
    tutorialSteps.forEach((step) => {
      if (step.target) {
        const element = document.querySelector(step.target);
        if (element) {
          element.style.border = '3px solid red';
          element.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
        }
      }
    });
  };

  const useAlternativeSelectors = () => {
    // 嘗試使用替代選擇器
    const alternatives = [
      { target: 'nav.mobile-tabs', name: 'navigation' },
      { target: '.border-dashed', name: 'file-upload' },
      { target: 'input[type="checkbox"]', name: 'llm-toggle' }
    ];
    
    alternatives.forEach(({ target, name }) => {
      const element = document.querySelector(target);
      if (element) {
        element.style.border = '3px solid blue';
        element.style.backgroundColor = 'rgba(0, 0, 255, 0.1)';
      }
    });
  };

  const clearHighlights = () => {
    tutorialSteps.forEach((step) => {
      if (step.target) {
        const element = document.querySelector(step.target);
        if (element) {
          element.style.border = '';
          element.style.backgroundColor = '';
        }
      }
    });
  };

  // if (!showDebug) {
  //   return (
  //     <button
  //       onClick={() => setShowDebug(true)}
  //       className={`fixed bottom-20 left-6 px-3 py-1 text-xs rounded z-50 ${
  //         theme === 'dark' 
  //           ? 'bg-gray-700 text-white border border-gray-600' 
  //           : 'bg-gray-200 text-black border border-gray-300'
  //       }`}
  //     >
  //       教學調試
  //     </button>
  //   );
  // }

  return (
    <div className={`fixed bottom-20 left-6 p-4 rounded-lg shadow-lg z-50 max-w-xs ${
      theme === 'dark' 
        ? 'bg-gray-800 text-white border border-gray-600' 
        : 'bg-white text-black border border-gray-300'
    }`}>
      <h4 className="font-bold mb-3">教學調試工具</h4>
      <div className="space-y-2">
        <button
          onClick={checkElements}
          className="w-full px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          檢查元素
        </button>
        <button
          onClick={highlightAllElements}
          className="w-full px-3 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
        >
          高亮所有目標
        </button>
        <button
          onClick={useAlternativeSelectors}
          className="w-full px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          測試替代選擇器
        </button>
        <button
          onClick={clearHighlights}
          className="w-full px-3 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600"
        >
          清除高亮
        </button>
        
        {/* 教學控制按鈕 */}
        <hr className="my-2" />
        <div className="text-xs font-medium mb-2">教學控制:</div>
        <button
          onClick={() => startTutorial()}
          className="w-full px-3 py-1 text-xs bg-purple-500 text-white rounded hover:bg-purple-600 mb-1"
        >
          啟動教學 ({isActive ? '活躍' : '非活躍'})
        </button>
        <button
          onClick={() => forceClose()}
          className="w-full px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
        >
          強制關閉教學
        </button>
        <button
          onClick={() => setShowDebug(false)}
          className={`w-full px-3 py-1 text-xs rounded ${
            theme === 'dark' 
              ? 'bg-gray-600 text-white hover:bg-gray-500' 
              : 'bg-gray-300 text-black hover:bg-gray-400'
          }`}
        >
          關閉
        </button>
      </div>
      
      <div className="mt-3 text-xs">
        <div className="font-medium mb-1">目標元素列表:</div>
        {tutorialSteps.map((step, index) => (
          <div key={index} className="text-xs opacity-75 mb-1">
            {index + 1}. {step.target}
          </div>
        ))}
      </div>
    </div>
  );
};

export default TutorialDebug;