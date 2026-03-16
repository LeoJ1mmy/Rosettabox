import React, { Component } from 'react';

class TutorialErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // 更新 state 使下一次渲染顯示降級後的 UI
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // 錯誤已被捕獲，清理副作用
    
    // 清理任何教學系統留下的副作用
    try {
      // 恢復頁面滾動
      document.body.style.overflow = '';
      document.body.style.overflowY = '';
      document.body.style.overflowX = '';
      document.documentElement.style.overflow = '';
      
      // 清理教學屬性
      const elements = document.querySelectorAll('[data-tutorial]');
      elements.forEach(el => {
        if (el.style.border) el.style.border = '';
        if (el.style.backgroundColor) el.style.backgroundColor = '';
        if (el.style.boxShadow) el.style.boxShadow = '';
      });
    } catch (cleanupError) {
      // 清理錯誤，靜默處理
    }
  }

  // 優雅重置狀態，不刷新整個頁面
  handleReset = () => {
    // 清理教學系統副作用
    this.cleanupTutorialEffects();
    // 重置狀態，讓 React 重新渲染子組件
    this.setState({ hasError: false, error: null });
  };

  // 🔧 新增：清理教學系統副作用
  cleanupTutorialEffects = () => {
    try {
      // 恢復頁面滾動
      document.body.style.overflow = '';
      document.body.style.overflowY = '';
      document.body.style.overflowX = '';
      document.documentElement.style.overflow = '';

      // 清理教學屬性
      const elements = document.querySelectorAll('[data-tutorial]');
      elements.forEach(el => {
        if (el.style.border) el.style.border = '';
        if (el.style.backgroundColor) el.style.backgroundColor = '';
        if (el.style.boxShadow) el.style.boxShadow = '';
      });

      // 移除可能遺留的教學覆蓋層
      const overlays = document.querySelectorAll('.tutorial-overlay, .tutorial-highlight');
      overlays.forEach(el => el.remove());
    } catch (cleanupError) {
      // 清理教學副作用錯誤，靜默處理
    }
  };

  render() {
    if (this.state.hasError) {
      // 你可以自定義降級後的 UI
      return (
        <div className="fixed bottom-4 right-4 z-50 bg-red-500 text-white p-4 rounded shadow-lg max-w-sm">
          <h3 className="font-bold mb-2">教學系統發生錯誤</h3>
          <p className="text-sm mb-3">教學功能暫時無法使用</p>
          <button
            onClick={this.handleReset}
            className="bg-white text-red-500 px-3 py-1 rounded text-sm font-medium hover:bg-red-50"
          >
            重新載入
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default TutorialErrorBoundary;