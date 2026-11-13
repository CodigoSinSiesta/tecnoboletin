"""Regresiones del cliente LLM del enricher.

`hermes_available()` no debe degradar el dia entero cuando el sondeo de la CLI
se queda colgado (el chequeo de actualizaciones de `hermes --version` hace
red cada 6h y puede exceder cualquier timeout corto).
"""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HermesAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = load("hermes_client")

    def test_binary_missing_is_reported(self):
        with mock.patch.object(self.client, "find_hermes", return_value=None):
            ok, reason = self.client.hermes_available()
        self.assertFalse(ok)
        self.assertIn("no encontrado", reason)

    def test_probe_timeout_does_not_disable_backend(self):
        with mock.patch.object(self.client, "find_hermes", return_value=Path("/usr/bin/hermes")), \
             mock.patch.object(self.client.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(cmd="hermes --version", timeout=60)):
            ok, reason = self.client.hermes_available()
        self.assertTrue(ok, "un timeout del sondeo no debe forzar --llm none")
        self.assertIn("no respondio", reason)

    def test_nonzero_exit_is_reported(self):
        completed = subprocess.CompletedProcess(args=["hermes", "--version"], returncode=1, stdout="", stderr="boom")
        with mock.patch.object(self.client, "find_hermes", return_value=Path("/usr/bin/hermes")), \
             mock.patch.object(self.client.subprocess, "run", return_value=completed):
            ok, reason = self.client.hermes_available()
        self.assertFalse(ok)
        self.assertIn("exit 1", reason)


if __name__ == "__main__":
    unittest.main()
