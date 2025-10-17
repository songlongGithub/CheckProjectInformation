#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能匹配功能测试脚本
演示如何使用智能匹配器减少对硬编码规则的依赖
"""

from smart_matcher import create_smart_matcher
from rule_manager import get_rule_manager


def test_rule_manager():
    """测试规则管理器功能"""
    print("=" * 60)
    print("测试 1: 规则管理器")
    print("=" * 60)
    
    rule_mgr = get_rule_manager()
    aliases, renames, gender_renames = rule_mgr.load_rules()
    
    print(f"✓ 已加载 {len(aliases)} 条别名规则")
    print(f"✓ 已加载 {len(renames)} 条重命名规则")
    print(f"✓ 已加载 {len(gender_renames)} 条性别规则")
    print(f"✓ 规则版本: {rule_mgr.version}")
    
    # 显示前5条规则
    print("\n前5条别名规则示例:")
    for i, (alias, standard) in enumerate(aliases[:5], 1):
        print(f"  {i}. {alias:20s} -> {standard}")
    
    print()


def test_smart_matcher():
    """测试智能匹配器功能"""
    print("=" * 60)
    print("测试 2: 智能匹配器")
    print("=" * 60)
    
    # 加载规则
    rule_mgr = get_rule_manager()
    aliases, _, _ = rule_mgr.load_rules()
    
    # 创建匹配器
    matcher = create_smart_matcher(aliases)
    
    # 模拟 Excel 标准项目列表
    excel_items = [
        '采血',
        '眼科检查',
        '标准早餐',
        'C13呼气试验',
        'C14呼气试验',
        '乳腺彩色超声',
        '女性彩色盆腔超声',
        '十二导联心电图',
        '腹部彩色超声',
        '耳鼻咽喉检查',
        '甲状腺彩色超声',
        '胸部CT',
        '血流变(新)',
        '肝功十三项',
        '空腹血糖',
        '人体成分分析',
    ]
    
    # 模拟 OCR 识别结果（包含各种变体）
    ocr_items = [
        # 精确匹配
        ('采血', 'exact'),
        # 规则匹配
        ('静脉采血', 'alias'),
        ('眼科常规', 'alias'),
        # 模糊匹配
        ('乳腺彩超', 'fuzzy'),
        ('心电图', 'fuzzy'),
        ('碳13呼气', 'fuzzy'),
        # 语义匹配
        ('胸部 CT', 'semantic'),
        ('肝功能十三项', 'semantic'),
        ('甲状腺超声', 'semantic'),
        # 难以匹配
        ('未知项目ABC', 'fail'),
    ]
    
    print("\n匹配测试结果:")
    print(f"{'OCR识别名称':<20s} {'匹配结果':<25s} {'预期类型':<10s} {'状态'}")
    print("-" * 70)
    
    for ocr_item, expected_type in ocr_items:
        match = matcher.match(ocr_item, excel_items, threshold=75)
        if match:
            status = "✓"
            result = match
        else:
            status = "✗" if expected_type != 'fail' else "○"
            result = "(未匹配)"
        
        print(f"{ocr_item:<20s} {result:<25s} {expected_type:<10s} {status}")
    
    # 显示匹配统计
    print("\n匹配统计:")
    stats = matcher.get_match_statistics()
    for method, count in stats.items():
        if count > 0:
            percentage = (count / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"  {method:12s}: {count:3d} 次 ({percentage:5.1f}%)")
    
    # 建议新规则
    print("\n建议添加的新规则:")
    suggestions = matcher.suggest_new_rules(min_occurrences=1)
    if suggestions:
        for ocr, excel, count in suggestions[:5]:
            print(f"  [{count}次] {ocr} -> {excel}")
    else:
        print("  (暂无建议)")
    
    print()


def test_comparison():
    """对比测试：有规则 vs 无规则"""
    print("=" * 60)
    print("测试 3: 规则数量对比")
    print("=" * 60)
    
    # 场景1: 使用完整规则库
    rule_mgr = get_rule_manager()
    aliases_full, _, _ = rule_mgr.load_rules()
    matcher_full = create_smart_matcher(aliases_full)
    
    # 场景2: 仅使用少量核心规则
    aliases_mini = [
        ['静脉采血', '采血'],
        ['眼科常规', '眼科检查'],
        ['乳腺彩超', '乳腺彩色超声'],
    ]
    matcher_mini = create_smart_matcher(aliases_mini)
    
    # 测试数据
    excel_items = [
        '采血', '眼科检查', '乳腺彩色超声', 'C13呼气试验',
        '甲状腺彩色超声', '十二导联心电图', '空腹血糖'
    ]
    
    ocr_items = [
        '静脉采血', '眼科常规', '乳腺彩超', '碳十三呼气检查',
        '甲状腺彩超', '常规心电图', '空腹血糖(GLU)'
    ]
    
    # 测试完整规则
    matched_full = sum(1 for item in ocr_items 
                      if matcher_full.match(item, excel_items, threshold=75))
    
    # 测试精简规则
    matched_mini = sum(1 for item in ocr_items 
                      if matcher_mini.match(item, excel_items, threshold=75))
    
    print(f"\n测试项目数: {len(ocr_items)}")
    print(f"\n方案1 - 完整规则库 ({len(aliases_full)} 条规则):")
    print(f"  匹配成功: {matched_full}/{len(ocr_items)} ({matched_full/len(ocr_items)*100:.1f}%)")
    
    print(f"\n方案2 - 精简规则库 ({len(aliases_mini)} 条规则) + 智能匹配:")
    print(f"  匹配成功: {matched_mini}/{len(ocr_items)} ({matched_mini/len(ocr_items)*100:.1f}%)")
    
    print(f"\n结论:")
    if matched_mini >= matched_full * 0.9:  # 90%以上的效果
        print(f"  ✓ 智能匹配可以用 {len(aliases_mini)} 条规则达到接近完整规则库的效果")
        print(f"  ✓ 规则数量减少 {(1-len(aliases_mini)/len(aliases_full))*100:.0f}%")
    else:
        print(f"  • 需要更多规则或调整匹配阈值")
    
    print()


def test_learning():
    """测试学习功能"""
    print("=" * 60)
    print("测试 4: 用户反馈学习")
    print("=" * 60)
    
    matcher = create_smart_matcher([])
    
    # 模拟用户反馈纠正
    feedbacks = [
        ('肝功', '肝功十三项'),
        ('肾功', '肾功能五项'),
        ('血糖', '空腹血糖'),
    ]
    
    print("\n用户反馈学习过程:")
    for ocr, correct in feedbacks:
        matcher.learn_from_feedback(ocr, correct)
        print(f"  ✓ 学习: {ocr} -> {correct}")
    
    # 测试学习效果
    print("\n应用学习结果:")
    excel_items = ['肝功十三项', '肾功能五项', '空腹血糖']
    
    for ocr in ['肝功', '肾功', '血糖']:
        match = matcher.match(ocr, excel_items)
        print(f"  {ocr} -> {match if match else '(未匹配)'}")
    
    # 导出学习规则
    learned = matcher.export_learned_rules()
    print(f"\n可导出 {len(learned)} 条学习规则到正式规则库")
    
    print()


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("智能匹配系统测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试1: 规则管理器
        test_rule_manager()
        
        # 测试2: 智能匹配器
        test_smart_matcher()
        
        # 测试3: 规则数量对比
        test_comparison()
        
        # 测试4: 学习功能
        test_learning()
        
        print("=" * 60)
        print("所有测试完成!")
        print("=" * 60)
        
        print("\n💡 使用建议:")
        print("  1. 保留核心的、高频的规则")
        print("  2. 使用智能匹配处理低频和变体情况")
        print("  3. 定期从匹配历史中提取新规则")
        print("  4. 结合用户反馈持续优化")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

