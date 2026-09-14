import os
import unittest
from pathlib import Path
from unittest.mock import patch


class SeekdbRuntimeTests(unittest.TestCase):
    def test_host_alone_does_not_enable_server_mode(self):
        from seekdb_runtime import resolve_seekdb_mode

        with patch.dict(os.environ, {"SEEKDB_HOST": "remote.example"}, clear=True):
            self.assertEqual(resolve_seekdb_mode(), "embedded")

    def test_embedded_mode_uses_explicit_path(self):
        from seekdb_runtime import create_seekdb_client

        with (
            patch.dict(os.environ, {"SEEKDB_MODE": "embedded"}, clear=True),
            patch("seekdb_runtime.embedded_available", return_value=True),
            patch("seekdb_runtime.pyseekdb.Client") as client_factory,
        ):
            create_seekdb_client(path="/tmp/course-seekdb")

        client_factory.assert_called_once_with(
            path=str(Path("/tmp/course-seekdb").resolve())
        )

    def test_embedded_mode_without_pylibseekdb_fails_with_platform_hint(self):
        from seekdb_runtime import create_seekdb_client

        with (
            patch.dict(os.environ, {"SEEKDB_MODE": "embedded"}, clear=True),
            patch("seekdb_runtime.embedded_available", return_value=False),
            patch("seekdb_runtime.pyseekdb.Client") as client_factory,
            self.assertRaisesRegex(RuntimeError, "pylibseekdb"),
        ):
            create_seekdb_client(path="/tmp/course-seekdb")

        client_factory.assert_not_called()

    def test_server_mode_uses_validated_environment(self):
        from seekdb_runtime import create_seekdb_client

        environment = {
            "SEEKDB_MODE": "server",
            "SEEKDB_HOST": "127.0.0.1",
            "SEEKDB_PORT": "2881",
            "SEEKDB_TENANT": "sys",
            "SEEKDB_DATABASE": "course_test",
            "SEEKDB_USER": "root",
            "SEEKDB_PASSWORD": "local-only",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("seekdb_runtime.pyseekdb.Client") as client_factory,
        ):
            create_seekdb_client(path="/tmp/ignored")

        client_factory.assert_called_once_with(
            host="127.0.0.1",
            port=2881,
            tenant="sys",
            database="course_test",
            user="root",
            password="local-only",
        )

    def test_invalid_server_port_fails_before_client_creation(self):
        from seekdb_runtime import create_seekdb_client

        with (
            patch.dict(
                os.environ,
                {
                    "SEEKDB_MODE": "server",
                    "SEEKDB_PORT": "65536",
                    "SEEKDB_DATABASE": "isolated_test",
                },
                clear=True,
            ),
            patch("seekdb_runtime.pyseekdb.Client") as client_factory,
            self.assertRaisesRegex(ValueError, "SEEKDB_PORT"),
        ):
            create_seekdb_client(path="/tmp/ignored")

        client_factory.assert_not_called()

    def test_server_mode_requires_explicit_database(self):
        from seekdb_runtime import create_seekdb_client

        with (
            patch.dict(
                os.environ,
                {"SEEKDB_MODE": "server", "SEEKDB_HOST": "127.0.0.1"},
                clear=True,
            ),
            patch("seekdb_runtime.pyseekdb.Client") as client_factory,
            self.assertRaisesRegex(ValueError, "SEEKDB_DATABASE"),
        ):
            create_seekdb_client(path="/tmp/ignored")

        client_factory.assert_not_called()

    def test_remote_destructive_access_requires_explicit_opt_in(self):
        from seekdb_runtime import require_destructive_seekdb_access

        with (
            patch.dict(
                os.environ,
                {"SEEKDB_MODE": "server", "SEEKDB_DATABASE": "shared"},
                clear=True,
            ),
            self.assertRaisesRegex(PermissionError, "SEEKDB_ALLOW_DESTRUCTIVE"),
        ):
            require_destructive_seekdb_access("写入知识库")

        with patch.dict(
            os.environ,
            {
                "SEEKDB_MODE": "server",
                "SEEKDB_DATABASE": "isolated_test",
                "SEEKDB_ALLOW_DESTRUCTIVE": "1",
            },
            clear=True,
        ):
            require_destructive_seekdb_access("写入知识库")


if __name__ == "__main__":
    unittest.main()
