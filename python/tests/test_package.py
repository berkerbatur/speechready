from pathlib import Path

import speechready

SPEC = Path(__file__).resolve().parents[2] / "spec"


def test_version_is_set():
    assert speechready.__version__


def test_shared_spec_is_reachable():
    fixtures = list((SPEC / "fixtures").rglob("*.yaml"))
    assert fixtures, "the shared fixture corpus in spec/fixtures is missing"
