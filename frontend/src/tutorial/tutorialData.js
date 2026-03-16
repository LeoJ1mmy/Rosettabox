// 新手教學配置數據
// 這個文件包含所有教學步驟的配置，可以獨立移除

export const tutorialSteps = [
  {
    id: 1,
    title: "歡迎使用語音文字處理系統！",
    content: "我是你的專屬助手！讓我帶你了解這個系統的強大功能。我們從頁面頂部開始，由上到下逐步介紹。",
    target: null, // 無特定目標，顯示在中央
    position: "center",
    duration: 6000,
    isStart: true
  },
  {
    id: 2,
    title: "主題切換",
    content: "首先看右上角的主題切換按鈕，你可以切換明暗主題，選擇喜歡的視覺風格！",
    target: "[data-tutorial='theme-toggle']",
    position: "bottom",
    duration: 5000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "50%" // 圓形按鈕
    }
  },
  {
    id: 3,
    title: "導航標籤",
    content: "接下來是導航區域，有三個主要功能：媒體處理（上傳音頻）、隊列狀態（查看進度）。",
    target: "[data-tutorial='navigation']",
    position: "bottom",
    duration: 6000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "0"
    }
  },
  {
    id: 4,
    title: "AI智能整理開關",
    content: "這是最重要的功能！開啟後，AI會幫你自動整理和摘要內容。建議新手先開啟這個功能體驗看看！",
    target: "[data-tutorial='llm-toggle']",
    position: "bottom",
    duration: 7000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "0"
    }
  },
  {
    id: 5,
    title: "處理模式選擇",
    content: "這裡可以選擇不同的處理模式：會議記錄、講座筆記、通用模式等。每種模式都針對特定場景優化！",
    target: "[data-tutorial='processing-mode']",
    position: "bottom",
    duration: 7000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "0"
    }
  },
  {
    id: 6,
    title: "摘要標籤功能",
    content: "開啟AI智能整理後，可以在這裡選擇摘要標籤，讓AI按照特定類別整理內容，例如：重點整理、行動項目等。",
    target: "[data-tutorial='tag-selector']",
    position: "bottom",
    duration: 7000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "0"
    }
  },
  {
    id: 7,
    title: "Email 完成通知",
    content: "處理大文件時，可以開啟Email通知功能，完成後會自動發送通知到你的信箱，不用一直等待！",
    target: "[data-tutorial='email-notification']",
    position: "bottom",
    duration: 6000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "0"
    }
  },
  {
    id: 8,
    title: "文件上傳區域",
    content: "最後是上傳區域！支援多種音頻格式，你可以拖拽文件到這裡，或點擊選擇文件。支援最大3GB的文件哦！",
    target: "[data-tutorial='file-upload']",
    position: "top",
    duration: 7000,
    highlightStyle: {
      padding: "8px",
      borderRadius: "0"
    }
  },
  {
    id: 9,
    title: "教學完成！",
    content: "恭喜你完成了新手教學！現在你可以開始上傳音頻文件體驗系統功能了。記得，我隨時在右下角待命協助你！",
    target: null, // 無特定目標，顯示在中央
    position: "center",
    duration: 8000,
    isFinish: true
  }
];

// 教學消息（精靈自動輪播的消息）
export const tutorialMessages = [
  "💡 小提示：開啟AI智能整理能讓結果更清晰易讀！",
  "🚀 支援大文件處理，會議錄音、講座內容都能輕鬆搞定！",
  "📋 想查看處理進度？切換到「隊列狀態」標籤就能看到了！",
  "🎨 覺得介面太亮？試試切換到暗色主題！",
  "🔧 遇到問題？點我回報故障，開發者會盡快回覆！"
];

// 精靈彈出菜單選項
export const botMenuOptions = [
  {
    id: 'feedback',
    icon: '💬',
    label: '意見故障回饋',
    description: '回報問題或提供建議'
  },
  // 暫時隱藏教學功能
  // {
  //   id: 'tutorial',
  //   icon: '🎓',
  //   label: '新手教學',
  //   description: '快速學會使用系統'
  // }
];