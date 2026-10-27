"""Artifact file names within a video's output directory.

Single source of truth for the pipeline's intermediate artifacts, so the
commands agree on where each step reads and writes.
"""

AUDIO_FILE_NAME = "audio.m4a"
TRANSCRIPT_FILE_NAME = "transcript.json"
HIGHLIGHTS_FILE_NAME = "highlights.json"
MERGED_FILE_NAME = "merged.mp4"
CLIPS_DIR_NAME = "clips"

# Web 层持久化的会话映射：video output 目录下记录源视频路径。
WEB_SESSION_FILE_NAME = "web-session.json"

# Highlight 序列的人工调整工作副本（Draft）：web 界面编辑落盘于此，
# 原始 highlights.json 永不被修改。
HIGHLIGHTS_DRAFT_FILE_NAME = "highlights.draft.json"
