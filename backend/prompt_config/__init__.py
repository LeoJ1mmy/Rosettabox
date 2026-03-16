"""
配置模組
"""

from .prompt_config import PromptConfig, ProcessingMode, DetailLevel, generate_prompt

__all__ = [
    'PromptConfig',
    'ProcessingMode', 
    'DetailLevel',
    'generate_prompt'
]

# 便利函數
def validate_config(mode: str, detail_level: str) -> tuple[bool, str]:
    """驗證配置參數"""
    return PromptConfig.validate_mode_and_detail(mode, detail_level)

def get_available_options():
    """獲取所有可用選項"""
    return {
        'modes': PromptConfig.get_available_modes(),
        'detail_levels': PromptConfig.get_available_detail_levels()
    }
