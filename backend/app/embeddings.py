import io
import logging
from functools import lru_cache

import numpy as np
import torch
import xxhash
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from .config import settings

logger = logging.getLogger(__name__)

EMBED_DIM = 512
_embedder: "FashionCLIPEmbedder | None" = None


class FashionCLIPEmbedder:
    def __init__(self, model_id: str = settings.model_id):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading FashionCLIP model %s on %s", model_id, self.device)
        self.model = CLIPModel.from_pretrained(model_id)
        self.processor = CLIPProcessor.from_pretrained(model_id)
        self.model = self.model.to(self.device)
        if self.device == "cuda":
            self.model = self.model.half()
        self.model.eval()
        self.model_id = model_id
        logger.info("FashionCLIP ready")

    def preprocess(self, raw: bytes) -> Image.Image:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        # Strip EXIF by re-encoding through Pillow (loses all metadata)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    def embed_pil_batch(self, images: list[Image.Image]) -> np.ndarray:
        inputs = self.processor(images=images, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            feats = self.model.get_image_features(**inputs)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().float().numpy()

    def embed_bytes(self, raw: bytes) -> tuple[np.ndarray, bytes]:
        """Embed a single image from raw bytes. Returns (embedding, content_hash)."""
        img = self.preprocess(raw)
        content_hash = xxhash.xxh64(raw).digest()
        embedding = self.embed_pil_batch([img])[0]
        return embedding, content_hash

    def embed_bytes_batch(self, raws: list[bytes]) -> tuple[list[np.ndarray], list[bytes]]:
        images = [self.preprocess(r) for r in raws]
        hashes = [xxhash.xxh64(r).digest() for r in raws]
        embeddings = self.embed_pil_batch(images)
        return list(embeddings), hashes


def get_embedder() -> FashionCLIPEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = FashionCLIPEmbedder()
    return _embedder
