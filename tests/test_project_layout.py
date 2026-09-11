import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from law_push import cli
from law_push.crawler import LawCrawler

ROOT = Path(__file__).resolve().parents[1]


def isolated_env(home):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('LAW_PUSH_', 'CASE_DB_', 'DIFY_', 'KINGDEE_'))}
    env['LAW_PUSH_HOME'] = str(home)
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def test_checkout_launcher_from_another_working_directory(tmp_path):
    home = tmp_path / 'deployment'
    config = home / 'config'
    config.mkdir(parents=True)
    (config / 'app.local.json').write_text(json.dumps({'dify': {
        'api_key': 'private-classifier-key', 'base_url': 'https://example.invalid/v1'}}))
    (config / 'kb_sync.local.json').write_text(json.dumps({
        'database': dict(host='localhost', port=5432, database='cases', user='test',
                         password='private-db-password', schema='public', table='cases'),
        'dify': dict(api_key='private-kb-key', base_url='https://example.invalid/v1', dataset_id='test'),
    }))
    result = subprocess.run([sys.executable, str(ROOT / 'run_filter.py'), 'check-config'],
        cwd=tmp_path, env=isolated_env(home), capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert str(home / 'data/output') in result.stdout
    assert 'private-' not in result.stdout + result.stderr
    assert (home / 'logs/law-push.log').exists()


@pytest.mark.parametrize('args', [['30', '--help'], ['crawl', '--help'],
    ['import-cases', '--help'], ['sync-kb', '--help'], ['push-kingdee', '--help']])
def test_all_public_commands_resolve_from_outside_project(tmp_path, args):
    result = subprocess.run([sys.executable, str(ROOT / 'run_filter.py'), *args],
        cwd=tmp_path, env=isolated_env(tmp_path), capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout


def test_command_dispatch_preserves_options(monkeypatch):
    module = Mock()
    module.main.return_value = 7
    monkeypatch.setattr(cli, 'configure_logging', Mock())
    loader = Mock(return_value=module)
    monkeypatch.setattr(cli, 'import_module', loader)
    assert cli.main(['sync-kb', '--database-config', 'custom.json', '--limit', '2']) == 7
    module.main.assert_called_once_with(['--database-config', 'custom.json', '--limit', '2'])


def test_importing_library_does_not_create_outputs_or_logs(tmp_path):
    env = isolated_env(tmp_path)
    env['PYTHONPATH'] = str(ROOT / 'src')
    result = subprocess.run([sys.executable, '-c', 'import law_push.pipeline'],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / 'logs').exists()
    assert not (tmp_path / 'data').exists()


def test_export_creates_output_directories(tmp_path):
    crawler = LawCrawler(days=30)
    try:
        crawler.results = crawler.case_results = []
        output = tmp_path / 'new/output'
        crawler.save_core_outputs(output / 'law.txt', output / 'case.csv')
        assert (output / 'law.txt').exists()
        assert (output / 'case.csv').read_text(encoding='utf-8-sig').startswith('标题,来源,日期,链接,文件日期')
    finally:
        crawler.session.close()
