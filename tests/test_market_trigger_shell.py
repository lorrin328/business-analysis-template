import pathlib,tempfile,subprocess,os
import pytest

@pytest.mark.skipif(os.name == 'nt', reason='Linux shell integration')
def test_manual_trigger_unloaded_failed_and_rejected(tmp_path):
 source=(pathlib.Path(__file__).resolve().parents[1] / 'deploy/market-analysis-trigger.sh').read_text()
 with tempfile.TemporaryDirectory() as root:
  p=pathlib.Path(root);(p/'bin').mkdir();(p/'state').mkdir()
  script=source.replace('/run/business-analysis-market-trigger/request',str(p/'request')).replace('/var/lib/business-analysis-market-trigger',str(p/'state'))
  # Exercise service/cooldown behavior as an unprivileged CI user. Only the
  # disposable test directory omits root ownership; production stays unchanged.
  script=script.replace('install -d -o root -g root -m 0700', 'install -d -m 0700')
  (p/'trigger.sh').write_text(script)
  (p/'bin/systemctl').write_text('#!/bin/bash\necho "$*" >> "$TEST_LOG"\ncase "$1" in\n is-active) exit 3;;\n is-failed) [ "$TEST_CASE" = failed ];;\n reset-failed) [ "$TEST_CASE" = failed ];;\n start) [ "$TEST_CASE" != rejected ];;\nesac\n')
  (p/'bin/logger').write_text('#!/bin/bash\nexit 0\n')
  for f in (p/'bin').iterdir():f.chmod(0o755)
  for case in ['unloaded','failed','rejected']:
   (p/'state/last-trigger').unlink(missing_ok=True);(p/'log').write_text('');(p/'request').write_text('{}')
   env=dict(os.environ,PATH=str(p/'bin')+':'+os.environ['PATH'],TEST_LOG=str(p/'log'),TEST_CASE=case)
   result=subprocess.run(['bash',str(p/'trigger.sh')],env=env,capture_output=True)
   log=(p/'log').read_text()
   assert ('start --no-block market-analysis.service' in log), result.stderr.decode()
   assert (result.returncode==0)==(case!='rejected')
   assert (p/'state/last-trigger').exists()==(case!='rejected')
   assert ('reset-failed' in log)==(case=='failed')
   print(case,'PASS')
