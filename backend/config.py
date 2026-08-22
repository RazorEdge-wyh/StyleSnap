"""StyleSnap 配置 / Configuration."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 未安装时静默跳过
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")
STYLES_FILE = BASE_DIR / "styles.yaml"
FRONTEND_DIR = BASE_DIR / "frontend"
OUTPUT_DIR = BASE_DIR / "output"


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


# Replicate API token —— 留空会自动进入演示模式(Mock)
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "").strip()
# InstantID 模型（zedge/instantid 字段: input_image + identitynet_strength_ratio + ip_adapter_scale）
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL", "zedge/instantid").strip()

# 演示模式：显式开启，或未配置 token 时自动开启
MOCK_MODE = _truthy(os.getenv("MOCK_MODE", "")) or not REPLICATE_API_TOKEN

PORT = int(os.getenv("PORT", "8000"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
