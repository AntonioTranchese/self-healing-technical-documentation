from typing import List, Set
from diff_parser import FileChange
from code_parser import CodeChunk

class ChunkMapper:
    def __init__(self, chunks: List[CodeChunk]):
        # Group chunks by file path for faster lookup
        self.chunks_by_file = {}
        for chunk in chunks:
            if chunk.file_path not in self.chunks_by_file:
                self.chunks_by_file[chunk.file_path] = []
            self.chunks_by_file[chunk.file_path].append(chunk)

    def get_affected_chunks(self, file_changes: List[FileChange]) -> Set[str]:
        affected_chunk_ids = set()

        for change in file_changes:
            if change.file_path not in self.chunks_by_file:
                continue # File might be new or not parsed

            chunks_in_file = self.chunks_by_file[change.file_path]
            
            # Combine all changed lines for this file
            all_changed_lines = set(change.added_lines + change.removed_lines)

            for chunk in chunks_in_file:
                if self._lines_overlap(all_changed_lines, chunk.start_line, chunk.end_line):
                    affected_chunk_ids.add(chunk.id)

        return affected_chunk_ids

    def _lines_overlap(self, changed_lines: Set[int], start: int, end: int) -> bool:
        # Check if any changed line falls within the chunk's boundaries
        return any(start <= line <= end for line in changed_lines)