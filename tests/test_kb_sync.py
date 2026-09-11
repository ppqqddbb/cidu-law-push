from contextlib import nullcontext
import json
from unittest.mock import MagicMock, Mock

import pytest
import requests

import sync_cases_kb as kb


class CaseDatabase:
    def __init__(self, count):
        self.pending = {index for index in range(1, count + 1)}
        self.updated = []

    def transaction(self):
        return nullcontext()

    def execute(self, statement, params):
        query = statement.as_string()
        cursor = Mock()
        if 'COUNT(*)' in query:
            cursor.fetchone.return_value = {'count': len(self.pending), 'max_id': max(self.pending, default=None)}
        elif 'FOR UPDATE' in query:
            fid = params[0]
            cursor.fetchone.return_value = dict(fid=fid, fk_r8p0_title='案例', fk_r8p0_summary='第一行\n第二行')
        elif query.startswith('SELECT fid FROM'):
            after = params[2] if len(params) == 4 else 0
            cursor.fetchall.return_value = [{'fid': fid} for fid in sorted(self.pending)
                                           if after < fid <= params[1]][:params[-1]]
        elif query.startswith('UPDATE'):
            assert params[0] == '否'
            self.pending.remove(params[1])
            self.updated.append(params[1])
        else:
            raise AssertionError(query)
        return cursor


def setup_sync(monkeypatch, count):
    database = CaseDatabase(count)
    connection = MagicMock()
    connection.__enter__.return_value = database
    monkeypatch.setattr(kb.psycopg, 'connect', Mock(return_value=connection))
    config = {'database': dict(host='localhost', port=5432, database='test', user='test',
                              schema='public', table='cases'),
              'dify': dict(base_url='https://dify.test/v1', api_key='test', dataset_id='dataset')}
    monkeypatch.setattr(kb, 'load', Mock(return_value=config))
    session = MagicMock()
    session.__enter__.return_value = session
    session.post.return_value.json.return_value = {'document': {'id': 'doc-id'}}
    factory = Mock(return_value=session)
    monkeypatch.setattr(kb.requests, 'Session', factory)
    return database, session, factory


def test_all_pending_batches_are_submitted_and_repeat_is_noop(monkeypatch):
    database, session, factory = setup_sync(monkeypatch, 105)
    assert kb.synchronize()['synced'] == 105
    assert not database.pending
    assert session.post.call_count == 105
    assert '第一行\n第二行' in session.post.call_args.kwargs['json']['text']
    assert kb.synchronize()['synced'] == 0
    assert factory.call_count == 1


@pytest.mark.parametrize('failure', ['http', 'invalid_document'])
def test_failed_rows_stay_pending_and_retry_only_those_rows(monkeypatch, failure):
    database, session, _ = setup_sync(monkeypatch, 3)
    accepted = Mock()
    accepted.json.return_value = {'document': {'id': 'doc-id'}}
    invalid = Mock()
    invalid.json.return_value = {'document': {}}
    session.post.side_effect = [accepted, requests.HTTPError('offline') if failure == 'http' else invalid, accepted]
    result = kb.synchronize()
    assert result['synced'] == 2
    assert result['failed'] == 1
    assert database.pending == {2}
    session.post.side_effect = None
    session.post.return_value = accepted
    assert kb.synchronize()['synced'] == 1
    assert database.updated == [1, 3, 2]


def test_dry_run_has_no_http_requests_or_database_updates(monkeypatch):
    database, _, factory = setup_sync(monkeypatch, 5)
    assert kb.synchronize(dry_run=True)['pending'] == 5
    factory.assert_not_called()
    assert not database.updated


def test_explicit_limit_leaves_remaining_cases_pending(monkeypatch):
    database, _, _ = setup_sync(monkeypatch, 5)
    assert kb.synchronize(limit=2)['synced'] == 2
    assert database.pending == {3, 4, 5}


def test_dataset_name_lookup_paginates_and_rejects_ambiguity():
    session = Mock()
    first, second = Mock(), Mock()
    first.json.return_value = {'data': [], 'has_more': True}
    second.json.return_value = {'data': [{'id': 'target', 'name': '案例库'}], 'has_more': False}
    session.get.side_effect = [first, second]
    config = {'base_url': 'https://dify.test/v1', 'dataset_name': '案例库'}
    assert kb.resolve_dataset(session, config) == 'target'
    assert session.get.call_args.kwargs['params']['page'] == 2
    first.json.return_value = {'data': [{'id': 'duplicate', 'name': '案例库'}], 'has_more': True}
    session.get.side_effect = [first, second]
    with pytest.raises(ValueError, match='dataset_id'):
        kb.resolve_dataset(session, config)


def test_sync_uses_same_config_and_environment_as_importer(tmp_path, monkeypatch):
    config = {'database': dict(host='localhost', port=5432, database='old', user='test',
                              schema='public', table='cases'), 'dify': {}}
    path = tmp_path / 'shared.json'
    path.write_text(json.dumps(config))
    monkeypatch.setenv('CASE_DB_CONFIG', str(path))
    monkeypatch.setenv('CASE_DB_NAME', 'shared')
    monkeypatch.setenv('DIFY_KB_DATASET_ID', 'target')
    loaded = kb.load()
    assert loaded['database']['database'] == 'shared'
    assert loaded['dify']['dataset_id'] == 'target'


def test_cli_returns_failure_for_partial_failure(monkeypatch):
    monkeypatch.setattr(kb, 'synchronize', Mock(return_value={'failed': 1}))
    assert kb.main([]) == 1
