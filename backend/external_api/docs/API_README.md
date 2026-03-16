# 外部 API 文檔 v1

## 概述

本 API 提供完整的語音文字處理服務，包括：
- 語音轉文字 (Whisper)
- AI 文字整理 (Ollama)
- 說話人分離
- 配置管理
- 批次處理

## 認證

### 註冊客戶端

```http
POST /external/v1/auth/register
Content-Type: application/json

{
  "client_name": "你的客戶端名稱",
  "description": "客戶端描述"
}
```

**回應：**
```json
{
  "status": "success",
  "client_id": "client_12345678",
  "api_key": "vtp_abcdef1234567890",
  "endpoints": { ... }
}
```

### 使用認證

所有後續請求需要在 Header 中包含：
```http
X-Client-ID: your_client_id
```

## API 端點

### 1. 系統狀態

```http
GET /external/v1/status
X-Client-ID: your_client_id
```

檢查系統健康狀態和可用服務。

### 2. 配置管理

#### 獲取配置
```http
GET /external/v1/config
X-Client-ID: your_client_id
```

#### 更新配置
```http
PUT /external/v1/config
X-Client-ID: your_client_id
Content-Type: application/json

{
  "config": {
    "ai_model": "Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M",
    "enable_diarization": false,
    "processing_mode": "meeting"
  }
}
```

### 3. 音頻處理

```http
POST /external/v1/audio/process
X-Client-ID: your_client_id
Content-Type: multipart/form-data

audio: [音頻文件]
whisper_model: base
enable_diarization: false
enable_llm: true
processing_mode: default
detail_level: normal
ai_model: phi4-mini:3.8b
language: chinese
```

**支援格式：** mp3, wav, flac, m4a, ogg, wma, aac

**回應：**
```json
{
  "status": "success",
  "transcription": {
    "original_text": "原始轉錄文字",
    "processed_text": "AI 整理後文字",
    "language": "chinese",
    "word_count": 123
  },
  "file_info": {
    "processing_time": {
      "whisper": 2.5,
      "ai_processing": 1.2,
      "total": 3.7
    }
  },
  "timestamps": [...],
  "diarization": {...}
}
```

### 4. 文字處理

```http
POST /external/v1/text/process
X-Client-ID: your_client_id
Content-Type: application/json

{
  "text": "要處理的文字內容",
  "processing_mode": "default",
  "detail_level": "normal",
  "ai_model": "phi4-mini:3.8b"
}
```

### 5. 批次文字處理

```http
POST /external/v1/batch/text
X-Client-ID: your_client_id
Content-Type: application/json

{
  "texts": [
    "第一段文字",
    "第二段文字",
    "第三段文字"
  ],
  "processing_mode": "default",
  "detail_level": "normal",
  "ai_model": "phi4-mini:3.8b"
}
```

## 配置選項

### Whisper 模型
- `tiny`: 最快，準確度較低
- `base`: 平衡選擇（默認）
- `small`: 較好準確度
- `medium`: 高準確度
- `large`: 最高準確度，最慢

### AI 模型
- `phi4-mini:3.8b`: 快速，適合一般文字
- `Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M`: 繁體中文優化

### 處理模式
- `default`: 一般整理
- `meeting`: 會議記錄優化
- `lecture`: 講座筆記優化

### 詳細程度
- `simple`: 簡潔版本
- `normal`: 標準詳細度（默認）
- `detailed`: 完整詳細版本

## 錯誤處理

所有錯誤回應格式：
```json
{
  "status": "error",
  "message": "錯誤描述"
}
```

### 常見錯誤碼
- `400`: 請求參數錯誤
- `401`: 認證失敗
- `413`: 文件過大
- `415`: 不支援的文件格式
- `500`: 服務器內部錯誤

## 限制

- 音頻文件最大 100MB
- 批次處理最多 100 個文字
- 請求頻率限制：每分鐘 60 次

## 使用範例

### Python 範例

```python
import requests

# 註冊客戶端
response = requests.post('http://localhost:3080/external/v1/auth/register', json={
    'client_name': '我的應用',
    'description': '測試應用'
})
client_data = response.json()
client_id = client_data['client_id']

# 處理文字
headers = {'X-Client-ID': client_id}
response = requests.post('http://localhost:3080/external/v1/text/process', 
                        headers=headers,
                        json={
                            'text': '今天的會議很重要',
                            'ai_model': 'phi4-mini:3.8b'
                        })
result = response.json()
print(result['processed_text'])
```

### JavaScript 範例

```javascript
// 註冊客戶端
const response = await fetch('http://localhost:3080/external/v1/auth/register', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    client_name: '我的應用',
    description: '測試應用'
  })
});
const clientData = await response.json();
const clientId = clientData.client_id;

// 處理音頻
const formData = new FormData();
formData.append('audio', audioFile);
formData.append('whisper_model', 'base');
formData.append('enable_llm', 'true');

const audioResponse = await fetch('http://localhost:3080/external/v1/audio/process', {
  method: 'POST',
  headers: {'X-Client-ID': clientId},
  body: formData
});
const audioResult = await audioResponse.json();
console.log(audioResult.transcription.processed_text);
```