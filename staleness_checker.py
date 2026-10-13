# staleness_checker.py
from typing import List, Optional

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

import os


# 1. Define the Structured Output Schema
class StalenessReport(BaseModel):
    is_stale: bool = Field(description="True if the documentation is no longer accurate based on the code change.")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in this assessment.")
    reason: str = Field(description="Brief explanation of why it is or isn't stale.")
    missing_info: Optional[str] = Field(None, description="If stale, what specific information is missing or wrong?")

class StalenessChecker:
    def __init__(self):
        # Instructor patches the OpenAI client to enforce Pydantic models
        client = OpenAI()
        self.client = instructor.from_openai(client)

    def check_section(self, old_code: str, new_code: str, doc_content: str, doc_heading: str) -> StalenessReport:
        prompt = f"""
        You are an expert technical writer and software engineer. 
        A developer changed some code. You need to determine if a specific section of the documentation is now stale (inaccurate).

        ### DOCUMENTATION SECTION: {doc_heading}
        {doc_content}

        ### OLD CODE
        ```python
        {old_code}
        ```

        ### NEW CODE
        ```python
        {new_code}
        ```

        ### INSTRUCTIONS
        1. Analyze the difference between the OLD CODE and NEW CODE.
        2. Determine if the DOCUMENTATION SECTION accurately reflects the NEW CODE.
        3. Ignore minor internal refactors that don't change external behavior.
        4. Focus on API signatures, configuration keys, return types, and behavioral changes.
        5. Return your assessment.
        """

        return self.client.chat.completions.create(
            model="gpt-4o-mini", # Fast and cheap for this specific task
            response_model=StalenessReport,
            messages=[
                {"role": "system", "content": "You are a precise documentation auditing assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1, # Low temperature for factual consistency
        )