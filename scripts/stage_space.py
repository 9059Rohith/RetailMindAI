"""Assemble only public, runtime files for the Hugging Face Docker Space."""
from pathlib import Path
from shutil import copy2, copytree, ignore_patterns


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    stage = root / ".hf-space"
    stage.mkdir(exist_ok=True)
    for folder in ("app", "retailmind", "data"):
        copytree(root / folder, stage / folder, dirs_exist_ok=True, ignore=ignore_patterns("__pycache__", "*.pyc"))
    (stage / ".streamlit").mkdir(exist_ok=True)
    copy2(root / ".streamlit" / "config.toml", stage / ".streamlit" / "config.toml")
    copy2(root / "Dockerfile", stage / "Dockerfile")
    copy2(root / "requirements.txt", stage / "requirements.txt")
    copy2(root / "deploy" / "huggingface" / "README.md", stage / "README.md")
    print(f"Staged public runtime at {stage}")


if __name__ == "__main__":
    main()
