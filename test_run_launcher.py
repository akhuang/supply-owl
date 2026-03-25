from pathlib import Path

import yaml

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


def test_prepare_runtime_env_writes_hermes_config_from_root_env(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text(
        "\n".join(
            [
                "LLM_MODEL=qwen3:32b",
                "LLM_BASE_URL=http://localhost:11434/v1",
                "LLM_API_KEY=ollama",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (project_root / "cli-config.yaml").write_text(
        "terminal:\n  command_approval: smart\n",
        encoding="utf-8",
    )

    env = prepare_runtime_env(project_root)

    config = yaml.safe_load((project_root / ".hermes" / "config.yaml").read_text(encoding="utf-8"))
    assert config["model"] == {
        "default": "qwen3:32b",
        "provider": "custom",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    }
    assert config["terminal"]["command_approval"] == "smart"
    assert env["HERMES_INFERENCE_PROVIDER"] == "custom"
