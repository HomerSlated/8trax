#!/usr/bin/env python3
"""Tarball-based backup for 8trax project files.

Commands:
  backup  [--dry-run]              Create a timestamped tarball in backups/
  restore [--dry-run] [--force]    Extract the most recent tarball
  clean   [--dry-run] [--keep N]   Delete old tarballs, keeping the N most recent (default: 3)

The manifest file (scripts/backup.manifest) lists files to include, one per line.
Lines beginning with '#' and blank lines are ignored.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from datetime import datetime
from pathlib import Path

_MANIFEST = Path(__file__).parent / "backup.manifest"
_BACKUP_DIR = Path(__file__).parent.parent / "backups"
_DEFAULT_KEEP = 3


def _load_manifest(manifest: Path) -> list[Path]:
    root = manifest.parent.parent
    files: list[Path] = []
    for raw in manifest.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        files.append(root / line)
    return files


def _list_tarballs() -> list[Path]:
    if not _BACKUP_DIR.exists():
        return []
    return sorted(_BACKUP_DIR.glob("backup_*.tar.gz"))


def cmd_backup(dry_run: bool) -> int:
    files = _load_manifest(_MANIFEST)
    present = [f for f in files if f.exists()]
    missing = [f for f in files if not f.exists()]

    for f in missing:
        print(f"Skipping missing: {f}")

    if not present:
        print("No files to back up.")
        return 0

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    tarball = _BACKUP_DIR / f"backup_{ts}.tar.gz"
    root = _MANIFEST.parent.parent

    if dry_run:
        print(f"[DRY] Would create {tarball} with {len(present)} files")
        for f in present:
            print(f"  {f.relative_to(root)}")
        return 0

    _BACKUP_DIR.mkdir(exist_ok=True)
    with tarfile.open(tarball, "w:gz") as tar:
        for f in present:
            tar.add(f, arcname=str(f.relative_to(root)))

    print(f"Backup created: {tarball.name} ({len(present)} files)")
    return 0


def cmd_restore(dry_run: bool, force: bool) -> int:
    tarballs = _list_tarballs()
    if not tarballs:
        print("No backups found.")
        return 1

    tarball = tarballs[-1]
    root = _MANIFEST.parent.parent

    print(f"Restoring from: {tarball.name}")

    with tarfile.open(tarball, "r:gz") as tar:
        members = tar.getmembers()

    if dry_run:
        print(f"[DRY] Would extract {len(members)} files to {root}/")
        for m in members:
            dest = root / m.name
            status = " (new)" if not dest.exists() else ""
            print(f"  {m.name}{status}")
        return 0

    if not force:
        conflicts = []
        with tarfile.open(tarball, "r:gz") as tar:
            for m in tar.getmembers():
                dest = root / m.name
                if dest.exists():
                    conflicts.append(m.name)
        if conflicts:
            print(f"Would overwrite {len(conflicts)} file(s). Use --force to proceed.")
            for c in conflicts[:10]:
                print(f"  {c}")
            if len(conflicts) > 10:
                print(f"  ... and {len(conflicts) - 10} more")
            return 1

    with tarfile.open(tarball, "r:gz") as tar:
        tar.extractall(root, filter="data")  # type: ignore[call-arg]

    print(f"Restored {len(members)} files.")
    return 0


def cmd_clean(dry_run: bool, keep: int) -> int:
    tarballs = _list_tarballs()
    to_delete = tarballs[:-keep] if keep > 0 else tarballs

    if not to_delete:
        print(f"Nothing to clean (keeping {keep}, have {len(tarballs)}).")
        return 0

    for t in to_delete:
        if dry_run:
            print(f"[DRY] Would delete {t.name}")
        else:
            t.unlink()
            print(f"Deleted {t.name}")

    if not dry_run:
        print(f"Kept {len(tarballs) - len(to_delete)} tarball(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without doing it")
    sub = parser.add_subparsers(dest="cmd", metavar="COMMAND")

    sub.add_parser("backup", help="Create a timestamped tarball backup")

    restore_p = sub.add_parser("restore", help="Extract the most recent tarball")
    restore_p.add_argument("--force", action="store_true", help="Overwrite existing files without prompting")

    clean_p = sub.add_parser("clean", help=f"Delete old tarballs (default: keep {_DEFAULT_KEEP})")
    clean_p.add_argument("--keep", type=int, default=_DEFAULT_KEEP, metavar="N", help="Number of tarballs to keep")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return 1

    dry_run: bool = args.dry_run

    if args.cmd == "backup":
        return cmd_backup(dry_run)
    if args.cmd == "restore":
        return cmd_restore(dry_run, getattr(args, "force", False))
    if args.cmd == "clean":
        return cmd_clean(dry_run, args.keep)

    print(f"Unknown command: {args.cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
