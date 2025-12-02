"""
pull_images.py

Utility to pull prebuilt FeatBench docker images from ghcr.io
and re-tag them with the local short name (e.g. featbench_<repo>:<id>).

Examples:
    python scripts/pull_images.py --dataset dataset/featbench_v1_0.json

"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from pathlib import Path
from typing import Set

import docker
from docker.errors import ImageNotFound, APIError
from tqdm import tqdm

DEFAULT_REMOTE_PREFIX = "ghcr.io/kndy666"
DEFAULT_DATASET = "dataset/featbench_v1_0.json"

def parse_dataset_for_images(dataset_path: Path) -> Set[str]:
    images = set()
    if not dataset_path.exists():
        print(f"Dataset not found at {dataset_path}")
        return images

    with dataset_path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"Failed to parse dataset: {e}")
            return images

    for instance in data:
        docker_image = instance.get("docker_image")
        if docker_image:
            images.add(docker_image)
            continue

        repo = instance.get("repo")
        number = instance.get("number")
        if repo and number:
            try:
                image_short = f"featbench_{repo.replace('/', '_').lower()}:{number}"
                images.add(image_short)
            except Exception:
                continue

    return images

def build_remote_name(short_image: str) -> str:
    if "/" in short_image and not short_image.startswith("featbench_"):
        return short_image
    return f"{DEFAULT_REMOTE_PREFIX}/{short_image}"

def tag_local(client: docker.DockerClient, remote_image: str, local_image: str) -> bool:
    print(f"  -> Tagging {remote_image} -> {local_image}")
    try:
        image = client.images.get(remote_image)
        if ":" in local_image:
            repo, tag = local_image.split(":", 1)
        else:
            repo, tag = local_image, None
        ok = image.tag(repository=repo, tag=tag)
        return ok
    except ImageNotFound:
        print(f"Remote image not found locally after pull: {remote_image}")
        return False
    except APIError as e:
        print(f"Docker API error during tag: {e}")
        return False

def pull_image(client: docker.DockerClient, remote_image: str) -> bool:
    print(f"  -> Pulling {remote_image}")
    try:
        client.images.pull(remote_image)
        return True
    except APIError as e:
        print(f"Docker API error during pull: {e}")
        return False

def docker_is_available(client: docker.DockerClient) -> bool:
    try:
        client.ping()
        return True
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Pull FeatBench images from a registry and retag them locally")

    parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET), help=f"Path to dataset JSON file (default: {DEFAULT_DATASET})")
    parser.add_argument("--dry-run", action="store_true", help="Show the operations that would be performed without executing them")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of parallel pulls")
    args = parser.parse_args()

    docker_client = None
    if not args.dry_run:
        docker_client = docker.from_env()

    if not args.dry_run and not docker_is_available(docker_client):
        print("Docker doesn't seem to be available or you do not have permission to access the daemon.")
        sys.exit(2)

    images: Set[str] = set()
    images = parse_dataset_for_images(args.dataset)

    if not images:
        print("No images found to pull")
        sys.exit(0)

    print(f"Found {len(images)} unique image(s) to pull")

    def _process_one(short_image: str) -> tuple[str, bool, str]:
        if ":" not in short_image:
            return short_image, False, "invalid image (no tag found)"

        remote = build_remote_name(short_image)
        if args.dry_run:
            return short_image, True, f"dry-run: would pull {remote} and retag to {short_image}"

        local_exists = True
        try:
            docker_client.images.get(short_image)
        except ImageNotFound:
            local_exists = False

        if not local_exists:
            success = pull_image(docker_client, remote)
            if not success:
                return short_image, False, f"failed to pull {remote}"
        else:
            return short_image, True, "local image already present"

        ok = tag_local(docker_client, remote, short_image)
        if not ok:
            return short_image, False, f"failed to tag {remote} as {short_image}"

        message = f"pulled {remote}" if not local_exists else "local existed"
        message += f", retagged to {short_image}"
        return short_image, True, message

    failed = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_image = {executor.submit(_process_one, s): s for s in sorted(images)}
        for future in tqdm(as_completed(future_to_image), total=len(future_to_image), desc="Pulling images"):
            short_image, success, message = future.result()
            if not success:
                print(f"{short_image}: {message}")
                failed.append((short_image, message))
            else:
                print(f"{short_image}: {message}")

    if failed:
        print("Some images failed to pull:")
        for name, message in failed:
            print(f" - {name}: {message}")
        sys.exit(1)
    else:
        print("Done.")


if __name__ == "__main__":
    main()