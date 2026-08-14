from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")


def _position(fragment: str) -> int:
    position = DEPLOY_SCRIPT.find(fragment)
    assert position >= 0, f"missing deploy fragment: {fragment}"
    return position


def test_online_backup_and_dependency_preparation_precede_service_stop():
    stop = _position('systemctl stop "$SERVICE_NAME"')

    assert _position('python3 "$SRC_DIR/backend/backup_database.py"') < stop
    assert _position('REUSE_EXISTING_VENV=0') < stop
    assert _position('python3 -m venv "$STAGED_VENV"') < stop
    assert stop < _position("rsync -a --delete")


def test_deploy_uses_migration_plan_instead_of_unconditional_aggregate_rebuild():
    assert 'REBUILD_AGGREGATES="${REBUILD_AGGREGATES:-auto}"' in DEPLOY_SCRIPT
    assert 'deployment_plan.py" snapshot' in DEPLOY_SCRIPT
    assert 'deployment_plan.py" plan' in DEPLOY_SCRIPT
    assert 'if [ "$SHOULD_REBUILD_FROM_EXCEL" = "1" ]' in DEPLOY_SCRIPT
    assert 'elif [ "$SHOULD_REBUILD_AGGREGATES" = "1" ]' in DEPLOY_SCRIPT
    assert "跳过耗时的全量聚合重建" in DEPLOY_SCRIPT


def test_main_service_health_is_restored_before_market_worker_sync():
    restart = _position('systemctl restart "$SERVICE_NAME"')
    health = _position('urlopen("http://127.0.0.1:45679/api/health"')
    market_sync = _position('bash "$APP_DIR/deploy/install-market-analysis.sh"')

    assert restart < health < market_sync
    assert 'systemctl reload nginx' in DEPLOY_SCRIPT
    assert 'systemctl restart nginx' not in DEPLOY_SCRIPT
