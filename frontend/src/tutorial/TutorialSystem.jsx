import React, { useState, useCallback } from 'react';
import { useTutorial } from './useTutorial';
import TutorialBot from './TutorialBot';
import TutorialOverlay from './TutorialOverlay';
import TutorialGuide from './TutorialGuide';
import TutorialErrorBoundary from './TutorialErrorBoundary';


// 完整的教學系統組件 - 整合所有教學功能
const TutorialSystem = ({ onOpenFeedback, theme }) => {
  const {
    isActive,
    currentStep,
    currentStepIndex,
    totalSteps,
    startTutorial,
    nextStep,
    prevStep,
    skipTutorial,
    finishTutorial,
    forceClose
  } = useTutorial();


  return (
    <TutorialErrorBoundary>
      {/* 教學精靈 - 替換原有的FeedbackBot */}
      <TutorialBot 
        onOpenFeedback={onOpenFeedback}
        onStartTutorial={startTutorial}
        theme={theme}
      />

      {/* 教學遮罩層 */}
      {isActive && (
        <TutorialOverlay
          isActive={isActive}
          targetElement={currentStep?.target}
          highlightStyle={currentStep?.highlightStyle}
          onOverlayClick={forceClose}
        />
      )}

      {/* 教學引導組件 */}
      {isActive && currentStep && (
        <TutorialGuide
          step={currentStep}
          totalSteps={totalSteps}
          onNext={nextStep}
          onPrev={prevStep}
          onSkip={forceClose}
          onFinish={finishTutorial}
          theme={theme}
        />
      )}
    </TutorialErrorBoundary>
  );
};

export default TutorialSystem;