/**
 * 設置面板組件 - 管理各種處理設置
 */
import React from 'react';
import { Settings, Zap, Brain, Mic } from 'lucide-react';
import CustomModeSettings from './CustomModeSettings';

const SettingsPanel = ({
  processingMode,
  setProcessingMode,
  detailLevel,
  setDetailLevel,
  whisperModel,
  setWhisperModel,
  aiModel,
  setAiModel,
  availableWhisperModels = [],
  availableAiModels = [],
  // 自訂模式相關 props
  customModePrompt,
  setCustomModePrompt,
  customDetailPrompt,
  setCustomDetailPrompt,
  onValidatePrompt
}) => {
  return (
    <div className="settings-panel">
      <h3>
        <Settings size={20} />
        <span>處理設置</span>
      </h3>

      {/* 處理模式 */}
      <div className="setting-group">
        <label>
          <Brain size={16} />
          處理模式
        </label>
        <select
          value={processingMode}
          onChange={(e) => setProcessingMode(e.target.value)}
        >
          <option value="default">通用模式</option>
          <option value="meeting">會議記錄</option>
          <option value="lecture">講座筆記</option>
          <option value="interview">訪談整理</option>
          <option value="speaker_alignment">說話人對齊</option>
          <option value="custom">自定義模式</option>
        </select>
      </div>

      {/* 詳細程度 */}
      <div className="setting-group">
        <label>
          <Zap size={16} />
          詳細程度
        </label>
        <select
          value={detailLevel}
          onChange={(e) => setDetailLevel(e.target.value)}
        >
          <option value="simple">簡單</option>
          <option value="normal">普通</option>
          <option value="detailed">詳細</option>
          <option value="custom">自定義詳細程度</option>
        </select>
      </div>

      {/* Whisper 模型選擇 */}
      <div className="setting-group">
        <label>
          <Mic size={16} />
          語音識別模型
        </label>
        <select
          value={whisperModel}
          onChange={(e) => setWhisperModel(e.target.value)}
        >
          {availableWhisperModels.length > 0 ? (
            availableWhisperModels.map(model => (
              <option key={model} value={model}>
                {model}
              </option>
            ))
          ) : (
            <>
              <option value="tiny">Tiny (快速)</option>
              <option value="base">Base (平衡)</option>
              <option value="small">Small (準確)</option>
              <option value="medium">Medium (高準確)</option>
              <option value="large">Large (最準確)</option>
            </>
          )}
        </select>
      </div>

      {/* AI 模型選擇 */}
      <div className="setting-group">
        <label>
          <Brain size={16} />
          AI 整理模型
        </label>
        <select
          value={aiModel}
          onChange={(e) => setAiModel(e.target.value)}
        >
          {availableAiModels.length > 0 ? (
            availableAiModels.map(model => (
              <option key={model} value={model}>
                {model}
              </option>
            ))
          ) : (
            <>
              <option value="phi4-mini:3.8b">Phi-4 Mini (快速)</option>
              <option value="llama3.2:3b">Llama 3.2 (平衡)</option>
              <option value="qwen2.5:3b">Qwen 2.5 (中文優化)</option>
            </>
          )}
        </select>
      </div>

      {/* 自定義模式設置 */}
      <CustomModeSettings
        processingMode={processingMode}
        setProcessingMode={setProcessingMode}
        detailLevel={detailLevel}
        setDetailLevel={setDetailLevel}
        customModePrompt={customModePrompt}
        setCustomModePrompt={setCustomModePrompt}
        customDetailPrompt={customDetailPrompt}
        setCustomDetailPrompt={setCustomDetailPrompt}
        onValidatePrompt={onValidatePrompt}
      />
    </div>
  );
};

export default SettingsPanel;