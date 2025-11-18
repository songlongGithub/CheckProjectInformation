#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR 解析逻辑验证"""

import logic

# 单方案场景样例
single_scheme_payload = {
    "words_result": [
        {"words": "03080032.0308003080"},
        {"words": "方案一女未婚（紫单见名单，不可替检）"},
        {"words": "1"},
        {"words": "未婚"},
        {"words": "女"},
        {"words": "03080032"},
        {"words": "03080030"},
        {"words": "自定义选项"},
        {"words": "复核后执行"},
        {"words": "血流变（新）"},
        {"words": "内科检查"},
        {"words": "血常规"},
        {"words": "甲状腺彩超"},
        {"words": "分组信息"},
        {"words": "婚姻状况"},
    ]
}

# 多方案场景样例
multi_scheme_payload = {
    "words_result": [
        {"words": "分组名称："},
        {"words": "方案一男（紫单、绿单见名单不可替"},
        {"words": "检)"},
        {"words": "分组价格："},
        {"words": "￥200.00"},
        {"words": "血流变（新）、放射项目不出胶片、肾"},
        {"words": "功三项、尿常规"},
        {"words": "分组交费方式：统一结账加项交费方式：用户自费"},
        {"words": "备注："},
        {"words": "分组名称："},
        {"words": "方案一女未婚（紫单、绿单见名单不"},
        {"words": "可替检)"},
        {"words": "分组价格："},
        {"words": "￥200.00"},
        {"words": "检)"},
        {"words": "可替检"},
        {"words": "重、放射项目不出胶片、超声项目不出片、血流变（新）、女性七项肿瘤标志物(H)、血常规、甲状腺彩"},
        {"words": "超、微量元素5项、甲状腺功能三项、糖化血红蛋白(A)、乳腺彩超、载脂蛋白A、女性盆腔彩超、常规心"},
        {"words": "电图、腹部超声、眼底检查、裂隙灯、血压、尿微量白蛋白、营养B餐、静脉采血、载脂蛋白B、颈动脉彩"},
        {"words": "超、C反应蛋白(CRP)、血脂五项、胸部正位DR、颈椎侧位DR、肝功两项、胆红素组合（三项）"},
        {"words": "分组交费方式：统一结账加项交费方式：用户自费"},
    ]
}

scheme_price_before_group_payload = {
    "words_result": [
        {"words": "方案五女已婚（心脑血管）（紫单、绿"},
        {"words": "分组价格："},
        {"words": "￥700.00"},
        {"words": "分组名称："},
        {"words": "单见名单不可替检)"},
        {"words": "载脂蛋白A、血常规、乳腺彩超、甲状腺彩超、经颅多普勒、常规心电图、女性TCT检测、妇科检查、女性益"},
        {"words": "腔彩超、腹部超声、裂隙灯、肾功三项、空腹血糖、眼科常规、眼底检查、心肌酶四项、内科检查、尿常"}
    ]
}

scheme_before_group_payload = {
    "words_result": [
        {"words": "方案二男（紫单、绿单见名单不可替"},
        {"words": "分组名称："},
        {"words": "分组价格："},
        {"words": "￥300.00"},
        {"words": "检)"},
        {"words": "蛋白组合（四项）、肾功三项、内科检查、眼科常规、空腹血糖、尿常规、身高体重、放射项目不出胶片、"},
        {"words": "超声项目不出片、血流变（新）、男性八项肿瘤标志物(H)、常规心电图、男性盆腔彩超、腹部超声、眼底"}
    ]
}

scheme_noise_title_payload = {
    "words_result": [
        {"words": "03080030.方案二男（紫单见名单，不可替检）"},
        {"words": "分组价格："},
        {"words": "￥300.00"},
        {"words": "分组名称："},
        {"words": "检)"},
        {"words": "可替检"},
        {"words": "蛋白组合（四项）、肾功三项"}
    ]
}

order_code_single_payload = {
    "words_result": [
        {"words": "订单编码"},
        {"words": "03080030"},
        {"words": "分组编码"},
        {"words": "0308A"},
        {"words": "方案三女未婚（需预约）"},
        {"words": "自定义选项"},
        {"words": "血常规"},
        {"words": "甲状腺彩超"},
        {"words": "分组信息"},
    ]
}


def test_single_scheme_parsing():
    """验证单方案提取结果"""
    schemes = logic.extract_data_from_ocr_json(single_scheme_payload)
    assert len(schemes) == 1, "Single scheme payload should produce exactly one scheme."
    title, items = schemes[0]
    assert "方案一女未婚" in title, "Title should contain the detected scheme name."
    assert items == ["血流变（新）", "内科检查", "血常规", "甲状腺彩超"], "Items should list each project line and skip first repeated hint."


