"""Stage the existing Flask static assets for Vercel's CDN."""

from pathlib import Path
from shutil import copytree


def main():
    root = Path(__file__).resolve().parents[1]
    copytree(root / "app" / "static", root / "public" / "static", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
