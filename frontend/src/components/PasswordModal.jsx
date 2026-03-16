import React, { useState } from 'react';
import { X, Lock, Loader2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const PasswordModal = ({ isOpen, onClose, onSuccess, theme }) => {
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) return;

    setIsLoading(true);
    setError('');

    try {
      const response = await api.verifyAdminPassword(password);
      if (response.success && response.data?.verified) {
        onSuccess(password);
        setPassword('');
        onClose();
      } else {
        setError('密碼錯誤');
      }
    } catch (err) {
      if (err.response?.status === 403) {
        setError('密碼錯誤');
      } else if (err.response?.status === 503) {
        setError('管理員功能未啟用');
      } else {
        setError('驗證失敗，請稍後再試');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setPassword('');
    setError('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-sm shadow-2xl relative animate-in zoom-in-95 duration-200 p-0 overflow-hidden">
        <div className={`flex items-center justify-between p-5 border-b shrink-0 ${theme === 'dark' ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-slate-50'
          }`}>
          <h2 className={`text-lg font-display font-bold flex items-center gap-2 ${theme === 'dark' ? 'text-white' : 'text-slate-800'
            }`}>
            <Lock className="text-brand-primary" size={20} />
            管理員驗證
          </h2>
          <button
            onClick={handleClose}
            className={`transition-colors ${theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-500 hover:text-slate-800'
              }`}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className={`block text-sm font-medium mb-2 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              }`}>
              請輸入管理員密碼
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="管理員密碼"
              className={`glass-input w-full ${theme === 'dark' ? '' : 'bg-white/50 border-slate-200 text-slate-800 placeholder:text-slate-400'
                }`}
              autoFocus
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div className="flex space-x-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              className={`flex-1 py-2 rounded-lg transition-colors font-medium border ${theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
                : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-sm'
                }`}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isLoading || !password.trim()}
              className={`flex-1 py-2 rounded-lg transition-colors font-medium flex items-center justify-center gap-2 border ${theme === 'dark'
                ? 'bg-brand-primary border-brand-primary text-white hover:bg-brand-primary/90 disabled:opacity-50 disabled:cursor-not-allowed'
                : 'bg-brand-primary border-brand-primary text-white hover:bg-brand-primary/90 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed'
                }`}
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>驗證中...</span>
                </>
              ) : (
                <span>確認</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PasswordModal;
