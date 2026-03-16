import React from 'react';
import { Upload, FileText, List, Loader2, Type } from 'lucide-react';

const tabs = [
  { id: 'upload',  icon: Upload,   label: '上傳音頻' },
  { id: 'text',    icon: Type,     label: '文字處理' },
  { id: 'results', icon: FileText, label: '處理結果' },
  { id: 'queue',   icon: List,     label: '處理隊列' },
];

const Navigation = ({ activeTab, setActiveTab, theme, processing, hasResult }) => {
  const inactive = theme === 'dark'
    ? 'text-slate-300 hover:text-white hover:bg-white/5'
    : 'text-slate-700 hover:text-slate-900 hover:bg-slate-200/50';

  const active = theme === 'dark'
    ? 'bg-brand-primary text-white shadow-lg shadow-brand-primary/25'
    : 'bg-brand-primary text-slate-900 shadow-lg shadow-brand-primary/30 font-bold';

  return (
    <div className="flex justify-center px-2">
      <div className="glass-panel p-1.5 sm:p-2 grid grid-cols-4 gap-1 sm:gap-1.5 w-full max-w-2xl">
        {tabs.map(({ id, icon: Icon, label }) => {
          const isActive = activeTab === id;
          const isResults = id === 'results';

          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`relative flex items-center justify-center gap-1.5 sm:gap-2 px-1 sm:px-4 py-2.5 sm:py-3 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-300 whitespace-nowrap ${
                isActive ? active : inactive
              }`}
            >
              {isResults && processing ? (
                <Loader2 size={16} className="animate-spin shrink-0" />
              ) : (
                <Icon size={16} className="shrink-0" />
              )}
              {label}
              {isResults && (processing || hasResult) && !isActive && (
                <span className={`absolute -top-1 -right-1 w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full ${
                  processing
                    ? 'bg-brand-primary animate-pulse'
                    : 'bg-emerald-400'
                }`} />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default Navigation;
