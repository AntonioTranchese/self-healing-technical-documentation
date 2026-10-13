# repair_engine.py
from typing import List, Literal

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field


# 1. Define Structured Outputs
class RewrittenSection(BaseModel):
    rewritten_markdown: str = Field(description="The fully rewritten markdown section.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the accuracy of the rewrite.")
    correction_mode: Literal["auto_fix", "draft_todo"] = Field(
        description="'auto_fix' for simple changes. 'draft_todo' if the change is complex and requires human review."
    )
    todos: List[str] = Field(default_factory=list, description="List of TODO comments to insert if mode is 'draft_todo'.")
    explanation: str = Field(description="Brief explanation of what was changed and why.")

class ValidationReport(BaseModel):
    is_valid: bool = Field(description="True if the rewritten doc passes the quality gate.")
    accuracy_score: float = Field(ge=0.0, le=1.0, description="How accurately it describes the new code.")
    style_preservation_score: float = Field(ge=0.0, le=1.0, description="How well it preserved the original tone/structure.")
    feedback: str = Field(description="Constructive feedback on what was done well or poorly.")


class DocRepairEngine:
    def __init__(self):
        client = OpenAI()
        self.client = instructor.from_openai(client)

    def generate_correction(
        self, 
        original_doc: str, 
        new_code: str, 
        staleness_diagnosis: str,
        doc_heading: str
    ) -> RewrittenSection:
        prompt = f"""
        You are an expert technical writer. A specific section of documentation is stale.
        
        ### ORIGINAL DOCUMENTATION SECTION: {doc_heading}
        {original_doc}

        ### NEW CODE
        ```python
        {new_code}
        ```

        ### STALENESS DIAGNOSIS
        {staleness_diagnosis}

        ### INSTRUCTIONS
        1. Rewrite the documentation to accurately reflect the NEW CODE.
        2. CRITICAL: Preserve the original style, tone, and structure. ONLY modify the parts that are stale. Do not rewrite parts that are still accurate.
        3. CORRECTION MODES:
           - If the change is simple (e.g., renamed parameter, updated default value, minor logic tweak), set `correction_mode` to "auto_fix".
           - If the change is complex (e.g., entirely new feature, removed capability, architectural shift), set `correction_mode` to "draft_todo". In this mode, insert HTML comments like `<!-- TODO: [Explain what needs human review] -->` directly into the `rewritten_markdown` where you are unsure, and list them in the `todos` array.
        """

        return self.client.chat.completions.create(
            model="gpt-4o", # Use the smarter model for generation
            response_model=RewrittenSection,
            messages=[
                {"role": "system", "content": "You are a precise, conservative technical writer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

    def validate_correction(
        self, 
        original_doc: str, 
        rewritten_doc: str, 
        new_code: str
    ) -> ValidationReport:
        prompt = f"""
        You are a strict QA Engineer reviewing a documentation update.

        ### ORIGINAL DOC
        {original_doc}

        ### REWRITTEN DOC
        {rewritten_doc}

        ### NEW CODE
        ```python
        {new_code}
        ```

        ### INSTRUCTIONS
        1. Check ACCURACY: Does the REWRITTEN DOC accurately describe the NEW CODE?
        2. Check PRESERVATION: Did the REWRITTEN DOC preserve the parts of the ORIGINAL DOC that were already correct? Did it maintain the original tone and structure?
        3. If the REWRITTEN DOC hallucinates features not in the code, or deletes correct information, it FAILS.
        """

        return self.client.chat.completions.create(
            model="gpt-4o-mini", # Fast/cheap model is fine for QA
            response_model=ValidationReport,
            messages=[
                {"role": "system", "content": "You are a meticulous QA reviewer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )    