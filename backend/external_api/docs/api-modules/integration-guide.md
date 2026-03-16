# Integration Guide & Examples

## 概覽

本指南提供完整的開發者整合範例、使用限制說明、最佳實踐和技術支援資訊。

**支援語言**: Python, JavaScript, Java, C#
**完整範例**: 包含錯誤處理和重試機制

---

## 使用限制

### 速率限制

| 限制類型 | 限制值 | 描述 |
|----------|--------|------|
| 每分鐘請求數 | 60 次 | 所有 API 端點的總請求次數 |
| 並發處理 | 5 個 | 同時進行的音頻處理任務數量 |
| 批次處理 | 100 個項目 | 單次批次處理的最大文字項目數 |

### 文件與內容限制

| 項目 | 限制值 | 說明 |
|------|--------|------|
| 音頻文件最大大小 | 100MB | 單個音頻文件大小限制 |
| 音頻最大長度 | 2 小時 | 支援的音頻時長上限 |
| 文字最大長度 | 50,000 字符 | 單次文字處理的字符數限制 |
| 支援的音頻格式 | wav, mp3, flac, m4a, ogg, wma, aac | 完整的音頻格式支援列表 |
| 支援的視頻格式 | mp4, avi, mov, mkv, webm, wmv, flv | 完整的視頻格式支援列表 |

### 模型可用性

- **Whisper 模型**: 根據系統資源動態載入，建議使用 `base` 模型平衡速度和精度
- **AI 模型**: 依賴 Ollama 服務，可用性會根據系統負載變化

---

## 開發者範例

### Python 完整範例

```python
import requests
import json
import time
from typing import Optional, Dict, Any

class VoiceTextProcessorClient:
    def __init__(self, base_url: str = "http://localhost:3080/external/v1"):
        self.base_url = base_url
        self.client_id: Optional[str] = None
        self.session = requests.Session()

    def register_client(self, client_name: str, description: str = "") -> Dict[str, Any]:
        """註冊新客戶端"""
        url = f"{self.base_url}/auth/register"
        data = {
            "client_name": client_name,
            "description": description
        }

        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            result = response.json()

            if result["status"] == "success":
                self.client_id = result["client_id"]
                return result
            else:
                raise Exception(f"註冊失敗: {result.get('message', 'Unknown error')}")

        except requests.RequestException as e:
            raise Exception(f"網路錯誤: {str(e)}")

    def _make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """發送認證請求"""
        if not self.client_id:
            raise Exception("客戶端未註冊，請先調用 register_client()")

        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get('headers', {})
        headers['X-Client-ID'] = self.client_id
        kwargs['headers'] = headers

        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_status(self) -> Dict[str, Any]:
        """檢查系統狀態"""
        return self._make_authenticated_request('GET', '/status')

    def get_config(self) -> Dict[str, Any]:
        """獲取配置"""
        return self._make_authenticated_request('GET', '/config')

    def update_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新配置"""
        data = {"config": config_updates}
        return self._make_authenticated_request('PUT', '/config', json=data)

    def process_text(self, text: str, processing_mode: str = "meeting",
                    detail_level: str = "normal", ai_model: Optional[str] = None) -> Dict[str, Any]:
        """處理文字"""
        data = {
            "text": text,
            "processing_mode": processing_mode,
            "detail_level": detail_level
        }
        if ai_model:
            data["ai_model"] = ai_model

        return self._make_authenticated_request('POST', '/text/process', json=data)

    def batch_process_text(self, texts: list, processing_mode: str = "meeting",
                          detail_level: str = "normal", ai_model: Optional[str] = None) -> Dict[str, Any]:
        """批次處理文字"""
        data = {
            "texts": texts,
            "processing_mode": processing_mode,
            "detail_level": detail_level
        }
        if ai_model:
            data["ai_model"] = ai_model

        return self._make_authenticated_request('POST', '/batch/text', json=data)

    def process_audio(self, audio_file_path: str, whisper_model: str = "base",
                     enable_diarization: bool = True, enable_llm: bool = True,
                     processing_mode: str = "meeting", detail_level: str = "normal",
                     ai_model: Optional[str] = None, language: str = "chinese") -> Dict[str, Any]:
        """處理音頻文件"""
        with open(audio_file_path, 'rb') as f:
            files = {"audio": f}
            data = {
                "whisper_model": whisper_model,
                "enable_diarization": str(enable_diarization).lower(),
                "enable_llm": str(enable_llm).lower(),
                "processing_mode": processing_mode,
                "detail_level": detail_level,
                "language": language
            }
            if ai_model:
                data["ai_model"] = ai_model

            return self._make_authenticated_request('POST', '/audio/process', files=files, data=data)

    def process_audio_with_retry(self, audio_file_path: str, max_retries: int = 3, **kwargs) -> Optional[Dict[str, Any]]:
        """帶重試機制的音頻處理"""
        for attempt in range(max_retries):
            try:
                return self.process_audio(audio_file_path, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"處理失敗，{wait_time} 秒後重試: {str(e)}")
                    time.sleep(wait_time)
                else:
                    raise e
        return None

# 使用範例
def main():
    # 初始化客戶端
    client = VoiceTextProcessorClient()

    try:
        # 註冊客戶端
        registration = client.register_client(
            "Python 語音處理應用",
            "用於會議記錄的自動化處理"
        )
        print(f"註冊成功，客戶端 ID: {registration['client_id']}")

        # 檢查系統狀態
        status = client.get_status()
        print(f"系統狀態: {status['status']}")

        # 處理文字
        text_result = client.process_text(
            "今天的會議討論了新產品開發和市場策略",
            processing_mode="meeting",
            ai_model="Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M"
        )
        print("文字處理結果:")
        print(text_result["processed_text"])

        # 批次處理文字
        texts = [
            "第一個議題：產品開發進度",
            "第二個議題：市場策略規劃",
            "第三個議題：團隊建設計畫"
        ]
        batch_result = client.batch_process_text(texts, processing_mode="meeting")
        print(f"批次處理完成，成功處理 {batch_result['summary']['success_count']} 個項目")

        # 處理音頻（如果有音頻文件）
        # audio_result = client.process_audio_with_retry("meeting.wav")
        # print("音頻處理結果:")
        # print(audio_result["transcription"]["ai_processed_text"])

    except Exception as e:
        print(f"錯誤: {str(e)}")

if __name__ == "__main__":
    main()
```

