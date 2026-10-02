#!/usr/bin/env python3
"""Re-run untouched project assertions and real XLSX/vision corpus via this Skill.

Reference checks need pandas/openpyxl/fuzzywuzzy/python-Levenshtein/requests.
The Skill CLI is deliberately executed with -S (no site packages).
No customer input or full report is embedded in the aggregate JSON.
"""
import argparse
import contextlib
import hashlib
import importlib
import io
import json
import logging
import os
import runpy
import socket
import subprocess
import sys
import tempfile
import types
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import check
import excel
import matcher
import ocr
import similarity


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def run(project, vision_dir=None, local_ocr_dir=None):
    logging.disable(logging.CRITICAL)
    def deny_network(*args, **kwargs):
        raise RuntimeError('Network prohibited during regression tests')
    socket.create_connection = deny_network
    socket.socket.connect = deny_network
    source = project / 'test_ocr_parsing.py'
    original_logic = sys.modules.get('logic')
    sys.modules['logic'] = types.SimpleNamespace(
        extract_data_from_ocr_json=lambda p: [(s.title, s.items) for s in ocr.extract_schemes(p)],
        find_best_match=lambda t, n: (matcher.match_scheme_name(t, n) or (None,))[0])
    try:
        tests = runpy.run_path(str(source))
        assertion_results = []
        for name, func in sorted(tests.items()):
            if name.startswith('test_') and callable(func):
                func()  # Original test body and expected values, unchanged.
                assertion_results.append({'test': name, 'outcome': 'passed'})
    finally:
        if original_logic is None: sys.modules.pop('logic', None)
        else: sys.modules['logic'] = original_logic
    sys.path.insert(0, str(project / 'skills/medical-exam-checker/scripts'))
    from core.excel_parser import ExcelParser
    from core.rules import load_rules
    from core.matcher import compare_items as original_compare, build_alias_map as original_aliases
    import pandas as pd
    from fuzzywuzzy import fuzz
    rules_path = project / 'skills/medical-exam-checker/config/default_rules.json'
    rules = load_rules(rules_path)
    raw_rules = check.validate_rules(check.read_json(rules_path))
    assert Path(check.DEFAULT_RULES).read_bytes() == rules_path.read_bytes(), 'Rules changed unexpectedly'
    read_excel = pd.read_excel
    def fixed_probe(*args, **kwargs):
        if kwargs.get('nrows') == 1:
            kwargs = dict(kwargs)
            kwargs.pop('nrows')
        return read_excel(*args, **kwargs)
    summary = {'upstream_commit': subprocess.check_output(['git', '-C', str(project), 'rev-parse', 'HEAD'], text=True).strip(),
               'original_test_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
               'original_assertions_on_skill': assertion_results,
               'excel': [], 'vision': [], 'local_ocr': []}
    corpus_terms = set()
    for workbook in sorted((project / 'test').rglob('*.xlsx')):
        group = workbook.parent.name
        old = [asdict(s) for s in ExcelParser(str(workbook), rules).parse()]
        with patch.object(pd, 'read_excel', fixed_probe):
            corrected = [asdict(s) for s in ExcelParser(str(workbook), rules).parse()]
        lite = excel.parse_excel(workbook, raw_rules)
        assert lite == corrected, f'Excel corpus group {group} differs from fixed-reader reference'
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'parsed.json'
            command = [sys.executable, '-S', str(SKILL/'scripts/check.py'), '--excel', str(workbook), '--excel-only', '--output', str(out)]
            proc = subprocess.run(command, capture_output=True, text=True)
            assert proc.returncode == 0, f'Excel CLI failed for group {group}'
            assert json.loads(out.read_text())['schemes'] == lite
        # Compare unchanged exact/alias/fuzzy pipeline for all real scheme item lists.
        amap = matcher.build_alias_map(raw_rules.get('aliases', []))
        match_checks = 0
        for scheme in lite:
            items = scheme['items']
            corpus_terms.update(items)
            variants = list(reversed(items)) + ['__unrelated_extra_item__']
            old_rows = [asdict(r) for r in original_compare(items, variants, amap, composites=None, llm_client=None)]
            new_rows = [asdict(r) for r in matcher.compare_items(items, variants, amap, composites=None)]
            for row in old_rows:
                if row['match_type'] == 'fuzzy': row['status'] = '需复核'  # Declared safety policy, mapping unchanged.
            assert old_rows == new_rows, f'Item matcher differs for group {group}'
            match_checks += 1
        summary['excel'].append({'group': group, 'workbook_sha256': hashlib.sha256(workbook.read_bytes()).hexdigest(),
                                 'upstream_schemes': len(old), 'skill_schemes': len(lite),
                                 'item_occurrences': sum(len(s['items']) for s in lite),
                                 'fixed_reference_equal': True, 'normalized_output_sha256': digest(lite),
                                 'cli_without_site_packages': 'passed', 'matcher_differential_schemes': match_checks, 'intentional_status_difference': 'fuzzy requires review'})
        images = sorted(p for p in workbook.parent.rglob('*') if p.suffix.lower() in ('.jpeg', '.jpg', '.png'))
        if vision_dir:
            records = []
            for number, image in enumerate(images, 1):
                transcribed = vision_dir / (image.stem + '.json')
                assert transcribed.is_file(), f'Missing independent vision input: group {group}, image {number}'
                records.append((number, image, transcribed))
            summary['vision'].extend(run_image_cli(group, workbook, records, 'independent_host_vision'))
        if local_ocr_dir:
            manifest = json.loads((local_ocr_dir / 'private-manifest.json').read_text())
            records = [(i+1, project/r['input_path'], local_ocr_dir/r['payload_file'])
                       for i,r in enumerate(manifest) if r['group'] == group]
            summary['local_ocr'].extend(run_image_cli(group, workbook, records, 'tesseract_chi_sim_eng_psm6'))
    terms = sorted(corpus_terms)
    checks = 0
    for a in terms:
        for b in terms:
            assert similarity.ratio(a,b) == fuzz.ratio(a,b)
            assert similarity.token_sort_ratio(a,b) == fuzz.token_sort_ratio(a,b)
            checks += 2
    summary['similarity'] = {'unique_real_corpus_terms':len(terms), 'scorer_comparisons':checks, 'mismatches':0}
    summary['scope'] = 'Software behavior and corpus execution, not independently labeled diagnostic/OCR accuracy'
    return summary


