"""Self-contained regression tests. Fixtures are synthetic; no customer data."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check
from excel import parse_excel
from matcher import Composite, build_alias_map, compare_items, match_scheme_name
from similarity import ratio


def workbook(path, rows, formula=False):
    def cell(col, n, text):
        return f'<c r="{col}{n}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
    content = ''.join(f'<row r="{n}">'+''.join(cell(col,n,text) for col,text in row.items())+'</row>' for n,row in enumerate(rows,1))
    if formula: content += '<row r="10"><c r="A10"><f>A1</f></c></row>'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+content+'</sheetData></worksheet>')


class ReconcileTests(unittest.TestCase):
    def report(self, items, payload, rules=None):
        return check.reconcile([{'sheet':'方案一','category':'男','items':items}], [('sample.json',payload)], rules or {})
    def payload(self, items, title='方案一男', uncertainties=None):
        return {'schemes':[{'title':title,'items':items,'uncertainties':uncertainties or []}]}
    def test_exact(self):
        r=self.report(['甲','乙'],self.payload(['乙','甲']))
        self.assertEqual(r['summary']['status'],'text_consistent')
    def test_alias_transitive(self):
        aliases=build_alias_map([['X','中'],['中','原始']])
        rows=compare_items(['X'],['原始'],aliases)
        self.assertEqual(rows[0].match_type,'alias')
    def test_duplicate_consumption(self):
        rows=compare_items(['甲','甲'],['甲'],{})
        self.assertEqual([r.status for r in rows],['匹配','缺失'])
    def test_extra(self):
        r=self.report(['甲'],self.payload(['甲','乙']))
        self.assertEqual(r['documents'][0]['schemes'][0]['stats']['extra'],1)
    def test_missing(self):
        r=self.report(['甲','乙'],self.payload(['甲']))
        self.assertEqual(r['documents'][0]['schemes'][0]['stats']['missing'],1)
    def test_fuzzy_review(self):
        r=self.report(['ABCDEFGHIJ1'],self.payload(['ABCDEFGHIJ2']))
        s=r['documents'][0]['schemes'][0]
        self.assertEqual(s['comparison'][0]['match_type'],'fuzzy')
        self.assertEqual(s['verdict'],'needs_review')
        self.assertEqual(s['stats']['matched'],0)
        self.assertEqual(s['stats']['review'],1)
    def test_composite_partial_not_success(self):
        rules={'composites':[{'parent':'套餐P','children':['甲','乙']} ]}
        r=self.report(['套餐P'],self.payload(['甲']),rules)
        self.assertEqual(r['summary']['status'],'review_required')
        self.assertEqual(r['documents'][0]['schemes'][0]['stats']['review'],1)
    def test_composite_no_evidence_not_success(self):
        rules={'composites':[{'parent':'套餐P','children':['甲']}]}
        r=self.report(['套餐P','甲'],self.payload([]),rules)
        self.assertNotEqual(r['summary']['status'],'text_consistent')
    def test_title_tie(self):
        self.assertIsNone(match_scheme_name('方案一女',['方案一 - 女已婚','方案一 - 女未婚']))
    def test_title_wrong_gender(self):
        self.assertIsNone(match_scheme_name('方案一男',['方案一 - 女已婚']))
    def test_title_noise(self):
        self.assertEqual(match_scheme_name('方案一男（紫单不可替检）',['方案一 - 男'])[0],'方案一 - 男')
    def test_uncertainty_propagates(self):
        r=self.report(['甲'],self.payload(['甲'],uncertainties=['截图底部被截断']))
        self.assertEqual(r['summary']['status'],'review_required')
    def test_empty_words(self):
        r=self.report(['甲'],{'words_result':[]})
        self.assertEqual(r['summary']['status'],'input_error')
        self.assertEqual(r['documents'][0]['status'],'no_scheme_detected')
    def test_invalid_words(self):
        r=self.report(['甲'],{'words_result':[None]})
        self.assertEqual(r['documents'][0]['status'],'invalid_input')
    def test_ocr_error(self):
        r=self.report(['甲'],{'error_code':17,'words_result':[]})
        self.assertEqual(r['summary']['document_errors'],1)
    def test_no_documents(self):
        r=check.reconcile([],[],{})
        self.assertEqual(r['summary']['status'],'input_error')
    def test_empty_items(self):
        r=self.report(['甲'],self.payload([]))
        self.assertEqual(r['summary']['status'],'review_required')
    def test_mixed_batch_preserves_failure(self):
        r=check.reconcile([{'sheet':'方案一','category':'男','items':['甲']}], [('ok',self.payload(['甲'])),('bad',{'words_result':None})],{})
        self.assertEqual(len(r['documents']),2)
        self.assertEqual(r['summary']['status'],'input_error')
        self.assertIn('invalid_input',check.render_text(r))
    def test_all_fail_text(self):
        text=check.render_text(self.report(['甲'],{'error':'unreadable'}))
        self.assertIn('input_error',text)
        self.assertNotIn('全部完美',text)
    def test_invalid_rules(self):
        with self.assertRaises(ValueError): check.validate_rules({'aliases':[['a']]})
    def test_nonstring_items(self):
        with self.assertRaises(ValueError): check.parse_input(self.payload([1]))
    def test_ratio_lcs(self):
        self.assertEqual(ratio('ABCD','ACBD'),75)
    def test_xlsx_real_columns(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.xlsx'
            workbook(p,[{'A':'合并标题'},{'A':'项目或组合'},{'A':'共用','E':'√','F':'√'},{'A':'男性检查'},{'B':'男项','E':'√'},{'A':'女性检查'},{'B':'女项','F':'√'}])
            schemes=parse_excel(p,{})
            self.assertEqual(len(schemes),3)
            self.assertEqual(schemes[0]['items'],['共用','男项'])
    def test_formula_without_cache_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.xlsx'; workbook(p,[],formula=True)
            with self.assertRaisesRegex(ValueError,'cached value'): parse_excel(p,{})
    def test_zero_scheme_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.xlsx'; workbook(p,[{'A':'项目或组合'},{'A':'通用'}])
            with self.assertRaisesRegex(ValueError,'No schemes'): parse_excel(p,{})
    def test_utf16_dtd_rejected(self):
        from excel import _xml
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.xlsx'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('test.xml', ('<?xml version="1.0" encoding="UTF-16"?>'
                    '<!DOCTYPE x [<!ENTITY demo "expanded">]><x>&demo;</x>').encode('utf-16'))
            with zipfile.ZipFile(p) as z:
                with self.assertRaisesRegex(ValueError,'declarations'): _xml(z,'test.xml')
    def test_missing_sheets_cli(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            p=Path(d)/'a.xlsx'; workbook(p,[])
            # Build a separate malformed archive without duplicate member names.
            with zipfile.ZipFile(p) as z: members={n:z.read(n) for n in z.namelist()}
            members['xl/workbook.xml']=b'<workbook/>'
            with zipfile.ZipFile(p,'w') as z:
                for name,value in members.items(): z.writestr(name,value)
            self.assertEqual(check.main(['--excel',str(p),'--excel-only']),2)
    def test_output_collision(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            p=Path(d)/'a.xlsx'; p.write_bytes(b'original')
            self.assertEqual(check.main(['--excel',str(p),'--excel-only','--output',str(p)]),2)
            self.assertEqual(p.read_bytes(),b'original')
    def test_invalid_zip_cli(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            p=Path(d)/'a.xlsx'; p.write_bytes(b'badzip')
            self.assertEqual(check.main(['--excel',str(p),'--excel-only']),2)
    def test_offline_cli_and_exitcode(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            d=Path(d); x=d/'a.xlsx'; o=d/'ocr.json'; out=d/'out.json'
            workbook(x,[{'A':'项目或组合'},{'A':'男性检查'},{'B':'甲','E':'√'}])
            o.write_text(json.dumps(self.payload(['乙'],title='方案男')))
            self.assertEqual(check.main(['--excel',str(x),'--ocr-json',str(o),'--output',str(out)]),1)
            self.assertEqual(json.loads(out.read_text())['summary']['status'],'review_required')

if __name__=='__main__': unittest.main()