### JavaScript/Node.js 範例

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class VoiceTextProcessorClient {
    constructor(baseUrl = 'http://localhost:3080/external/v1') {
        this.baseUrl = baseUrl;
        this.clientId = null;
        this.axios = axios.create({
            timeout: 60000, // 60 秒超時
        });
    }

    async registerClient(clientName, description = '') {
        try {
            const response = await this.axios.post(`${this.baseUrl}/auth/register`, {
                client_name: clientName,
                description: description
            });

            if (response.data.status === 'success') {
                this.clientId = response.data.client_id;
                return response.data;
            } else {
                throw new Error(`註冊失敗: ${response.data.message}`);
            }
        } catch (error) {
            throw new Error(`網路錯誤: ${error.message}`);
        }
    }

    async makeAuthenticatedRequest(method, endpoint, data = null, options = {}) {
        if (!this.clientId) {
            throw new Error('客戶端未註冊，請先調用 registerClient()');
        }

        const config = {
            method,
            url: `${this.baseUrl}${endpoint}`,
            headers: {
                'X-Client-ID': this.clientId,
                ...options.headers
            },
            ...options
        };

        if (data) {
            config.data = data;
        }

        try {
            const response = await this.axios(config);
            return response.data;
        } catch (error) {
            if (error.response && error.response.data) {
                throw new Error(`API 錯誤: ${error.response.data.message}`);
            }
            throw new Error(`請求失敗: ${error.message}`);
        }
    }

    async getStatus() {
        return await this.makeAuthenticatedRequest('GET', '/status');
    }

    async getConfig() {
        return await this.makeAuthenticatedRequest('GET', '/config');
    }

    async updateConfig(configUpdates) {
        return await this.makeAuthenticatedRequest('PUT', '/config', {
            config: configUpdates
        });
    }

    async processText(text, options = {}) {
        const data = {
            text,
            processing_mode: options.processingMode || 'meeting',
            detail_level: options.detailLevel || 'normal',
            ...(options.aiModel && { ai_model: options.aiModel })
        };

        return await this.makeAuthenticatedRequest('POST', '/text/process', data);
    }

    async batchProcessText(texts, options = {}) {
        const data = {
            texts,
            processing_mode: options.processingMode || 'meeting',
            detail_level: options.detailLevel || 'normal',
            ...(options.aiModel && { ai_model: options.aiModel })
        };

        return await this.makeAuthenticatedRequest('POST', '/batch/text', data);
    }

    async processAudio(audioFilePath, options = {}) {
        const formData = new FormData();
        formData.append('audio', fs.createReadStream(audioFilePath));
        formData.append('whisper_model', options.whisperModel || 'base');
        formData.append('enable_diarization', options.enableDiarization !== false ? 'true' : 'false');
        formData.append('enable_llm', options.enableLLM !== false ? 'true' : 'false');
        formData.append('processing_mode', options.processingMode || 'meeting');
        formData.append('detail_level', options.detailLevel || 'normal');
        formData.append('language', options.language || 'chinese');

        if (options.aiModel) {
            formData.append('ai_model', options.aiModel);
        }

        return await this.makeAuthenticatedRequest('POST', '/audio/process', formData, {
            headers: {
                ...formData.getHeaders()
            },
            timeout: 300000 // 5 分鐘超時，適用於大文件
        });
    }

    async processAudioWithRetry(audioFilePath, options = {}, maxRetries = 3) {
        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                return await this.processAudio(audioFilePath, options);
            } catch (error) {
                if (attempt < maxRetries - 1) {
                    const waitTime = Math.pow(2, attempt) * 1000;
                    console.log(`處理失敗，${waitTime/1000} 秒後重試: ${error.message}`);
                    await new Promise(resolve => setTimeout(resolve, waitTime));
                } else {
                    throw error;
                }
            }
        }
    }
}

