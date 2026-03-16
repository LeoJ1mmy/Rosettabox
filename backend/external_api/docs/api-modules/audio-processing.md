# Audio Processing API

## 概覽

本模組提供音頻文件的語音轉文字和 AI 智能處理功能，支援多種音頻格式和說話人分離功能。

**認證要求**: 所有請求需要提供 `X-Client-ID` Header
**Content-Type**: `multipart/form-data`

---

## 音頻處理

### 處理音頻文件

上傳音頻文件進行語音轉文字和 AI 整理分析。

#### 請求

```http
POST /external/v1/audio/process
X-Client-ID: your_client_id
Content-Type: multipart/form-data

audio: [音頻文件二進位數據]
whisper_model: base
enable_diarization: true
enable_llm: true
processing_mode: meeting
detail_level: normal
ai_model: Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M
language: chinese
```

#### 請求參數

| 參數 | 類型 | 必需 | 可選值 | 描述 |
|------|------|------|--------|------|
| `audio` | file | 是 | - | 音頻文件（支援多種格式） |
| `whisper_model` | string | 否 | tiny, base, small, medium, large | Whisper 模型大小 |
| `enable_diarization` | boolean | 否 | true, false | 是否啟用說話人分離 |
| `enable_llm` | boolean | 否 | true, false | 是否啟用 AI 文字處理 |
| `processing_mode` | string | 否 | default, meeting, lecture, interview | 處理模式 |
| `detail_level` | string | 否 | simple, normal, detailed | 詳細程度 |
| `ai_model` | string | 否 | 見模型列表 | AI 處理模型 |
| `language` | string | 否 | chinese, english, auto | 語言設定 |

---

## 支援格式

### 音頻格式

- **wav**: 標準音頻格式，推薦使用
- **mp3**: 常用壓縮格式
- **flac**: 無損壓縮格式
- **m4a**: AAC 音頻格式
- **ogg**: 開源音頻格式
- **wma**: Windows Media Audio
- **aac**: 高級音頻編碼

### 視頻格式

- **mp4**: 標準視頻格式
- **avi**: Audio Video Interleave
- **mov**: QuickTime 格式
- **mkv**: Matroska 視頻
- **webm**: Web 視頻格式
- **wmv**: Windows Media Video
- **flv**: Flash 視頻格式

### 文件限制

- **最大文件大小**: 100MB
- **最大音頻長度**: 2 小時
- **推薦格式**: WAV 或 MP3
- **推薦採樣率**: 16kHz 或以上

---

## 成功回應

```json
{
  "status": "success",
  "client_id": "client_12345678",
  "file_info": {
    "filename": "meeting_record.wav",
    "file_size": 15728640,
    "duration": 180.5,
    "format": "wav",
    "sample_rate": 16000,
    "channels": 1,
    "processing_time": {
      "whisper": 12.5,
      "diarization": 8.2,
      "ai_processing": 15.3,
      "total": 36.0
    }
  },
  "transcription": {
    "raw_text": "今天的會議主要討論了新產品的開發進度，我們需要在下個月完成第一階段的開發，然後進行測試。大家對於這個時程安排有什麼意見嗎？接下來討論市場策略部分，我認為我們應該先做市場調研。",
    "diarized_text": "Speaker_0: 今天的會議主要討論了新產品的開發進度，我們需要在下個月完成第一階段的開發，然後進行測試。大家對於這個時程安排有什麼意見嗎？\nSpeaker_1: 接下來討論市場策略部分，我認為我們應該先做市場調研。",
    "ai_processed_text": "## 會議摘要\n\n### 主要議題\n1. **新產品開發進度** (Speaker_0)\n   - 第一階段開發目標：下個月完成\n   - 後續安排：完成開發後進行測試\n   - 需要團隊成員確認時程安排的可行性\n\n2. **市場策略討論** (Speaker_1)\n   - 建議優先進行市場調研\n   - 制定完整的市場策略方案\n\n### 待討論事項\n- 團隊對開發時程的意見和建議\n- 市場調研的具體實施計畫",
    "language": "chinese",
    "word_count": 450,
    "whisper_confidence": 0.95
  },
  "timestamps": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "今天的會議主要討論了",
      "speaker": "Speaker_0"
    },
    {
      "start": 3.5,
      "end": 8.2,
      "text": "新產品的開發進度",
      "speaker": "Speaker_0"
    }
  ],
  "diarization": {
    "enabled": true,
    "speaker_count": 3,
    "speakers": [
      {
        "speaker_id": "Speaker_0",
        "total_time": 120.5,
        "segments": 15
      },
      {
        "speaker_id": "Speaker_1",
        "total_time": 45.2,
        "segments": 8
      },
      {
        "speaker_id": "Speaker_2",
        "total_time": 14.8,
        "segments": 3
      }
    ]
  },
  "processing_config": {
    "whisper_model": "base",
    "ai_model": "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M",
    "processing_mode": "meeting",
    "detail_level": "normal",
    "enable_diarization": true,
    "language": "chinese"
  },
  "statistics": {
    "compression_ratio": 0.65,
    "processing_speed": 5.0
  }
}
```

