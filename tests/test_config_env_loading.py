from __future__ import annotations


def test_frozen_local_build_loads_repo_root_env(tmp_path, monkeypatch) -> None:
    import outlook_dashboard.config as config

    app_root = tmp_path / "dist" / "ReplyRight"
    app_root.mkdir(parents=True)
    repo_env = tmp_path / ".env"
    repo_env.write_text("SUPABASE_URL=https://example.supabase.co\n", encoding="utf-8")

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("REPLYRIGHT_LOAD_DOTENV_FOR_TESTS", "1")
    monkeypatch.setattr(config, "ROOT_DIR", app_root)
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)

    config._load_env()

    assert config.os.getenv("SUPABASE_URL") == "https://example.supabase.co"
