# Error Handling Guide

## 概覽

本指南詳細說明 API 的錯誤處理機制、錯誤代碼定義、常見問題解決方案和最佳實踐。

**統一錯誤格式**: 所有 API 錯誤都使用一致的 JSON 回應格式

---

## 錯誤回應格式

### 標準錯誤結構

所有錯誤都使用以下統一格式：

```json
{
  "status": "error",
  "error_code": "ERROR_CODE",
  "message": "錯誤描述",
  "details": {
    "field": "具體錯誤信息"
  },
  "timestamp": "2025-09-11 12:00:00"
}
```

### 欄位說明

| 欄位 | 類型 | 描述 |
|------|------|------|
| `status` | string | 固定值 "error" |
| `error_code` | string | 錯誤代碼，用於程式判斷 |
| `message` | string | 人類可讀的錯誤描述 |
| `details` | object | 額外的錯誤詳細資訊 |
| `timestamp` | string | 錯誤發生時間 |

---

## HTTP 狀態碼與錯誤碼對照

### 4xx 客戶端錯誤

#### 400 Bad Request

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `INVALID_REQUEST` | 請求格式錯誤 | JSON 格式錯誤、必需欄位缺失 | 檢查請求格式和必需參數 |
| `MISSING_PARAMETER` | 缺少必要參數 | 未提供必需的請求參數 | 提供所有必要參數 |
| `INVALID_PARAMETER` | 參數值無效 | 參數值超出允許範圍 | 檢查參數值是否符合規範 |
| `INVALID_FILE_FORMAT` | 不支援的文件格式 | 上傳了不支援的音頻格式 | 使用支援的音頻/視頻格式 |
| `TEXT_TOO_LONG` | 文字內容過長 | 超過 50,000 字符限制 | 分割文字或使用批次處理 |
| `BATCH_TOO_LARGE` | 批次大小超限 | 批次項目超過 100 個 | 減少批次大小 |

#### 401 Unauthorized

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `AUTHENTICATION_REQUIRED` | 需要認證 | 未提供 X-Client-ID Header | 在請求中提供 X-Client-ID |
| `INVALID_CLIENT_ID` | 無效的客戶端 ID | 客戶端 ID 格式錯誤或不存在 | 重新註冊客戶端或檢查 ID |
| `CLIENT_NOT_FOUND` | 客戶端不存在 | 使用了未註冊的客戶端 ID | 使用有效的客戶端 ID |

#### 413 Payload Too Large

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `FILE_TOO_LARGE` | 文件過大 | 音頻文件超過 100MB | 壓縮文件或分割處理 |

#### 415 Unsupported Media Type

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `UNSUPPORTED_MEDIA_TYPE` | 不支援的媒體類型 | Content-Type 不正確 | 設定正確的 Content-Type |

#### 429 Too Many Requests

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `RATE_LIMIT_EXCEEDED` | 請求頻率超限 | 每分鐘請求超過 60 次 | 降低請求頻率，實施請求佇列 |

### 5xx 伺服器錯誤

#### 500 Internal Server Error

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `INTERNAL_ERROR` | 服務器內部錯誤 | 服務器程式異常 | 聯繫技術支援，檢查伺服器日誌 |
| `MODEL_ERROR` | 模型處理錯誤 | AI 模型執行異常 | 重試請求或使用其他模型 |
| `PROCESSING_ERROR` | 處理過程錯誤 | 文件處理過程中出現異常 | 檢查文件格式，重試請求 |

#### 503 Service Unavailable

| 錯誤碼 | 描述 | 常見原因 | 解決方法 |
|--------|------|----------|----------|
| `SERVICE_UNAVAILABLE` | 服務暫時不可用 | 系統維護或過載 | 稍後重試，檢查系統狀態 |
| `MODEL_UNAVAILABLE` | 模型不可用 | 指定的 AI 模型未載入 | 選擇其他可用模型 |
| `WHISPER_UNAVAILABLE` | Whisper 服務不可用 | Whisper 服務離線 | 檢查系統狀態，等待服務恢復 |

---

## 錯誤範例

### 認證錯誤

```json
{
  "status": "error",
  "error_code": "INVALID_CLIENT_ID",
  "message": "無效的客戶端 ID",
  "details": {
    "client_id": "client_invalid123",
    "suggestion": "請重新註冊客戶端或檢查 ID 格式"
  },
  "timestamp": "2025-09-11 12:00:00"
}
```

### 文件格式錯誤

```json
{
  "status": "error",
  "error_code": "INVALID_FILE_FORMAT",
  "message": "不支援的文件格式",
  "details": {
    "received_format": "txt",
    "supported_formats": ["wav", "mp3", "flac", "m4a", "ogg", "wma", "aac", "mp4", "avi", "mov", "mkv", "webm", "wmv", "flv"]
  },
  "timestamp": "2025-09-11 12:00:00"
}
```

### 參數錯誤

