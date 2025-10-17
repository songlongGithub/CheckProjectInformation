#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在线更新功能测试客户端
演示如何使用在线更新功能
"""

import json
from rule_manager import get_rule_manager


def print_section(title):
    """打印分隔标题"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def display_rules(rules_data):
    """显示规则摘要"""
    print(f"  版本: {rules_data.get('version', 'unknown')}")
    print(f"  更新时间: {rules_data.get('last_updated', 'unknown')}")
    print(f"  别名规则: {len(rules_data.get('aliases', []))} 条")
    print(f"  重命名规则: {len(rules_data.get('renames', []))} 条")
    print(f"  性别规则: {len(rules_data.get('gender_renames', []))} 条")
    
    changelog = rules_data.get('changelog')
    if changelog:
        print(f"  更新说明: {changelog}")


def test_basic_update():
    """测试 1: 基本更新流程"""
    print_section("测试 1: 基本在线更新流程")
    
    # 获取规则管理器
    rule_mgr = get_rule_manager()
    
    print("\n当前本地规则:")
    with open('default_rules.json', 'r', encoding='utf-8') as f:
        local_rules = json.load(f)
    display_rules(local_rules)
    
    # 测试服务器地址（需要先启动 test_update_server.py）
    server_url = "http://localhost:5000/medical_rules.json"
    
    print(f"\n正在从服务器更新: {server_url}")
    print("提示: 请确保 test_update_server.py 已启动\n")
    
    try:
        # 执行更新
        success = rule_mgr.update_rules_online(server_url)
        
        if success:
            print("✓ 更新成功！")
            print("\n更新后的规则:")
            with open('default_rules.json', 'r', encoding='utf-8') as f:
                updated_rules = json.load(f)
            display_rules(updated_rules)
        else:
            print("○ 当前已是最新版本，无需更新")
            
    except Exception as e:
        print(f"✗ 更新失败: {e}")
        print("\n可能的原因:")
        print("  1. 测试服务器未启动（请运行: python test_update_server.py）")
        print("  2. 网络连接问题")
        print("  3. Flask 未安装（请运行: pip install flask）")


def test_version_comparison():
    """测试 2: 版本比较逻辑"""
    print_section("测试 2: 版本号比较算法")
    
    rule_mgr = get_rule_manager()
    
    test_cases = [
        ("1.2.0", "1.1.5", "在线版本更新"),
        ("1.0.5", "1.1.0", "本地版本更新"),
        ("1.2.3", "1.2.3", "版本相同"),
        ("2.0.0", "1.9.9", "大版本更新"),
        ("1.2", "1.2.0", "长度不同（相同）"),
    ]
    
    print("\n版本比较测试:")
    print(f"{'在线版本':<12s} {'本地版本':<12s} {'比较结果':<15s} {'说明'}")
    print("-" * 60)
    
    for v1, v2, desc in test_cases:
        result = rule_mgr._compare_version(v1, v2)
        if result > 0:
            status = "需要更新 ↑"
        elif result < 0:
            status = "无需更新 ↓"
        else:
            status = "版本相同 ≡"
        
        print(f"{v1:<12s} {v2:<12s} {status:<15s} {desc}")


def test_check_updates():
    """测试 3: 检查更新（不自动下载）"""
    print_section("测试 3: 检查是否有新版本")
    
    import requests
    from rule_manager import get_rule_manager
    
    server_url = "http://localhost:5000/version"
    
    try:
        rule_mgr = get_rule_manager()
        print(f"\n当前本地版本: {rule_mgr.version}")
        
        print(f"正在检查服务器版本: {server_url}")
        response = requests.get(server_url, timeout=5)
        response.raise_for_status()
        
        server_info = response.json()
        server_version = server_info['version']
        
        print(f"服务器最新版本: {server_version}")
        
        if rule_mgr._compare_version(server_version, rule_mgr.version) > 0:
            print(f"\n✓ 发现新版本: {server_version}")
            if 'changelog' in server_info and server_info['changelog']:
                print(f"更新内容: {server_info['changelog']}")
            print("\n可以执行更新操作")
        else:
            print("\n○ 当前已是最新版本")
            
    except Exception as e:
        print(f"\n✗ 检查失败: {e}")


def test_manual_version_update():
    """测试 4: 指定版本更新"""
    print_section("测试 4: 更新到指定版本")
    
    rule_mgr = get_rule_manager()
    
    # 可选的测试版本
    versions = ["1.0.0", "1.1.0", "1.2.0"]
    
    print("\n可用的测试版本:")
    for i, v in enumerate(versions, 1):
        print(f"  {i}. 版本 {v}")
    
    print(f"\n当前本地版本: {rule_mgr.version}")
    
    try:
        choice = input("\n请选择要更新的版本 (1-3，回车跳过): ").strip()
        
        if choice and choice.isdigit() and 1 <= int(choice) <= len(versions):
            target_version = versions[int(choice) - 1]
            url = f"http://localhost:5000/medical_rules.json?version={target_version}"
            
            print(f"\n正在更新到版本 {target_version}...")
            success = rule_mgr.update_rules_online(url)
            
            if success:
                print(f"✓ 成功更新到版本 {target_version}")
            else:
                print("○ 无需更新或版本相同")
        else:
            print("跳过测试")
            
    except Exception as e:
        print(f"✗ 更新失败: {e}")


def test_list_all_versions():
    """测试 5: 查看所有可用版本"""
    print_section("测试 5: 查看服务器所有可用版本")
    
    url = "http://localhost:5000/versions"
    
    try:
        import requests
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        versions = response.json()
        
        print("\n服务器可用版本列表:")
        print(f"{'版本':<10s} {'更新时间':<15s} {'规则数':<10s} {'说明'}")
        print("-" * 60)
        
        for v in versions:
            print(f"{v['version']:<10s} {v['last_updated']:<15s} "
                  f"{v['rule_count']:<10d} {v['changelog']}")
                  
    except Exception as e:
        print(f"\n✗ 查询失败: {e}")


def interactive_menu():
    """交互式菜单"""
    while True:
        print("\n" + "=" * 60)
        print("在线更新功能测试菜单")
        print("=" * 60)
        print("1. 执行在线更新")
        print("2. 测试版本比较算法")
        print("3. 检查是否有新版本")
        print("4. 更新到指定版本")
        print("5. 查看服务器所有版本")
        print("0. 退出")
        print("=" * 60)
        
        choice = input("\n请选择操作 (0-5): ").strip()
        
        if choice == '1':
            test_basic_update()
        elif choice == '2':
            test_version_comparison()
        elif choice == '3':
            test_check_updates()
        elif choice == '4':
            test_manual_version_update()
        elif choice == '5':
            test_list_all_versions()
        elif choice == '0':
            print("\n再见！")
            break
        else:
            print("\n无效选择，请重试")
        
        input("\n按回车继续...")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("在线更新功能测试工具")
    print("=" * 60)
    print("\n使用说明:")
    print("1. 在另一个终端窗口运行: python test_update_server.py")
    print("2. 等待服务器启动（看到 'Running on http://0.0.0.0:5000'）")
    print("3. 回到本窗口，按任意键开始测试")
    
    input("\n准备好后按回车键继续...")
    
    # 检查服务器是否可用
    try:
        import requests
        response = requests.get("http://localhost:5000/health", timeout=2)
        print("✓ 测试服务器已就绪\n")
    except:
        print("✗ 警告: 无法连接到测试服务器")
        print("请确保已运行: python test_update_server.py\n")
    
    # 显示交互式菜单
    interactive_menu()


if __name__ == "__main__":
    main()