---

## 回應欄位說明

### 文件資訊 (file_info)

| 欄位 | 類型 | 描述 |
|------|------|------|
| `filename` | string | 原始文件名稱 |
| `file_size` | integer | 文件大小（字節） |
| `duration` | float | 音頻時長（秒） |
| `format` | string | 音頻格式 |
| `sample_rate` | integer | 採樣率 |
| `channels` | integer | 聲道數 |
| `processing_time` | object | 各階段處理時間 |

### 轉錄結果 (transcription)

| 欄位 | 類型 | 描述 |
|------|------|------|
| `raw_text` | string | Whisper 原始轉錄文字 |
| `diarized_text` | string | 標記說話人的文字 |
| `ai_processed_text` | string | AI 處理後的結構化文字 |
| `language` | string | 檢測到的語言 |
| `word_count` | integer | 字數統計 |
| `whisper_confidence` | float | 轉錄可信度分數 |

### 時間戳記 (timestamps)

| 欄位 | 類型 | 描述 |
|------|------|------|
| `start` | float | 開始時間（秒） |
| `end` | float | 結束時間（秒） |
| `text` | string | 對應文字片段 |
| `speaker` | string | 說話人 ID（如果啟用分離） |

### 說話人分離 (diarization)

| 欄位 | 類型 | 描述 |
|------|------|------|
| `enabled` | boolean | 是否已啟用說話人分離 |
| `speaker_count` | integer | 檢測到的說話人數量 |
| `speakers` | array | 各說話人的詳細統計 |

---

## 處理最佳實踐

### 音頻品質優化

1. **採樣率**: 使用 16kHz 或更高採樣率
2. **格式選擇**: WAV 格式提供最佳相容性
3. **雜音處理**: 預先去除背景雜音可提高準確度
4. **音量正規化**: 確保音量適中，避免過度壓縮

### 性能優化

1. **模型選擇**: 根據需求平衡速度和準確度
   - `tiny`: 最快，適合即時應用
   - `base`: 平衡選擇，適合大多數場景
   - `large`: 最高準確度，適合重要文件

2. **說話人分離**: 僅在多人對話時啟用以節省處理時間

3. **AI 處理**: 根據需求決定是否啟用 LLM 處理

### 錯誤處理

常見音頻處理錯誤：

| 錯誤碼 | 描述 | 解決方法 |
|--------|------|----------|
| `INVALID_FILE_FORMAT` | 不支援的文件格式 | 使用支援的音頻格式 |
| `FILE_TOO_LARGE` | 文件過大 | 分割文件或壓縮音頻 |
| `INVALID_AUDIO_CONTENT` | 音頻內容無效 | 檢查文件是否損壞 |
| `PROCESSING_TIMEOUT` | 處理逾時 | 減少文件大小或使用較小模型 |

---

## 相關模組

- **[認證管理 API](authentication.md)** - 客戶端註冊和認證
- **[系統管理 API](system-management.md)** - 系統狀態和配置
- **[文字處理 API](text-processing.md)** - 純文字處理功能
- **[錯誤處理指南](error-handling.md)** - 完整的錯誤處理文檔
- **[整合指南](integration-guide.md)** - 開發者範例和最佳實踐

---

*更新時間: 2025-09-11*