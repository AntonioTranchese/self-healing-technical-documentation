import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import networkx as nx

from code_parser import CodeChunk, PythonCodeParser
from doc_parser import DocSection, MarkdownDocParser

# Note: In production, you would import:
# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer('all-MiniLM-L6-v2')

class DocumentationGraphBuilder:
    def __init__(self, code_dir: str, docs_dir: str, output_path: str):
        self.code_dir = code_dir
        self.docs_dir = docs_dir
        self.output_path = output_path
        self.graph = nx.Graph()

    def build(self):
        print("Parsing codebase...")
        code_parser = PythonCodeParser(self.code_dir)
        code_parser.parse_directory()

        print("Parsing documentation...")
        doc_parser = MarkdownDocParser(self.docs_dir)
        doc_parser.parse_directory()

        print(f"Found {len(code_parser.chunks)} code chunks and {len(doc_parser.sections)} doc sections.")

        # 1. Add Nodes
        self._add_code_nodes(code_parser.chunks)
        self._add_doc_nodes(doc_parser.sections)
        
        # 2. Add Edges (Heuristics)
        self._build_heuristic_edges(code_parser.chunks, doc_parser.sections)
        
        # 3. Add Edges (Semantic - Placeholder for Embeddings)
        # self._build_semantic_edges(code_parser.chunks, doc_parser.sections)
        
        # 4. Export
        self._export_json(code_parser.chunks, doc_parser.sections)
        print(f"Graph exported to {self.output_path}")

    def _add_code_nodes(self, chunks: list[CodeChunk]):
        for chunk in chunks:
            file_hash = self._get_file_hash(chunk.file_path)
            self.graph.add_node(chunk.id,
                                type='code',
                                file=chunk.file_path,
                                file_hash=file_hash,
                                symbol_type=chunk.symbol_type,
                                content_snippet=chunk.raw_source[:200] + "..."
                                )

    def _add_doc_nodes(self, sections: list[DocSection]):
        for section in sections:
            file_hash = self._get_file_hash(section.file_path)
            self.graph.add_node(section.id, 
                type="doc", 
                file=section.file_path, 
                file_hash=file_hash,
                heading_path=section.heading_path,
                content_snippet=section.raw_content[:200] + "..."
            )

    def _build_heuristic_edges(self, chunks: list[CodeChunk], sections: list[DocSection]):
        # Create a fast lookup set of all code symbol names
        code_symbols = {chunk.name.lower() for chunk in chunks}

        for section in sections:
            for ref in section.code_references:
                if ref.lower() in code_symbols:
                    matching_chunks = [c.id for c in chunks if c.name.lower() == ref.lower()]
                    for chunk_id in matching_chunks:
                        self.graph.add_edge(section.id, chunk_id, link_type="heuristic", confidence=1.0)

    def _build_semantic_edges(self, chunks: list[CodeChunk], sections: list[DocSection]):
        """
        TODO: Implement with sentence-transformers.
        1. Embed chunk.docstring + chunk.signature
        2. Embed section.raw_content
        3. Calculate cosine similarity.
        4. Add edge if similarity > 0.75.
        """
        #pass

    def _get_file_hash(self, relative_path: str) -> str:
        # Determine if it's in code or docs dir
        base_dir = self.code_dir if Path(self.code_dir, relative_path).exists() else self.docs_dir
        full_path = Path(base_dir, relative_path)
        if not full_path.exists():
            return "unknown"
        return hashlib.md5(full_path.read_bytes()).hexdigest()

    def _export_json(self, chunks: list[CodeChunk], sections: list[DocSection]):
        output = {
            "metadata": {
                "version": "1.0.0",
                "tool": "self-healing-docs",
                "code_dir": self.code_dir,
                "docs_dir": self.docs_dir
            },
            "nodes": {},
            "edges": []
        }
        
        # Nodes
        for node_id, data in self.graph.nodes(data=True):
            output["nodes"][node_id] = data
            
        # Edges
        for u, v, data in self.graph.edges(data=True):
            output["edges"].append({
                "source": u,
                "target": v,
                **data
            })
            
        Path(self.output_path).write_text(json.dumps(output, indent=2))

if __name__ == "__main__":
    # Example usage
    builder = DocumentationGraphBuilder(
        code_dir="./my_project/src",
        docs_dir="./my_project/docs",
        output_path="./doc_graph.json"
    )
    builder.build() 