#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证知识库配置是否正确"""

import sys
import io
from pathlib import Path

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from law_push.knowledge_base import load

def main():
    print("=" * 60)
    print("知识库配置验证")
    print("=" * 60)

    try:
        config = load()
        dify = config.get('dify', {})

        print("\n[OK] 配置文件加载成功")
        print(f"\n知识库配置:")
        print(f"  Base URL: {dify.get('base_url')}")
        print(f"  Dataset Name: {dify.get('dataset_name')}")
        print(f"  Dataset ID: {dify.get('dataset_id')}")
        print(f"  API Key: {'已配置' if dify.get('api_key') else '未配置'}")

        # 验证必需字段
        required_fields = ['base_url', 'api_key', 'dataset_id', 'dataset_name']
        missing_fields = [field for field in required_fields if not dify.get(field)]

        if missing_fields:
            print(f"\n[ERROR] 缺少必需字段: {', '.join(missing_fields)}")
            return 1

        # 验证知识库 ID
        expected_id = "28522cdc-67e0-414d-83b1-fada32f48958"
        actual_id = dify.get('dataset_id')

        if actual_id == expected_id:
            print(f"\n[OK] 知识库 ID 正确（法律案例知识库）")
        else:
            print(f"\n[ERROR] 知识库 ID 不匹配")
            print(f"  期望: {expected_id}")
            print(f"  实际: {actual_id}")
            return 1

        print("\n" + "=" * 60)
        print("[SUCCESS] 所有配置验证通过！")
        print("=" * 60)
        return 0

    except FileNotFoundError:
        print("\n[ERROR] 配置文件不存在")
        print("  请确保 config/kb_sync.local.json 文件存在")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 配置验证失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
