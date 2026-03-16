# 外部 API 接口規格文檔 - 模組化導航索引

## 基本信息

- **API 版本**: v1
- **基礎 URL**: `http://{server_url}:3080/external/v1`
- **認證方式**: Client ID Header 認證
- **數據格式**: JSON / Multipart Form Data

---

## 📚 API 模組導航

本文檔已採用 MECE 原則進行模組化重構，提供更清晰的導航和專業的功能分類。

### 🔐 核心功能模組

#### [1. 認證與客戶端管理](api-modules/authentication.md)
- **功能範圍**: 客戶端註冊、認證機制、權限管理
- **主要端點**: `/auth/register`
- **適用場景**: 新應用接入、身份驗證、安全管理
- **核心內容**:
  - 客戶端註冊流程
  - Header 認證機制
  - 認證錯誤處理
  - 安全最佳實踐

#### [2. 系統管理](api-modules/system-management.md)
- **功能範圍**: 系統狀態監控、配置管理、服務健康檢查
- **主要端點**: `/status`, `/config`
- **適用場景**: 系統運維、配置調整、故障診斷
- **核心內容**:
  - 系統健康狀態檢查
  - 處理配置管理
  - 模型可用性查詢
  - 服務狀態監控

### 🎯 處理功能模組

#### [3. 音頻處理](api-modules/audio-processing.md)
- **功能範圍**: 音頻轉錄、說話人分離、AI 文字處理
- **主要端點**: `/audio/process`
- **適用場景**: 會議錄音處理、語音轉文字、多媒體分析
- **核心內容**:
  - 多格式音頻支援
  - Whisper 語音轉錄
  - 說話人分離技術
  - AI 智能文字處理
  - 時間戳記與統計資訊

#### [4. 文字處理](api-modules/text-processing.md)
- **功能範圍**: 單一文字處理、批次文字處理、AI 智能分析
- **主要端點**: `/text/process`, `/batch/text`
- **適用場景**: 文檔整理、內容分析、批量處理
- **核心內容**:
  - 單一文字智能處理
  - 批次文字處理
  - 多種處理模式
  - 結構化輸出格式

### 🔧 支援與整合模組

#### [5. 錯誤處理指南](api-modules/error-handling.md)
- **功能範圍**: 錯誤代碼定義、故障排除、最佳實踐
- **適用場景**: 錯誤診斷、問題解決、系統除錯
- **核心內容**:
  - 統一錯誤格式
  - 完整錯誤代碼對照表
  - 常見問題解決方案
  - 錯誤處理最佳實踐
  - 除錯指南與診斷方法

#### [6. 整合指南與範例](api-modules/integration-guide.md)
- **功能範圍**: 開發者範例、使用限制、技術支援
- **適用場景**: 應用開發、系統整合、技術實現
- **核心內容**:
  - 完整的 Python/JavaScript 範例
  - React Web 應用範例
  - 使用限制與配額說明
  - 性能優化建議
  - 技術支援與更新日誌

---

## 🚀 快速開始指南

### 基本使用流程

1. **[認證設定](api-modules/authentication.md#客戶端註冊)**: 註冊客戶端獲取 API 存取權限
2. **[系統檢查](api-modules/system-management.md#獲取系統狀態)**: 確認系統服務狀態正常
3. **選擇處理方式**:
   - **音頻處理**: 使用 [音頻處理 API](api-modules/audio-processing.md)
   - **文字處理**: 使用 [文字處理 API](api-modules/text-processing.md)
4. **[錯誤處理](api-modules/error-handling.md)**: 參考錯誤處理指南解決問題
5. **[整合應用](api-modules/integration-guide.md)**: 使用完整範例進行系統整合

### 核心端點速覽

| 端點類型 | 路徑 | 功能 | 文檔連結 |
|----------|------|------|----------|
| 認證 | `/auth/register` | 客戶端註冊 | [認證管理](api-modules/authentication.md) |
| 系統 | `/status` | 系統狀態 | [系統管理](api-modules/system-management.md) |
| 系統 | `/config` | 配置管理 | [系統管理](api-modules/system-management.md) |
| 音頻 | `/audio/process` | 音頻處理 | [音頻處理](api-modules/audio-processing.md) |
| 文字 | `/text/process` | 單一文字處理 | [文字處理](api-modules/text-processing.md) |
| 文字 | `/batch/text` | 批次文字處理 | [文字處理](api-modules/text-processing.md) |

---

## 🎯 使用場景指南

### 會議記錄自動化
1. 使用 [音頻處理 API](api-modules/audio-processing.md) 處理會議錄音
2. 啟用說話人分離功能識別發言者
3. 使用 `meeting` 模式進行 AI 智能整理

### 文檔批量處理
1. 使用 [批次文字處理](api-modules/text-processing.md#批次文字處理)
2. 根據內容類型選擇合適的處理模式
3. 設定適當的詳細程度level

### 多媒體內容分析
1. 支援多種音頻/視頻格式輸入
2. 結合 Whisper 轉錄和 AI 分析
3. 輸出結構化的分析結果

---

## 📋 技術規範

### 支援的格式與限制

| 項目 | 規範 | 詳細說明 |
|------|------|----------|
| **音頻格式** | wav, mp3, flac, m4a, ogg, wma, aac | 推薦使用 WAV 或 MP3 |
| **視頻格式** | mp4, avi, mov, mkv, webm, wmv, flv | 自動提取音頻進行處理 |
| **文件大小** | 最大 100MB | 音頻/視頻文件限制 |
| **音頻長度** | 最長 2 小時 | 單個文件處理時長限制 |
| **文字長度** | 最多 50,000 字符 | 單次文字處理限制 |
| **批次大小** | 最多 100 個項目 | 批次處理項目數限制 |
| **請求頻率** | 每分鐘 60 次 | API 調用頻率限制 |

### 支援的模型

| 模型類型 | 可用選項 | 推薦用途 |
|----------|----------|----------|
| **Whisper** | tiny, base, small, medium, large | base (平衡), large (高精度) |
| **AI 模型** | phi4-mini:3.8b, Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M | TAIDE (中文優化) |

---

## 📞 技術支援

### 即時系統資訊
使用 [`/status` 端點](api-modules/system-management.md#獲取系統狀態) 獲取即時系統狀態和服務可用性。

### 問題報告與建議
- **錯誤診斷**: 參考 [錯誤處理指南](api-modules/error-handling.md)
- **整合支援**: 查看 [完整開發者範例](api-modules/integration-guide.md)
- **功能建議**: 歡迎提出 API 改進建議

---

## 📄 版本資訊

### 當前版本: v1.0.0 (2025-09-11)

**主要特性**:
- ✅ 模組化 API 文檔架構
- ✅ 完整的認證與權限系統
- ✅ 多格式音頻處理能力
- ✅ 智能文字處理與批次操作
- ✅ 說話人分離技術
- ✅ 多 AI 模型支援
- ✅ 統一錯誤處理機制
- ✅ 豐富的開發者範例

**更新說明**:
- 📁 文檔結構按 MECE 原則重新組織
- 🔍 提供清晰的模組導航和功能分類
- 📚 各模組獨立維護，便於查閱和更新
- 🔗 完善的交叉引用和導航連結

---

*本文檔採用模組化設計，各功能模組獨立維護。如需查看具體 API 詳情，請點擊對應模組連結。*

*文檔將持續更新，請關注最新版本。*