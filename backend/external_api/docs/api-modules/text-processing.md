# Text Processing API

## 概覽

本模組提供純文字的 AI 智能處理功能，包括單一文字處理和批次處理能力，適用於已有文字內容的場景。

**認證要求**: 所有請求需要提供 `X-Client-ID` Header
**Content-Type**: `application/json`

---

## 單一文字處理

### 處理單一文字內容

對提供的文字進行 AI 整理、結構化和優化處理。

#### 請求

```http
POST /external/v1/text/process
X-Client-ID: your_client_id
Content-Type: application/json

{
  "text": "今天的會議討論了很多重要議題，包括新產品開發、市場策略、以及團隊擴張計畫。",
  "processing_mode": "meeting",
  "detail_level": "normal",
  "ai_model": "gpt-oss:20b"
}
```

#### 請求參數

| 參數 | 類型 | 必需 | 可選值 | 描述 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 要處理的文字內容（最多 50,000 字符） |
| `processing_mode` | string | 否 | default, meeting, lecture, interview | 處理模式 |
| `detail_level` | string | 否 | simple, normal, detailed | 處理詳細程度 |
| `ai_model` | string | 否 | 見模型列表 | 使用的 AI 模型 |

#### 成功回應

```json
{
  "status": "success",
  "client_id": "client_12345678",
  "original_text": "今天的會議討論了很多重要議題，包括新產品開發、市場策略、以及團隊擴張計畫。",
  "processed_text": "## 會議記錄\n\n### 主要討論議題\n1. **新產品開發**\n   - 產品功能規劃\n   - 開發時程安排\n\n2. **市場策略**\n   - 目標客群分析\n   - 競爭對手研究\n\n3. **團隊擴張計畫**\n   - 人力需求評估\n   - 招募策略制定",
  "processing_config": {
    "ai_model": "gpt-oss:20b",
    "processing_mode": "meeting",
    "detail_level": "normal"
  },
  "statistics": {
    "original_length": 42,
    "processed_length": 156,
    "compression_ratio": 0.27,
    "processing_time": 3.2,
    "word_count": 45
  },
  "timestamp": "2025-09-11 12:15:30"
}
```

---

## 批次文字處理

### 批次處理多段文字

同時處理多段文字內容，適用於需要處理大量文字片段的場景。

#### 請求

```http
POST /external/v1/batch/text
X-Client-ID: your_client_id
Content-Type: application/json

{
  "texts": [
    "第一段會議記錄...",
    "第二段討論內容...",
    "",
    "第三段決議事項..."
  ],
  "processing_mode": "meeting",
  "detail_level": "normal",
  "ai_model": "phi4-mini:3.8b"
}
```

#### 請求參數

| 參數 | 類型 | 必需 | 可選值 | 描述 |
|------|------|------|--------|------|
| `texts` | array | 是 | - | 文字陣列（最多 100 個項目） |
| `processing_mode` | string | 否 | default, meeting, lecture, interview | 處理模式 |
| `detail_level` | string | 否 | simple, normal, detailed | 處理詳細程度 |
| `ai_model` | string | 否 | 見模型列表 | 使用的 AI 模型 |

#### 成功回應

```json
{
  "status": "success",
  "client_id": "client_12345678",
  "summary": {
    "total_items": 4,
    "success_count": 3,
    "error_count": 0,
    "skip_count": 1,
    "total_processing_time": 12.5,
    "average_time_per_item": 3.1
  },
  "results": [
    {
      "index": 0,
      "status": "success",
      "original_text": "第一段會議記錄...",
      "processed_text": "## 會議記錄 - 第一部分\n\n...",
      "processing_time": 4.2,
      "statistics": {
        "original_length": 25,
        "processed_length": 120,
        "word_count": 32
      }
    },
    {
      "index": 1,
      "status": "success",
      "original_text": "第二段討論內容...",
      "processed_text": "## 討論內容整理\n\n...",
      "processing_time": 3.8,
      "statistics": {
        "original_length": 22,
        "processed_length": 98,
        "word_count": 28
      }
    },
    {
      "index": 2,
      "status": "skipped",
      "reason": "空白內容",
      "original_text": ""
    },
    {
      "index": 3,
      "status": "success",
      "original_text": "第三段決議事項...",
      "processed_text": "## 決議事項\n\n...",
      "processing_time": 4.5,
      "statistics": {
        "original_length": 20,
        "processed_length": 85,
        "word_count": 25
      }
    }
  ],
  "processing_config": {
    "ai_model": "phi4-mini:3.8b",
    "processing_mode": "meeting",
    "detail_level": "normal"
  },
  "timestamp": "2025-09-11 12:20:45"
}
```

