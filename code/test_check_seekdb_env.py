import contextlib
import io
import os
import socket
import unittest
from unittest.mock import patch

import pymysql

import check_seekdb_env


class SeekdbEnvironmentCheckTests(unittest.TestCase):
    def run_check(self, environment):
        output = io.StringIO()
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(check_seekdb_env, "embedded_available", return_value=False),
            contextlib.redirect_stdout(output),
        ):
            result = check_seekdb_env.main()
        return result, output.getvalue()

    def test_open_port_without_database_configuration_fails(self):
        # 重现旧自检：端口可达，但实际客户端缺少必填数据库配置。
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            result, output = self.run_check({
                "SEEKDB_MODE": "server",
                "SEEKDB_PORT": str(listener.getsockname()[1]),
            })
        self.assertEqual(result, 1)
        self.assertIn("SEEKDB_DATABASE", output)

    def test_invalid_mode_and_port_return_actionable_failure(self):
        for environment, expected in (
            ({"SEEKDB_MODE": "typo"}, "SEEKDB_MODE"),
            ({"SEEKDB_MODE": "server", "SEEKDB_PORT": "abc"}, "SEEKDB_PORT"),
            ({"SEEKDB_MODE": "server", "SEEKDB_PORT": "65536"}, "SEEKDB_PORT"),
        ):
            with self.subTest(environment=environment):
                result, output = self.run_check({
                    "SEEKDB_DATABASE": "isolated_demo",
                    **environment,
                })
                self.assertEqual(result, 1)
                self.assertIn(expected, output)

    def test_database_and_authentication_errors_fail_even_with_open_port(self):
        for error in (
            pymysql.err.OperationalError(1049, "Unknown database 'isolated_demo'"),
            pymysql.err.OperationalError(1045, "Access denied"),
        ):
            with self.subTest(error=error), socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen()
                with patch("pymysql.connect", side_effect=error):
                    result, output = self.run_check({
                        "SEEKDB_MODE": "server",
                        "SEEKDB_PORT": str(listener.getsockname()[1]),
                        "SEEKDB_DATABASE": "isolated_demo",
                    })
                self.assertEqual(result, 1)
                self.assertIn(str(error), output)

    def test_success_requires_read_only_query_and_releases_connection(self):
        statements = []

        class Connection:
            closed = False

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.closed = True

            def cursor(self):
                return contextlib.nullcontext(self)

            def execute(self, statement):
                statements.append(statement)

            def fetchone(self):
                return (1,)

        connection = Connection()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with patch("pymysql.connect", return_value=connection) as connect:
                result, output = self.run_check({
                    "SEEKDB_MODE": "server",
                    "SEEKDB_HOST": "127.0.0.1",
                    "SEEKDB_PORT": str(port),
                    "SEEKDB_DATABASE": "isolated_demo",
                    "SEEKDB_TENANT": "test_tenant",
                    "SEEKDB_USER": "reader",
                    "SEEKDB_PASSWORD": "test-password",
                })
        self.assertEqual(result, 0, output)
        self.assertEqual(statements, ["SELECT 1"])
        self.assertTrue(connection.closed)
        self.assertEqual(connect.call_args.kwargs["user"], "reader@test_tenant")
        self.assertEqual(connect.call_args.kwargs["database"], "isolated_demo")
        self.assertNotIn("test-password", output)

    def test_missing_embedded_extension_returns_server_instructions(self):
        result, output = self.run_check({"SEEKDB_MODE": "embedded"})
        self.assertEqual(result, 1)
        self.assertIn("docker compose", output)


if __name__ == "__main__":
    unittest.main()
