import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CodeChunk:
    id: str
    file_path: str
    symbol_type: str
    name: str
    signature: str
    docstring: Optional[str]
    raw_source: str
    decorators: list[str] = field(default_factory=list)

class PythonCodeParser:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.chunks: list[CodeChunk] = []

    def parse_directory(self):
        for py_file in self.root_dir.rglob("*.py"):
            if any(part.startswith('.') or part == 'venv' or part == 'env' for part in py_file.parts):
                continue
            self._parse_file(py_file)

    def _parse_file(self, file_path: Path):
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return 

        rel_path = file_path.relative_to(self.root_dir)
        visitor = _ASTChunkVisitor(source.splitlines(), str(rel_path))
        visitor.visit(tree)
        self.chunks.extend(visitor.chunks)

class _ASTChunkVisitor(ast.NodeVisitor):
    def __init__(self, source_lines: list[str], file_path: str):
        self.source_lines = source_lines
        self.file_path = file_path
        self.chunks: list[CodeChunk] = []
        self.class_context: Optional[str] = None

    def _get_source_text(self, node: ast.AST) -> str:
        start = node.lineno - 1
        end = node.end_lineno
        return "\n".join(self.source_lines[start:end])

    def _get_decorators(self, node: ast.AST) -> list[str]:
        if not hasattr(node, 'decorator_list'):
            return []
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(ast.unparse(dec))
            elif isinstance(dec, ast.Call):
                decorators.append(ast.unparse(dec.func))
        return decorators

    def _classify_symbol(self, name: str, decorators: list[str], bases: list[str]) -> str:
        # Heuristics for special Python constructs
        dec_str = " ".join(decorators).lower()
        if any(api in dec_str for api in ["route", "get", "post", "put", "delete", "api_view"]):
            return "api_endpoint"
        if any(cli in dec_str for cli in ["command", "argument", "option", "typer"]):
            return "cli_command"
        if any(cfg in " ".join(bases).lower() for cfg in ["basesettings", "basemodel", "config"]):
            return "config_schema"
        return "class" if self.class_context else "function"

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_context = self.class_context
        self.class_context = node.name

        bases = [ast.unparse(b) for b in node.bases]
        decorators = self._get_decorators(node)
        symbol_type = self._classify_symbol(node.name, decorators, bases)

        if symbol_type == "config_schema":
            self._add_chunk(node, symbol_type, node.name)
        else:
            self.generic_visit(node)

        self.class_context = prev_context

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._add_chunk(node, "function", node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def _add_chunk(self, node: ast.AST, default_type: str, name: str):
        decorators = self._get_decorators(node)
        symbol_type = self._classify_symbol(name, decorators, []) if default_type == "function" else default_type

        # Build stable ID
        prefix = f"{self.class_context}::" if self.class_context and default_type == "function" else ""
        chunk_id = f"{self.file_path}::{prefix}{name}"

        # Extract signature and docstring
        signature = ast.unparse(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else f"class {name}"
        docstring = ast.get_docstring(node)
        raw_source = self._get_source_text(node)

        self.chunks.append(CodeChunk(
            id=chunk_id,
            file_path=self.file_path,
            symbol_type=symbol_type,
            name=name,
            signature=signature.split('\n')[0], # Just the first line for signature
            docstring=docstring,
            raw_source=raw_source,
            decorators=decorators
        ))