import { useState, useEffect, useCallback } from 'react';
import { tutorialSteps } from './tutorialData';

// 教學系統狀態管理Hook
export const useTutorial = () => {
  const [isActive, setIsActive] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);

  // 獲取當前步驟 - 只有在活躍狀態下才返回步驟
  const currentStep = isActive ? (tutorialSteps[currentStepIndex] || null) : null;

  // 檢查教學是否已完成（從localStorage）
  useEffect(() => {
    const tutorialCompleted = localStorage.getItem('tutorial-completed');
    if (tutorialCompleted === 'true') {
      setIsCompleted(true);
    }
  }, []);

  // 滾動到目標元素 - 改進版，確保目標元素完全可見
  const scrollToTarget = useCallback((target) => {
    return new Promise((resolve) => {
      // 增加重試邏輯，處理延遲渲染的元素
      let attempts = 0;
      const maxAttempts = 5;

      const tryScroll = () => {
        attempts++;
        const element = document.querySelector(target);

        if (element) {
          const rect = element.getBoundingClientRect();
          const viewportHeight = window.innerHeight;
          const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;

          // 檢查元素是否已經在可視範圍內
          const isVisible = rect.top >= 50 && rect.bottom <= viewportHeight - 100;

          if (isVisible) {
            resolve();
            return;
          }

          // 計算最佳滾動位置 - 讓元素位於螢幕上半部
          const elementTopInDocument = rect.top + currentScrollTop;
          const targetScrollPosition = elementTopInDocument - viewportHeight * 0.3;
          const finalScrollPosition = Math.max(0, targetScrollPosition);

          // 執行平滑滾動
          window.scrollTo({
            top: finalScrollPosition,
            behavior: 'smooth'
          });

          // 等待滾動完成，使用更長的延遲確保穩定
          setTimeout(() => {
            resolve();
          }, 1000); // 增加到1秒等待時間
        } else if (attempts >= maxAttempts) {
          resolve();
        } else {
          setTimeout(tryScroll, 300);
        }
      };

      // 開始第一次嘗試
      setTimeout(tryScroll, 150);
    });
  }, []);

  // 移除教學數據屬性
  const removeTutorialAttributes = useCallback(() => {
    const tutorialElements = document.querySelectorAll('[data-tutorial]');
    tutorialElements.forEach(element => {
      element.removeAttribute('data-tutorial');
    });
  }, []);

  // 添加教學數據屬性到DOM元素的函數定義
  const addTutorialAttributes = useCallback(() => {
    // 由於我們已經在組件中手動添加了 data-tutorial 屬性，
    // 這個函數主要用於調試和確保屬性存在
  }, []);

  // 開始教學
  const startTutorial = useCallback(() => {
    setIsActive(true);
    setCurrentStepIndex(0);
    setIsCompleted(false);
    
    // 滾動到頁面頂部
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    // 延遲執行屬性檢查，確保DOM已渲染
    setTimeout(() => {
      addTutorialAttributes();
    }, 500);
  }, [addTutorialAttributes]);

  // 下一步 - 改進版，確保穩定的滾動和高亮流程
  const nextStep = useCallback(async () => {
    if (currentStepIndex < tutorialSteps.length - 1) {
      const newIndex = currentStepIndex + 1;
      const nextStepData = tutorialSteps[newIndex];

      try {
        // 階段1: 暫時隱藏當前高亮，準備切換
        setCurrentStepIndex(-1);

        // 短暫延遲讓UI更新完成
        await new Promise(resolve => setTimeout(resolve, 100));

        // 階段2: 如果有目標元素，執行滾動
        if (nextStepData && nextStepData.target) {
          await scrollToTarget(nextStepData.target);

          // 階段3: 滾動完成後等待DOM穩定
          await new Promise(resolve => setTimeout(resolve, 400));
        }

        // 階段5: 激活新步驟的高亮
        setCurrentStepIndex(newIndex);

      } catch (error) {
        // 錯誤處理：直接設置新步驟
        setCurrentStepIndex(newIndex);
      }
    }
  }, [currentStepIndex, scrollToTarget]);

  // 上一步
  const prevStep = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(prev => prev - 1);
      
      // 滾動到目標元素
      const prevStep = tutorialSteps[currentStepIndex - 1];
      if (prevStep && prevStep.target) {
        scrollToTarget(prevStep.target);
      }
    }
  }, [currentStepIndex, scrollToTarget]);

  // 跳過教學
  const skipTutorial = useCallback(() => {
    setIsActive(false);
    setCurrentStepIndex(0);
    setIsCompleted(false);
    removeTutorialAttributes();
  }, [removeTutorialAttributes]);

  // 強制關閉教學 - 最強力的清理方法
  const forceClose = useCallback(() => {
    try {
      // 立即設置所有狀態為關閉狀態
      setIsActive(false);
      setCurrentStepIndex(0);
      setIsCompleted(false);
      
      // 清除所有教學相關的DOM屬性和樣式
      removeTutorialAttributes();
      
      // 恢復頁面正常滾動
      document.body.style.overflow = '';
      document.body.style.overflowY = '';
      document.body.style.overflowX = '';
      document.documentElement.style.overflow = '';
      
      // 不直接刪除 DOM 元素，讓 React 自己管理
      // React 會在狀態改變後自動清理組件
      
      // 只清理動態添加的樣式，不刪除元素
      const allElements = document.querySelectorAll('[data-tutorial]');
      allElements.forEach(element => {
        // 清理可能添加的內聯樣式，但不刪除元素
        if (element.style.border && element.style.border.includes('rgb(59, 130, 246)')) {
          element.style.border = '';
        }
        if (element.style.backgroundColor && element.style.backgroundColor.includes('rgba(59, 130, 246')) {
          element.style.backgroundColor = '';
        }
        if (element.style.boxShadow && element.style.boxShadow.includes('59, 130, 246')) {
          element.style.boxShadow = '';
        }
      });

    } catch (error) {
      // 即使發生錯誤也要確保基本狀態被重置
      setIsActive(false);
      setCurrentStepIndex(0);
      setIsCompleted(false);
    }

    // 延遲檢查和額外清理
    setTimeout(() => {
      // 確保頁面滾動正常
      document.body.style.overflow = '';
      document.body.style.overflowY = '';
      document.body.style.overflowX = '';
      document.documentElement.style.overflow = '';
    }, 100);
  }, [removeTutorialAttributes]);

  // 完成教學
  const finishTutorial = useCallback(() => {
    setIsActive(false);
    setCurrentStepIndex(0);
    setIsCompleted(true);
    
    // 保存完成狀態到localStorage
    localStorage.setItem('tutorial-completed', 'true');
    
    removeTutorialAttributes();
  }, [removeTutorialAttributes]);

  // 重置教學
  const resetTutorial = useCallback(() => {
    setIsActive(false);
    setCurrentStepIndex(0);
    setIsCompleted(false);
    localStorage.removeItem('tutorial-completed');
    removeTutorialAttributes();
  }, [removeTutorialAttributes]);



  // 自動進入下一步（基於時間）- 暫時禁用以避免干擾關閉功能
  useEffect(() => {
    if (!isActive || !currentStep) return;

    // 暫時禁用自動播放，讓用戶手動控制
    // const timer = setTimeout(() => {
    //   if (currentStep.isFinish) {
    //     // 最後一步不自動進入下一步
    //     return;
    //   }
    //   
    //   if (currentStepIndex < tutorialSteps.length - 1) {
    //     nextStep();
    //   }
    // }, currentStep.duration || 6000);

    // return () => clearTimeout(timer);
  }, [isActive, currentStep, currentStepIndex, nextStep]);

  return {
    // 狀態
    isActive,
    currentStep,
    currentStepIndex,
    totalSteps: tutorialSteps.length,
    isCompleted,
    
    // 控制方法
    startTutorial,
    nextStep,
    prevStep,
    skipTutorial,
    finishTutorial,
    resetTutorial,
    forceClose,
    
    // 輔助方法
    addTutorialAttributes,
    removeTutorialAttributes
  };
};