import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from config import Config, _find_env_file


class ConfigTests(unittest.TestCase):
    def test_template_api_keys_are_not_configured(self):
        template_values = {
            "SILICONFLOW_API_KEY": "your_siliconflow_api_key_here",
            "DASHSCOPE_API_KEY": "your_dashscope_api_key_here",
            "OPENAI_API_KEY": "your_openai_api_key_here",
        }

        for key_name, template_value in template_values.items():
            with self.subTest(key_name=key_name):
                output = io.StringIO()

                with patch.object(Config, key_name, template_value), redirect_stdout(output):
                    self.assertFalse(Config.check_api_key(key_name))

                self.assertIn(f"{key_name} 未配置", output.getvalue())

    def test_non_template_api_key_is_configured(self):
        with patch.object(Config, "SILICONFLOW_API_KEY", "sk-example"):
            self.assertTrue(Config.check_api_key("SILICONFLOW_API_KEY"))

    def test_missing_and_legacy_api_keys_are_not_configured(self):
        for value in ("", "YOUR_API_KEY"):
            with self.subTest(value=value):
                with patch.object(Config, "SILICONFLOW_API_KEY", value), redirect_stdout(io.StringIO()):
                    self.assertFalse(Config.check_api_key("SILICONFLOW_API_KEY"))


class EnvFileDiscoveryTests(unittest.TestCase):
    def test_prefers_code_env_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "repo"
            code_dir = repo_dir / "code"
            code_dir.mkdir(parents=True)
            (repo_dir / ".git").mkdir()
            root_env = repo_dir / ".env"
            code_env = code_dir / ".env"
            root_env.write_text("SILICONFLOW_API_KEY=root\n", encoding="utf-8")
            code_env.write_text("SILICONFLOW_API_KEY=code\n", encoding="utf-8")

            self.assertEqual(_find_env_file(code_dir), code_env)

    def test_falls_back_to_repo_root_env_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "repo"
            code_dir = repo_dir / "code"
            code_dir.mkdir(parents=True)
            (repo_dir / ".git").mkdir()
            root_env = repo_dir / ".env"
            root_env.write_text("SILICONFLOW_API_KEY=root\n", encoding="utf-8")

            self.assertEqual(_find_env_file(code_dir), root_env)

    def test_stops_at_repo_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_dir = Path(temp_dir)
            repo_dir = workspace_dir / "repo"
            code_dir = repo_dir / "code"
            code_dir.mkdir(parents=True)
            (repo_dir / ".git").mkdir()
            (workspace_dir / ".env").write_text(
                "SILICONFLOW_API_KEY=workspace\n",
                encoding="utf-8",
            )

            self.assertIsNone(_find_env_file(code_dir))


if __name__ == "__main__":
    unittest.main()
