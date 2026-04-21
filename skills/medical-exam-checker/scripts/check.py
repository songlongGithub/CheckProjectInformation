#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI 2: check

端到端体检方案核对：
  Excel → 方案分类 → 对每张图片调 OCR（或读缓存）→ 抽方案 → 匹配（三层）→ 报告

用法：
  # 完整链路（默认用 Gemini 做 LLM 兜底）
  python scripts/check.py --excel a.xlsx --images a.jpg --output report.json

  # 只做 Excel 解析（离线验证）
  python scripts/check.py --excel a.xlsx --excel-only --output schemes.json

  # 关闭 LLM 层（纯规则+fuzzy）
  python scripts/check.py --excel a.xlsx --images a.jpg --no-llm --output report.json

  # 切换到 Claude
  python scripts/check.py --excel a.xlsx --images a.jpg \\
      --llm-provider claude --llm-model claude-haiku-4-5

  # 用已有 OCR 缓存复跑（不消耗百度配额）
  python scripts/check.py --excel a.xlsx --images a.jpg b.jpg \\
      --ocr-cache-dir test/1/.ocr_cache/ --output report.json --markdown report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

# 支持脚本直跑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.core.excel_parser import ExcelParser, Scheme  # noqa: E402
from scripts.core.llm_client import build_llm_client  # noqa: E402
from scripts.core.logger import configure_logging, get_logger  # noqa: E402
from scripts.core.matcher import (  # noqa: E402
    build_alias_map,
    compare_items,
    match_scheme_name,
)
from scripts.core.ocr_client import BaiduOCRClient, OCRError  # noqa: E402
from scripts.core.ocr_extractor import extract_schemes  # noqa: E402
from scripts.core.reporter import (  # noqa: E402
    build_image_result_failed,
    build_image_result_ok,
    build_ocr_scheme_result,
    build_report,
    render_markdown,
)
from scripts.core.rules import (  # noqa: E402
    default_credentials_path,
    default_rules_path,
    load_credentials,
    load_llm_credentials,
    load_rules,
)

