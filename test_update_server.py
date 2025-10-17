#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在线更新测试服务器
用于演示和测试在线更新功能
"""

from flask import Flask, jsonify, request
import json
from datetime import datetime

app = Flask(__name__)

# 模拟不同版本的规则数据
RULE_VERSIONS = {
    "1.0.0": {
        "version": "1.0.0",
        "last_updated": "2025-10-17",
        "aliases": [
            ["静脉采血", "采血"],
            ["眼科常规", "眼科检查"],
        ],
        "renames": [
            ["一般检查", "身高体重,血压"]
        ],
        "gender_renames": [
            ["外科检查", "外科检查(男)", "外科检查(女)"]
        ]
    },
    "1.1.0": {
        "version": "1.1.0",
        "last_updated": "2025-10-17",
        "changelog": "新增 5 条别名规则",
        "aliases": [
            ["静脉采血", "采血"],
            ["眼科常规", "眼科检查"],
            ["乳腺彩超", "乳腺彩色超声"],  # 新增
            ["甲状腺彩超", "甲状腺彩色超声"],  # 新增
            ["常规心电图", "十二导联心电图"],  # 新增
        ],
        "renames": [
            ["一般检查", "身高体重,血压"]
        ],
        "gender_renames": [
            ["外科检查", "外科检查(男)", "外科检查(女)"]
        ]
    },
    "1.2.0": {
        "version": "1.2.0",
        "last_updated": "2025-10-18",
        "changelog": "新增重命名规则和性别规则",
        "aliases": [
            ["静脉采血", "采血"],
            ["眼科常规", "眼科检查"],
            ["乳腺彩超", "乳腺彩色超声"],
            ["甲状腺彩超", "甲状腺彩色超声"],
            ["常规心电图", "十二导联心电图"],
        ],
        "renames": [
            ["一般检查", "身高体重,血压"],
            ["妇科检查", "SELF,白带常规"],  # 新增
        ],
        "gender_renames": [
            ["外科检查", "外科检查(男)", "外科检查(女)"]
        ]
    }
}

# 当前提供的版本（模拟服务器端规则更新）
CURRENT_VERSION = "1.2.0"


@app.route('/')
def index():
    """首页：显示可用的 API"""
    return """
    <h1>医疗规则更新服务器 - 测试版</h1>
    <h2>可用接口：</h2>
    <ul>
        <li><a href="/medical_rules.json">/medical_rules.json</a> - 获取最新规则</li>
        <li><a href="/version">/version</a> - 查看当前版本</li>
        <li><a href="/versions">/versions</a> - 查看所有可用版本</li>
        <li>/medical_rules.json?version=1.0.0 - 获取指定版本</li>
    </ul>
    
    <h2>当前版本：{}</h2>
    <p>启动时间：{}</p>
    """.format(CURRENT_VERSION, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/medical_rules.json')
def get_rules():
    """获取规则数据"""
    # 获取请求的版本号（可选）
    requested_version = request.args.get('version', CURRENT_VERSION)
    
    # 获取对应版本的规则
    rules = RULE_VERSIONS.get(requested_version)
    
    if rules:
        # 记录访问日志
        client_ip = request.remote_addr
        client_version = request.headers.get('X-Current-Version', 'unknown')
        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"客户端 {client_ip} 请求规则 "
              f"(当前版本: {client_version}, 请求版本: {requested_version})")
        
        return jsonify(rules)
    else:
        return jsonify({"error": "版本不存在"}), 404


@app.route('/version')
def get_version():
    """仅返回版本信息"""
    return jsonify({
        "version": CURRENT_VERSION,
        "last_updated": RULE_VERSIONS[CURRENT_VERSION]["last_updated"],
        "changelog": RULE_VERSIONS[CURRENT_VERSION].get("changelog", "")
    })


@app.route('/versions')
def list_versions():
    """列出所有可用版本"""
    versions = [
        {
            "version": v,
            "last_updated": data["last_updated"],
            "changelog": data.get("changelog", "初始版本"),
            "rule_count": len(data["aliases"])
        }
        for v, data in sorted(RULE_VERSIONS.items())
    ]
    return jsonify(versions)


@app.route('/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


def main():
    """启动测试服务器"""
    print("=" * 60)
    print("医疗规则更新服务器 - 测试版")
    print("=" * 60)
    print(f"\n当前版本: {CURRENT_VERSION}")
    print(f"可用版本: {', '.join(RULE_VERSIONS.keys())}")
    print(f"\n服务器地址: http://localhost:5000")
    print(f"规则接口: http://localhost:5000/medical_rules.json")
    print(f"版本信息: http://localhost:5000/version")
    print("\n按 Ctrl+C 停止服务器\n")
    print("=" * 60)
    
    # 启动 Flask 服务器
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=5000,       # 端口号
        debug=True       # 调试模式
    )


if __name__ == '__main__':
    main()

