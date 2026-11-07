"""Regresiones del contrato v2 del boletin y de los limites prompt/codigo.

Cada caso viene de un fallo real de 2026-10 (ver REPAIR-NOTES.md).
Los tests de corpus usan TECNOBOLETIN_VAULT o ~/obsidian-vault y se saltan
si no hay boletines.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load_script("validate_bulletin_md")
extract = load_script("extract_items")
quality = load_script("validate_quality")
synth = load_script("synthesize_article")
editorial = load_script("generate_editorial")

VAULT = Path(os.environ.get("TECNOBOLETIN_VAULT", Path.home() / "obsidian-vault/Research/Boletines"))

CARD = """#### {n}. [owner/repo{n}](https://github.com/owner/repo{n}) — tagline
- **URL**: https://github.com/owner/repo{n}
- **Qué es**: una herramienta.
- **Por qué importa**: porque si.
- **Madurez/señales**: 1.234 estrellas · 10 forks · Rust · último push 2026-11-01
- **Relación con el grafo**: `repo:owner/repo{n} --uses--> tool:x`
- **Acción sugerida**: **leer** — motivo.
"""


def bulletin(cards: str | None = None, extra: str = "") -> str:
    cards = cards if cards is not None else "\n".join(CARD.format(n=n) for n in (1, 2, 3))
    return f"""## Boletín IA/dev — 2026-11-03

### Resumen ejecutivo
- Tesis.

### Hallazgos principales

