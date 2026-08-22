"""StyleSnap —— 照片 + 提示词 → 百种风格

FastAPI 服务：
  GET  /api/health         状态（demo / replicate 模式）
  GET  /api/styles         提示词库（?lang=zh|en）
  POST /api/transform      单张照片 + 风格 → 生成结果
  GET  /                   前端单页
"""
import logging
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .providers import MockProvider, ReplicateProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("stylesnap")

app = FastAPI(title="StyleSnap", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------- 加载提示词库 / load the prompt library ----------------
with open(config.STYLES_FILE, encoding="utf-8") as f:
    LIBRARY = yaml.safe_load(f)
STYLES = LIBRARY["styles"]
STYLE_MAP = {s["id"]: s for s in STYLES}
DEFAULT_NEGATIVE = LIBRARY.get("common_negative", "")

CATEGORIES = {
    "anime": {"zh": "动漫", "en": "Anime"},
    "film3d": {"zh": "影视/3D", "en": "Film & 3D"},
    "art": {"zh": "艺术", "en": "Art"},
    "scifi": {"zh": "科幻", "en": "Sci-fi"},
    "guofeng": {"zh": "古风", "en": "Chinese"},
    "fun": {"zh": "趣味", "en": "Fun"},
}

# ---------------- Provider 选择 ----------------
if config.MOCK_MODE:
    provider = MockProvider()
    MODE = "demo"
    logger.warning("运行在演示模式(Mock)——未配置 REPLICATE_API_TOKEN，将输出模拟结果")
else:
    provider = ReplicateProvider(config.REPLICATE_MODEL, config.REPLICATE_API_TOKEN)
    MODE = "replicate"
    logger.info("运行在真实生成模式，模型：%s", config.REPLICATE_MODEL)

MAX_IMAGE_BYTES = 15_000_000


def _localize(style: dict, lang: str) -> dict:
    return {
        "id": style["id"],
        "emoji": style.get("emoji", "✨"),
        "category": style["category"],
        "category_zh": CATEGORIES.get(style["category"], {}).get("zh", ""),
        "category_en": CATEGORIES.get(style["category"], {}).get("en", ""),
        "name": style["name_zh"] if lang == "zh" else style["name_en"],
        "desc": style["desc_zh"] if lang == "zh" else style["desc_en"],
        "prompt": style["prompt"],
        "negative_prompt": style.get("negative_prompt", DEFAULT_NEGATIVE),
        "params": style.get("params", {}),
    }


def _build_prompt(style: dict, subject: str, prompt_override: str) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()
    return style["prompt"].format(subject=(subject or "this person").strip())


# ---------------- 路由 ----------------
@app.get("/api/health")
def health():
    return {"ok": True, "mode": MODE, "styles": len(STYLES), "model": config.REPLICATE_MODEL}


@app.get("/api/styles")
def list_styles(lang: str = "zh"):
    return {
        "categories": [{"key": k, "name_zh": v["zh"], "name_en": v["en"]} for k, v in CATEGORIES.items()],
        "styles": [_localize(s, lang) for s in STYLES],
    }


@app.post("/api/transform")
async def transform(
    image: UploadFile = File(...),
    style_id: str = Form(...),
    subject: str = Form("this person"),
    prompt: str = Form(""),
):
    if style_id not in STYLE_MAP:
        raise HTTPException(404, f"未知风格 / unknown style: {style_id}")

    data = await image.read()
    if not data:
        raise HTTPException(400, "空图片 / empty image")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "图片过大，请压缩到 15MB 以内 / image too large (max 15MB)")

    style = STYLE_MAP[style_id]
    final_prompt = _build_prompt(style, subject, prompt)
    logger.info("transform style=%s prompt=%r", style_id, final_prompt[:120])

    out_name = f"{style_id}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = config.OUTPUT_DIR / out_name
    try:
        provider.transform(data, style, subject or "this person", out_path)
    except Exception as exc:  # 统一转成可读错误
        logger.exception("生成失败 / generation failed")
        raise HTTPException(502, f"生成失败 / generation failed: {exc}")

    return {"style_id": style_id, "output_url": f"/output/{out_name}", "mode": MODE}


# ---------------- 静态资源 ----------------
app.mount("/output", StaticFiles(directory=str(config.OUTPUT_DIR)), name="output")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=config.PORT, reload=True)
