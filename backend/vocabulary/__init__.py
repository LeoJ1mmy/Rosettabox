"""
Vocabulary package - 詞彙管理模組
"""

# 導出主要的配置對象
from .vocabulary_config import vocabulary_config, VocabularyConfig
from .vocabulary_prompt_generator import prompt_generator, VocabularyPromptGenerator, generate_whisper_prompt

__all__ = [
    'vocabulary_config',
    'VocabularyConfig',
    'prompt_generator',
    'VocabularyPromptGenerator',
    'generate_whisper_prompt',
]