// 使用範例
async function main() {
    const client = new VoiceTextProcessorClient();

    try {
        // 註冊客戶端
        const registration = await client.registerClient(
            'Node.js 語音處理應用',
            '用於會議記錄的自動化處理'
        );
        console.log(`註冊成功，客戶端 ID: ${registration.client_id}`);

        // 檢查系統狀態
        const status = await client.getStatus();
        console.log(`系統狀態: ${status.status}`);

        // 處理文字
        const textResult = await client.processText(
            '今天的會議討論了新產品開發和市場策略',
            {
                processingMode: 'meeting',
                aiModel: 'Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M'
            }
        );
        console.log('文字處理結果:');
        console.log(textResult.processed_text);

        // 批次處理文字
        const texts = [
            '第一個議題：產品開發進度',
            '第二個議題：市場策略規劃',
            '第三個議題：團隊建設計畫'
        ];
        const batchResult = await client.batchProcessText(texts, {
            processingMode: 'meeting'
        });
        console.log(`批次處理完成，成功處理 ${batchResult.summary.success_count} 個項目`);

        // 處理音頻（如果有音頻文件）
        // const audioResult = await client.processAudioWithRetry('meeting.wav');
        // console.log('音頻處理結果:');
        // console.log(audioResult.transcription.ai_processed_text);

    } catch (error) {
        console.error(`錯誤: ${error.message}`);
    }
}

// 如果直接執行此文件
if (require.main === module) {
    main();
}

module.exports = VoiceTextProcessorClient;
```

### React Web 應用範例

```jsx
import React, { useState, useCallback } from 'react';

class APIClient {
    constructor(baseUrl = 'http://localhost:3080/external/v1') {
        this.baseUrl = baseUrl;
        this.clientId = null;
    }

