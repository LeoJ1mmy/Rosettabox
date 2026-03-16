# Authentication & Client Management API

## 概覽

本模組提供外部客戶端的註冊、認證和基本管理功能。所有 API 請求都需要通過客戶端認證系統驗證身份。

**基礎資訊**:
- **API 版本**: v1
- **認證方式**: Client ID Header 認證
- **Header 格式**: `X-Client-ID: your_client_id`

---

## 客戶端註冊

### 註冊新客戶端

註冊新的外部客戶端以獲取 API 存取權限。

#### 請求

```http
POST /external/v1/auth/register
Content-Type: application/json

{
  "client_name": "你的應用名稱",
  "description": "應用描述 (可選)"
}
```

#### 參數說明

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `client_name` | string | 是 | 客戶端應用名稱，用於識別 |
| `description` | string | 否 | 應用描述，幫助管理和識別用途 |

#### 成功回應

```json
{
  "status": "success",
  "client_id": "client_12345678",
  "api_key": "vtp_abcdef1234567890",
  "endpoints": {
    "status": "/external/v1/status",
    "config": "/external/v1/config",
    "audio_process": "/external/v1/audio/process",
    "text_process": "/external/v1/text/process",
    "batch_text": "/external/v1/batch/text"
  },
  "rate_limits": {
    "requests_per_minute": 60,
    "audio_file_max_size": "100MB",
    "batch_max_items": 100
  },
  "available_models": {
    "whisper": ["tiny", "base", "small", "medium", "large"],
    "ai": ["phi4-mini:3.8b", "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M"]
  }
}
```

#### 回應欄位說明

| 欄位 | 類型 | 描述 |
|------|------|------|
| `client_id` | string | 客戶端唯一識別碼，用於後續 API 認證 |
| `api_key` | string | API 金鑰（目前版本暫未使用，保留供未來版本） |
| `endpoints` | object | 可用的 API 端點列表 |
| `rate_limits` | object | 該客戶端的使用限制 |
| `available_models` | object | 可用的模型列表 |

---

## 認證使用

### Header 認證

所有需要認證的 API 請求都必須在 Header 中提供有效的客戶端 ID：

```http
X-Client-ID: client_12345678
```

### 認證示例

```http
GET /external/v1/status
X-Client-ID: client_12345678
```

---

## 認證相關錯誤

### 常見認證錯誤

| 錯誤碼 | HTTP 狀態 | 描述 | 解決方法 |
|--------|-----------|------|----------|
| `INVALID_CLIENT_ID` | 401 | 無效的客戶端 ID | 重新註冊客戶端或檢查 ID 格式 |
| `AUTHENTICATION_REQUIRED` | 401 | 缺少認證 Header | 提供 X-Client-ID Header |
| `CLIENT_NOT_FOUND` | 401 | 客戶端不存在 | 使用有效的客戶端 ID |

### 錯誤回應示例

```json
{
  "status": "error",
  "error_code": "INVALID_CLIENT_ID",
  "message": "無效的客戶端 ID",
  "details": {
    "client_id": "client_invalid123"
  },
  "timestamp": "2025-09-11 12:00:00"
}
```

---

## 最佳實踐

### 客戶端 ID 管理

1. **安全存儲**: 將客戶端 ID 安全存儲，避免硬編碼在客戶端代碼中
2. **環境隔離**: 為不同環境（開發、測試、生產）使用不同的客戶端 ID
3. **監控使用**: 定期檢查 API 使用情況，避免超出速率限制

### 註冊建議

1. **描述性命名**: 使用清楚描述應用用途的客戶端名稱
2. **詳細描述**: 提供完整的應用描述，有助於管理和排除問題
3. **單一用途**: 每個應用或服務使用獨立的客戶端 ID

---

## 相關模組

- **[系統管理 API](system-management.md)** - 系統狀態檢查和配置管理
- **[錯誤處理指南](error-handling.md)** - 完整的錯誤處理文檔
- **[整合指南](integration-guide.md)** - 開發者範例和整合指導

---

*更新時間: 2025-09-11*