from pathlib import Path

from ytvg.config import Settings
from ytvg.infrastructure.storage.temp_manager import TempWorkspaceManager


def _mgr(tmp_path: Path) -> TempWorkspaceManager:
    settings = Settings(
        telegram_bot_token="x",
        temp_dir=tmp_path,
        temp_ttl_hours=0,
    )
    return TempWorkspaceManager(settings)


def test_prepare_and_wipe(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    job_id = "abc123"
    root = Path(mgr.prepare(job_id))
    audio = Path(mgr.audio_path(job_id, 1))
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"fake")
    assert root.exists()
    mgr.wipe(job_id)
    assert not root.exists()


def test_rejects_path_traversal(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    try:
        mgr.prepare("../etc")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_stale_sweep(tmp_path: Path) -> None:
    settings = Settings(telegram_bot_token="x", temp_dir=tmp_path, temp_ttl_hours=-1)
    mgr = TempWorkspaceManager(settings)
    job_id = "oldjob"
    path = Path(mgr.prepare(job_id))
    (path / "marker").write_text("x")
    removed = mgr.wipe_all_stale()
    assert removed >= 1
    assert not path.exists()
