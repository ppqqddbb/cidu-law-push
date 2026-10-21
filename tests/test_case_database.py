import csv
import json
from datetime import date
from unittest.mock import Mock

import pytest

from law_push import database as case_database
from law_push import pipeline as run_filter


def test_config_uses_same_database_name_variable_as_api(tmp_path, monkeypatch):
    path = tmp_path / 'law_push.settings.json'
    path.write_text(json.dumps({'database': dict(host='localhost', port=5432,
        database='old', user='test', schema='public', table='cases')}))
    monkeypatch.setenv('CASE_DB_NAME', 'shared_cases')
    assert case_database.load_config(path)['database'] == 'shared_cases'


def test_config_can_be_supplied_entirely_by_environment(tmp_path, monkeypatch):
    for key, value in dict(HOST='localhost', PORT='5432', NAME='cases',
                           USER='test', SCHEMA='public', TABLE='cases').items():
        monkeypatch.setenv('CASE_DB_' + key, value)
    monkeypatch.setattr(case_database, 'DEFAULT_CONFIG', tmp_path / 'absent.json')
    assert case_database.load_config()['database'] == 'cases'


def test_repeated_csv_import_skips_existing_rows(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    path = tmp_path / 'case.csv'
    row = ['案例', '法院', '2026-09-09', 'https://example.com', '2026-09-10 09:20:31', '摘要']
    write_csv(path, [row, row])
    connection = MagicMock()
    stored = set()

    def execute(statement, params=None):
        query = statement.as_string()
        cursor = Mock()
        if 'MAX(fid)' in query:
            cursor.fetchone.return_value = {'id': 101}
        elif 'SELECT 1' in query:
            cursor.fetchone.return_value = {'exists': 1} if params in stored else None
        elif 'INSERT INTO' in query:
            stored.add((params[1], params[3]))
        return cursor

    connection.execute.side_effect = execute
    monkeypatch.setattr(case_database.psycopg, 'connect', Mock(return_value=connection))
    monkeypatch.setattr(case_database, 'load_config', Mock(return_value=dict(
        host='localhost', port=5432, database='test', user='test', schema='public', table='cases')))
    assert case_database.import_csv(path) == {'inserted': 1, 'skipped': 1}
    assert case_database.import_csv(path) == {'inserted': 0, 'skipped': 2}


def test_csv_import_cli_reports_failure(monkeypatch):
    monkeypatch.setattr(case_database, 'import_csv', Mock(side_effect=RuntimeError('offline')))
    assert case_database.main(['case.csv']) == 1


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['标题', '来源', '日期', '链接', '文件日期', '摘要'])
        writer.writerows(rows)


def test_csv_preserves_dates_long_links_and_multiline_summary(tmp_path):
    path = tmp_path / 'case.csv'
    url = 'https://example.com/' + 'a' * 100
    write_csv(path, [['案例,"一"', '法院', '2026-09-09', url, '2026-09-10 09:20:31', '第一行\n第二行']])
    row = case_database.read_cases(path)[0]
    assert row['link'] == url
    assert row['file_date'].strftime('%Y-%m-%d %H:%M:%S') == '2026-09-10 09:20:31'
    assert row['date'].date().isoformat() == '2026-09-09'
    assert row['summary'] == '第一行\n第二行'


def test_invalid_csv_never_connects(tmp_path, monkeypatch):
    path = tmp_path / 'case.csv'
    write_csv(path, [['案例', '', 'bad-date', '', '', '']])
    connect = Mock()
    monkeypatch.setattr(case_database.psycopg, 'connect', connect)
    with pytest.raises(ValueError, match='日期'):
        case_database.import_csv(path)
    connect.assert_not_called()


