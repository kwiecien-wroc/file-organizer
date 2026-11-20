import argparse
import hashlib
import os
import shutil
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Iterable


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _raise_walk_error(error: OSError) -> None:
    raise error


def _iter_files(root: Path, excluded_roots: Iterable[Path] = ()) -> list[Path]:
    excluded = tuple(path.resolve() for path in excluded_roots)
    files: list[Path] = []

    for current, directories, filenames in os.walk(root, onerror=_raise_walk_error):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if not any(
                _is_within((current_path / name).resolve(), excluded_root)
                for excluded_root in excluded
            )
        ]
        files.extend(
            current_path / filename
            for filename in filenames
            if not (current_path / filename).is_symlink()
        )

    return sorted(files, key=lambda path: str(path).casefold())


def _category_path(output_dir: Path, answer: str) -> Path | None:
    relative = Path(answer.strip())
    windows_relative = PureWindowsPath(answer.strip())
    if (
        not answer.strip()
        or relative.is_absolute()
        or windows_relative.is_absolute()
        or ".." in relative.parts
        or ".." in windows_relative.parts
    ):
        return None

    target = (output_dir / relative).resolve()
    if not _is_within(target, output_dir.resolve()):
        return None
    return target


def _unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination

    while True:
        candidate = destination.with_name(
            f"{destination.stem}_{uuid.uuid4()}{destination.suffix}"
        )
        if not candidate.exists():
            return candidate


def organize(input_dir: Path, output_dir: Path) -> int:
    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not input_dir.is_dir():
        print(f"Input directory does not exist: {input_dir}", file=sys.stderr)
        return 2

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"Could not create output directory: {error}", file=sys.stderr)
        return 2

    excluded = [output_dir] if output_dir != input_dir and _is_within(output_dir, input_dir) else []
    try:
        files = _iter_files(input_dir, excluded)
    except OSError as error:
        print(f"Could not scan directory: {error}", file=sys.stderr)
        return 1

    categories: dict[str, Path] = {}
    moved = 0
    failed = 0

    for source in files:
        extension = source.suffix.lower() or "[no extension]"
        if extension not in categories:
            while True:
                answer = input(
                    f"Extension {extension}. Enter destination folder: "
                )
                category = _category_path(output_dir, answer)
                if category is not None:
                    categories[extension] = category
                    break
                print("Enter a relative folder name without a '..' segment.")

        category = categories[extension]
        try:
            category.mkdir(parents=True, exist_ok=True)
            destination = category / source.name
            if source.resolve() == destination.resolve():
                continue
            destination = _unique_destination(destination)
            shutil.move(str(source), str(destination))
            moved += 1
            print(f"Moved: {source} -> {destination}")
        except OSError as error:
            print(f"Could not move {source}: {error}", file=sys.stderr)
            failed += 1

    print(f"Finished. Files moved: {moved}.")
    if failed:
        print(f"Files that could not be processed: {failed}.", file=sys.stderr)
        return 1
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_duplicates(directory: Path, log_file: Path | None = None) -> int:
    directory = directory.expanduser().resolve()
    if not directory.is_dir():
        print(f"Directory to check does not exist: {directory}", file=sys.stderr)
        return 2

    if log_file is None:
        log_file = directory.parent / f"{directory.name}_duplicates_removed.log"
    log_file = log_file.expanduser().resolve()

    try:
        files = _iter_files(directory)
    except OSError as error:
        print(f"Could not scan directory: {error}", file=sys.stderr)
        return 1

    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in files:
        if path.resolve() == log_file:
            continue
        try:
            by_size[path.stat().st_size].append(path)
        except OSError as error:
            print(f"Could not read {path}: {error}", file=sys.stderr)

    by_hash: dict[tuple[int, str], list[Path]] = defaultdict(list)
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                by_hash[(size, _sha256(path))].append(path)
            except OSError as error:
                print(f"Could not calculate checksum for {path}: {error}", file=sys.stderr)

    duplicate_groups = [
        sorted(paths, key=lambda path: str(path).casefold())
        for paths in by_hash.values()
        if len(paths) > 1
    ]
    duplicate_groups.sort(key=lambda group: str(group[0]).casefold())
    if not duplicate_groups:
        print("No duplicates found.")
        return 0

    print("Duplicates found (the first file in each group will be kept):")
    for group in duplicate_groups:
        print(f"\nKeeping: {group[0]}")
        for duplicate in group[1:]:
            print(f"  Duplicate: {duplicate}")

    confirmation = input("Remove the listed duplicates? [y/N]: ").strip().casefold()
    if confirmation not in {"y", "yes"}:
        print("Cancelled. No files were removed.")
        return 0

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now().astimezone().isoformat(timespec='seconds')}]\n")
            log.flush()
            os.fsync(log.fileno())
            removed = 0
            for group in duplicate_groups:
                for duplicate in group[1:]:
                    try:
                        duplicate.unlink()
                    except OSError as error:
                        print(f"Could not remove {duplicate}: {error}", file=sys.stderr)
                        continue

                    removed += 1
                    try:
                        log.write(f"REMOVED: {duplicate}\nKEPT: {group[0]}\n")
                        log.flush()
                        os.fsync(log.fileno())
                    except OSError as error:
                        print(
                            f"Removed {duplicate}, but could not write the log entry: {error}",
                            file=sys.stderr,
                        )
                        return 1
                    print(f"Removed: {duplicate}")
        print(f"Removed-files log: {log_file}")
    except OSError as error:
        print(f"Could not write log {log_file}: {error}", file=sys.stderr)
        return 1

    print(f"Duplicates removed: {removed}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Organize files by extension and remove duplicate files."
    )
    parser.add_argument("input_dir", nargs="?", type=Path, help="source directory")
    parser.add_argument("output_dir", nargs="?", type=Path, help="destination directory")
    parser.add_argument(
        "--duplicates",
        type=Path,
        metavar="DIRECTORY",
        help="find duplicates in a directory instead of organizing files",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        metavar="FILE",
        help="path for the removed-files log (used with --duplicates)",
    )
    args = parser.parse_args()

    if args.duplicates is not None:
        if args.input_dir is not None or args.output_dir is not None:
            parser.error("--duplicates does not accept source and destination directories")
        return remove_duplicates(args.duplicates, args.log_file)

    if args.log_file is not None:
        parser.error("--log-file can only be used with --duplicates")
    if args.input_dir is None or args.output_dir is None:
        parser.error("provide source and destination directories or use --duplicates DIRECTORY")
    return organize(args.input_dir, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
