import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from config import Config


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


if __name__ == "__main__":
    unittest.main()
