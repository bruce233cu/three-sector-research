"""External-only launcher; --preflight/--verify are offline."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    from mainline.poc.phase1f_c import main
    raise SystemExit(main(ROOT, Path(__file__).resolve().parent))
