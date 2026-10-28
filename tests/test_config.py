from spokenslate.config import load_settings


def test_new_names_win_and_old_names_still_work(monkeypatch):
    for k in ("SPOKENSLATE_BOARD_MODEL", "SEED_BOARD_MODEL", "SPOKENSLATE_CAMERA_INDEX",
              "PAPEROS_CAMERA_INDEX", "SPOKENSLATE_SAM_MODEL", "SEED_SAM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("spokenslate.config.load_dotenv", lambda: None)
    monkeypatch.setenv("SEED_BOARD_MODEL", "old")
    monkeypatch.setenv("PAPEROS_CAMERA_INDEX", "2")
    s = load_settings()
    assert s.board_model == "old" and s.camera_index == 2      # pre-rename .env keeps working
    monkeypatch.setenv("SPOKENSLATE_BOARD_MODEL", "new")
    assert load_settings().board_model == "new"                # new name wins
    assert load_settings().sam_model == ""
