from pathlib import Path

from run_launcher import prepare_runtime_env


def test_prepare_runtime_env_uses_project_local_hermes_home(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text(
        "LLM_MODEL=qwen3:32b\nLLM_BASE_URL=http://localhost:11434/v1\n",
        encoding="utf-8",
    )

    env = prepare_runtime_env(project_root)

    hermes_home = project_root / ".hermes"
    assert Path(env["HERMES_HOME"]) == hermes_home
    assert (hermes_home / ".env").read_text(encoding="utf-8") == (
        project_root / ".env"
    ).read_text(encoding="utf-8")
