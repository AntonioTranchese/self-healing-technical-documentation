import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocSection:
    id: str
    file_path: str
    heading_path: str
    raw_content: str
    code_references: list[str] = field(default_factory=list)

class MarkdownDocParser:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.sections: list[DocSection] = []

    def parse_directory(self):
        for md_file in self.root_dir.rglob("*.md"):
            self._parse_file(md_file)

    def _parse_file(self, file_path: Path):
        content = file_path.read_text(encoding='utf-8')
        rel_path = str(file_path.relative_to(self.root_dir))

        # Split by headings using regex to maintain hierarchy
        # Matches #, ##, ###, etc.
        heading_pattern = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)

        chunks = heading_pattern.split(content)

        # chunks structure: [preamble, '#', 'Title', 'text...', '##', 'Subtitle', 'text...']
        heading_stack = []
        # not used
        current_content = chunks[0] if chunks[0].strip() else ""

        i = 1
        while i < len(chunks):
            level_char = chunks[i]
            heading_text = chunks[i+1]
            body_text = chunks[i+2] if i+2 < len(chunks) else ""

            level = len(level_char)

            # Adjust stack to current level
            heading_stack = heading_stack[:level-1]
            heading_stack.append(heading_text)

            heading_path = " > ".join(heading_stack)
            section_id = f"{rel_path}::{heading_path}"

            # Extract inline code references (e.g., `my_function`)
            # Mistune is great, but regex is faster for just extracting backticks
            refs = re.findall(r'`([^`]+)`', body_text)
            # Filter out obvious non-code backticks (like single letters or long sentences)
            clean_refs = [r for r in refs if 2 < len(r) < 50 and not r.startswith('http')]

        self.sections.append(DocSection(
            id=section_id,
            file_path=rel_path,
            heading_path=heading_path,
            raw_content=body_text.strip(),
            code_references=list(set(clean_refs))
        ))
        
        i += 3