def test_multi_scheme_parsing():
    """验证多方案提取结果"""
    schemes = logic.extract_data_from_ocr_json(multi_scheme_payload)
    assert len(schemes) == 2, "Multi scheme payload should produce two schemes."
    first_title, first_items = schemes[0]
    second_title, second_items = schemes[1]
    assert "方案一男" in first_title, "First scheme title missing."
    assert first_items == ["血流变（新）", "放射项目不出胶片", "肾功三项", "尿常规"], "First scheme items mismatch."
    assert "方案一女未婚" in second_title, "Second scheme title missing."
    required_items = {"甲状腺彩超", "常规心电图", "颈动脉彩超"}
    missing = required_items - set(second_items)
    assert not missing, f"Second scheme items missing expected entries: {missing}"


def test_scheme_before_group_parsing():
    """验证方案标题位于分组名称之前的解析结果"""
    schemes = logic.extract_data_from_ocr_json(scheme_before_group_payload)
    assert len(schemes) == 1, "Payload with title before label should produce one scheme."
    title, items = schemes[0]
    assert "方案二男" in title, "Scheme title should be detected from preceding line."
    required = {"蛋白组合（四项）", "肾功三项", "常规心电图"}
    missing = required - set(items)
    assert not missing, f"Items missing expected entries: {missing}"


def test_price_before_group_parsing():
    """验证标题在分组价格前出现的解析结果"""
    schemes = logic.extract_data_from_ocr_json(scheme_price_before_group_payload)
    assert len(schemes) == 1, "Payload with price before group should produce one scheme."
    title, items = schemes[0]
    assert "方案五女已婚" in title, "Title should come from line preceding price marker."
    assert "载脂蛋白A" in items and "常规心电图" in items, "Items should include all parsed entries."


def test_noise_prefix_title_parsing():
    """验证标题存在前缀噪声时能正确截断"""
    schemes = logic.extract_data_from_ocr_json(scheme_noise_title_payload)
    assert len(schemes) == 1, "Payload with noisy title should still produce one scheme."
    title, items = schemes[0]
    assert title.startswith("方案二男"), "Title should trim prefix before the keyword."
    assert items == ["蛋白组合（四项）", "肾功三项"], "Items should remain unaffected."


def test_order_code_triggers_single_scheme():
    """验证包含订单/分组编码时也被视为单方案"""
    schemes = logic.extract_data_from_ocr_json(order_code_single_payload)
    assert len(schemes) == 1, "Order-code payload should be treated as single scheme."
    title, items = schemes[0]
    assert title.startswith("方案三女未婚"), "Title should be the first line containing '方案'."
    assert items == ["血常规", "甲状腺彩超"], "Items should list entries after '自定义选项'."


def test_find_best_match_ignores_noise_parentheses():
    """匹配时忽略括号里的提示信息"""
    scheme_names = ["方案一 - 男", "方案一 - 女未婚"]
    matched = logic.find_best_match("方案一男（不可替检紫单见名单）", scheme_names)
    assert matched == "方案一 - 男", "Noise-only parentheses should not block matching."


def test_find_best_match_preserves_category_parentheses():
    """保留括号中的性别/婚姻提示"""
    scheme_names = ["方案一 - 男", "方案一 - 女未婚"]
    matched = logic.find_best_match("方案一（女未婚）", scheme_names)
    assert matched == "方案一 - 女未婚", "Category hints inside parentheses must remain."


def test_find_best_match_handles_unclosed_noise_parentheses():
    """缺少右括号的提示信息也应被剔除"""
    scheme_names = ["方案四 - 女未婚", "方案五 - 女已婚", "方案三（CT） - 女已婚"]
    assert (
        logic.find_best_match("方案四女未婚（紫单绿单见名单不可替", scheme_names) == "方案四 - 女未婚"
    ), "Unclosed noise-only parentheses should be removed."
    assert (
        logic.find_best_match("方案五女已婚（紫单绿单见名单不可替", scheme_names) == "方案五 - 女已婚"
    ), "Unclosed noise-only parentheses should be removed for other schemes as well."
    assert (
        logic.find_best_match("方案三女已婚(CT)(紫单绿单见名单", scheme_names) == "方案三（CT） - 女已婚"
    ), "Mixed CT markers with trailing noise should match."


def run_all():
    """运行全部测试用例"""
    test_single_scheme_parsing()
    print("PASS: single scheme parsing behaves as expected.")
    test_multi_scheme_parsing()
    print("PASS: multi scheme parsing behaves as expected.")
    test_scheme_before_group_parsing()
    print("PASS: scheme-before-label parsing behaves as expected.")
    test_price_before_group_parsing()
    print("PASS: price-before-group parsing behaves as expected.")
    test_noise_prefix_title_parsing()
    print("PASS: noisy title parsing behaves as expected.")
    test_order_code_triggers_single_scheme()
    print("PASS: order-code payload treated as single scheme.")
    test_find_best_match_ignores_noise_parentheses()
    print("PASS: best-match ignores noise-only parentheses.")
    test_find_best_match_preserves_category_parentheses()
    print("PASS: best-match preserves category parentheses.")
    test_find_best_match_handles_unclosed_noise_parentheses()
    print("PASS: best-match handles unclosed noise parentheses.")


if __name__ == "__main__":
    run_all()
