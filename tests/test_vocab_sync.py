import re
from pathlib import Path

from reels.spec import Timeline
from reels.vocab import ICONS

REMOTION = Path(__file__).resolve().parents[1] / "remotion" / "src"


def test_icons_match_remotion():
    ts = (REMOTION / "components" / "icons.ts").read_text()
    body = ts.split("export const ICONS")[1]
    names = set(re.findall(r"^  (\w+): \{", body, flags=re.M))
    assert names == set(ICONS)


def test_timeline_fields_match_zod_schema():
    ts = (REMOTION / "schema.ts").read_text()
    block = ts.split("export const timelineSchema = z.object({")[1].split("\n});")[0]
    zod_keys = set(re.findall(r"^  (\w+):", block, flags=re.M))
    assert zod_keys == set(Timeline.model_fields)
