"""生成 Provider / Generation providers.

两个后端实现同一个 transform() 接口：
  - ReplicateProvider  真实生成，调用 Replicate 上的 InstantID（需 API token，成本约 ¥0.1/张）
  - MockProvider       演示模式，用 Pillow 做简易风格化，无密钥也能跑通整个产品流程

Both implement the same transform() interface:
  - ReplicateProvider  real generation via Replicate InstantID (needs API token)
  - MockProvider       local demo mode using Pillow filters, no key required
"""
import io
import logging

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

logger = logging.getLogger(__name__)


class BaseProvider:
    def transform(self, image_bytes: bytes, style: dict, subject: str, out_path) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# ReplicateProvider —— 真实生成 / real generation
# ---------------------------------------------------------------------------
class ReplicateProvider(BaseProvider):
    def __init__(self, model: str, token: str):
        self.model = model
        self.token = token

    def transform(self, image_bytes: bytes, style: dict, subject: str, out_path) -> None:
        import replicate

        client = replicate.Client(api_token=self.token)
        params = style.get("params", {})
        inputs = {
            "input_image": io.BytesIO(image_bytes),  # file-like，SDK 会自动上传
            "prompt": style["prompt"].format(subject=subject or "this person"),
            "negative_prompt": style.get("negative_prompt", ""),
            "identitynet_strength_ratio": params.get("identitynet", 0.8),
            "ip_adapter_scale": params.get("adapter", 0.8),
            "num_inference_steps": params.get("steps", 30),
            "guidance_scale": params.get("guidance", 5),
        }
        try:
            output = client.run(self.model, input=inputs)
        except Exception as exc:
            # 个别端口把字段命名为 adapter_strength_ratio，失败时重试一次
            if "adapter_strength_ratio" in str(exc) or "ip_adapter_scale" in str(exc):
                inputs["adapter_strength_ratio"] = inputs.pop("ip_adapter_scale")
                output = client.run(self.model, input=inputs)
            else:
                raise

        url = output[0] if isinstance(output, list) else output
        if not isinstance(url, str) or not url.startswith("http"):
            raise RuntimeError(f"unexpected output from {self.model}: {url!r}")

        import httpx
        resp = httpx.get(url, timeout=300, follow_redirects=True)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)


# ---------------------------------------------------------------------------
# MockProvider —— 演示模式 / demo mode
# ---------------------------------------------------------------------------
class MockProvider(BaseProvider):
    """用 Pillow 滤镜模拟风格化，仅用于演示产品流程，非真实 AI 生成。"""

    def transform(self, image_bytes: bytes, style: dict, subject: str, out_path) -> None:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = _style_filter(img, style.get("id", ""))
        _draw_demo_badge(img)
        img.save(out_path, "JPEG", quality=92)


def _draw_demo_badge(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    label = "StyleSnap DEMO"
    try:
        font = ImageFont.load_default(size=26)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), label, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x, y = img.width - w - 18, img.height - h - 18
    draw.rounded_rectangle([x - 10, y - 8, x + w + 10, y + h + 8], radius=8, fill=(0, 0, 0, 190))
    draw.text((x, y), label, font=font, fill=(255, 255, 255))


def _matrix(img: Image.Image, matrix: list) -> Image.Image:
    return img.convert("RGB", matrix)


def _style_filter(img: Image.Image, style_id: str) -> Image.Image:
    sid = style_id or ""
    if sid == "pixel":
        small = img.resize((max(8, img.width // 12), max(8, img.height // 12)), Image.Resampling.NEAREST)
        return small.resize(img.size, Image.Resampling.NEAREST)
    if sid == "sketch":
        gray = ImageOps.grayscale(img)
        edges = ImageOps.invert(gray.filter(ImageFilter.FIND_EDGES))
        return ImageOps.autocontrast(edges).convert("RGB")
    if sid == "manga":
        gray = ImageOps.grayscale(img).filter(ImageFilter.SMOOTH_MORE)
        return ImageOps.posterize(gray, 4).convert("RGB")
    if sid == "goldstatue":
        return ImageOps.posterize(_matrix(img, SEPIA), 5)
    if sid == "oil":
        return ImageOps.posterize(_matrix(img, SEPIA), 6)
    if sid in ("anime", "ghibli"):
        return ImageEnhance.Color(ImageOps.posterize(img, 5)).enhance(1.6).filter(ImageFilter.SMOOTH)
    if sid == "cyberpunk":
        return ImageEnhance.Contrast(_matrix(img, TEAL_MAGENTA)).enhance(1.3)
    if sid in ("clay", "toy", "lego", "chibi", "3drender", "pixar", "robot", "mecha", "cat", "doll", "guofeng", "hanfu"):
        return img.quantize(colors=32).convert("RGB").filter(ImageFilter.SHARPEN)
    if sid == "watercolor":
        return ImageEnhance.Brightness(img.filter(ImageFilter.GaussianBlur(1.5))).enhance(1.05)
    if sid == "inkwash":
        return _matrix(ImageOps.autocontrast(img), WARM)
    return img.filter(ImageFilter.SMOOTH)


# 简易调色矩阵（PIL convert 用 4×3 共 12 元组）/ simple color matrices (PIL 4x3)
SEPIA = [0.393, 0.769, 0.189, 0, 0.349, 0.686, 0.168, 0, 0.272, 0.534, 0.131, 0]
TEAL_MAGENTA = [0.95, 0.0, 0.25, 0, 0.0, 1.0, 0.0, 0, 0.25, 0.0, 1.1, 0]
WARM = [1.05, 0.08, 0.04, 0, 0.0, 0.98, 0.05, 0, 0.0, 0.0, 0.92, 0]
