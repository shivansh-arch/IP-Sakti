"""
deploy/push_space.py — publish IP-SAKTI to a Hugging Face Docker Space.

Prerequisite (once):  .venv\\Scripts\\hf auth login      (token with write access)

    python deploy/push_space.py                    # create/update <you>/ip-sakti
    python deploy/push_space.py --set-secrets      # also copy QDRANT_URL / QDRANT_API_KEY
                                                   # from your local .env into Space secrets
    python deploy/push_space.py --name my-space --private

The Space builds the repo's Dockerfile (API + frontend in one container).
Only the files the image needs are uploaded — no data, notes or .env.
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
FILES = ["Dockerfile", "requirements-api.txt", "frontend/index.html"]
DIRS = ["api", "lexicon"]


def stage(dst: Path):
    for f in FILES:
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dst / f)
    for d in DIRS:
        shutil.copytree(ROOT / d, dst / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "deploy/hf-space/README.md", dst / "README.md")  # Space card (sdk: docker)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="ip-sakti")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--set-secrets", action="store_true")
    args = ap.parse_args()

    api = HfApi()
    try:
        user = api.whoami()["name"]
    except Exception:
        sys.exit("Not logged in to Hugging Face. Run:  .venv\\Scripts\\hf auth login")
    repo_id = f"{user}/{args.name}"

    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)
    print(f"Space ready: {repo_id}")

    if args.set_secrets:
        env = dotenv_values(ROOT / ".env")
        for key in ("QDRANT_URL", "QDRANT_API_KEY"):
            if not env.get(key):
                sys.exit(f"{key} missing from .env — cannot set Space secret")
            api.add_space_secret(repo_id, key, env[key])
        print("Secrets set: QDRANT_URL, QDRANT_API_KEY")

    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=tmp,
                          commit_message="Deploy IP-SAKTI from GitHub main")
    print(f"Uploaded. Build logs: https://huggingface.co/spaces/{repo_id}?logs=build")
    print(f"App URL (once built): https://{repo_id.replace('/', '-').replace('_', '-').lower()}.hf.space")


if __name__ == "__main__":
    main()
