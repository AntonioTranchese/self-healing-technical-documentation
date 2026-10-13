import subprocess
from dataclasses import dataclass
from typing import List, Tuple

from unidiff import Hunk, PatchSet


@dataclass
class FileChange:
    file_path: str
    added_lines: List[int]
    removed_lines: List[int]
    diff_text: str # The raw unified diff for this file

class DiffParser:
    def __init__(self, base_branch: str = "origin/main"):
        self.base_branch = base_branch

    def get_changed_files(self) -> List[FileChange]:
        cmd = ["git", "diff", "-w", f"{self.base_branch}...HEAD"]
        try:
            diff_output = subprocess.check_output(cmd, text=True)
        except subprocess.CalledProcessError:
            return []

        if not diff_output.strip():
            return []

        patch_set = PatchSet(diff_output)
        changes = []

        for patched_file in patch_set:
            # 1. Filetr out test files
            if self._is_test_file(patched_file.path):
                continue

            added, removed = self._extract_line_changes(patched_file)

            # 2. Filter out comment-only changes
            if self._is_only_comments(patched_file):
                continue

            if added or removed:
                changes.append(FileChange(
                    file_path=patched_file.path,
                    added_lines=added,
                    removed_lines=removed,
                    diff_text=str(patched_file)
                ))

        return changes

    def _is_test_file(self, path: str) -> bool:
        parts = path.split('/')
        return any("test" in p.lower() for p in parts) or path.endswith("_test.py")

    def _extract_line_changes(self, patched_file) -> Tuple[List[int], List[int]]:
        added, removed = [], []
        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    added.append(line.target_line_no)
                elif line.is_removed:
                    removed.append(line.source_line_no)
        return added, removed

    def _is_only_comments(self, patched_file) -> bool:

        added_lines = []
        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    added_lines.append(line.value.strip())

        if not added_lines:
            return True

        return all(line.startswith('#') for line in added_lines if line)