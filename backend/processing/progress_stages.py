"""
統一進度常量和 ProgressTracker 類

提供規範的階段名稱（無 emoji，前端友好）和單調遞增的進度追蹤器。
"""
import logging

logger = logging.getLogger(__name__)

# 規範階段名稱（無 emoji，前端友好）
STAGE_PREPARING = "音頻預處理"
STAGE_AUDIO_ENHANCEMENT = "音頻增強"
STAGE_NORMALIZATION = "響度正規化"
STAGE_ASR = "語音識別"
STAGE_REFINEMENT = "文字精煉"
STAGE_AI_PROCESSING = "AI 智能整理"
STAGE_COMPLETED = "處理完成"

# 文字處理專用階段
STAGE_TEXT_PREPARING = "準備處理文字"
STAGE_TEXT_CLEANING = "文字清理"
STAGE_TEXT_AI_PROCESSING = "AI 處理中"


class ProgressTracker:
    """單調遞增進度追蹤器，防止進度倒退"""

    def __init__(self, task_id, queue_manager):
        self._task_id = task_id
        self._qm = queue_manager
        self._current_pct = 0

    def update(self, stage, percentage, message=None):
        """更新進度，確保百分比不會倒退

        Args:
            stage: 階段名稱（使用 STAGE_* 常量）
            percentage: 百分比（0-100）
            message: 可選的詳細訊息
        """
        safe_pct = max(self._current_pct, int(percentage))
        self._current_pct = safe_pct
        if self._qm:
            self._qm.update_task_progress(
                self._task_id, stage, safe_pct, message or stage
            )

    def make_callback(self):
        """產生可傳遞到子模組的 callback function"""
        def callback(stage, percentage, message=None):
            self.update(stage, percentage, message)
        return callback