    async registerClient(clientName, description = '') {
        const response = await fetch(`${this.baseUrl}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_name: clientName, description })
        });

        const data = await response.json();
        if (data.status === 'success') {
            this.clientId = data.client_id;
            return data;
        }
        throw new Error(data.message);
    }

    async makeAuthenticatedRequest(method, endpoint, body = null, isFormData = false) {
        if (!this.clientId) {
            throw new Error('客戶端未註冊');
        }

        const options = {
            method,
            headers: { 'X-Client-ID': this.clientId }
        };

        if (body) {
            if (isFormData) {
                options.body = body;
            } else {
                options.headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(body);
            }
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, options);
        const data = await response.json();

        if (data.status === 'error') {
            throw new Error(data.message);
        }

        return data;
    }

    async processText(text, options = {}) {
        return await this.makeAuthenticatedRequest('POST', '/text/process', {
            text,
            processing_mode: options.processingMode || 'meeting',
            detail_level: options.detailLevel || 'normal',
            ...(options.aiModel && { ai_model: options.aiModel })
        });
    }

    async processAudio(audioFile, options = {}) {
        const formData = new FormData();
        formData.append('audio', audioFile);
        formData.append('whisper_model', options.whisperModel || 'base');
        formData.append('enable_diarization', options.enableDiarization !== false ? 'true' : 'false');
        formData.append('enable_llm', options.enableLLM !== false ? 'true' : 'false');
        formData.append('processing_mode', options.processingMode || 'meeting');
        formData.append('detail_level', options.detailLevel || 'normal');
        formData.append('language', options.language || 'chinese');

        if (options.aiModel) {
            formData.append('ai_model', options.aiModel);
        }

        return await this.makeAuthenticatedRequest('POST', '/audio/process', formData, true);
    }
}

function VoiceTextProcessor() {
    const [client] = useState(() => new APIClient());
    const [isRegistered, setIsRegistered] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const initializeClient = useCallback(async () => {
        try {
            await client.registerClient('React 語音處理應用');
            setIsRegistered(true);
            setError(null);
        } catch (err) {
            setError(`註冊失敗: ${err.message}`);
        }
    }, [client]);

    const processText = useCallback(async (text) => {
        if (!isRegistered) {
            await initializeClient();
        }

        setIsProcessing(true);
        setError(null);

        try {
            const result = await client.processText(text, {
                processingMode: 'meeting',
                aiModel: 'Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M'
            });
            setResult(result);
        } catch (err) {
            setError(`處理失敗: ${err.message}`);
        } finally {
            setIsProcessing(false);
        }
    }, [client, isRegistered, initializeClient]);

    const processAudio = useCallback(async (file) => {
        if (!isRegistered) {
            await initializeClient();
        }

        setIsProcessing(true);
        setError(null);

        try {
            const result = await client.processAudio(file, {
                processingMode: 'meeting',
                enableDiarization: true
            });
            setResult(result);
        } catch (err) {
            setError(`處理失敗: ${err.message}`);
        } finally {
            setIsProcessing(false);
        }
    }, [client, isRegistered, initializeClient]);

    return (
        <div className="voice-text-processor">
            <h1>語音文字處理器</h1>

            {error && (
                <div className="error">
                    錯誤: {error}
                </div>
            )}

            <div className="input-section">
                <h2>文字處理</h2>
                <textarea
                    placeholder="輸入要處理的文字..."
                    onBlur={(e) => {
                        if (e.target.value.trim()) {
                            processText(e.target.value);
                        }
                    }}
                />

                <h2>音頻處理</h2>
                <input
                    type="file"
                    accept=".wav,.mp3,.flac,.m4a,.ogg,.wma,.aac,.mp4,.avi,.mov,.mkv,.webm,.wmv,.flv"
                    onChange={(e) => {
                        if (e.target.files[0]) {
                            processAudio(e.target.files[0]);
                        }
                    }}
                />
            </div>

            {isProcessing && (
                <div className="processing">
                    處理中...
                </div>
            )}

            {result && (
                <div className="result">
                    <h2>處理結果</h2>
                    {result.processed_text && (
                        <div>
                            <h3>處理後文字:</h3>
                            <pre>{result.processed_text}</pre>
                        </div>
                    )}
                    {result.transcription && (
                        <div>
                            <h3>轉錄結果:</h3>
                            <pre>{result.transcription.ai_processed_text}</pre>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default VoiceTextProcessor;
```

---

## 最佳實踐

### 性能優化

1. **連接池管理**:
   ```python
   # 使用會話重用連接
   session = requests.Session()
   session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))
   ```

2. **並發控制**:
   ```python
   import asyncio
   import aiohttp

   async def process_multiple_texts(texts, max_concurrent=3):
       semaphore = asyncio.Semaphore(max_concurrent)

       async def process_single(text):
           async with semaphore:
               # 處理單個文字
               pass

       tasks = [process_single(text) for text in texts]
       return await asyncio.gather(*tasks)
   ```

3. **快取策略**:
   ```python
   import functools
   import time

   @functools.lru_cache(maxsize=100)
   def cached_process_text(text_hash, processing_mode):
       # 對相同文字內容使用快取
       pass
   ```

### 錯誤恢復

1. **斷點續傳**:
   ```python
   def resume_batch_processing(batch_id, processed_items):
       # 從上次中斷的地方繼續處理
       remaining_items = get_remaining_items(batch_id, processed_items)
       return process_batch(remaining_items)
   ```

2. **優雅降級**:
   ```python
   def process_with_fallback(text):
       try:
           return process_text_with_ai(text)
       except ServiceUnavailableError:
           return process_text_basic(text)  # 使用基本處理
   ```

### 監控與日誌

1. **性能監控**:
   ```python
   import time
   import logging

   def log_performance(func):
       def wrapper(*args, **kwargs):
           start_time = time.time()
           result = func(*args, **kwargs)
           duration = time.time() - start_time
           logging.info(f"{func.__name__} 耗時: {duration:.2f} 秒")
           return result
       return wrapper
   ```

2. **錯誤追蹤**:
   ```python
   import traceback

   def log_error(error, context):
       logging.error(f"錯誤: {str(error)}")
       logging.error(f"上下文: {context}")
       logging.error(f"堆疊追蹤: {traceback.format_exc()}")
   ```

---

## 技術支援

### 支援管道

- **API 文檔**: 本文檔提供完整的 API 規格說明
- **系統狀態**: 使用 `/external/v1/status` 端點獲取即時系統資訊
- **錯誤診斷**: 參考 [錯誤處理指南](error-handling.md) 進行問題排除

### 問題報告

提交問題時請提供以下資訊：

1. **錯誤詳情**:
   - 完整的錯誤回應 JSON
   - 請求的詳細內容（去除敏感資訊）
   - 錯誤發生的時間戳記

2. **環境資訊**:
   - API 版本
   - 客戶端語言和版本
   - 網路環境說明

3. **重現步驟**:
   - 詳細的操作步驟
   - 使用的參數和配置
   - 預期結果與實際結果

### 功能建議

歡迎提出以下類型的改進建議：

- **新功能需求**: 額外的處理模式或 AI 模型支援
- **性能優化**: 處理速度或準確度改進建議
- **整合改善**: 更好的 SDK 或開發工具
- **文檔完善**: API 文檔或範例代碼改進

---

## 更新日誌

### v1.0.0 (2025-09-11)

**新功能**:
- 初始版本發布
- 支援客戶端註冊和認證系統
- 實現音頻處理（Whisper + AI 整理）
- 實現單一和批次文字處理
- 支援多種音頻/視頻格式
- 說話人分離功能
- 多 AI 模型支援

**技術特性**:
- RESTful API 設計
- JSON 和 Multipart 數據格式支援
- 完整的錯誤處理機制
- 速率限制和安全控制
- 即時系統狀態監控

**支援的模型**:
- **Whisper 模型**: tiny, base, small, medium, large
- **AI 模型**: phi4-mini:3.8b, Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M

---

## 相關模組

- **[認證管理 API](authentication.md)** - 客戶端註冊和認證
- **[系統管理 API](system-management.md)** - 系統狀態和配置管理
- **[音頻處理 API](audio-processing.md)** - 音頻轉錄和處理
- **[文字處理 API](text-processing.md)** - 文字分析和處理
- **[錯誤處理指南](error-handling.md)** - 完整的錯誤處理文檔

---

*此文檔將持續更新，請關注最新版本。*
*更新時間: 2025-09-11*