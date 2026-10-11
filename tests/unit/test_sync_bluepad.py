"""bluepad_ur.py embeds library/uremote.py; fail loudly when the copy is stale."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import sync_bluepad  # noqa: E402


def test_bluepad_embeds_current_uremote():
    stale = sync_bluepad.build() != (sync_bluepad.LIB / "bluepad_ur.py").read_text()
    assert not stale, "bluepad_ur.py is out of date with uremote.py. Run: python tools/sync_bluepad.py"
