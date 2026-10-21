#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试知识库禁用功能（模拟模式）"""

import sys
import io
from unittest.mock import Mock, MagicMock
from pathlib import Path

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from law_push.knowledge_base import disable_old_documents

def test_disable_old_documents():
    """测试禁用旧文档功能"""
    print("=" * 60)
    print("测试知识库文档禁用功能")
    print("=" * 60)

    # 创建模拟的 session
    session = MagicMock()

    # 模拟知识库配置
    dify = {
        'base_url': 'http://ciduai.daneng.cc/v1',
        'api_key': 'test-key'
    }

    dataset_id = '28522cdc-67e0-414d-83b1-fada32f48958'

    # 模拟 API 响应 - 第一页有 2 个文档
    mock_response = Mock()
    mock_response.json.return_value = {
        'data': [
            {'id': 'doc-1', 'enabled': True, 'name': 'case-1'},
            {'id': 'doc-2', 'enabled': True, 'name': 'case-2'},
            {'id': 'doc-3', 'enabled': False, 'name': 'case-3'}  # 已禁用，应跳过
        ],
        'has_more': False
    }
    mock_response.raise_for_status = Mock()
    session.get.return_value = mock_response

    # 模拟禁用文档的响应
    mock_update_response = Mock()
    mock_update_response.raise_for_status = Mock()
    session.post.return_value = mock_update_response

    print("\n模拟场景:")
    print(f"  知识库 ID: {dataset_id}")
    print("  文档列表: 3 个文档（2 个启用，1 个已禁用）")

    # 执行禁用操作
    disabled_count = disable_old_documents(session, dify, dataset_id)

    print(f"\n执行结果:")
    print(f"  禁用文档数量: {disabled_count}")
    print(f"  GET 请求次数: {session.get.call_count}")
    print(f"  POST 请求次数: {session.post.call_count}")

    # 验证结果
    assert disabled_count == 2, f"预期禁用 2 个文档，实际禁用 {disabled_count} 个"
    assert session.get.call_count == 1, f"预期 1 次 GET 请求，实际 {session.get.call_count} 次"
    assert session.post.call_count == 2, f"预期 2 次 POST 请求，实际 {session.post.call_count} 次"

    # 验证 API 调用
    get_call = session.get.call_args
    assert f'/datasets/{dataset_id}/documents' in get_call[0][0], "GET 请求 URL 不正确"

    # 验证禁用请求
    for call in session.post.call_args_list:
        assert 'status' in call[0][0], "POST 请求 URL 应包含 'status'"
        assert call[1]['json'] == {'enabled': False}, "POST 请求 body 不正确"

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)
    print("\n功能说明:")
    print("  1. 只禁用指定知识库的文档")
    print("  2. 只禁用当前启用的文档（enabled=True）")
    print("  3. 跳过已经禁用的文档")
    print("  4. 支持分页处理大量文档")

if __name__ == "__main__":
    try:
        test_disable_old_documents()
    except AssertionError as e:
        print(f"\n[ERROR] 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
