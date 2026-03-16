import React, { useState } from 'react';
import { Sun, Moon, Settings } from 'lucide-react';
import PasswordModal from './PasswordModal';

const Header = ({ theme, toggleTheme, setActiveTab, adminPassword, setAdminPassword }) => {
  const [showPasswordModal, setShowPasswordModal] = useState(false);

  const handlePasswordSuccess = (password) => {
    setAdminPassword(password);
    setActiveTab('hotwords');
  };

  const handleAdminClick = () => {
    if (adminPassword) {
      setActiveTab('hotwords');
    } else {
      setShowPasswordModal(true);
    }
  };

  return (
    <>
      <div className="glass-panel relative overflow-hidden group mb-8 px-6 py-6">
        {/* Top gradient accent bar */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand-primary via-brand-secondary to-brand-accent opacity-60"></div>

        {/* Background glow behind logo */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-brand-primary/8 rounded-full blur-3xl pointer-events-none"></div>

        {/* 3-column grid: buttons stay top-aligned, logo in center */}
        <div className="grid grid-cols-[auto_1fr_auto] items-start relative z-10">
          {/* Admin Button - Left */}
          <button
            onClick={handleAdminClick}
            className={`w-10 h-10 flex items-center justify-center rounded-lg bg-glass-200 hover:bg-glass-300 hover:text-brand-accent transition-all duration-300 opacity-30 hover:opacity-100 mt-1 ${
              theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
            }`}
            title="熱詞管理"
          >
            <Settings size={18} />
          </button>

          {/* Centered Logo */}
          <div
            className="flex flex-col items-center cursor-pointer select-none"
            onClick={() => setActiveTab('upload')}
          >
            <img
              src="/logo.png"
              alt="RosettaBox"
              className={`h-16 sm:h-20 object-contain transition-transform duration-300 group-hover:scale-105 ${
                theme === 'dark' ? 'invert brightness-200' : ''
              }`}
            />
            <p className={`text-xs tracking-[0.2em] uppercase mt-1.5 font-medium ${
              theme === 'dark' ? 'text-slate-400' : 'text-slate-400'
            }`}>
              您的資料，由我整理出價值
            </p>
          </div>

          {/* Theme Toggle - Right */}
          <button
            onClick={toggleTheme}
            data-tutorial="theme-toggle"
            className={`p-2.5 rounded-lg bg-glass-200 hover:bg-glass-300 hover:text-brand-primary transition-all duration-300 mt-1 ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}
            title={theme === 'dark' ? '切換至淺色模式' : '切換至深色模式'}
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </div>

      {/* Modals */}
      <PasswordModal
        isOpen={showPasswordModal}
        onClose={() => setShowPasswordModal(false)}
        onSuccess={handlePasswordSuccess}
        theme={theme}
      />
    </>
  );
};

export default Header;
