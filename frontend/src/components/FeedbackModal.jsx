import React, { useState, useCallback } from 'react';
import { X, Send, Loader2, MessageSquare, Bug, Lightbulb, HelpCircle } from 'lucide-react';

const FeedbackModal = ({ isOpen, onClose, theme }) => {
  const [formData, setFormData] = useState({
    type: 'bug',
    subject: '',
    message: '',
    userEmail: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.message.trim()) return;

    setIsSubmitting(true);
    setSubmitStatus(null);

    try {
      const response = await fetch('/api/feedback/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        setSubmitStatus('success');
        setFormData({
          type: 'bug',
          subject: '',
          message: '',
          userEmail: ''
        });
        setTimeout(() => {
          onClose();
          setSubmitStatus(null);
        }, 2000);
      } else {
        setSubmitStatus('error');
      }
    } catch (error) {
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className={`glass-panel w-full max-w-md shadow-2xl relative animate-in zoom-in-95 duration-200 p-0 overflow-hidden ${
        theme === 'dark' ? '' : 'bg-white border-slate-300'
      }`}>
        <div className={`flex items-center justify-between p-5 border-b ${
          theme === 'dark' ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-slate-50'
        }`}>
          <h2 className={`text-lg font-display font-bold flex items-center gap-2 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            <MessageSquare className="text-brand-primary" size={20} />
            故障回報及建議回饋
          </h2>
          <button
            onClick={onClose}
            className={`transition-colors ${
              theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className={`block text-sm font-medium mb-2 ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}>
              回饋類型
            </label>
            <div className="relative">
              <select
                name="type"
                value={formData.type}
                onChange={handleChange}
                className={`glass-input w-full appearance-none ${
                  theme === 'dark' ? '' : 'bg-slate-50 border-slate-300 text-slate-900'
                }`}
              >
                <option value="bug">故障回報</option>
                <option value="suggestion">功能建議</option>
                <option value="improvement">改進建議</option>
                <option value="other">其他</option>
              </select>
              <div className={`absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none ${
                theme === 'dark' ? 'text-slate-300' : 'text-slate-500'
              }`}>
                {formData.type === 'bug' && <Bug size={16} />}
                {formData.type === 'suggestion' && <Lightbulb size={16} />}
                {formData.type === 'improvement' && <Loader2 size={16} />}
                {formData.type === 'other' && <HelpCircle size={16} />}
              </div>
            </div>
          </div>

          <div>
            <label className={`block text-sm font-medium mb-2 ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}>
              主題 (選填)
            </label>
            <input
              type="text"
              name="subject"
              value={formData.subject}
              onChange={handleChange}
              placeholder="簡短描述問題或建議..."
              className={`glass-input w-full ${
                theme === 'dark' ? '' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-400'
              }`}
            />
          </div>

          <div>
            <label className={`block text-sm font-medium mb-2 ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}>
              詳細內容 *
            </label>
            <textarea
              name="message"
              value={formData.message}
              onChange={handleChange}
              required
              rows={4}
              placeholder="請詳細描述遇到的問題或您的建議..."
              className={`glass-input w-full resize-none ${
                theme === 'dark' ? '' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-400'
              }`}
            />
          </div>

          <div>
            <label className={`block text-sm font-medium mb-2 ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}>
              您的 Email (選填)
            </label>
            <input
              type="email"
              name="userEmail"
              value={formData.userEmail}
              onChange={handleChange}
              placeholder="如需回覆請留下您的 Email..."
              className={`glass-input w-full ${
                theme === 'dark' ? '' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-400'
              }`}
            />
          </div>

          {submitStatus === 'success' && (
            <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
              theme === 'dark'
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                : 'bg-emerald-50 border border-emerald-200 text-emerald-700'
            }`}>
              <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
              回饋已成功送出，感謝您的意見！
            </div>
          )}

          {submitStatus === 'error' && (
            <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
              theme === 'dark'
                ? 'bg-red-500/10 border border-red-500/20 text-red-400'
                : 'bg-red-50 border border-red-200 text-red-700'
            }`}>
              <div className="w-2 h-2 rounded-full bg-red-500"></div>
              送出失敗，請稍後再試。
            </div>
          )}

          <div className="flex space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className={`flex-1 glass-button ${
                theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !formData.message.trim()}
              className="flex-1 glass-button bg-brand-primary/20 hover:bg-brand-primary/30 text-brand-primary border-brand-primary/30 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>送出中...</span>
                </>
              ) : (
                <>
                  <Send size={16} />
                  <span>送出</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FeedbackModal;
