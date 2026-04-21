#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI 1: ocr-image

对一张或多张图片跑百度 OCR，抽取方案标题和项目列表，输出结构化 JSON。

用法示例：
  python scripts/ocr_image.py --image a.jpg --image b.jpg --output ocr.json
  python scripts/ocr_image.py --image test/1/*.jpeg --cache-dir test/1/.ocr_cache/

凭据优先级：CLI 参数 > 环境变量 > --credentials 文件（默认读 config/credentials.json）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

# 支持 'python scripts/ocr_image.py' 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.core.logger import configure_logging, get_logger  # noqa: E402
from scripts.core.ocr_client import BaiduOCRClient, OCRError  # noqa: E402
from scripts.core.ocr_extractor import extract_schemes  # noqa: E402
from scripts.core.rules import (  # noqa: E402
    default_credentials_path,
    load_credentials,
)

logger = get_logger(__name__)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="对图片跑百度 OCR 并抽取方案。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--image",
        action="append",
        required=True,
        help="图片路径（可重复；也可用 shell 通配符一次传入多张）",
    )
    parser.add_argument("--api-key", default=None, help="百度 OCR API Key（最高优先级）")
    parser.add_argument("--secret-key", default=None, help="百度 OCR Secret Key（最高优先级）")
    parser.add_argument(
        "--credentials",
        default=str(default_credentials_path()),
        help="凭据 JSON 文件路径（兜底）",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="OCR 原始响应缓存目录（命中则跳过 API）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出 JSON 路径；不指定则输出到 stdout",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="输出 DEBUG 级别日志"
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    configure_logging(level=10 if args.verbose else 20)  # 10=DEBUG 20=INFO

    credentials = load_credentials(args.api_key, args.secret_key, args.credentials)
    client = BaiduOCRClient(credentials=credentials, cache_dir=args.cache_dir)

    image_results = []
    for image_path in args.image:
        result = _process_one_image(client, image_path)
        image_results.append(result)

    payload = {"images": image_results}
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        logger.info(f"OCR result written to {out}")
    else:
        sys.stdout.write(text + "\n")

    return 0


def _process_one_image(client: BaiduOCRClient, image_path: str) -> dict:
    """处理单张图片，返回 {file, path, status, error, ocr_schemes, raw_words}"""
    p = Path(image_path)
    base = {"file": p.name, "path": str(p)}
    try:
        payload = client.recognize(image_path)
    except (OCRError, FileNotFoundError) as exc:
        logger.error(f"OCR failed for {p.name}: {exc}")
        return {**base, "status": "ocr_failed", "error": str(exc), "ocr_schemes": [], "raw_words": []}

    schemes = extract_schemes(payload)
    raw_words = [str(e.get("words", "")) for e in payload.get("words_result", [])]
    status = "ok" if schemes else "no_scheme_detected"
    error = None if schemes else "OCR returned no scheme."

    return {
        **base,
        "status": status,
        "error": error,
        "ocr_schemes": [{"title": s.title, "items": s.items} for s in schemes],
        "raw_words": raw_words,
    }


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except Exception as exc:
        logger.exception(f"ocr-image failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
