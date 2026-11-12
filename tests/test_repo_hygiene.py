"""Keeps the contribution docs, labels, templates and CI in step with each other."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def labels():
    return json.loads((ROOT / ".github" / "labels.json").read_text(encoding="utf-8"))


def backticked(text):
    return set(re.findall(r"`([^`]+)`", text))


def labels_section_of_integration_md():
    text = (ROOT / "integration.md").read_text(encoding="utf-8")
    start = text.index("### Labels")
    end = text.index("\n## ", start)
    return text[start:end]


def test_label_file_is_well_formed():
    items = labels()
    names = [l["name"] for l in items]
    assert names and len(names) == len(set(names))
    for l in items:
        assert re.fullmatch(r"[0-9a-fA-F]{6}", l["color"]), l
        assert 0 < len(l["description"]) <= 100, l


def test_every_label_in_integration_md_exists_in_the_label_file_and_vice_versa():
    documented = backticked(labels_section_of_integration_md())
    defined = {l["name"] for l in labels()}
    assert documented == defined, (documented ^ defined)


def test_issue_templates_only_use_defined_labels():
    defined = {l["name"] for l in labels()}
    templates = list((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
    assert {t.name for t in templates} >= {"bug_report.yml", "feature_request.yml", "config.yml"}
    for t in templates:
        for label in re.findall(r'labels:\s*\[([^\]]*)\]', t.read_text(encoding="utf-8")):
            for name in re.findall(r'"([^"]+)"', label):
                assert name in defined, (t.name, name)


def test_issue_config_disables_blank_issues_and_points_security_reports_to_a_private_channel():
    config = (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    assert "blank_issues_enabled: false" in config
    assert "security/advisories" in config


def test_ci_workflow_runs_unit_tests_on_pull_requests_to_integration_and_main():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for needle in ("pull_request", "integration", "main", "ubuntu-latest", '"3.12"', "python -m pytest", "contents: read"):
        assert needle in ci, needle
    assert "secrets." not in ci  # tests must run offline with no keys


def test_pull_request_template_points_at_the_integration_branch():
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "integration" in template


def test_label_sync_script_builds_one_forced_create_command_per_label():
    from sync_labels import build_commands

    commands = build_commands(labels())
    assert len(commands) == len(labels())
    for cmd, label in zip(commands, labels()):
        assert cmd[:3] == ["gh", "label", "create"] and cmd[3] == label["name"] and "--force" in cmd
        assert cmd[cmd.index("--color") + 1] == label["color"]
