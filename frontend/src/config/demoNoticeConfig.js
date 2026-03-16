/**
 * Demo Notice Configuration / 示範階段通知設定
 *
 * 停用示範通知彈窗的方式：
 * 1. 將 ENABLED 設為 false，或
 * 2. 刪除此檔案並從 App.jsx 移除 DemoNoticeModal 的引入
 */

export const DEMO_NOTICE_CONFIG = {
  // 設為 false 可完全停用彈窗
  ENABLED: true,

  // LocalStorage 鍵值，用於追蹤是否已關閉
  STORAGE_KEY: 'demo_notice_dismissed',

  // 標題內容
  header: {
    title: '示範階段公告',
    subtitle: '重要資訊',
  },

  // 要顯示的通知項目
  notices: [
    {
      id: 'demo-phase',
      type: 'warning', // 'warning' | 'info'
      title: '系統目前為示範階段',
      description: '本系統目前處於示範階段，功能與服務可能會在不另行通知的情況下進行調整。',
    },
    {
      id: 'maintenance',
      type: 'info',
      title: '每日維護時段',
      description: '系統更新與修復作業將於每日 15:30 至 18:30 進行，期間系統可能會暫時無法使用。',
      highlights: ['15:30', '18:30'], // 要強調的文字
    },
    {
      id: 'file-size-limit',
      type: 'info',
      title: '檔案大小限制',
      description: '上傳檔案請勿超過 500MB，超過限制的檔案將無法上傳。',
      highlights: ['500MB'], // 要強調的文字
    },
  ],

  // 按鈕文字
  dismissButtonText: '我已瞭解',
};
