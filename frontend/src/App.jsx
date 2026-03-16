import React, { useRef, useEffect, useLayoutEffect } from 'react';
import './App.css';

// Hooks
import { useAppState } from './hooks/useAppState';
import { useFileUpload } from './hooks/useFileUpload';
import { useTextProcessing } from './hooks/useTextProcessing';

// Components
import Header from './components/Header';
import Navigation from './components/Navigation';
import FileUpload from './components/FileUpload';
import TextInput from './components/TextInput';
import ProcessingSettings from './components/ProcessingSettings';
import CustomModal from './components/CustomModal';
import ResultDisplay from './components/ResultDisplay';
import QueuePage from './pages/QueuePage';
import HotWordsPage from './pages/HotWordsPage';
import FeedbackModal from './components/FeedbackModal';
import DemoNoticeModal from './components/DemoNoticeModal';
import TutorialSystem from './tutorial/TutorialSystem';

function App() {
  // 使用自定義hooks管理狀態
  const appState = useAppState();
  const { handleFileUpload } = useFileUpload(appState);
  const { handleTextProcess } = useTextProcessing(appState);

  // 包裝處理函數以追蹤 sourceType
  const wrappedHandleFileUpload = React.useCallback(() => {
    appState.setSourceType('audio');
    handleFileUpload();
  }, [handleFileUpload, appState.setSourceType]);

  const wrappedHandleTextProcess = React.useCallback(() => {
    appState.setSourceType('text');
    handleTextProcess();
  }, [handleTextProcess, appState.setSourceType]);

  // 回饋模態框狀態
  const [showFeedbackModal, setShowFeedbackModal] = React.useState(false);

  // Auto-switch to results tab when processing starts or result arrives
  // useLayoutEffect runs BEFORE browser paint, preventing a flash of the
  // intermediate state (upload tab with processing=true)
  const prevProcessing = useRef(false);
  const prevResult = useRef(null);

  useLayoutEffect(() => {
    if (appState.processing && !prevProcessing.current) {
      appState.setActiveTab('results');
    }
    prevProcessing.current = appState.processing;
  }, [appState.processing]);

  useLayoutEffect(() => {
    if (appState.result && !prevResult.current) {
      appState.setActiveTab('results');
    }
    prevResult.current = appState.result;
  }, [appState.result]);

  const {
    // 基本狀態
    theme,
    toggleTheme,
    activeTab,
    setActiveTab,
    userId,

    // 文件和處理狀態
    files,
    setFiles,
    processing,
    uploading,
    uploadProgress,
    uploadSpeed,
    result,
    error,
    currentTaskId,
    taskProgress,

    // 處理設置
    processingMode,
    setProcessingMode,
    whisperModel,
    setWhisperModel,
    aiModel,
    setAiModel,
    enableLLMProcessing,
    setEnableLLMProcessing,
    availableModels,
    setAvailableModels,
    availableAiModels,
    setAvailableAiModels,
    modelLoading,
    setModelLoading,
    ollamaStatus,
    setOllamaStatus,

    // 自定義模式狀態
    customModePrompt,
    setCustomModePrompt,
    customDetailPrompt,
    setCustomDetailPrompt,
    showCustomModal,
    setShowCustomModal,
    customModalType,
    setCustomModalType,

    // 標籤狀態
    selectedTags,
    setSelectedTags,
    customTagPrompt,
    setCustomTagPrompt,

    // Email 通知設定
    emailEnabled,
    setEmailEnabled,
    emailAddress,
    setEmailAddress,

    // 文字處理設定
    textInput,
    setTextInput,
    enableCleanFiller,
    setEnableCleanFiller,
    sourceType,
    setSourceType,

    // 系統配置
    systemConfig,
    emailFeatureEnabled,
  } = appState;

  return (
    <div className="min-h-screen text-slate-100 font-sans selection:bg-brand-primary/30">
      {/* Animated Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-brand-primary/20 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-brand-secondary/20 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-32 left-1/3 w-96 h-96 bg-brand-accent/20 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      <div className="max-w-screen-2xl mx-auto px-6 sm:px-8 lg:px-10 py-8">
        {/* Header */}
        <Header
          theme={theme}
          toggleTheme={toggleTheme}
          setActiveTab={setActiveTab}
          adminPassword={appState.adminPassword}
          setAdminPassword={appState.setAdminPassword}
        />

        {/* Navigation */}
        <div className="mb-8" data-tutorial="navigation">
          <Navigation
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            theme={theme}
            processing={processing}
            hasResult={!!result}
          />
        </div>

        {/* Main Content */}
        {activeTab === 'upload' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left: File Upload (sticky) */}
            <div>
              <div className="lg:sticky lg:top-24 space-y-6" data-tutorial="file-upload">
                <FileUpload
                  theme={theme}
                  files={files}
                  setFiles={setFiles}
                  processing={processing}
                  uploading={uploading}
                  uploadProgress={uploadProgress}
                  uploadSpeed={uploadSpeed}
                  handleFileUpload={wrappedHandleFileUpload}
                />

                {error && (
                  <div className={`glass-panel p-6 animate-pulse-slow ${theme === 'dark'
                      ? 'border-red-500/30 bg-red-500/10 text-red-200'
                      : 'border-red-200 bg-red-50 text-red-700'
                    }`}>
                    <div className="flex items-start gap-4">
                      <div className="text-2xl">⚠️</div>
                      <div>
                        <div className="font-semibold mb-2 text-base">{error}</div>
                        {(error.includes('413') || error.includes('Request Entity Too Large') || error.includes('大於') || error.includes('too large')) && (
                          <div className={`text-sm mt-3 p-4 rounded-lg border ${theme === 'dark'
                              ? 'bg-red-500/10 border-red-500/20 text-red-200/90'
                              : 'bg-red-100 border-red-200 text-red-800'
                            }`}>
                            <div className="font-semibold mb-2">檔案大小超出限制</div>
                            <ul className="list-disc list-inside mt-2 space-y-1.5">
                              <li>目前限制：500MB</li>
                              <li>大型檔案處理時間較長</li>
                              <li>建議轉換為 MP3 或 AAC 格式</li>
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Processing Settings */}
            <div data-tutorial="processing-settings">
              <ProcessingSettings
                theme={theme}
                files={files}
                processing={processing}
                uploading={uploading}
                handleFileUpload={wrappedHandleFileUpload}
                processingMode={processingMode}
                setProcessingMode={setProcessingMode}
                whisperModel={whisperModel}
                setWhisperModel={setWhisperModel}
                aiModel={aiModel}
                setAiModel={setAiModel}
                enableLLMProcessing={enableLLMProcessing}
                setEnableLLMProcessing={setEnableLLMProcessing}
                availableModels={availableModels}
                setAvailableModels={setAvailableModels}
                availableAiModels={availableAiModels}
                setAvailableAiModels={setAvailableAiModels}
                modelLoading={modelLoading}
                setModelLoading={setModelLoading}
                ollamaStatus={ollamaStatus}
                setCustomModalType={setCustomModalType}
                setShowCustomModal={setShowCustomModal}
                emailEnabled={emailEnabled}
                setEmailEnabled={setEmailEnabled}
                emailAddress={emailAddress}
                setEmailAddress={setEmailAddress}
                emailFeatureEnabled={emailFeatureEnabled}
                selectedTags={selectedTags}
                setSelectedTags={setSelectedTags}
                customTagPrompt={customTagPrompt}
                setCustomTagPrompt={setCustomTagPrompt}
              />
            </div>
          </div>
        )}

        {activeTab === 'text' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left: Text Input (sticky) */}
            <div>
              <div className="lg:sticky lg:top-24 space-y-6">
                <TextInput
                  theme={theme}
                  textInput={textInput}
                  setTextInput={setTextInput}
                  processing={processing}
                  enableCleanFiller={enableCleanFiller}
                  setEnableCleanFiller={setEnableCleanFiller}
                />

                {error && (
                  <div className={`glass-panel p-6 animate-pulse-slow ${theme === 'dark'
                      ? 'border-red-500/30 bg-red-500/10 text-red-200'
                      : 'border-red-200 bg-red-50 text-red-700'
                    }`}>
                    <div className="flex items-start gap-4">
                      <div className="text-2xl">⚠️</div>
                      <div>
                        <div className="font-semibold mb-2 text-base">{error}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Processing Settings */}
            <div>
              <ProcessingSettings
                theme={theme}
                files={files}
                processing={processing}
                uploading={uploading}
                handleFileUpload={wrappedHandleTextProcess}
                processingMode={processingMode}
                setProcessingMode={setProcessingMode}
                whisperModel={whisperModel}
                setWhisperModel={setWhisperModel}
                aiModel={aiModel}
                setAiModel={setAiModel}
                enableLLMProcessing={enableLLMProcessing}
                setEnableLLMProcessing={setEnableLLMProcessing}
                availableModels={availableModels}
                setAvailableModels={setAvailableModels}
                availableAiModels={availableAiModels}
                setAvailableAiModels={setAvailableAiModels}
                modelLoading={modelLoading}
                setModelLoading={setModelLoading}
                ollamaStatus={ollamaStatus}
                setCustomModalType={setCustomModalType}
                setShowCustomModal={setShowCustomModal}
                emailEnabled={emailEnabled}
                setEmailEnabled={setEmailEnabled}
                emailAddress={emailAddress}
                setEmailAddress={setEmailAddress}
                emailFeatureEnabled={emailFeatureEnabled}
                selectedTags={selectedTags}
                setSelectedTags={setSelectedTags}
                customTagPrompt={customTagPrompt}
                setCustomTagPrompt={setCustomTagPrompt}
                sourceType="text"
                textInput={textInput}
              />
            </div>
          </div>
        )}

        {activeTab === 'results' && (
          <div>
            <ResultDisplay
              theme={theme}
              result={result}
              processing={processing}
              enableLLMProcessing={enableLLMProcessing}
              taskProgress={taskProgress}
              sourceType={sourceType}
              onCancel={currentTaskId ? () => {
                const hostname = window.location.hostname;
                const protocol = window.location.protocol;
                const port = window.location.port;
                const base = (protocol === 'https:' || !port || port === '80' || port === '443' || hostname === 'localhost' || hostname === '127.0.0.1')
                  ? '/api'
                  : `${protocol}//${hostname}:3080/api`;
                fetch(`${base}/task/${currentTaskId}/cancel?user_id=${userId}`, { method: 'POST' });
              } : undefined}
            />
          </div>
        )}

        {activeTab === 'queue' && (
          <QueuePage userId={userId} theme={theme} />
        )}

        {activeTab === 'hotwords' && (
          <HotWordsPage
            adminPassword={appState.adminPassword}
            setActiveTab={setActiveTab}
            theme={theme}
          />
        )}

        {/* Custom Modal */}
        <CustomModal
          theme={theme}
          showCustomModal={showCustomModal}
          setShowCustomModal={setShowCustomModal}
          customModalType={customModalType}
          customModePrompt={customModePrompt}
          setCustomModePrompt={setCustomModePrompt}
          customDetailPrompt={customDetailPrompt}
          setCustomDetailPrompt={setCustomDetailPrompt}
          setProcessingMode={setProcessingMode}
        />
      </div>

      {/* Tutorial System */}
      <TutorialSystem onOpenFeedback={() => setShowFeedbackModal(true)} theme={theme} />

      {/* Feedback Modal */}
      <FeedbackModal
        isOpen={showFeedbackModal}
        onClose={() => setShowFeedbackModal(false)}
        theme={theme}
      />

      {/* Demo Notice Modal - Shows on first load */}
      <DemoNoticeModal />
    </div>
  );
}

export default App;