{cards}
### Radar secundario
- **[o/r9](https://github.com/o/r9)** (10 estrellas, último push 2026-11-01, Go) — algo. Acción: **vigilar**.

### Grafo actualizado
- **Nodos nuevos relevantes**: `tool:x`

### Ideas de contenido para Código Sin Siesta
1. **"Idea"** — ángulo.

### Candidatos para exploración profunda
1. **o/r1** — motivo.
{extra}"""


class ContractTests(unittest.TestCase):
    def check(self, text):
        return contract.validate_text(text)

    def test_valid_bulletin_has_no_errors_or_warnings(self):
        errors, warnings, stats = self.check(bulletin())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(stats["hallazgos"], 3)

    def test_missing_label_names_card_and_field(self):
        text = bulletin().replace("- **Acción sugerida**: **leer** — motivo.\n", "", 1)
        errors, _, _ = self.check(text)
        self.assertTrue(any("hallazgo 1" in e and "accion_sugerida" in e for e in errors), errors)

    def test_legacy_bold_bullet_cards_are_rejected(self):
        # 2026-10-16..19: tarjetas como viñeta en negrita, sin `#### N.`
        legacy = "**`o/r` — titulo**\n- URL: https://github.com/o/r\n- Qué es: x\n"
        errors, _, _ = self.check(bulletin(cards=legacy))
        self.assertTrue(any("sin tarjetas" in e for e in errors), errors)

    def test_bare_advisory_url_is_warning_and_extractor_normalizes_it(self):
        # 2026-10-22: "- **URL**: GHSA-... (CVE-...)" sin enlace
        card = CARD.format(n=1).replace("(https://github.com/owner/repo1)", "").replace(
            "[owner/repo1]", "CVE-2026-109618").replace(
            "- **URL**: https://github.com/owner/repo1", "- **URL**: GHSA-w8hw-w9fx-j79w (CVE-2026-109618)")
        text = bulletin(cards=card + "\n" + CARD.format(n=2) + "\n" + CARD.format(n=3))
        errors, warnings, _ = self.check(text)
        self.assertEqual(errors, [])
        self.assertTrue(any("GHSA/CVE" in w for w in warnings), warnings)
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "2026-11-03-trending.md"
            md.write_text(text, encoding="utf-8")
            data = extract.parse(md)
        first = data["items"][0]
        self.assertEqual(first["url"], "https://github.com/advisories/GHSA-w8hw-w9fx-j79w")
        self.assertIn("https://nvd.nist.gov/vuln/detail/CVE-2026-109618", first["urls_adicionales"])
        self.assertEqual(quality.validate(data), [])

    def test_card_without_any_url_is_error(self):
        card = CARD.format(n=1).replace("(https://github.com/owner/repo1)", "").replace(
            "- **URL**: https://github.com/owner/repo1", "- **URL**: pendiente")
        errors, _, _ = self.check(bulletin(cards=card))
        self.assertTrue(any("sin URL https" in e for e in errors), errors)

    def test_relation_outside_vocabulary_is_warning(self):
        text = bulletin().replace("--uses-->", "--reveals-->", 1)
        _, warnings, _ = self.check(text)
        self.assertTrue(any("reveals" in w for w in warnings), warnings)

    def test_new_vocabulary_terms_are_accepted(self):
        text = bulletin().replace("--uses-->", "--extends-->", 1)
        _, warnings, _ = self.check(text)
        self.assertFalse(any("vocabulario" in w for w in warnings), warnings)

    def test_cjk_is_error_and_glued_words_are_warning(self):
        errors, warnings, _ = self.check(bulletin(extra="Nota: 中文 y tresOCs.\n"))
        self.assertTrue(any("CJK" in e for e in errors), errors)
        self.assertTrue(any("tresOCs" in w for w in warnings), warnings)

    def test_action_must_start_with_known_verb(self):
        text = bulletin().replace("**leer** — motivo.", "revisar más tarde.", 1)
        _, warnings, _ = self.check(text)
        self.assertTrue(any("accion" in w for w in warnings), warnings)


class PromptCodeConsistencyTests(unittest.TestCase):
    def test_critique_limit_is_told_to_model_and_enforced(self):
        # 2026-10-30: originales de 219-283 chars, reescrituras de ~2.8x
        # rechazadas sin que el prompt diera ningun tope.
        self.assertIn("max_chars", synth.CRITIQUE_INSTRUCTIONS)
        payload = synth.build_payload([{
            "idx": 0, "seccion": "hallazgo_principal", "relacion_grafo": [],
            "contenido": {"que_es": "x", "por_que_importa": "a" * 283, "madurez_senales": "m"},
        }])
        limit = payload[0]["max_chars"]
        self.assertEqual(limit, synth.max_chars("a" * 283))
        ok, too_long = synth._accept([{"idx": 0, "por_que_importa": "b" * (limit + 1)}], {0: limit})
        self.assertEqual(ok, {})
        self.assertIn(0, too_long)
        ok, too_long = synth._accept([{"idx": 0, "por_que_importa": "b" * limit}], {0: limit})
        self.assertIn(0, ok)

    def test_editorial_prompt_no_longer_allows_empty_sections(self):
        # 2026-10-20/21: el prompt permitia convergencia_stack_css vacia y
        # el gate del cron la exige -> exit 2.
        self.assertNotIn("o vacio ''", editorial.EDITORIAL_INSTRUCTIONS)
        self.assertIn("NINGUN parrafo puede ir vacio", editorial.EDITORIAL_INSTRUCTIONS)

    def test_editorial_absolute_limit_matches_validator(self):
        self.assertIn(f"limite absoluto: {editorial.SECTION_MAX_OK}", editorial.EDITORIAL_INSTRUCTIONS)
        self.assertEqual(editorial.POS_MAX_OK, editorial.SECTION_MAX_OK)


@unittest.skipUnless(any(VAULT.glob("2026-1*-trending.md")), "sin boletines reales")
class CorpusTests(unittest.TestCase):
    def test_contract_v2_era_bulletins_pass(self):
        for md in sorted(VAULT.glob("*-trending.md")):
            if md.name < "2026-10-20":
                continue
            with self.subTest(day=md.name[:10]):
                errors, _, _ = contract.validate_text(md.read_text(encoding="utf-8"))
                self.assertEqual(errors, [])

    def test_extraction_gate_passes_on_2026_10_22_after_advisory_normalization(self):
        md = VAULT / "2026-10-22-trending.md"
        if not md.exists():
            self.skipTest("falta 2026-10-22")
        self.assertEqual(quality.validate(extract.parse(md)), [])


if __name__ == "__main__":
    unittest.main()
