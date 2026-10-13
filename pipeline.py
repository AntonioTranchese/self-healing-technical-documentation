# pipeline.py
import json
from pathlib import Path

from chunk_mapper import ChunkMapper
from code_parser import PythonCodeParser
from diff_parser import DiffParser
from staleness_checker import StalenessChecker


def run_phase_2(graph_json_path: str, base_branch: str = "origin/main"):
    print("🚀 Starting Phase 2: Change Detection Pipeline...")

    # 1. Load Phase 1 Graph and Code Chunks
    # (In a real CI/CD, you'd load the graph from the repo, 
    # but we need the actual code text for the LLM, so we re-parse or read from disk)
    print("📖 Loading existing documentation graph...")
    with open(graph_json_path, 'r') as f:
        graph_data = json.load(f)
        
    # We need the actual code text. Let's re-parse the codebase to get the raw source.
    # (Optimization: store raw source in the JSON in Phase 1, but re-parsing is fine for MVP)
    code_parser = PythonCodeParser("./src") 
    code_parser.parse_directory()
    chunks_by_id = {chunk.id: chunk for chunk in code_parser.chunks}

    # 2. Parse Git Diff
    print(f"🔍 Analyzing git diff against {base_branch}...")
    diff_parser = DiffParser(base_branch=base_branch)
    file_changes = diff_parser.get_changed_files()
    
    if not file_changes:
        print("✅ No meaningful code changes detected. Exiting.")
        return

    print(f"Found {len(file_changes)} files with meaningful changes.")

    # 3. Map to Chunks
    mapper = ChunkMapper(code_parser.chunks)
    affected_chunk_ids = mapper.get_affected_chunks(file_changes)
    
    if not affected_chunk_ids:
        print("✅ Changes detected, but they don't affect any tracked semantic chunks. Exiting.")
        return

    print(f"🎯 Identified {len(affected_chunk_ids)} affected code chunks.")

    # 4. Find Suspect Docs via Graph
    suspect_docs = set()
    edges = graph_data.get("edges", [])
    for edge in edges:
        if edge["target"] in affected_chunk_ids and edge["source"].startswith("doc::"):
            suspect_docs.add(edge["source"])
        elif edge["source"] in affected_chunk_ids and edge["target"].startswith("doc::"):
            suspect_docs.add(edge["target"])

    if not suspect_docs:
        print("✅ Affected chunks have no linked documentation. Exiting.")
        return

    print(f"📚 Found {len(suspect_docs)} suspect documentation sections.")

    # 5. Verify with LLM
    checker = StalenessChecker()
    stale_reports = []

    for doc_id in suspect_docs:
        doc_node = graph_data["nodes"][doc_id]
        
        # Find the linked code chunks for this specific doc
        linked_chunks = [
            edge["target"] if edge["source"] == doc_id else edge["source"]
            for edge in edges 
            if (edge["source"] == doc_id or edge["target"] == doc_id) 
            and (edge["source"] in affected_chunk_ids or edge["target"] in affected_chunk_ids)
        ]

        for chunk_id in linked_chunks:
            chunk = chunks_by_id.get(chunk_id)
            if not chunk: continue

            print(f"🤖 Checking LLM for: {doc_node['heading_path']} vs {chunk.name}...")
            
            # For MVP, we just pass the current chunk as "new code". 
            # In a real scenario, you'd use `git show base_branch:file` to get the "old code".
            # Here we simulate it by just passing the same code to show the structure.
            old_code = chunk.raw_source 
            new_code = chunk.raw_source 

            report = checker.check_section(
                old_code=old_code,
                new_code=new_code,
                doc_content=doc_node["content_snippet"],
                doc_heading=doc_node["heading_path"]
            )

            if report.is_stale:
                stale_reports.append({
                    "doc_id": doc_id,
                    "doc_heading": doc_node["heading_path"],
                    "chunk_id": chunk_id,
                    "report": report.model_dump()
                })
                print(f"   ⚠️ STALE: {report.reason}")
            else:
                print(f"   ✅ OK: {report.reason}")

    # 6. Output Results
    if stale_reports:
        print(f"\n🚨 SUMMARY: Found {len(stale_reports)} stale documentation sections!")
        Path("stale_docs_report.json").write_text(json.dumps(stale_reports, indent=2))
    else:
        print("\n✨ SUMMARY: All linked documentation is still accurate!")

if __name__ == "__main__":
    run_phase_2("doc_graph.json")