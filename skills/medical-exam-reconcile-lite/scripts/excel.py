"""Offline XLSX reader and the project's sex/category state machine (stdlib only)."""
from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
TRIGGERS = [('男性检查', 'M'), ('女未婚检查', 'FU'), ('女已婚检查H', 'FH'),
            ('女已婚检查', 'FM'), ('女性检查', 'FG'), ('标准早餐', 'N')]
CATEGORIES = [('M', '男'), ('FU', '女未婚'), ('FM', '女已婚'), ('FH', '女已婚检查H')]
EXCLUDED = ('健康管理', '套餐价格', '价格', '合计', '小计', '费用', '收费', '总计')
PACKAGES = ('全套', '套餐', '肝功十三项', '肝功十一项')
MARITAL = ('妇科', '宫颈', 'TCT', 'HPV', '白带', '阴道', '子宫', '卵巢', '宫颈刮片', '妇检')


def normalize(value):
    return str(value or '').strip().replace(' ', '').replace('\u3000', '').replace('（', '(').replace('）', ')')


def _xml(archive, path):
    raw = archive.read(path)
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('XML entity declarations are not supported')
    class RejectDTD(ET.TreeBuilder):
        def doctype(self, name, pubid, system):
            raise ValueError('XML document type declarations are not supported')
    return ET.fromstring(raw, parser=ET.XMLParser(target=RejectDTD()))


def read_workbook(path):
    """Read stored values only. Never evaluate formulas, macros or external links."""
    path = Path(path)
    if path.suffix.lower() != '.xlsx':
        raise ValueError('Only .xlsx input is supported')
    if path.stat().st_size > 50_000_000:
        raise ValueError('Workbook exceeds 50 MB input limit')
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 200_000_000:
            raise ValueError('Workbook exceeds safe archive limits')
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(si.itertext()) if not list(si.iter(NS + 't')) else
                      ''.join(t.text or '' for t in si.iter(NS + 't'))
                      for si in _xml(z, 'xl/sharedStrings.xml').findall(NS + 'si')]
        rels = {r.attrib['Id']: r.attrib for r in _xml(z, 'xl/_rels/workbook.xml.rels')}
        result = []
        sheet_nodes = _xml(z, 'xl/workbook.xml').find(NS + 'sheets')
        if sheet_nodes is None or not len(sheet_nodes):
            raise ValueError('Workbook contains no worksheets')
        for sheet in sheet_nodes:
            rel = rels[sheet.attrib[REL + 'id']]
            if rel.get('TargetMode') == 'External':
                raise ValueError('External worksheet references are not supported')
            target = rel['Target']
            member = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
            if not member.startswith('xl/') or '..' in member.split('/'):
                raise ValueError('Invalid worksheet archive path')
            root = _xml(z, member)
            rows = []
            for row in root.findall('.//' + NS + 'sheetData/' + NS + 'row'):
                rownum = int(row.attrib.get('r', len(rows) + 1))
                if rownum > 100000:
                    raise ValueError('Worksheet exceeds 100000 rows')
                values = dict.fromkeys(('A', 'B', 'C', 'E', 'F'), '')
                for cell in row:
                    col = re.sub(r'\d+', '', cell.attrib.get('r', ''))
                    if col not in values:
                        continue
                    value = cell.find(NS + 'v')
                    typ = cell.attrib.get('t')
                    if cell.find(NS + 'f') is not None and (value is None or value.text is None):
                        raise ValueError('Formula has no cached value in a required column; recalculate and save Excel first')
                    if typ == 's':
                        if value is None or value.text is None:
                            raise ValueError('Shared-string cell is missing its index')
                        index = int(value.text)
                        if not 0 <= index < len(shared):
                            raise ValueError('Shared-string cell has an invalid index')
                        text = shared[index]
                    elif typ == 'inlineStr':
                        text = ''.join(t.text or '' for t in cell.iter(NS + 't'))
                    elif typ == 'e':
                        raise ValueError('Excel error value in a required column')
                    else:
                        text = value.text if value is not None else ''
                    values[col] = str(text or '').strip()
                rows.append((rownum, values))
            result.append((sheet.attrib['name'], rows))
        return result


def parse_excel(path, rules):
    """Preserve the upstream 1.1.0 category and item ordering semantics."""
    rename = {a: [v.strip() for v in b.split(',') if v.strip()] for a, b in rules.get('renames', [])}
    gender = {a: (m, f) for a, m, f in rules.get('gender_renames', [])}
    raw_sheets = read_workbook(path)
    sheets, records = [], {}
    for raw_name, rows in raw_sheets:
        name = '方案' if len(raw_sheets) == 1 and raw_name.strip().lower() == 'sheet' else raw_name.strip()
        if name in records:
            raise ValueError('Worksheet display names collide after trimming')
        sheets.append(name)
        records[name] = projects = []
        state, started, last_main, last_package = 'N', False, '', ''
        for rownum, row in rows:
            a, b, c = row['A'], row['B'], row['C']
            if a.replace(' ', '') == '项目或组合':
                started = True
                continue
            if not started:
                continue
            if '健康管理' in a:
                break
            transition = next((s for kw, s in TRIGGERS if kw in f'{a} {b}'), None)
            if transition:
                state = transition
            if a and not b and not c and any(kw in a for kw, _ in TRIGGERS):
                continue
            if a:
                last_main = a
            if any(kw in last_main for kw in EXCLUDED):
                continue
            if any(kw in last_main for kw in PACKAGES):
                if last_main == last_package:
                    continue
                item, last_package = last_main, last_main
            else:
                item = b or a
            item = normalize(item)
            if not item or item in {kw for kw, _ in TRIGGERS if kw != '标准早餐'} or any(k in item for k in EXCLUDED):
                continue
            male, female = row['E'] == '√', row['F'] == '√'
            if not (male or female):
                male, female = state in ('N', 'M'), state in ('N', 'FU', 'FM', 'FH', 'FG')
            for offset, replacement in enumerate(rename.get(item, [item])):
                projects.append({'name': item if replacement == 'SELF' else replacement,
                                 'context': f'{last_main} {b}', 'state': state,
                                 'male': male, 'female': female, 'order': rownum + offset * .1})
    marital = set()
    for projects in records.values():
        for p in projects:
            n = p['name']
            exempt = any(k in n for k in ('乳腺', '盆腔')) and any(k in n for k in ('彩超', '超声'))
            if not exempt and any(k in p['context'] for k in MARITAL):
                marital.add(n)
    schemes = []
    for sheet in sheets:
        universal_m, universal_f = [], []
        buckets = {key: [] for key, _ in CATEGORIES}
        for p in records[sheet]:
            state = p['state']
            if state == 'N':
                if p['male']: universal_m.append(p)
                if p['female']: universal_f.append(p)
            elif state == 'M' and p['male']:
                buckets['M'].append(p)
            elif state in ('FU', 'FM', 'FH') and p['female']:
                buckets[state].append(p)
            elif state == 'FG' and p['female']:
                buckets['FM'].append(p)
                if p['name'] not in marital: buckets['FU'].append(p)
        for key, category in CATEGORIES:
            if not buckets[key]:
                continue
            items = {}
            for p in (universal_m if key == 'M' else universal_f) + buckets[key]:
                old = p['name']
                replacement = gender.get(old, ('', ''))[0 if key == 'M' else 1]
                items[replacement or old] = p['order']
            schemes.append({'sheet': sheet, 'category': category,
                            'items': sorted(items, key=items.get)})
    if not schemes:
        raise ValueError('No schemes found: check 项目或组合 header, A/B/C/E/F columns and category blocks')
    return schemes
