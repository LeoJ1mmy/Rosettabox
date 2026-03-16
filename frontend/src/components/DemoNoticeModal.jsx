import React, { useState, useEffect } from 'react';
import { X, AlertTriangle, Clock, Wrench } from 'lucide-react';
import { DEMO_NOTICE_CONFIG } from '../config/demoNoticeConfig';

const ICON_MAP = {
  warning: Wrench,
  info: Clock,
};

const TYPE_STYLES = {
  warning: {
    panelDark: 'dark:bg-brand-accent/10 dark:border-brand-accent/30',
    panelLight: 'bg-teal-50 border-teal-300',
    iconDark: 'dark:text-brand-accent',
    iconLight: 'text-teal-600',
    highlightDark: 'dark:text-brand-accent',
    highlightLight: 'text-teal-700',
  },
  info: {
    panelDark: 'dark:bg-brand-primary/10 dark:border-brand-primary/30',
    panelLight: 'bg-blue-50 border-blue-300',
    iconDark: 'dark:text-brand-primary',
    iconLight: 'text-blue-600',
    highlightDark: 'dark:text-brand-primary',
    highlightLight: 'text-blue-700',
  },
};

const DemoNoticeModal = () => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if feature is enabled
    if (!DEMO_NOTICE_CONFIG.ENABLED) return;

    // Check if user has already dismissed the modal
    const dismissed = localStorage.getItem(DEMO_NOTICE_CONFIG.STORAGE_KEY);
    if (!dismissed) {
      setIsVisible(true);
    }
  }, []);

  const handleDismiss = () => {
    localStorage.setItem(DEMO_NOTICE_CONFIG.STORAGE_KEY, 'true');
    setIsVisible(false);
  };

  // Don't render if disabled or dismissed
  if (!DEMO_NOTICE_CONFIG.ENABLED || !isVisible) return null;

  const { header, notices, dismissButtonText } = DEMO_NOTICE_CONFIG;

  // 🔒 安全修復：使用 React 元素替代 dangerouslySetInnerHTML
  const renderDescription = (notice) => {
    if (!notice.highlights || notice.highlights.length === 0) {
      return notice.description;
    }

    const styles = TYPE_STYLES[notice.type] || TYPE_STYLES.info;
    const parts = [];
    let remaining = notice.description;
    let key = 0;

    // 按順序處理每個高亮文字
    notice.highlights.forEach((text) => {
      const index = remaining.indexOf(text);
      if (index !== -1) {
        // 添加高亮前的普通文字
        if (index > 0) {
          parts.push(<span key={key++}>{remaining.substring(0, index)}</span>);
        }
        // 添加高亮文字
        parts.push(
          <span key={key++} className={`${styles.highlightLight} ${styles.highlightDark} font-semibold`}>
            {text}
          </span>
        );
        remaining = remaining.substring(index + text.length);
      }
    });

    // 添加剩餘文字
    if (remaining) {
      parts.push(<span key={key++}>{remaining}</span>);
    }

    return <>{parts}</>;
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="w-full max-w-lg p-6 shadow-2xl relative animate-in zoom-in-95 duration-300 rounded-2xl border-2 bg-white dark:bg-slate-800 border-slate-300 dark:border-brand-secondary/30">

        {/* Close button */}
        <button
          type="button"
          onClick={handleDismiss}
          className="absolute top-4 right-4 text-gray-500 hover:text-black dark:text-gray-400 dark:hover:text-white transition-colors"
          aria-label="關閉"
        >
          <X size={20} />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 rounded-xl bg-brand-secondary/20 border border-brand-secondary/30">
            <AlertTriangle className="text-brand-secondary" size={28} />
          </div>
          <div>
            <h2 className="text-xl font-display font-bold text-black dark:text-white">
              {header.title}
            </h2>
            <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{header.subtitle}</p>
          </div>
        </div>

        {/* Dynamic Notices */}
        <div className="space-y-4 mb-6">
          {notices.map((notice) => {
            const Icon = ICON_MAP[notice.type] || Clock;
            const styles = TYPE_STYLES[notice.type] || TYPE_STYLES.info;

            return (
              <div
                key={notice.id}
                className={`rounded-xl p-4 border-2 ${styles.panelLight} ${styles.panelDark}`}
              >
                <div className="flex items-start gap-3">
                  <Icon
                    className={`${styles.iconLight} ${styles.iconDark} mt-0.5 flex-shrink-0`}
                    size={20}
                  />
                  <div>
                    <p className="text-black dark:text-white font-bold mb-1">
                      {notice.title}
                    </p>
                    <p className="text-sm text-gray-800 dark:text-gray-300 font-medium">
                      {renderDescription(notice)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleDismiss}
            className="px-8 py-2.5 font-medium rounded-lg border-2 border-brand-primary bg-brand-primary/20 hover:bg-brand-primary/30 text-black dark:text-white font-bold transition-all duration-200"
          >
            {dismissButtonText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DemoNoticeModal;
