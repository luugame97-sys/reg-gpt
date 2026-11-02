"""Deployment races must defer without interrupting account work or bypassing CAS."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


DEPLOY_HELPER = Path(__file__).parents[1] / '_ai_workbench/tools/deploy_cumulative_traffic.py'
pytestmark = pytest.mark.skipif(
    not DEPLOY_HELPER.is_file(),
    reason='The private deployment helper is not included in source-only checkouts',
)


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    fake=types.ModuleType('deploy_task_traffic')
    fake.ROOT=tmp_path;fake.REMOTE='/opt/fixture';fake.APPLY='def idle():\n return\n'
    monkeypatch.setitem(sys.modules,'deploy_task_traffic',fake)
    spec=importlib.util.spec_from_file_location('fixture_deploy_manager',DEPLOY_HELPER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fake.REPORT=tmp_path/'staging.json';fake.RELEASE_REPORT=tmp_path/'release.json'
    fake.REPORT.write_text(json.dumps({'release':'first','applied':False}),encoding='utf-8')
    calls={'probe':0,'stage':0,'apply':0,'stat':0}
    def command(*args):calls['probe']+=1;return json.dumps({'idle':True})
    def stage(*args):calls['stage']+=1;fake.REPORT.write_text(json.dumps({'release':'second','applied':False}),encoding='utf-8')
    def apply(*args):
        calls['apply']+=1
        metadata=json.loads(fake.REPORT.read_text());metadata['applied']=True
        fake.RELEASE_REPORT.write_text(json.dumps(metadata),encoding='utf-8')
    fake.command=command;fake.stage=stage;fake.apply=apply
    class Sftp:
        exists=False
        def stat(self,path):
            calls['stat']+=1
            if not self.exists:raise FileNotFoundError(path)
        def close(self):pass
    sftp=Sftp();client=types.SimpleNamespace(open_sftp=lambda:sftp)
    return module,fake,calls,client,sftp


def test_busy_service_is_read_only_and_does_not_attempt_apply(deployment):
    module,fake,calls,client,_=deployment
    fake.command=lambda *args:json.dumps({'idle':False,'reason':'A background refresh is active'})
    result=module.attempt_apply(client)
    assert result['status']=='deferred'
    assert calls['stage']==calls['apply']==calls['stat']==0
    assert not fake.RELEASE_REPORT.exists()


def test_new_work_at_the_final_gate_defers_without_retrying(deployment):
    module,fake,calls,client,_=deployment
    def blocked(*args):calls['apply']+=1;raise RuntimeError('A background refresh is active')
    fake.apply=blocked
    assert module.attempt_apply(client)['status']=='deferred'
    assert calls['apply']==1 and calls['stage']==0


def test_cas_conflicts_are_not_treated_as_a_busy_service(deployment):
    module,fake,calls,client,_=deployment
    fake.apply=lambda *args:(_ for _ in ()).throw(RuntimeError('CAS conflict: webui/db.py'))
    with pytest.raises(RuntimeError,match='CAS conflict'):module.attempt_apply(client)


def test_already_applied_release_never_restarts_again(deployment):
    module,fake,calls,client,_=deployment
    marker={'release':'first','applied':True}
    fake.REPORT.write_text(json.dumps(marker));fake.RELEASE_REPORT.write_text(json.dumps(marker))
    assert module.attempt_apply(client)['status']=='already_applied'
    assert not any(calls.values())


def test_backup_from_aborted_attempt_is_retained_and_a_new_release_is_staged(deployment):
    module,fake,calls,client,sftp=deployment;sftp.exists=True
    result=module.attempt_apply(client)
    assert result['status']=='applied' and result['release']=='second' and result['restaged_from']=='first'
    assert calls['stage']==calls['apply']==1


def test_idle_service_applies_the_prepared_package_once(deployment):
    module,fake,calls,client,_=deployment
    assert module.attempt_apply(client)['status']=='applied'
    assert calls['apply']==1 and calls['stage']==0
