"""
網路模式管理器
管理上網模式的開啟和關閉，以及相關功能的啟用
"""
import logging
import requests
import time
from typing import Optional, Dict, Any
from config import config

logger = logging.getLogger(__name__)

class NetworkManager:
    def __init__(self):
        self.is_online = False
        self.last_check_time = 0
        self.check_interval = 60  # 60秒檢查一次
        self.test_urls = [
            "https://www.google.com",
            "https://www.microsoft.com",
            "https://httpbin.org/get"
        ]
    
    def is_network_mode_enabled(self) -> bool:
        """檢查是否啟用網路模式"""
        return config.NETWORK_MODE_ENABLED
    
    def check_internet_connection(self, force_check: bool = False) -> bool:
        """
        檢查網路連接狀態

        🔒 離線優化：當 NETWORK_MODE_ENABLED=false 時，
        直接返回 False，不進行任何網路請求，避免延遲
        """
        # 🔒 離線模式優化：立即返回，無延遲
        if not self.is_network_mode_enabled():
            self.is_online = False
            return False

        current_time = time.time()

        # 如果不強制檢查且距離上次檢查時間不足間隔時間，返回緩存結果
        if not force_check and (current_time - self.last_check_time) < self.check_interval:
            return self.is_online

        self.last_check_time = current_time

        # 🔒 優化：使用更短的超時時間，減少離線時的等待
        for url in self.test_urls:
            try:
                response = requests.get(url, timeout=3)  # 從 5 秒減少到 3 秒
                if response.status_code == 200:
                    self.is_online = True
                    logger.debug(f"網路連接正常：{url}")  # 改為 debug 減少日誌
                    return True
            except requests.exceptions.Timeout:
                logger.debug(f"連接超時: {url}")
                continue
            except requests.exceptions.ConnectionError:
                logger.debug(f"無法連接: {url}")
                continue
            except Exception as e:
                logger.debug(f"網路檢查錯誤 {url}: {str(e)}")
                continue

        self.is_online = False
        logger.debug("網路連接不可用（離線模式）")  # 改為 debug，不是警告
        return False
    
    def get_network_status(self) -> Dict[str, Any]:
        """
        獲取網路狀態信息
        """
        return {
            "network_mode_enabled": self.is_network_mode_enabled(),
            "is_online": self.is_online,
            "last_check_time": self.last_check_time,
            "check_interval": self.check_interval
        }
    
    def enable_network_mode(self) -> bool:
        """
        啟用網路模式（需要更新配置）
        """
        # 這裡只是檢查，實際的啟用需要更新環境變數或配置文件
        logger.info("網路模式啟用請求")
        return self.check_internet_connection(force_check=True)
    
    def disable_network_mode(self) -> bool:
        """
        禁用網路模式
        """
        logger.info("網路模式禁用")
        self.is_online = False
        return True

# 全局網路管理器實例
network_manager = NetworkManager()

