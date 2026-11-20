#!/usr/bin/env python3
"""Give the container application read access to published run artifacts only.

Uses POSIX access ACLs through libacl; it never reads artifact contents. Existing
principals retain their effective permissions even when the ACL mask changes.
Default ACLs and non-published file types (including SQLite databases) are left
untouched. Run again after producing new report artifacts.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import errno
import json
import os
from pathlib import Path
import stat
import sys


PUBLISHED_EXTENSIONS = frozenset({".json", ".jsonl", ".csv", ".md", ".html", ".xml", ".png"})
ACL_TYPE_ACCESS = 0x8000
USER_OBJ, USER, GROUP_OBJ, GROUP, MASK, OTHER = 1, 2, 4, 8, 16, 32
GROUP_CLASS = frozenset({USER, GROUP_OBJ, GROUP})


class AccessACL:
    def __init__(self) -> None:
        library = ctypes.util.find_library("acl")
        if not library:
            raise OSError(errno.ENOSYS, "libacl is unavailable")
        self.lib = ctypes.CDLL(library, use_errno=True)
        pointer = ctypes.c_void_p
        signatures = {
            "acl_get_file": (pointer, [ctypes.c_char_p, ctypes.c_int]),
            "acl_get_entry": (ctypes.c_int, [pointer, ctypes.c_int, ctypes.POINTER(pointer)]),
            "acl_get_tag_type": (ctypes.c_int, [pointer, ctypes.POINTER(ctypes.c_int)]),
            "acl_get_qualifier": (pointer, [pointer]),
            "acl_get_permset": (ctypes.c_int, [pointer, ctypes.POINTER(pointer)]),
            "acl_get_perm": (ctypes.c_int, [pointer, ctypes.c_int]),
            "acl_init": (pointer, [ctypes.c_int]),
            "acl_create_entry": (ctypes.c_int, [ctypes.POINTER(pointer), ctypes.POINTER(pointer)]),
            "acl_set_tag_type": (ctypes.c_int, [pointer, ctypes.c_int]),
            "acl_set_qualifier": (ctypes.c_int, [pointer, pointer]),
            "acl_clear_perms": (ctypes.c_int, [pointer]),
            "acl_add_perm": (ctypes.c_int, [pointer, ctypes.c_int]),
            "acl_valid": (ctypes.c_int, [pointer]),
            "acl_set_file": (ctypes.c_int, [ctypes.c_char_p, ctypes.c_int, pointer]),
            "acl_free": (ctypes.c_int, [pointer]),
        }
        for name, (result, arguments) in signatures.items():
            function = getattr(self.lib, name)
            function.restype, function.argtypes = result, arguments

    @staticmethod
    def checked(result):
        if result == -1 or result is None:
            code = ctypes.get_errno() or errno.EIO
            raise OSError(code, os.strerror(code))
        return result

    def read(self, path: Path) -> dict[tuple[int, int | None], int]:
        acl = self.checked(self.lib.acl_get_file(os.fsencode(path), ACL_TYPE_ACCESS))
        entries = {}
        try:
            entry = ctypes.c_void_p()
            position = 0  # ACL_FIRST_ENTRY, then ACL_NEXT_ENTRY
            while self.checked(self.lib.acl_get_entry(acl, position, ctypes.byref(entry))):
                position = 1
                tag = ctypes.c_int()
                self.checked(self.lib.acl_get_tag_type(entry, ctypes.byref(tag)))
                qualifier = None
                if tag.value in (USER, GROUP):
                    value = self.checked(self.lib.acl_get_qualifier(entry))
                    try:
                        qualifier = ctypes.cast(value, ctypes.POINTER(ctypes.c_uint)).contents.value
                    finally:
                        self.lib.acl_free(value)
                permissions = ctypes.c_void_p()
                self.checked(self.lib.acl_get_permset(entry, ctypes.byref(permissions)))
                bits = sum(bit for bit in (4, 2, 1) if self.checked(self.lib.acl_get_perm(permissions, bit)))
                entries[(tag.value, qualifier)] = bits
        finally:
            self.lib.acl_free(acl)
        return entries

    def write(self, path: Path, entries: dict[tuple[int, int | None], int]) -> None:
        acl = ctypes.c_void_p(self.checked(self.lib.acl_init(len(entries))))
        try:
            for (tag, qualifier), bits in sorted(entries.items(), key=lambda item: (item[0][0], item[0][1] or 0)):
                entry = ctypes.c_void_p()
                self.checked(self.lib.acl_create_entry(ctypes.byref(acl), ctypes.byref(entry)))
                self.checked(self.lib.acl_set_tag_type(entry, tag))
                if qualifier is not None:
                    value = ctypes.c_uint(qualifier)
                    self.checked(self.lib.acl_set_qualifier(entry, ctypes.byref(value)))
                permissions = ctypes.c_void_p()
                self.checked(self.lib.acl_get_permset(entry, ctypes.byref(permissions)))
                self.checked(self.lib.acl_clear_perms(permissions))
                for bit in (4, 2, 1):
                    if bits & bit:
                        self.checked(self.lib.acl_add_perm(permissions, bit))
            self.checked(self.lib.acl_valid(acl))
            self.checked(self.lib.acl_set_file(os.fsencode(path), ACL_TYPE_ACCESS, acl))
        finally:
            self.lib.acl_free(acl)

    @staticmethod
    def effective(entries: dict[tuple[int, int | None], int]) -> dict[tuple[int, int | None], int]:
        mask = entries.get((MASK, None), 7)
        return {key: bits & mask if key[0] in GROUP_CLASS else bits
                for key, bits in entries.items() if key[0] != MASK}

    def grant(self, path: Path, uid: int, permissions: int) -> bool:
        before = self.read(path)
        effective = self.effective(before)
        target = (USER_OBJ, None) if path.stat(follow_symlinks=False).st_uid == uid else (USER, uid)
        if effective.get(target, 0) & permissions == permissions:
            return False

        # Freeze all mask-controlled entries at their previous EFFECTIVE bits.
        # Simply widening the mask would otherwise grant latent group/user bits.
        after = dict(effective)
        after[target] = effective.get(target, 0) | permissions
        if target[0] == USER or (MASK, None) in before:
            after[(MASK, None)] = 0
            for key, bits in after.items():
                if key[0] in GROUP_CLASS:
                    after[(MASK, None)] |= bits

        expected = self.effective(after)
        assert all(expected[key] == bits for key, bits in effective.items() if key != target)
        try:
            self.write(path, after)
            actual = self.effective(self.read(path))
            if actual != expected:
                raise OSError(errno.EIO, "Written ACL did not retain expected effective permissions")
        except Exception:
            self.write(path, before)
            raise
        return True


def prepare(root: Path, uid: int) -> dict:
    if root.is_symlink() or not root.is_dir() or not (root / "runs").is_dir():
        raise OSError(errno.ENOENT, "Report root must contain a runs directory")
    acl = AccessACL()
    counts = {"uid": uid, "root": str(root), "directories_checked": 0,
              "artifacts_checked": 0, "acl_updates": 0, "skipped_private_files": 0,
              "skipped_symlinks": 0, "other_effective_permissions_preserved": True,
              "world_permissions_widened": False, "artifact_contents_read": False}
    counts["acl_updates"] += acl.grant(root, uid, 5)
    counts["directories_checked"] += 1
    for directory, subdirectories, files in os.walk(root / "runs", followlinks=False):
        directory = Path(directory)
        if directory.is_symlink():
            raise OSError(errno.ELOOP, "Refusing symlinked runs directory")
        counts["acl_updates"] += acl.grant(directory, uid, 5)
        counts["directories_checked"] += 1
        for name in list(subdirectories):
            if (directory / name).is_symlink():
                subdirectories.remove(name)
                counts["skipped_symlinks"] += 1
        for name in files:
            path = directory / name
            info = path.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                counts["skipped_symlinks"] += 1
            elif not stat.S_ISREG(info.st_mode) or path.suffix not in PUBLISHED_EXTENSIONS:
                counts["skipped_private_files"] += 1
            else:
                counts["acl_updates"] += acl.grant(path, uid, 4)
                counts["artifacts_checked"] += 1
    counts["status"] = "prepared"
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", type=int, default=10001, help="Application container UID (default: 10001)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "reports")
    parser.add_argument("--required", action="store_true", help="Fail if libacl or filesystem ACL support is unavailable")
    args = parser.parse_args()
    if not 0 <= args.uid < 2**32 - 1:
        parser.error("--uid must be a valid nonnegative POSIX UID")
    try:
        result = prepare(args.root.absolute(), args.uid)
    except OSError as error:
        unsupported = error.errno in {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
        result = {"status": "unsupported" if unsupported else "failed", "uid": args.uid,
                  "errno": error.errno, "error": error.strerror}
        print(json.dumps(result))
        return 0 if unsupported and not args.required else 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