---

## 處理模式詳細說明

### 模式類型

1. **default**:
   - 通用文字處理
   - 基本結構化整理
   - 適用於各種類型文件

2. **meeting**:
   - 會議記錄優化
   - 議題分類和摘要
   - 行動項目提取

3. **lecture**:
   - 演講內容結構化
   - 重點概念提取
   - 階層式組織

4. **interview**:
   - 訪談對話整理
   - 問答結構化
   - 關鍵資訊提取

### 詳細程度設定

1. **simple**:
   - 簡潔摘要
   - 關鍵點提取
   - 適合快速瀏覽

2. **normal**:
   - 標準結構化
   - 平衡詳細度
   - 適合一般使用

3. **detailed**:
   - 詳細分析
   - 完整結構化
   - 適合深度分析

---

## 回應欄位說明

### 單一處理回應

| 欄位 | 類型 | 描述 |
|------|------|------|
| `original_text` | string | 原始輸入文字 |
| `processed_text` | string | AI 處理後的結構化文字 |
| `processing_config` | object | 使用的處理配置 |
| `statistics` | object | 處理統計資訊 |

### 批次處理回應

| 欄位 | 類型 | 描述 |
|------|------|------|
| `summary` | object | 批次處理統計摘要 |
| `results` | array | 各個項目的處理結果 |
| `processing_config` | object | 使用的處理配置 |

### 批次處理狀態類型

- **success**: 處理成功
- **error**: 處理出現錯誤
- **skipped**: 跳過處理（如空白內容）

---

## 使用限制

### 文字內容限制

- **單一文字最大長度**: 50,000 字符
- **批次處理最大項目數**: 100 個
- **空白內容處理**: 自動跳過空字串
- **特殊字符**: 支援 Unicode 字符

### 性能考量

- **處理時間**: 依據文字長度和模型複雜度而定
- **並發限制**: 同時最多 5 個處理任務
- **記憶體使用**: 大型文字可能需要更多處理時間

---

## 最佳實踐

### 文字準備

1. **內容清理**: 移除不必要的格式字符
2. **分段處理**: 將長文本分割為邏輯段落
3. **語言一致性**: 確保文字語言與設定一致

### 批次處理策略

1. **合理分組**: 將相關內容組織在一起
2. **錯誤處理**: 檢查每個項目的處理狀態
3. **進度監控**: 利用統計資訊監控處理進度

### 結果應用

1. **格式保持**: 處理結果通常為 Markdown 格式
2. **結構利用**: 充分利用 AI 生成的結構化內容
3. **品質驗證**: 檢查處理結果的邏輯性和完整性

---

## 常見錯誤

| 錯誤碼 | 描述 | 解決方法 |
|--------|------|----------|
| `TEXT_TOO_LONG` | 文字超過長度限制 | 分割文字或使用批次處理 |
| `EMPTY_TEXT` | 提供的文字為空 | 確保文字內容不為空 |
| `INVALID_ENCODING` | 文字編碼問題 | 使用 UTF-8 編碼 |
| `BATCH_TOO_LARGE` | 批次項目過多 | 減少批次大小 |
| `MODEL_UNAVAILABLE` | 指定模型不可用 | 選擇其他可用模型 |

---

## 相關模組

- **[認證管理 API](authentication.md)** - 客戶端註冊和認證
- **[系統管理 API](system-management.md)** - 系統狀態和配置
- **[音頻處理 API](audio-processing.md)** - 音頻轉錄和處理
- **[錯誤處理指南](error-handling.md)** - 完整的錯誤處理文檔
- **[整合指南](integration-guide.md)** - 開發者範例和最佳實踐

---

*更新時間: 2025-09-11*