import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


extract = load_script("extract_items")
quality = load_script("validate_quality")


class ExtractionRegressionTests(unittest.TestCase):
    def test_recent_bulletin_formats_extract_with_required_fields(self):
        vault = Path.home() / "obsidian-vault/Research/Boletines"
        for date, expected_main in (("2026-10-20", 6), ("2026-10-21", 6), ("2026-10-23", 5), ("2026-10-26", 6)):
            with self.subTest(date=date):
                data = extract.parse(vault / f"{date}-trending.md")
                self.assertEqual(sum(i["seccion"] == "hallazgo_principal" for i in data["items"]), expected_main)
                self.assertEqual(quality.validate(data), [])

    def test_2026_10_26_deeptutor_has_identity(self):
        data = extract.parse(Path.home() / "obsidian-vault/Research/Boletines/2026-10-26-trending.md")
        deep_tutor = [i for i in data["items"] if "deeptutor" in (i["titulo"] + i["url"]).lower()]
        self.assertEqual(len(deep_tutor), 1)
        self.assertEqual(deep_tutor[0]["url"], "https://github.com/HKUDS/DeepTutor")
        self.assertTrue(deep_tutor[0]["contenido"]["que_es"])

    def test_multiple_repo_finding_preserves_secondary_repo_url(self):
        data = extract.parse(Path.home() / "obsidian-vault/Research/Boletines/2026-10-21-trending.md")
        item = next(i for i in data["items"] if i["titulo"].startswith("DeepInfer + deepseek-recipe"))
        self.assertEqual(item["url"], "https://github.com/deepseek-ai/DeepInfer")
        self.assertIn("https://github.com/deepseek-ai/deepseek-recipe", item["urls_adicionales"])

    def test_missing_required_field_fails_extractor_cli(self):
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "bad.md"
            md.write_text("""### Hallazgos principales\n#### 1. [owner/repo](https://github.com/owner/repo)\n- **Qué es:** Descripción\n- **Por qué importa:** Relevancia\n- **Madurez/señales:** Señales\n- **Relación con el grafo:** `repo:owner/repo --uses--> tool:x`\n""", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPTS / "extract_items.py"), str(md)], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("accion_sugerida", proc.stderr)

    def test_current_extractors_are_byte_identical(self):
        active = Path.home() / ".hermes/skills/research/tecnoboletin-enricher/scripts/extract_items.py"
        self.assertEqual(active.read_bytes(), (SCRIPTS / "extract_items.py").read_bytes())


class QualityGateTests(unittest.TestCase):
    def test_gate_rejects_empty_required_fields(self):
        valid = {"items": [{"idx": 0, "titulo": "r", "url": "https://github.com/o/r", "seccion": "hallazgo_principal", "contenido": {"que_es": "x", "por_que_importa": "x", "madurez_senales": "x", "accion_sugerida": "x"}, "relacion_grafo": [{"src": "a", "rel": "uses", "dst": "b"}]}]}
        self.assertEqual(quality.validate(valid), [])
        valid["items"][0]["contenido"]["por_que_importa"] = "  "
        self.assertTrue(any("por_que_importa" in e for e in quality.validate(valid)))

    def test_persist_rejects_bad_input_before_writing(self):
        bad = {"items": [{"idx": 0, "titulo": "repo", "url": "https://github.com/o/r", "seccion": "hallazgo_principal", "contenido": {"que_es": "", "por_que_importa": "x", "madurez_senales": "x", "accion_sugerida": "x"}, "relacion_grafo": [{"src": "a", "rel": "uses", "dst": "b"}]}]}
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "input.json"
            out = Path(td) / "data"
            src.write_text(json.dumps(bad), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPTS / "persist.py"), "--date", "2099-01-01", "--enriched", str(src), "--repo-data-dir", str(out)], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("que_es", proc.stderr)
            self.assertFalse((out / "2099-01-01").exists())


if __name__ == "__main__":
    unittest.main()