```json
{
  "status": "error",
  "error_code": "MISSING_PARAMETER",
  "message": "缺少必要參數",
  "details": {
    "missing_fields": ["text"],
    "example": {
      "text": "要處理的文字內容"
    }
  },
  "timestamp": "2025-09-11 12:00:00"
}
```

### 服務不可用錯誤

```json
{
  "status": "error",
  "error_code": "SERVICE_UNAVAILABLE",
  "message": "Whisper 服務暫時不可用",
  "details": {
    "service": "whisper",
    "status": "offline",
    "estimated_recovery": "2025-09-11 12:30:00"
  },
  "timestamp": "2025-09-11 12:00:00"
}
```

---

## 錯誤處理最佳實踐

### 客戶端錯誤處理

1. **解析錯誤回應**:
   ```javascript
   try {
     const response = await fetch('/external/v1/text/process', options);
     const data = await response.json();

     if (data.status === 'error') {
       handleApiError(data);
       return;
     }

     // 處理成功回應
   } catch (error) {
     handleNetworkError(error);
   }
   ```

2. **根據錯誤碼處理**:
   ```javascript
   function handleApiError(errorData) {
     switch (errorData.error_code) {
       case 'INVALID_CLIENT_ID':
         // 重新註冊客戶端
         registerNewClient();
         break;
       case 'RATE_LIMIT_EXCEEDED':
         // 實施退避策略
         setTimeout(retryRequest, 60000);
         break;
       case 'SERVICE_UNAVAILABLE':
         // 顯示服務維護訊息
         showMaintenanceMessage();
         break;
       default:
         // 顯示通用錯誤訊息
         showGenericError(errorData.message);
     }
   }
   ```

3. **重試機制**:
   ```python
   import time
   import requests
   from typing import Optional

   def api_request_with_retry(url: str, data: dict, max_retries: int = 3) -> Optional[dict]:
       for attempt in range(max_retries):
           try:
               response = requests.post(url, json=data)
               result = response.json()

               if result['status'] == 'success':
                   return result
               elif result['error_code'] in ['RATE_LIMIT_EXCEEDED', 'SERVICE_UNAVAILABLE']:
                   # 可重試錯誤
                   if attempt < max_retries - 1:
                       time.sleep(2 ** attempt)  # 指數退避
                       continue
               else:
                   # 不可重試錯誤
                   raise Exception(f"API Error: {result['message']}")

           except requests.RequestException as e:
               if attempt < max_retries - 1:
                   time.sleep(2 ** attempt)
                   continue
               raise e

       return None
   ```

### 錯誤日誌記錄

1. **記錄關鍵資訊**:
   ```python
   import logging

   def log_api_error(error_data: dict, request_data: dict):
       logging.error(
           f"API Error: {error_data['error_code']} - {error_data['message']}\n"
           f"Request: {request_data}\n"
           f"Details: {error_data.get('details', {})}\n"
           f"Timestamp: {error_data['timestamp']}"
       )
   ```

2. **監控錯誤趨勢**:
   - 追蹤錯誤頻率和類型
   - 設定錯誤率警報
   - 分析錯誤模式以改善用戶體驗

### 使用者體驗優化

1. **友善錯誤訊息**:
   ```javascript
   const ERROR_MESSAGES = {
     'INVALID_FILE_FORMAT': '請上傳支援的音頻檔案格式（如 MP3、WAV）',
     'FILE_TOO_LARGE': '檔案太大，請選擇小於 100MB 的檔案',
     'RATE_LIMIT_EXCEEDED': '請求過於頻繁，請稍後再試',
     'SERVICE_UNAVAILABLE': '服務暫時無法使用，請稍後重試'
   };
   ```

2. **進度指示**:
   - 在長時間處理時顯示進度
   - 提供取消操作選項
   - 在錯誤時提供重試按鈕

---

## 除錯指南

### 常見問題診斷

1. **認證問題**:
   - 檢查 X-Client-ID Header 是否正確設定
   - 確認客戶端已註冊且 ID 有效
   - 驗證請求 URL 是否正確

2. **文件上傳問題**:
   - 確認文件格式在支援列表中
   - 檢查文件大小是否超過限制
   - 驗證 Content-Type 設定正確

3. **參數問題**:
   - 檢查所有必需參數是否提供
   - 確認參數值在允許範圍內
   - 驗證 JSON 格式是否正確

### 系統狀態檢查

使用狀態端點檢查系統健康狀態：

```bash
curl -H "X-Client-ID: your_client_id" \
     http://localhost:3080/external/v1/status
```

檢查回應中的 `services` 欄位，確認所需服務狀態為 `healthy`。

---

## 相關模組

- **[認證管理 API](authentication.md)** - 客戶端註冊和認證問題
- **[系統管理 API](system-management.md)** - 系統狀態檢查
- **[音頻處理 API](audio-processing.md)** - 音頻處理相關錯誤
- **[文字處理 API](text-processing.md)** - 文字處理相關錯誤
- **[整合指南](integration-guide.md)** - 完整的開發者範例

---

*更新時間: 2025-09-11*