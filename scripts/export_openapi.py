import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def main() -> None:
    spec = app.openapi()
    destination = ROOT / "openapi.yaml"
    destination.write_text(
        yaml.safe_dump(spec, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"OpenAPI gravado em {destination}")


if __name__ == "__main__":
    main()
