#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 云端更新快速测试脚本
"""

import json
import requests
from rule_manager import get_rule_manager


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def test_github_access():
    """测试 1: 检查 GitHub 访问"""
    print_section("测试 1: 检查 GitHub Raw 文件访问")
    
    github_url = "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json"
    
    print(f"\n测试 URL: {github_url}\n")
    
    try:
        print("正在连接 GitHub...")
        response = requests.get(github_url, timeout=10)
        
        print(f"✓ HTTP 状态码: {response.status_code}")
        print(f"✓ 响应时间: {response.elapsed.total_seconds():.2f} 秒")
        print(f"✓ 内容大小: {len(response.content)} 字节")
        
        # 解析 JSON
        rules = response.json()
        print(f"\n规则信息:")
        print(f"  版本: {rules.get('version', 'unknown')}")
        print(f"  更新时间: {rules.get('last_updated', 'unknown')}")
        print(f"  别名规则: {len(rules.get('aliases', []))} 条")
        print(f"  重命名规则: {len(rules.get('renames', []))} 条")
        print(f"  性别规则: {len(rules.get('gender_renames', []))} 条")
        
        changelog = rules.get('changelog')
        if changelog:
            print(f"  更新说明: {changelog}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ 连接失败: 无法连接到 GitHub")
        print("  可能原因:")
        print("  1. 网络连接问题")
        print("  2. GitHub 服务不可用")
        print("  3. 需要代理访问")
        return False
        
    except requests.exceptions.Timeout:
        print("✗ 连接超时: GitHub 响应太慢")
        print("  建议:")
        print("  1. 检查网络连接")
        print("  2. 尝试使用 CDN 加速")
        return False
        
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP 错误: {e}")
        print("  可能原因:")
        print("  1. 仓库是私有的")
        print("  2. 文件不存在")
        print("  3. 分支名称错误")
        return False
        
    except json.JSONDecodeError:
        print("✗ JSON 解析失败: 文件格式错误")
        return False
        
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        return False


def test_version_comparison():
    """测试 2: 版本号比较"""
    print_section("测试 2: 版本号比较")
    
    rule_mgr = get_rule_manager()
    github_url = "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json"
    
    try:
        # 获取本地版本
        with open('default_rules.json', 'r', encoding='utf-8') as f:
            local_rules = json.load(f)
            local_version = local_rules.get('version', '0.0.0')
        
        # 获取 GitHub 版本
        response = requests.get(github_url, timeout=10)
        github_rules = response.json()
        github_version = github_rules.get('version', '0.0.0')
        
        print(f"\n本地版本: {local_version}")
        print(f"GitHub 版本: {github_version}")
        
        # 比较版本
        result = rule_mgr._compare_version(github_version, local_version)
        
        print(f"\n比较结果:")
        if result > 0:
            print("  ✓ GitHub 版本更新 - 可以更新")
            print(f"  更新说明: {github_rules.get('changelog', '无')}")
        elif result < 0:
            print("  ○ 本地版本更新 - 无需更新")
        else:
            print("  ≡ 版本相同 - 无需更新")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 比较失败: {e}")
        return False


def test_update_from_github():
    """测试 3: 执行 GitHub 更新"""
    print_section("测试 3: 从 GitHub 更新规则")
    
    github_url = "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json"
    
    try:
        # 备份当前规则
        print("\n正在备份当前规则...")
        import shutil
        from datetime import datetime
        backup_file = f"default_rules.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy2('default_rules.json', backup_file)
        print(f"✓ 已备份到: {backup_file}")
        
        # 执行更新
        print(f"\n正在从 GitHub 更新...")
        print(f"URL: {github_url}")
        
        rule_mgr = get_rule_manager()
        success = rule_mgr.update_rules_online(github_url)
        
        if success:
            print("\n✓ 更新成功!")
            
            # 显示更新后的信息
            with open('default_rules.json', 'r', encoding='utf-8') as f:
                updated_rules = json.load(f)
            
            print(f"\n更新后的规则:")
            print(f"  版本: {updated_rules.get('version')}")
            print(f"  更新时间: {updated_rules.get('last_updated')}")
            print(f"  别名规则: {len(updated_rules.get('aliases', []))} 条")
            
            changelog = updated_rules.get('changelog')
            if changelog:
                print(f"  更新说明: {changelog}")
            
            print(f"\n💡 如需回滚，运行:")
            print(f"   cp {backup_file} default_rules.json")
            
        else:
            print("\n○ 当前已是最新版本，无需更新")
        
        return success
        
    except Exception as e:
        print(f"\n✗ 更新失败: {e}")
        print("\n💡 提示:")
        print("  1. 检查网络连接")
        print("  2. 确认 GitHub 仓库可访问")
        print("  3. 查看详细错误信息")
        return False


def test_cdn_access():
    """测试 4: 测试 CDN 加速访问"""
    print_section("测试 4: CDN 加速访问测试")
    
    urls = {
        "GitHub Raw (直连)": "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json",
        "jsDelivr CDN": "https://cdn.jsdelivr.net/gh/songlongGithub/CheckProjectInformation@main/default_rules.json",
    }
    
    print("\n测试不同访问方式的速度:\n")
    
    results = []
    
    for name, url in urls.items():
        try:
            import time
            start = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                results.append((name, elapsed, True))
                print(f"✓ {name:25s} 耗时: {elapsed:.2f} 秒")
            else:
                results.append((name, 0, False))
                print(f"✗ {name:25s} 失败 (HTTP {response.status_code})")
                
        except Exception as e:
            results.append((name, 0, False))
            print(f"✗ {name:25s} 失败 ({e})")
    
    # 推荐最快的方式
    print("\n推荐配置:")
    successful = [(n, t) for n, t, s in results if s]
    if successful:
        fastest = min(successful, key=lambda x: x[1])
        print(f"  最快: {fastest[0]} ({fastest[1]:.2f} 秒)")
        
        if "CDN" in fastest[0]:
            print("\n💡 建议修改 settings_dialog.py 使用 CDN URL:")
            print("   online_url = \"https://cdn.jsdelivr.net/gh/songlongGithub/CheckProjectInformation@main/default_rules.json\"")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("GitHub 云端更新测试工具")
    print("=" * 70)
    print("\n仓库: https://github.com/songlongGithub/CheckProjectInformation")
    print("文件: default_rules.json")
    
    # 运行所有测试
    tests = [
        ("GitHub 访问测试", test_github_access),
        ("版本比较测试", test_version_comparison),
        ("CDN 速度测试", test_cdn_access),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} 异常: {e}")
            results.append((name, False))
        
        input("\n按回车继续下一个测试...")
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name:30s} {status}")
    
    # 是否执行更新
    print("\n" + "=" * 70)
    choice = input("\n是否执行实际更新？(y/n): ").strip().lower()
    
    if choice == 'y':
        test_update_from_github()
    else:
        print("\n已跳过更新测试")
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
    print("\n相关文档:")
    print("  - GitHub云端更新指南.md")
    print("  - 在线更新功能详解.md")
    print("  - 在线更新测试指南.md")


if __name__ == "__main__":
    main()