@pytest.mark.parametrize('fail', [False, True])
def test_filter_automatically_imports_saved_csv_and_keeps_files_on_failure(tmp_path, monkeypatch, fail):
    from law_push.crawler import LawCrawler

    crawler = LawCrawler(days=30)
    crawler.results = [dict(title='案例', date=date.today().isoformat(), url='https://example.com/case')]
    crawler.case_results = crawler.results[:]
    crawler.crawl_all = Mock()
    monkeypatch.setattr(run_filter, 'LawCrawler', Mock(return_value=crawler))
    for key, name in [('RESULT_OUTPUT_FILE', 'result.txt'), ('LAW_OUTPUT_FILE', 'law.txt'), ('CASE_OUTPUT_FILE', 'case.csv')]:
        monkeypatch.setattr(run_filter, key, tmp_path / name)
    calls = []

    def importer(path, config_path=None):
        calls.append(path)
        assert case_database.read_cases(path)[0]['title'] == '案例'
        if fail:
            raise RuntimeError('offline')
        return {'inserted': 1, 'skipped': 0}

    monkeypatch.setattr(run_filter, 'import_csv', importer)
    def syncer(config_path=None):
        assert calls == [tmp_path / 'case.csv']
        return {'synced': 1, 'failed': 0}
    synchronize = Mock(side_effect=syncer)
    monkeypatch.setattr(run_filter, 'synchronize', synchronize)
    try:
        if fail:
            with pytest.raises(RuntimeError, match='case.csv'):
                run_filter.run(30, Mock(classify=Mock(return_value='case')))
        else:
            assert run_filter.run(30, Mock(classify=Mock(return_value='case'))) == (0, 1, 0)
        assert calls == [tmp_path / 'case.csv']
        assert synchronize.call_count == (0 if fail else 1)
        assert (tmp_path / 'law.txt').exists()
        assert (tmp_path / 'case.csv').exists()
        assert not (tmp_path / 'case.txt').exists()
        assert not (tmp_path / 'law.csv').exists()
    finally:
        crawler.session.close()


@pytest.mark.parametrize('sync_failure', [False, True])
def test_sync_failure_preserves_database_import_and_csv(tmp_path, monkeypatch, sync_failure):
    from law_push.crawler import LawCrawler

    crawler = LawCrawler(days=30)
    crawler.results = crawler.case_results = []
    crawler.crawl_all = Mock()
    monkeypatch.setattr(run_filter, 'LawCrawler', Mock(return_value=crawler))
    for key, name in [('RESULT_OUTPUT_FILE', 'result.txt'), ('LAW_OUTPUT_FILE', 'law.txt'), ('CASE_OUTPUT_FILE', 'case.csv')]:
        monkeypatch.setattr(run_filter, key, tmp_path / name)
    importer = Mock(return_value={'inserted': 0, 'skipped': 0})
    synchronizer = Mock(return_value={'failed': 1})
    monkeypatch.setattr(run_filter, 'import_csv', importer)
    monkeypatch.setattr(run_filter, 'synchronize', synchronizer)
    try:
        if sync_failure:
            with pytest.raises(RuntimeError, match='sync-kb'):
                run_filter.run(30, Mock(), database_config='shared.json')
            synchronizer.assert_called_once_with('shared.json')
        else:
            run_filter.run(30, Mock(), database_config='shared.json', sync_knowledge_base=False)
            synchronizer.assert_not_called()
        importer.assert_called_once_with(tmp_path / 'case.csv', 'shared.json')
        assert (tmp_path / 'case.csv').exists()
    finally:
        crawler.session.close()


@pytest.mark.parametrize('flags, expected', [([], (True, True)),
    (['--no-sync-kb'], (True, False)), (['--no-push-case'], (False, True))])
def test_command_defaults_and_opt_out_flags(monkeypatch, flags, expected):
    monkeypatch.setattr('sys.argv', ['law_push.pipeline.py', '30', *flags])
    monkeypatch.setenv('DIFY_API_KEY', 'test-key')
    runner = Mock()
    monkeypatch.setattr(run_filter, 'run', runner)
    assert run_filter.main() == 0
    assert runner.call_args.kwargs['import_database'] is expected[0]
    assert runner.call_args.kwargs['sync_knowledge_base'] is expected[1]