logger = get_logger(__name__)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="体检方案 Excel × 图片 OCR 端到端核对（三层匹配：规则 → fuzzy → LLM）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--excel", required=True, help="体检方案 Excel 文件路径")
    parser.add_argument(
        "--images",
        nargs="*",
        default=[],
        help="图片路径列表（支持 shell 通配符）",
    )
    parser.add_argument(
        "--rules",
        default=str(default_rules_path()),
        help="规则 JSON（别名/重命名/性别重命名/composites）",
    )
    # 百度 OCR 凭据
    parser.add_argument("--api-key", default=None, help="百度 OCR API Key（最高优先级）")
    parser.add_argument("--secret-key", default=None, help="百度 OCR Secret Key（最高优先级）")
    parser.add_argument(
        "--credentials",
        default=str(default_credentials_path()),
        help="凭据 JSON 文件路径（OCR + LLM 兜底）",
    )
    parser.add_argument(
        "--ocr-cache-dir",
        default=None,
        help="OCR 缓存目录；命中则不调 API，不命中自动回源并写缓存",
    )
    # LLM 开关
    parser.add_argument(
        "--llm-provider",
        default="gemini",
        choices=["gemini", "claude", "none"],
        help="LLM 提供方（none 表示关闭 LLM 层）",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM 模型（gemini 默认 gemini-2.0-flash；claude 默认 claude-haiku-4-5）",
    )
    parser.add_argument("--gemini-key", default=None, help="Gemini API Key（覆盖环境变量）")
    parser.add_argument("--claude-key", default=None, help="Claude API Key（覆盖环境变量）")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="便捷开关：等同 --llm-provider=none",
    )
    parser.add_argument(
        "--llm-cache-dir",
        default=None,
        help="LLM 响应缓存目录（按内容 hash，复跑零成本）",
    )
    # 其他
    parser.add_argument(
        "--excel-only",
        action="store_true",
        help="只解析 Excel 并导出 schemes，不跑 OCR 与对比",
    )
    parser.add_argument(
        "--output",
        default="report.json",
        help="输出 JSON 路径",
    )
    parser.add_argument(
        "--markdown",
        default=None,
        help="可选：额外输出 Markdown 报告到该路径",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG 级别日志")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    configure_logging(level=10 if args.verbose else 20)

    # ---------- 1. 加载规则 ----------
    rules = load_rules(args.rules)
    alias_map = build_alias_map(rules.aliases)

    # ---------- 2. 解析 Excel ----------
    parser_ = ExcelParser(args.excel, rules)
    schemes = parser_.parse()

    # ---------- 3. excel-only 分支 ----------
    if args.excel_only:
        _write_excel_only_report(args.excel, parser_.sheet_names_in_order, schemes, args.output)
        return 0

    # ---------- 4. 必须有图片 ----------
    if not args.images:
        logger.error("No images provided. Use --images or pass --excel-only.")
        return 2

    # ---------- 5. 构建 OCR 客户端 ----------
    ocr_client = _build_ocr_client(args)

    # ---------- 6. 构建 LLM 客户端 ----------
    llm_client = _build_llm_client(args)

    # ---------- 7. 逐图处理 ----------
    full_scheme_names = [s.full_name for s in schemes]
    excel_items_by_full_name: Dict[str, List[str]] = {s.full_name: s.items for s in schemes}

    image_results = []
    for image_path in args.images:
        image_result = _process_image(
            image_path=image_path,
            client=ocr_client,
            full_scheme_names=full_scheme_names,
            excel_items_by_full_name=excel_items_by_full_name,
            alias_map=alias_map,
            composites=rules.composites,
            llm_client=llm_client,
        )
        image_results.append(image_result)

    # ---------- 8. 合成报告 ----------
    report = build_report(
        excel_path=args.excel,
        sheets_in_order=parser_.sheet_names_in_order,
        schemes=schemes,
        image_results=image_results,
    )
    _write_json(args.output, report)
    logger.info(f"Report written to {args.output}")

    if args.markdown:
        _write_text(args.markdown, render_markdown(report))
        logger.info(f"Markdown report written to {args.markdown}")

    return 0


def _build_ocr_client(args: argparse.Namespace) -> BaiduOCRClient:
    """初始化 OCR 客户端；凭据优先级 CLI > env > 文件"""
    credentials = load_credentials(args.api_key, args.secret_key, args.credentials)
    return BaiduOCRClient(credentials=credentials, cache_dir=args.ocr_cache_dir)


def _build_llm_client(args: argparse.Namespace):
    """初始化 LLM 客户端。凭据缺失或 --no-llm 时返回 None（静默降级）"""
    provider = "none" if args.no_llm else args.llm_provider
    if provider == "none":
        logger.info("LLM layer disabled by --no-llm / --llm-provider=none.")
        return None

    cli_key = args.gemini_key if provider == "gemini" else args.claude_key
    credentials = load_llm_credentials(provider, cli_key, args.credentials)
    if credentials is None:
        logger.warning(
            f"LLM provider '{provider}' selected but no credentials found; "
            "falling back to rule+fuzzy only."
        )
        return None
    return build_llm_client(
        provider=provider,
        credentials=credentials,
        model=args.llm_model,
        cache_dir=args.llm_cache_dir,
    )


def _process_image(
    image_path: str,
    client: BaiduOCRClient,
    full_scheme_names: List[str],
    excel_items_by_full_name: Dict[str, List[str]],
    alias_map: Dict[str, str],
    composites,
    llm_client,
) -> Dict:
    """对单张图片执行 OCR → 抽方案 → 每个方案匹配 + 对比"""
    # 1. OCR（失败直接返回 failed 结果）
    try:
        ocr_payload = client.recognize(image_path)
    except (OCRError, FileNotFoundError) as exc:
        return build_image_result_failed(image_path, str(exc))

    # 2. 抽方案
    ocr_schemes = extract_schemes(ocr_payload)
    if not ocr_schemes:
        return build_image_result_failed(image_path, "OCR returned no scheme.")

    # 3. 逐方案匹配 + 对比
    scheme_results = []
    for idx, ocr_scheme in enumerate(ocr_schemes, 1):
        match_result = match_scheme_name(ocr_scheme.title, full_scheme_names)
        if match_result is None:
            scheme_results.append(
                build_ocr_scheme_result(
                    index=idx,
                    ocr_title=ocr_scheme.title,
                    ocr_items=ocr_scheme.items,
                    matched_full_name=None,
                    confidence=None,
                    comparison_rows=None,
                    excel_items_count=0,
                )
            )
            continue

        matched_full_name, score = match_result
        excel_items = excel_items_by_full_name.get(matched_full_name, [])
        rows = compare_items(
            excel_items=excel_items,
            ocr_items=ocr_scheme.items,
            alias_map=alias_map,
            composites=composites,
            llm_client=llm_client,
        )
        scheme_results.append(
            build_ocr_scheme_result(
                index=idx,
                ocr_title=ocr_scheme.title,
                ocr_items=ocr_scheme.items,
                matched_full_name=matched_full_name,
                confidence=score,
                comparison_rows=rows,
                excel_items_count=len(excel_items),
            )
        )

    return build_image_result_ok(image_path, scheme_results)


def _write_excel_only_report(
    excel_path: str,
    sheets: List[str],
    schemes: List[Scheme],
    output: str,
) -> None:
    payload = {
        "excel": {
            "file": excel_path,
            "sheets_in_order": sheets,
            "schemes": [
                {"sheet": s.sheet, "category": s.category, "items": s.items}
                for s in schemes
            ],
        },
        "summary": {
            "total_schemes": len(schemes),
            "items_total": sum(len(s.items) for s in schemes),
        },
    }
    _write_json(output, payload)
    logger.info(f"Excel-only report written to {output}: {len(schemes)} schemes.")


def _write_json(path: str, payload: Dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _write_text(path: str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except Exception as exc:
        logger.exception(f"check failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
