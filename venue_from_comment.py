"""
从 arXiv Atom comment 中解析顶会标签（如 venue.NeurIPS，不含年份）。
仅通过 AiApi（LLM）；comment 无固定格式，不使用正则规则。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ai_api import AiApi


def extract_venue_tag_from_comment(
    comment: str, ai_api: Optional["AiApi"] = None
) -> Optional[str]:
    """
    返回完整标签名（venue. 会议简称，无年份）；无 ai_api、comment 为空，或 API 未配置 / 无明确顶会时返回 None。
    """
    if ai_api is None or not (comment or "").strip():
        return None
    return ai_api.extract_venue_tag_from_comment(comment)
