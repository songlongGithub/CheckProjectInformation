#!/usr/bin/env python3
"""Offline package reconciliation; no HTTP, credentials, auto-install or servers."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from excel import parse_excel
from matcher import Composite, build_alias_map, compare_items, match_scheme_name
from ocr import extract_schemes

VERSION = '0.1.0'
SOURCE_COMMIT = '1392fcc2cf9451467b40f0be4e840a274967a481'
DEFAULT_RULES = Path(__file__).resolve().parent.parent / 'config/default_rules.json'


def read_json(path):
    if Path(path).stat().st_size > 20_000_000:
        raise ValueError('JSON exceeds 20 MB input limit')
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_rules(value):
    if not isinstance(value, dict):
        raise ValueError('Rules must be an object')
    for key, width in [('aliases', 2), ('renames', 2), ('gender_renames', 3)]:
        rows = value.get(key, [])
        if not isinstance(rows, list) or any(not isinstance(r, list) or len(r) != width or
            any(not isinstance(s, str) or not s.strip() for s in r) for r in rows):
            raise ValueError(f'Invalid rules field: {key}')
    composites = value.get('composites', [])
    if not isinstance(composites, list):
        raise ValueError('composites must be a list')
    for r in composites:
        if not isinstance(r, dict) or not isinstance(r.get('parent'), str) or not r['parent'].strip():
            raise ValueError('Composite requires a nonempty parent')
        string_list(r.get('children'), 'composite children')
        if not r['children']:
            raise ValueError('Composite children must not be empty')
    return value


def string_list(value, field):
    if not isinstance(value, list) or len(value) > 10000 or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f'{field} must be a list of nonempty strings (max 10000)')
    if any(len(v) > 10000 for v in value):
        raise ValueError(f'{field} contains an excessively long string')
    return value


def parse_input(payload):
    """Accept raw Baidu words_result or host-vision transcription {schemes:[...]}.

    Do not infer or repair missing OCR text using the expected Excel projects.
    """
    if not isinstance(payload, dict):
        raise ValueError('Each OCR document must be a JSON object')
    if payload.get('error_code') or payload.get('error'):
        raise ValueError('OCR document reports a recognition error')
    if 'words_result' in payload:
        words = payload['words_result']
        if not isinstance(words, list) or len(words) > 10000 or any(not isinstance(w, dict) or not isinstance(w.get('words'), str) for w in words):
            raise ValueError('words_result must contain objects with string words')
        string_list([w['words'] for w in words if w['words'].strip()], 'words_result')
        return [asdict(s) for s in extract_schemes(payload)]
    schemes = payload.get('schemes')
    if not isinstance(schemes, list) or len(schemes) > 1000:
        raise ValueError('Expected words_result or schemes list')
    result = []
    for scheme in schemes:
        if not isinstance(scheme, dict) or not isinstance(scheme.get('title'), str) or not scheme['title'].strip():
            raise ValueError('Every scheme requires a nonempty title')
        items = string_list(scheme.get('items'), 'scheme items')
        uncertainties = string_list(scheme.get('uncertainties', []), 'uncertainties')
        result.append({'title': scheme['title'], 'items': items, 'uncertainties': uncertainties})
    return result


def reconcile(schemes, documents, rules):
    names = {f"{s['sheet']} - {s['category']}": s for s in schemes}
    if len(names) != len(schemes):
        raise ValueError('Duplicate scheme full names')
    aliases = build_alias_map(rules.get('aliases', []))
    composites = [Composite(r['parent'], r['children'], str(r.get('note', ''))) for r in rules.get('composites', [])]
    results = []
    for index, (source, payload) in enumerate(documents, 1):
        record = {'index': index, 'source': Path(source).name, 'status': 'ok', 'schemes': []}
        results.append(record)
        try:
            if isinstance(payload, Exception):
                raise payload
            extracted = parse_input(payload)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            record.update(status='invalid_input', error=str(exc))
            continue
        if not extracted:
            record.update(status='no_scheme_detected', error='No scheme could be extracted')
            continue
        for scheme in extracted:
            output = {'title': scheme['title'], 'matched_scheme': None, 'score': None,
                      'verdict': 'no_match', 'review_reasons': [], 'comparison': []}
            record['schemes'].append(output)
            matched = match_scheme_name(scheme['title'], list(names))
            if not matched:
                output['review_reasons'].append('Title below threshold or tied candidates; select/confirm a scheme')
                continue
            name, score = matched
            output.update(matched_scheme=name, score=score)
            rows = compare_items(names[name]['items'], scheme['items'], aliases, composites)
            counts = {s: sum(r.status == s for r in rows) for s in ('匹配', '缺失', '多余', '需复核')}
            output['stats'] = {'matched': counts['匹配'], 'missing': counts['缺失'], 'extra': counts['多余'],
                               'review': counts['需复核'], 'total_excel': len(names[name]['items']), 'total_ocr': len(scheme['items'])}
            output['comparison'] = [asdict(r) for r in rows]
            if any(r.match_type == 'fuzzy' for r in rows):
                output['review_reasons'].append('Fuzzy matches are similarity candidates, not verified equivalence')
            if any(r.match_type == 'composite' for r in rows):
                output['review_reasons'].append('Composite coverage needs confirmation; a child is not proof of the full parent package')
            output['review_reasons'].extend(scheme.get('uncertainties', []))
            if not scheme['items']:
                output['review_reasons'].append('Scheme contains no recognized items')
            if counts['缺失'] or counts['多余']:
                output['verdict'] = 'differences'
            elif output['review_reasons']:
                output['verdict'] = 'needs_review'
            else:
                output['verdict'] = 'no_difference_in_supplied_text'
    all_schemes = [s for r in results for s in r['schemes']]
    errors = sum(r['status'] != 'ok' for r in results)
    unresolved = sum(s['verdict'] != 'no_difference_in_supplied_text' for s in all_schemes)
    summary = {'documents': len(results), 'document_errors': errors, 'schemes': len(all_schemes),
               'unresolved_schemes': unresolved,
               'text_consistent_schemes': len(all_schemes) - unresolved,
               'status': 'input_error' if errors or not results else 'review_required' if unresolved else 'text_consistent'}
    return {'schema_version': VERSION, 'upstream_commit': SOURCE_COMMIT,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'offline_no_external_services',
            'scope': 'Consistency of supplied package lists only; not medical advice or a guarantee of OCR completeness',
            'documents': results, 'summary': summary}


def render_text(report):
    s = report['summary']
    lines = [f"核对结果：{s['status']}", f"输入 {s['documents']} 份；识别 {s['schemes']} 个方案；输入失败 {s['document_errors']}；待处理 {s['unresolved_schemes']}"]
    for doc in report['documents']:
        lines.append(f"\n{doc['source']}：{doc['status']}")
        if doc.get('error'):
            lines.append(doc['error'])
        for scheme in doc['schemes']:
            lines.append(f"- {scheme['title']} → {scheme['matched_scheme'] or '未确定方案'}：{scheme['verdict']}")
            for row in scheme['comparison']:
                if row['status'] != '匹配' or row['match_type'] == 'fuzzy':
                    lines.append(f"  {row['status']}：{row['excel_item']} ↔ {row['ocr_item']} ({row['match_type'] or '-'})")
            for reason in scheme['review_reasons']:
                lines.append(f"  复核：{reason}")
    lines.append('\n结论仅针对已提供文本；请保留原图核对识别遗漏，不代表临床验证。')
    return '\n'.join(lines) + '\n'


def write_output(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.reconcile-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--excel', required=True)
    p.add_argument('--rules', default=str(DEFAULT_RULES))
    p.add_argument('--excel-only', action='store_true')
    p.add_argument('--ocr-json', nargs='+', default=[])
    p.add_argument('--output')
    p.add_argument('--text-output')
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    try:
        inputs = {Path(v).resolve() for v in [args.excel, args.rules] + args.ocr_json}
        outputs = [Path(v).resolve() for v in [args.output, args.text_output] if v]
        if any(v in inputs for v in outputs) or len(set(outputs)) != len(outputs):
            raise ValueError('Output paths must differ from input paths and each other')
        if args.excel_only and (args.ocr_json or args.text_output):
            raise ValueError('--excel-only cannot be combined with OCR/text output')
        if not args.excel_only and not args.ocr_json:
            raise ValueError('Provide --ocr-json, or use --excel-only')
        rules = validate_rules(read_json(args.rules))
        schemes = parse_excel(args.excel, rules)
        if args.excel_only:
            report, code = {'schemes': schemes, 'mode': 'excel_only'}, 0
        else:
            documents = []
            for path in args.ocr_json:
                try:
                    documents.append((path, read_json(path)))
                except (OSError, ValueError) as exc:
                    documents.append((path, ValueError(type(exc).__name__ + ': invalid or unreadable OCR JSON')))
            report = reconcile(schemes, documents, rules)
            report['input_manifest'] = []
            for kind, path in [('excel', args.excel), ('rules', args.rules)] + [('ocr_json', p) for p in args.ocr_json]:
                try:
                    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                except OSError:
                    sha = None
                report['input_manifest'].append({'kind': kind, 'file': Path(path).name, 'sha256': sha})
            code = {'text_consistent': 0, 'review_required': 1, 'input_error': 2}[report['summary']['status']]
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output: write_output(args.output, encoded)
        else: print(encoded, end='')
        if args.text_output: write_output(args.text_output, render_text(report))
        return code
    except (OSError, ValueError, TypeError, KeyError, IndexError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(json.dumps({'status': 'input_error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
