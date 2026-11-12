"""Guard: the web code must never hard-code a currency symbol. All money goes through format.js `money()`."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "dcf" / "web"
FORBIDDEN = [
    (re.compile(r"\$\d"), "dollar sign followed by a digit"),
    (re.compile(r"\$\$\{"), "template literal starting with a dollar sign"),
    (re.compile(r"""['"`]\$['"`]"""), "quoted dollar sign"),
    (re.compile(r"""\+\s*['"]\$"""), "string concatenation with a dollar sign"),
    (re.compile(r"[€£¥₹₩₽]"), "literal currency symbol"),
    (re.compile(r"""['"`](USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY|INR|TWD)['"`]"""), "quoted currency code"),
]


def test_no_hardcoded_dollar_signs_in_web_code():
    files = [p for p in WEB.rglob("*") if p.suffix in {".js", ".html"}]
    assert files, "web code not found"
    problems = []
    for path in files:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, why in FORBIDDEN:
                if pattern.search(line):
                    problems.append(f"{path.name}:{n}: {why}: {line.strip()}")
    assert not problems, "\n".join(problems)


def test_guard_actually_detects_violations():
    assert FORBIDDEN[0][0].search("price: $5")
    assert FORBIDDEN[1][0].search("`$${x}`")
    assert FORBIDDEN[3][0].search("'a' + '$'")
    assert FORBIDDEN[4][0].search("const label = '€' + x")
    assert FORBIDDEN[5][0].search("money(x, 'USD')") and FORBIDDEN[5][0].search('money(x, "EUR")')