def run_image_cli(group, workbook, records, method):
    from core.matcher import compare_items as original_compare
    rules = check.validate_rules(check.read_json(check.DEFAULT_RULES))
    amap = matcher.build_alias_map(rules.get('aliases', []))
    composites = [matcher.Composite(r['parent'], r['children'], r.get('note', '')) for r in rules.get('composites', [])]
    schemes = {f"{s['sheet']} - {s['category']}": s for s in excel.parse_excel(workbook, rules)}
    result = []
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'report.json'
        command = [sys.executable, '-S', str(SKILL/'scripts/check.py'), '--excel', str(workbook),
                   '--ocr-json'] + [str(p) for _,_,p in records] + ['--output',str(out)]
        proc = subprocess.run(command, capture_output=True, text=True)
        assert proc.returncode in (0,1,2) and out.exists(), f'Image CLI crashed for group {group}'
        report = json.loads(out.read_text())
        assert len(report['documents']) == len(records)
        for (number,image,transcription), doc in zip(records,report['documents']):
            compared = 0
            if doc['status'] == 'ok':
                extracted = check.parse_input(check.read_json(transcription))
                for given, actual in zip(extracted, doc['schemes']):
                    if not actual['matched_scheme']:
                        continue
                    reference = [asdict(row) for row in original_compare(schemes[actual['matched_scheme']]['items'], given['items'], amap, composites=composites, llm_client=None)]
                    for row in reference:
                        if row['match_type'] in ('fuzzy', 'composite'): row['status'] = '需复核'
                        if row['match_type'] == 'composite' and row['reason']: row['reason'] = '规则候选，覆盖未确认：' + row['reason']
                    assert reference == actual['comparison'], f'Real image matcher mapping differs for group {group} image {number}'
                    compared += 1
            matched_types = {}
            stats = {'matched':0,'missing':0,'extra':0,'review':0}
            for scheme in doc['schemes']:
                for key in stats: stats[key] += scheme.get('stats',{}).get(key,0)
                for row in scheme['comparison']:
                    key = row['match_type'] or row['status']
                    matched_types[key] = matched_types.get(key,0) + 1
            result.append({'image_id':f'group{group}-image{number:02d}', 'group':group, 'method':method,
                           'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
                           'transcription_sha256':hashlib.sha256(transcription.read_bytes()).hexdigest(),
                           'status':doc['status'], 'scheme_count':len(doc['schemes']),
                           'verdicts':[s['verdict'] for s in doc['schemes']], 'stats':stats,
                           'match_types':matched_types, 'cli_group_exit_code':proc.returncode,
                           'original_matcher_differential_schemes':compared, 'mapping_equal_after_declared_review_policy': True})
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--vision-dir',type=Path)
    p.add_argument('--local-ocr-dir',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    data=run(args.project.resolve(),args.vision_dir,args.local_ocr_dir)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'upstream_assertion_tests':len(data['original_assertions_on_skill']),
                      'workbooks':len(data['excel']),'schemes':sum(r['skill_schemes'] for r in data['excel']),
                      'vision_images':len(data['vision']),'local_ocr_images':len(data['local_ocr']),
                      'similarity':data['similarity']},ensure_ascii=False))
