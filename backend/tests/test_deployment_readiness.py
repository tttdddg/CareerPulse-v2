"""Deployment-boundary tests that do not require external services."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_postgres_config
from app.main import create_app


PROJECT_DIR = Path(__file__).resolve().parents[2]


class DeploymentReadinessTests(unittest.TestCase):
    def test_healthz_returns_only_minimal_process_status(self) -> None:
        client = TestClient(create_app(mcp_enabled=False))

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertNotIn("/healthz", client.get("/openapi.json").json()["paths"])

    def test_legacy_postgres_config_reads_environment(self) -> None:
        values = {
            "POSTGRES_HOST": "db.internal",
            "POSTGRES_PORT": "5544",
            "POSTGRES_DATABASE": "careerpulse",
            "POSTGRES_USER": "careerpulse_app",
            "POSTGRES_PASSWORD": "test-only-password",
            "POSTGRES_CONNECT_TIMEOUT": "9",
        }
        with patch.dict(os.environ, values, clear=False):
            config = get_postgres_config()

        self.assertEqual(
            config,
            {
                "host": "db.internal",
                "port": 5544,
                "database": "careerpulse",
                "user": "careerpulse_app",
                "password": "test-only-password",
                "connect_timeout": 9,
            },
        )

    def test_legacy_postgres_password_default_is_empty(self) -> None:
        names = {
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DATABASE",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_CONNECT_TIMEOUT",
        }
        clean_environment = {
            key: value for key, value in os.environ.items() if key not in names
        }
        with patch.dict(os.environ, clean_environment, clear=True):
            config = get_postgres_config()

        self.assertEqual(config["host"], "localhost")
        self.assertEqual(config["port"], 5433)
        self.assertEqual(config["database"], "careerpulse_micro")
        self.assertEqual(config["user"], "postgres")
        self.assertEqual(config["password"], "")
        self.assertEqual(config["connect_timeout"], 5)

    def test_legacy_postgres_rejects_invalid_port(self) -> None:
        with patch.dict(os.environ, {"POSTGRES_PORT": "70000"}, clear=False):
            with self.assertRaisesRegex(ValueError, "POSTGRES_PORT"):
                get_postgres_config()

    def test_postgres_db_alias_fails_instead_of_connecting_to_default(self) -> None:
        names = {"POSTGRES_DATABASE", "POSTGRES_DB"}
        clean_environment = {
            key: value for key, value in os.environ.items() if key not in names
        }
        clean_environment["POSTGRES_DB"] = "wrong_database"
        with patch.dict(os.environ, clean_environment, clear=True):
            with self.assertRaisesRegex(ValueError, "POSTGRES_DATABASE"):
                get_postgres_config()

    def test_production_requirements_are_curated_and_include_pdf_export(self) -> None:
        requirements = (PROJECT_DIR / "backend" / "requirements-prod.txt").read_text(
            encoding="utf-8"
        )

        self.assertIn("Python 3.11", requirements)
        self.assertIn("reportlab==", requirements)
        self.assertNotIn("pywin32", requirements.lower())

    def test_nginx_preserves_mcp_and_tbox_transport_requirements(self) -> None:
        nginx = (PROJECT_DIR / "deploy" / "nginx" / "careerpulse.conf").read_text(
            encoding="utf-8"
        )

        self.assertIn("client_max_body_size 10m;", nginx)
        self.assertIn("location = /mcp", nginx)
        self.assertIn("location = /api/tbox/chat", nginx)
        self.assertGreaterEqual(nginx.count("proxy_set_header Host $host;"), 2)
        self.assertGreaterEqual(
            nginx.count("proxy_set_header Authorization $http_authorization;"), 2
        )
        self.assertGreaterEqual(nginx.count("proxy_buffering off;"), 2)
        self.assertIn("proxy_read_timeout 75s;", nginx)
        self.assertIn("proxy_read_timeout 150s;", nginx)

    def test_systemd_uses_loopback_single_worker_and_protected_environment(self) -> None:
        service = (
            PROJECT_DIR / "deploy" / "systemd" / "careerpulse.service"
        ).read_text(encoding="utf-8")

        self.assertIn("EnvironmentFile=/etc/careerpulse/careerpulse.env", service)
        self.assertIn("--host 127.0.0.1", service)
        self.assertIn("--port 8000", service)
        self.assertIn("--workers 1", service)
        self.assertIn("User=careerpulse", service)

    def test_deployment_environment_keeps_secrets_empty(self) -> None:
        environment = (
            PROJECT_DIR / "deploy" / "env" / "careerpulse.env.example"
        ).read_text(encoding="utf-8")

        self.assertIn("MCP_ENABLED=true", environment)
        self.assertIn("POSTGRES_PORT=5433", environment)
        self.assertIn("POSTGRES_DATABASE=careerpulse_micro", environment)
        self.assertNotIn("POSTGRES_DB=", environment)
        self.assertIn(
            "A02_STATE_DB_PATH=/var/lib/careerpulse/career_state.sqlite3",
            environment,
        )
        for variable in (
            "A02_LLM_API_KEY",
            "A02_TBOX_API_TOKEN",
            "TBOX_CHAT_AUTHORIZATION",
            "TBOX_USER_ID_SECRET",
            "MCP_API_TOKEN",
            "POSTGRES_PASSWORD",
        ):
            self.assertIn(f"{variable}=\n", environment)

    def test_smoke_initialize_payload_matches_mcp_server(self) -> None:
        token = "test-only-deployment-token"
        application = create_app(
            mcp_enabled=True,
            mcp_auth_enabled=True,
            mcp_api_token=token,
            mcp_host="127.0.0.1",
            mcp_path="/mcp",
            mcp_allowed_hosts=["testserver"],
            mcp_allowed_origins=["http://testserver"],
        )
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {
                    "name": "careerpulse-deploy-smoke",
                    "version": "1.0.0",
                },
            },
        }

        with TestClient(application) as client:
            unauthorized = client.post(
                "/mcp",
                json=payload,
                headers={"Accept": "application/json, text/event-stream"},
            )
            response = client.post(
                "/mcp",
                json=payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Authorization": f"Bearer {token}",
                },
            )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertIn("result", response.json())


if __name__ == "__main__":
    unittest.main()
