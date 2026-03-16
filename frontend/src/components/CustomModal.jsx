import React from 'react';
import { X, Settings, List } from 'lucide-react';

const CustomModal = ({
  theme,
  showCustomModal,
  setShowCustomModal,
  customModalType,
  customModePrompt,
  setCustomModePrompt,
  customDetailPrompt,
  setCustomDetailPrompt,
  setProcessingMode
}) => {
  const handleConfirm = () => {
    if (customModalType === 'mode') {
      setProcessingMode('custom');
    }
    setShowCustomModal(false);
  };

  if (!showCustomModal) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className={`glass-panel w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-2xl relative animate-in zoom-in-95 duration-200 ${
        theme === 'dark' ? '' : 'bg-white border-slate-300'
      }`}>
        <div className="flex items-center justify-between mb-6">
          <h3 className={`text-xl font-display font-bold flex items-center gap-2 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            <Settings className="text-brand-primary" size={24} />
            自定義設置
          </h3>
          <button
            type="button"
            onClick={() => setShowCustomModal(false)}
            className={`transition-colors ${
              theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            <X size={24} />
          </button>
        </div>

        {customModalType === 'mode' && (
          <div className="mb-6">
            <label className={`block text-sm font-medium mb-2 flex items-center gap-2 ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}>
              <List size={16} className="text-brand-secondary" />
              自定義處理模式
            </label>
            <textarea
              value={customModePrompt}
              onChange={(e) => setCustomModePrompt(e.target.value)}
              placeholder="請輸入自定義的處理指令..."
              className={`glass-input w-full h-32 resize-vertical ${
                theme === 'dark' ? '' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-400'
              }`}
            />
            <p className={`text-xs mt-2 ${
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            }`}>
              定義您希望 AI 如何精確地處理您的內容。
            </p>
          </div>
        )}

        <div className={`flex justify-end space-x-3 pt-4 border-t ${
          theme === 'dark' ? 'border-white/10' : 'border-slate-200'
        }`}>
          <button
            type="button"
            onClick={() => setShowCustomModal(false)}
            className={`glass-button px-6 py-2 ${
              theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className="glass-button bg-brand-primary/20 hover:bg-brand-primary/30 text-brand-primary border-brand-primary/30 px-6 py-2 font-medium"
          >
            確認並應用
          </button>
        </div>
      </div>
    </div>
  );
};

export default CustomModal;
