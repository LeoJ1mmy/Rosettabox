#!/usr/bin/env python3
"""
外部 API 完整測試套件
測試所有端點功能，包括認證、音頻處理、文字處理、配置管理等
"""

import requests
import json
import time
import os
import tempfile
import wave
import numpy as np
from typing import Dict, Any, Optional
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from test_data.sample_texts import SAMPLE_MEETING_TEXT, SHORT_TEXT_SAMPLE, MEDIUM_TEXT_SAMPLE

class ExternalAPITester:
    """外部 API 測試器"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:3080"):
        self.base_url = base_url
        self.api_base = f"{base_url}/external/v1"
        self.client_id = None
        self.api_key = None
        
    def create_test_audio(self, duration: float = 3.0, sample_rate: int = 16000) -> str:
        """創建測試音頻文件"""
        # 生成正弦波音頻
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t)  # 440Hz 音調
        
        # 轉換為 16-bit PCM
        audio_data = (audio_data * 32767).astype(np.int16)
        
        # 創建臨時 WAV 文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        
        with wave.open(temp_file.name, 'w') as wav_file:
            wav_file.setnchannels(1)  # 單聲道
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        return temp_file.name
    
    def test_client_registration(self) -> bool:
        """測試客戶端註冊"""
        print("\n=== 測試客戶端註冊 ===")
        
        try:
            response = requests.post(f"{self.api_base}/auth/register", json={
                "client_name": "測試客戶端",
                "description": "API 測試用客戶端"
            })
            
            if response.status_code == 200:
                data = response.json()
                self.client_id = data.get('client_id')
                self.api_key = data.get('api_key')
                
                print(f"✅ 客戶端註冊成功")
                print(f"   Client ID: {self.client_id}")
                print(f"   API Key: {self.api_key}")
                print(f"   可用端點: {len(data.get('endpoints', {}))}")
                return True
            else:
                print(f"❌ 註冊失敗: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 註冊異常: {e}")
            return False
    
    def test_system_status(self) -> bool:
        """測試系統狀態"""
        print("\n=== 測試系統狀態 ===")
        
        try:
            headers = {'X-Client-ID': self.client_id} if self.client_id else {}
            response = requests.get(f"{self.api_base}/status", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 系統狀態: {data.get('status')}")
                
                services = data.get('services', {})
                for service, status in services.items():
                    status_icon = "✅" if status.get('status') == 'healthy' else "❌"
                    print(f"   {status_icon} {service}: {status.get('message')}")
                
                system_info = data.get('system', {})
                models = system_info.get('available_models', {})
                print(f"   可用模型: Whisper({len(models.get('whisper', []))}), AI({len(models.get('ai', []))})")
                
                return data.get('status') in ['healthy', 'degraded']
            else:
                print(f"❌ 狀態檢查失敗: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 狀態檢查異常: {e}")
            return False
    
    def test_config_management(self) -> bool:
        """測試配置管理"""
        print("\n=== 測試配置管理 ===")
        
        if not self.client_id:
            print("❌ 需要先註冊客戶端")
            return False
        
        try:
            headers = {'X-Client-ID': self.client_id}
            
            # 1. 獲取配置
            print("1. 獲取配置...")
            response = requests.get(f"{self.api_base}/config", headers=headers)
            
            if response.status_code != 200:
                print(f"❌ 獲取配置失敗: {response.status_code}")
                return False
            
            config_data = response.json()
            current_config = config_data.get('config', {})
            print(f"✅ 配置獲取成功，包含 {len(current_config)} 個字段")
            
            # 2. 更新配置
            print("2. 更新配置...")
            config_updates = {
                'ai_model': 'Yu-Feng/Llama-3.1-TAIDE-LX-8B-Chat:Q4_K_M',
                'processing_mode': 'meeting'
            }
            
            response = requests.put(f"{self.api_base}/config", 
                                  headers=headers, 
                                  json={'config': config_updates})
            
            if response.status_code == 200:
                print("✅ 配置更新成功")
                updated_config = response.json().get('config', {})
                
                # 驗證更新
                for key, value in config_updates.items():
                    if updated_config.get(key) == value:
                        print(f"   ✅ {key}: {value}")
                    else:
                        print(f"   ❌ {key}: 期望 {value}, 實際 {updated_config.get(key)}")
                
                return True
            else:
                print(f"❌ 配置更新失敗: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 配置管理異常: {e}")
            return False
    
    def test_text_processing(self) -> bool:
        """測試文字處理"""
        print("\n=== 測試文字處理 ===")
        
        if not self.client_id:
            print("❌ 需要先註冊客戶端")
            return False
        
        try:
            headers = {'X-Client-ID': self.client_id}
            
            # 使用測試數據模組的中等長度文本
            test_text = MEDIUM_TEXT_SAMPLE.strip()
            
            payload = {
                'text': test_text,
                'processing_mode': 'meeting',
                'detail_level': 'normal',
                'ai_model': 'gpt-oss:20b'
            }
            
            print(f"處理文字: {test_text[:50]}...")
            start_time = time.time()
            
            response = requests.post(f"{self.api_base}/text/process", 
                                   headers=headers, 
                                   json=payload)
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 文字處理成功 (耗時: {processing_time:.2f}s)")
                
                original = data.get('original_text', '')
                processed = data.get('processed_text', '')
                stats = data.get('statistics', {})
                
                print(f"   原始長度: {len(original)} 字符")
                print(f"   處理長度: {len(processed)} 字符")
                print(f"   壓縮比例: {stats.get('compression_ratio', 0):.2f}")
                print(f"   使用模型: {data.get('processing_config', {}).get('ai_model', 'N/A')}")
                print(f"   處理結果: {processed[:100]}...")
                
                return True
            else:
                print(f"❌ 文字處理失敗: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 文字處理異常: {e}")
            return False
    
    def test_batch_text_processing(self) -> bool:
        """測試批次文字處理"""
        print("\n=== 測試批次文字處理 ===")
        
        if not self.client_id:
            print("❌ 需要先註冊客戶端")
            return False
        
        try:
            headers = {'X-Client-ID': self.client_id}
            
            # 使用測試數據模組的文本樣本進行批次測試
            test_texts = [
                SHORT_TEXT_SAMPLE,
                MEDIUM_TEXT_SAMPLE.split('\n')[1],  # 取中等文本的第一段
                "",  # 空文字測試
                "技術測試：系統性能優化已完成，準備進入下一階段的功能測試。"
            ]
            
            payload = {
                'texts': test_texts,
                'processing_mode': 'default',
                'detail_level': 'normal',
                'ai_model': 'phi4-mini:3.8b'
            }
            
            print(f"批次處理 {len(test_texts)} 個文字...")
            start_time = time.time()
            
            response = requests.post(f"{self.api_base}/batch/text", 
                                   headers=headers, 
                                   json=payload)
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                summary = data.get('summary', {})
                
                print(f"✅ 批次處理完成 (耗時: {processing_time:.2f}s)")
                print(f"   總數: {summary.get('total_items')}")
                print(f"   成功: {summary.get('success_count')}")
                print(f"   錯誤: {summary.get('error_count')}")
                print(f"   跳過: {summary.get('skip_count')}")
                print(f"   平均耗時: {summary.get('average_time_per_item', 0):.2f}s/項")
                
                # 檢查結果
                results = data.get('results', [])
                for result in results:
                    status_icon = "✅" if result['status'] == 'success' else "⚠️" if result['status'] == 'skipped' else "❌"
                    print(f"   {status_icon} 項目 {result['index']}: {result['status']}")
                
                return summary.get('success_count', 0) > 0
            else:
                print(f"❌ 批次處理失敗: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 批次處理異常: {e}")
            return False
    
    def test_audio_processing(self) -> bool:
        """測試音頻處理"""
        print("\n=== 測試音頻處理 ===")
        
        if not self.client_id:
            print("❌ 需要先註冊客戶端")
            return False
        
        try:
            headers = {'X-Client-ID': self.client_id}
            
            # 創建測試音頻
            print("創建測試音頻文件...")
            audio_file = self.create_test_audio(duration=2.0)
            
            try:
                with open(audio_file, 'rb') as f:
                    files = {'audio': ('test_audio.wav', f, 'audio/wav')}
                    data = {
                        'whisper_model': 'base',
                        'enable_llm': 'true',
                        'processing_mode': 'default',
                        'detail_level': 'normal',
                        'ai_model': 'phi4-mini:3.8b',
                        'language': 'chinese'
                    }
                    
                    print("上傳並處理音頻...")
                    start_time = time.time()
                    
                    response = requests.post(f"{self.api_base}/audio/process", 
                                           headers=headers, 
                                           files=files, 
                                           data=data,
                                           timeout=120)
                    
                    processing_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"✅ 音頻處理成功 (耗時: {processing_time:.2f}s)")
                        
                        file_info = result.get('file_info', {})
                        transcription = result.get('transcription', {})
                        timing = file_info.get('processing_time', {})
                        
                        print(f"   文件大小: {file_info.get('file_size', 0)} bytes")
                        print(f"   Whisper 耗時: {timing.get('whisper', 0)}s")
                        print(f"   AI 處理耗時: {timing.get('ai_processing', 0)}s")
                        print(f"   總耗時: {timing.get('total', 0)}s")
                        
                        original_text = transcription.get('original_text', '')
                        processed_text = transcription.get('processed_text', '')
                        
                        print(f"   原始轉錄: {original_text}")
                        if processed_text:
                            print(f"   AI 整理: {processed_text}")
                        
                        print(f"   字數: {transcription.get('word_count', 0)}")
                        print(f"   語言: {transcription.get('language', 'N/A')}")
                        
                        return True
                    else:
                        print(f"❌ 音頻處理失敗: {response.status_code} - {response.text}")
                        return False
                        
            finally:
                # 清理測試文件
                try:
                    os.unlink(audio_file)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ 音頻處理異常: {e}")
            return False
    
    def run_complete_test(self) -> Dict[str, bool]:
        """運行完整測試"""
        print("🧪 開始外部 API 完整測試...")
        print(f"API 基礎 URL: {self.api_base}")
        
        test_results = {}
        
        # 測試順序很重要
        tests = [
            ('客戶端註冊', self.test_client_registration),
            ('系統狀態', self.test_system_status),
            ('配置管理', self.test_config_management),
            ('文字處理', self.test_text_processing),
            ('批次文字處理', self.test_batch_text_processing),
            ('音頻處理', self.test_audio_processing)
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                test_results[test_name] = result
                
                if result:
                    print(f"✅ {test_name} 測試通過")
                else:
                    print(f"❌ {test_name} 測試失敗")
                    
            except Exception as e:
                print(f"❌ {test_name} 測試異常: {e}")
                test_results[test_name] = False
        
        return test_results
    
    def print_test_summary(self, results: Dict[str, bool]):
        """打印測試總結"""
        print("\n" + "="*60)
        print("📊 測試結果總結")
        print("="*60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        for test_name, result in results.items():
            status = "✅ 通過" if result else "❌ 失敗"
            print(f"{test_name:20} : {status}")
        
        print("-" * 60)
        print(f"通過率: {passed}/{total} ({pass_rate:.1f}%)")
        
        if pass_rate == 100:
            print("🎉 所有測試通過！外部 API 可以投入使用")
        elif pass_rate >= 80:
            print("⚠️ 大部分測試通過，可能有些功能需要修復")
        else:
            print("❌ 多項測試失敗，需要檢查系統配置")
        
        print("="*60)
        
        if self.client_id:
            print(f"\n🔑 測試客戶端信息:")
            print(f"Client ID: {self.client_id}")
            print(f"API Key: {self.api_key}")

def main():
    """主測試函數"""
    # 檢查服務器是否運行
    try:
        response = requests.get("http://127.0.0.1:3080/health", timeout=5)
        print("✅ 檢測到 Flask 服務器正在運行")
    except:
        print("❌ Flask 服務器未運行，請先啟動服務器")
        print("   cd backend && python app.py")
        return
    
    # 運行測試
    tester = ExternalAPITester()
    results = tester.run_complete_test()
    tester.print_test_summary(results)

if __name__ == "__main__":
    main()