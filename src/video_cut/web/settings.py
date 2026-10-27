"""System settings management API routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from video_cut.auth.auth import require_role
from video_cut.db.models import User


router = APIRouter()

# Settings file path
SETTINGS_FILE = Path("data/settings.json")


class ModelConfig(BaseModel):
    """Model configuration."""
    model_name: str = Field(..., description="Model name/ID")
    api_key: Optional[str] = Field(None, description="API key for the model")
    endpoint: Optional[str] = Field(None, description="Custom API endpoint")
    enabled: bool = Field(True, description="Whether this model is enabled")


class SystemSettings(BaseModel):
    """Complete system settings."""
    # ASR Settings
    asr_model: str = Field(default="paraformer-realtime-v2", description="ASR model to use")
    asr_api_key: Optional[str] = Field(None, description="ASR API key")

    # LLM Settings
    llm_model: str = Field(default="qwen-max", description="LLM model to use")
    llm_api_key: Optional[str] = Field(None, description="LLM API key")

    # VL Settings
    vl_model: str = Field(default="qwen-vl-max", description="Vision-Language model")
    vl_api_key: Optional[str] = Field(None, description="VL API key")

    # General Settings
    max_upload_size_gb: int = Field(default=5, description="Maximum upload file size in GB")
    default_output_duration: int = Field(default=180, description="Default output duration in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "asr_model": "paraformer-realtime-v2",
                "asr_api_key": "sk-xxx",
                "llm_model": "qwen-max",
                "llm_api_key": "sk-xxx",
                "vl_model": "qwen-vl-max",
                "vl_api_key": "sk-xxx",
                "max_upload_size_gb": 5,
                "default_output_duration": 180
            }
        }


def load_settings() -> SystemSettings:
    """Load settings from file or return defaults."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return SystemSettings(**data)
        except Exception:
            # If file is corrupted, return defaults
            pass

    # Return default settings
    return SystemSettings(
        asr_api_key=os.getenv("VIDEO_CUT_DASHSCOPE_API_KEY"),
        llm_api_key=os.getenv("VIDEO_CUT_DASHSCOPE_API_KEY"),
        vl_api_key=os.getenv("VIDEO_CUT_DASHSCOPE_API_KEY"),
    )


def save_settings(settings: SystemSettings) -> None:
    """Save settings to file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings.dict(), f, indent=2, ensure_ascii=False)


def update_env_file(key: str, value: str) -> None:
    """Update .env file with new setting."""
    env_file = Path(".env")

    # Read existing content
    lines = []
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    # Update or add the key
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}\n")

    # Write back
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)


@router.get("/settings", response_class=None)
async def settings_page(
    request: Request,
    templates: Jinja2Templates = Depends(lambda: Jinja2Templates(directory=Path(__file__).parent / "templates")),
    current_user: User = Depends(require_role("admin")),
):
    """Settings page (admin only)."""
    return templates.TemplateResponse(request, "settings.html", {})


@router.get("/api/settings", response_model=SystemSettings)
async def get_settings(current_user: User = Depends(require_role("admin"))):
    """Get current system settings (admin only)."""
    return load_settings()


@router.post("/api/settings", response_model=SystemSettings)
async def update_settings(
    settings: SystemSettings,
    current_user: User = Depends(require_role("admin")),
):
    """Update system settings (admin only)."""
    try:
        save_settings(settings)

        # Also update .env file for backward compatibility
        if settings.asr_api_key:
            update_env_file("VIDEO_CUT_DASHSCOPE_API_KEY", settings.asr_api_key)
        if settings.llm_api_key:
            update_env_file("VIDEO_CUT_LLM_MODEL", settings.llm_model)
        if settings.asr_model:
            update_env_file("VIDEO_CUT_ASR_MODEL", settings.asr_model)

        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.get("/api/settings/models/asr")
async def list_asr_models(current_user: User = Depends(require_role("admin"))):
    """List available ASR models."""
    return {
        "models": [
            {"id": "paraformer-realtime-v2", "name": "Paraformer Realtime v2 (推荐)", "description": "实时流式识别，无需OSS"},
            {"id": "paraformer-v2", "name": "Paraformer v2", "description": "异步任务式识别"},
        ],
        "default": "paraformer-realtime-v2"
    }


@router.get("/api/settings/models/llm")
async def list_llm_models(current_user: User = Depends(require_role("admin"))):
    """List available LLM models."""
    return {
        "models": [
            {"id": "qwen-max", "name": "Qwen-Max (推荐)", "description": "最强语义理解能力"},
            {"id": "qwen-plus", "name": "Qwen-Plus", "description": "平衡性能与成本"},
            {"id": "qwen-turbo", "name": "Qwen-Turbo", "description": "快速响应，适合简单任务"},
        ],
        "default": "qwen-max"
    }


@router.get("/api/settings/models/vl")
async def list_vl_models(current_user: User = Depends(require_role("admin"))):
    """List available Vision-Language models."""
    return {
        "models": [
            {"id": "qwen-vl-max", "name": "Qwen-VL-Max (推荐)", "description": "最强视觉理解能力"},
            {"id": "qwen-vl-plus", "name": "Qwen-VL-Plus", "description": "平衡性能与成本"},
        ],
        "default": "qwen-vl-max"
    }


@router.delete("/api/settings/cache")
async def clear_settings_cache(current_user: User = Depends(require_role("admin"))):
    """Clear settings cache and temporary files (admin only)."""
    try:
        cleaned = 0
        # Clean up old upload files
        upload_dir = Path("output/_uploads")
        if upload_dir.exists():
            import time
            now = time.time()
            max_age_seconds = 24 * 3600  # 24 hours

            for file_path in upload_dir.glob("*"):
                if file_path.is_file():
                    file_age = now - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            cleaned += 1
                        except OSError:
                            pass

        return {"message": f"Cache cleared, {cleaned} files removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
