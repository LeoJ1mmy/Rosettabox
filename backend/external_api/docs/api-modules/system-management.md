# System Management API

## 概覽

本模組提供系統狀態檢查和配置管理功能，讓開發者能夠監控服務健康狀態並調整處理參數。

**認證要求**: 所有請求需要提供 `X-Client-ID` Header

---

## 系統狀態檢查

### 獲取系統狀態

檢查系統健康狀態和各項服務的可用性。

#### 請求

```http
GET /external/v1/status
X-Client-ID: your_client_id
```

#### 成功回應

```json
{
  "status": "healthy",
  "client_id": "client_12345678",
  "message": "系統狀態檢查完成",
  "timestamp": "2025-09-11 11:57:44",
  "services": {
    "whisper": {
      "status": "healthy",
      "message": "Whisper 服務正常",
      "backend": "CTranslate2",
      "model_info": {
        "status": "已載入",
        "model_size": "base",
        "backend": "CTranslate2",
        "device": "cuda",
        "model_path": "/tmp/whisper-base-ct2"
      }
    },
    "ollama": {
      "status": "healthy",
      "message": "Ollama 服務正常",
      "model_count": 8,
      "available_models": [
        "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M",
        "phi4-mini:3.8b",
        "gemma3:12b",
        "llama3.2:3b"
      ]
    },
    "config": {
      "status": "healthy",
      "message": "配置服務正常",
      "config_fields": 17
    }
  },
  "system": {
    "uptime": 1757563064.6099293,
    "available_models": {
      "whisper": ["tiny", "base", "small", "medium", "large"],
      "ai": ["Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M", "phi4-mini:3.8b"]
    },
    "supported_formats": {
      "audio": ["wav", "ogg", "wma", "m4a", "flac", "aac", "mp3"],
      "video": ["mov", "flv", "avi", "webm", "wmv", "mp4", "mkv"]
    }
  }
}
```

#### 回應欄位說明

| 欄位 | 類型 | 描述 |
|------|------|------|
| `status` | string | 整體系統狀態: `healthy`, `degraded`, `unhealthy` |
| `services` | object | 各項服務的詳細狀態資訊 |
| `system` | object | 系統層級資訊（運行時間、支援格式等） |

#### 服務狀態類型

- **healthy**: 服務正常運行
- **degraded**: 服務運行但有問題
- **unhealthy**: 服務無法正常運行

---

## 配置管理

### 獲取當前配置

取得目前的處理配置設定。

#### 請求

```http
GET /external/v1/config
X-Client-ID: your_client_id
```

#### 成功回應

```json
{
  "status": "success",
  "client_id": "client_12345678",
  "config": {
    "whisper_model": "base",
    "enable_diarization": true,
    "ai_model": "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M",
    "processing_mode": "default",
    "detail_level": "normal",
    "language": "chinese",
    "enable_llm": true,
    "output_format": "json",
    "max_file_size": 104857600,
    "batch_size": 50
  },
  "available_options": {
    "whisper_models": ["tiny", "base", "small", "medium", "large"],
    "ai_models": ["phi4-mini:3.8b", "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M"],
    "processing_modes": ["default", "meeting", "lecture", "interview"],
    "detail_levels": ["simple", "normal", "detailed"],
    "languages": ["chinese", "english", "auto"]
  }
}
```

### 更新配置

更新處理配置設定。

#### 請求

```http
PUT /external/v1/config
X-Client-ID: your_client_id
Content-Type: application/json

{
  "config": {
    "ai_model": "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M",
    "enable_diarization": false,
    "processing_mode": "meeting",
    "detail_level": "detailed"
  }
}
```

#### 可配置參數

| 參數 | 類型 | 可選值 | 描述 |
|------|------|--------|------|
| `whisper_model` | string | tiny, base, small, medium, large | Whisper 模型大小 |
| `enable_diarization` | boolean | true, false | 是否啟用說話人分離 |
| `ai_model` | string | 見可用模型列表 | AI 文字處理模型 |
| `processing_mode` | string | default, meeting, lecture, interview | 處理模式 |
| `detail_level` | string | simple, normal, detailed | 詳細程度 |
| `language` | string | chinese, english, auto | 語言設定 |
| `enable_llm` | boolean | true, false | 是否啟用 LLM 處理 |

#### 成功回應

```json
{
  "status": "success",
  "message": "配置更新成功",
  "client_id": "client_12345678",
  "config": {
    "whisper_model": "base",
    "enable_diarization": false,
    "ai_model": "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M",
    "processing_mode": "meeting",
    "detail_level": "detailed",
    "language": "chinese",
    "enable_llm": true
  },
  "updated_fields": ["ai_model", "enable_diarization", "processing_mode", "detail_level"]
}
```

---

## 處理模式說明

### 可用處理模式

1. **default**: 通用處理模式，適用於各種場景
2. **meeting**: 會議優化模式，強化多人對話識別
3. **lecture**: 演講模式，適合單人長時間發言
4. **interview**: 訪談模式，優化問答對話結構

### 詳細程度說明

1. **simple**: 簡潔摘要，關鍵資訊提取
2. **normal**: 標準詳細程度，平衡內容和簡潔性
3. **detailed**: 詳細分析，包含完整結構化內容

---

## 監控與診斷

### 健康檢查最佳實踐

1. **定期檢查**: 建議每 5-10 分鐘檢查一次系統狀態
2. **錯誤處理**: 根據服務狀態調整處理策略
3. **模型可用性**: 在處理前確認所需模型已載入

### 配置管理建議

1. **批次更新**: 一次更新多個相關設定以避免不一致
2. **驗證設定**: 更新後檢查 `updated_fields` 確認變更成功
3. **回滾準備**: 保存原始配置以便出現問題時回滾

---

## 相關錯誤

| 錯誤碼 | 描述 | 解決方法 |
|--------|------|----------|
| `SERVICE_UNAVAILABLE` | 某項服務不可用 | 等待服務恢復或使用替代配置 |
| `INVALID_CONFIGURATION` | 配置參數無效 | 檢查參數值是否在允許範圍內 |
| `MODEL_NOT_LOADED` | 指定模型未載入 | 等待模型載入或選擇其他模型 |

---

## 相關模組

- **[認證管理 API](authentication.md)** - 客戶端註冊和認證
- **[音頻處理 API](audio-processing.md)** - 音頻轉錄和處理
- **[文字處理 API](text-processing.md)** - 文字分析和處理
- **[錯誤處理指南](error-handling.md)** - 完整的錯誤處理文檔

---

*更新時間: 2025-09-11*