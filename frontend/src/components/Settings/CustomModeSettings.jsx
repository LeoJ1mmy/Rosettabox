/**
 * 自訂模式設置組件 - 支持用戶自訂處理模式和詳細程度
 */
import React, { useState, useEffect } from 'react';
import { Edit3, AlertCircle, CheckCircle, BookOpen, Lightbulb } from 'lucide-react';

const CustomModeSettings = ({
  processingMode,
  setProcessingMode,
  detailLevel,
  setDetailLevel,
  customModePrompt,
  setCustomModePrompt,
  customDetailPrompt,
  setCustomDetailPrompt,
  onValidatePrompt
}) => {
  const [showCustomModeInput, setShowCustomModeInput] = useState(false);
  const [showCustomDetailInput, setShowCustomDetailInput] = useState(false);
  const [modeValidation, setModeValidation] = useState({ valid: true, message: '' });
  const [detailValidation, setDetailValidation] = useState({ valid: true, message: '' });
  const [suggestions, setSuggestions] = useState({});
  const [showSuggestions, setShowSuggestions] = useState(false);

  // 處理模式變化
  useEffect(() => {
    if (processingMode === 'custom') {
      setShowCustomModeInput(true);
    } else {
      setShowCustomModeInput(false);
      setCustomModePrompt('');
    }
  }, [processingMode, setCustomModePrompt]);

  // 詳細程度變化
  useEffect(() => {
    if (detailLevel === 'custom') {
      setShowCustomDetailInput(true);
    } else {
      setShowCustomDetailInput(false);
      setCustomDetailPrompt('');
    }
  }, [detailLevel, setCustomDetailPrompt]);

  // 獲取自訂 prompt 建議
  const fetchSuggestions = async () => {
    try {
      const response = await fetch('/api/text/custom-prompt/suggestions');
      const data = await response.json();
      setSuggestions(data.suggestions || {});
    } catch (error) {
      // 獲取建議失敗，靜默處理
    }
  };

  // 驗證自訂 prompt
  const validatePrompt = async (prompt, type) => {
    if (!prompt || !onValidatePrompt) return;

    try {
      const result = await onValidatePrompt(prompt);
      if (type === 'mode') {
        setModeValidation(result);
      } else if (type === 'detail') {
        setDetailValidation(result);
      }
    } catch (error) {
      const errorResult = { valid: false, message: '驗證服務不可用' };
      if (type === 'mode') {
        setModeValidation(errorResult);
      } else if (type === 'detail') {
        setDetailValidation(errorResult);
      }
    }
  };

  // 套用建議的 prompt
  const applySuggestion = (suggestionText, type) => {
    if (type === 'mode') {
      setCustomModePrompt(suggestionText);
      validatePrompt(suggestionText, 'mode');
    } else if (type === 'detail') {
      setCustomDetailPrompt(suggestionText);
      validatePrompt(suggestionText, 'detail');
    }
    setShowSuggestions(false);
  };

  // 組件載入時獲取建議
  useEffect(() => {
    fetchSuggestions();
  }, []);

  return (
    <div className="custom-mode-settings">
      {/* 自訂處理模式 */}
      {showCustomModeInput && (
        <div className="custom-input-section">
          <div className="custom-input-header">
            <Edit3 size={16} />
            <span>自訂處理模式</span>
            <button
              type="button"
              className="toggle-suggestions-btn"
              onClick={() => setShowSuggestions(!showSuggestions)}
              title="查看建議"
            >
              <Lightbulb size={14} />
            </button>
          </div>

          {showSuggestions && (
            <div className="suggestions-panel">
              <div className="suggestions-header">
                <BookOpen size={14} />
                <span>建議範例</span>
              </div>
              <div className="suggestions-list">
                {Object.entries(suggestions).map(([key, value]) => (
                  <div key={key} className="suggestion-item">
                    <div className="suggestion-title">{key}</div>
                    <div className="suggestion-content">{value}</div>
                    <button
                      type="button"
                      className="apply-suggestion-btn"
                      onClick={() => applySuggestion(value, 'mode')}
                    >
                      套用
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <textarea
            value={customModePrompt}
            onChange={(e) => {
              setCustomModePrompt(e.target.value);
              validatePrompt(e.target.value, 'mode');
            }}
            placeholder="請輸入自訂的處理指令，例如：請將以下內容整理成技術文件..."
            className="custom-prompt-textarea"
            rows={4}
          />

          {/* 驗證狀態顯示 */}
          <div className={`validation-message ${modeValidation.valid ? 'valid' : 'invalid'}`}>
            {modeValidation.valid ? (
              <CheckCircle size={14} />
            ) : (
              <AlertCircle size={14} />
            )}
            <span>{modeValidation.message}</span>
          </div>
        </div>
      )}

      {/* 自訂詳細程度 */}
      {showCustomDetailInput && (
        <div className="custom-input-section">
          <div className="custom-input-header">
            <Edit3 size={16} />
            <span>自訂詳細程度</span>
          </div>

          <textarea
            value={customDetailPrompt}
            onChange={(e) => {
              setCustomDetailPrompt(e.target.value);
              validatePrompt(e.target.value, 'detail');
            }}
            placeholder="請輸入詳細程度要求，例如：保留所有技術細節，總字數控制在 2000 字以內..."
            className="custom-prompt-textarea"
            rows={3}
          />

          {/* 驗證狀態顯示 */}
          <div className={`validation-message ${detailValidation.valid ? 'valid' : 'invalid'}`}>
            {detailValidation.valid ? (
              <CheckCircle size={14} />
            ) : (
              <AlertCircle size={14} />
            )}
            <span>{detailValidation.message}</span>
          </div>
        </div>
      )}


      {/* 使用提示 */}
      {(showCustomModeInput || showCustomDetailInput) && (
        <div className="custom-mode-tips">
          <AlertCircle size={14} />
          <div className="tips-content">
            <div className="tip-title">使用提示：</div>
            <ul>
              <li>處理模式：定義 AI 如何理解和處理內容</li>
              <li>詳細程度：控制輸出的深度和長度</li>
              <li>格式模板：指定輸出的結構和樣式</li>
              <li>確保指令清晰明確，避免過於複雜的要求</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomModeSettings;
