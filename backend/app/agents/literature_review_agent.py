from app.agents.llm_json import (
    ensure_str_list,
    parse_llm_json,
)
from app.services.citations import (
    CITATION_KEY,
    strip_unknown_citations,
)


class LiteratureReviewAgent:
    """
    Writes a thesis-style literature review from the
    extracted evidence.

    The LLM may only cite source keys that appear in the
    evidence it is given ([chunk_...] or [paper_N]). Keys it
    invents are removed, and the in-text citations and
    reference list are produced later from paper metadata.
    """

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):
        print()
        print("=" * 70)
        print("LITERATURE REVIEW")
        print("=" * 70)

        if not state.evidence:
            print("[LIT REVIEW] No evidence available.")
            return

        evidence_text, valid_keys = self._format_evidence(state)

        if not valid_keys:
            print("[LIT REVIEW] Evidence has no citable sources.")
            return

        critic = state.critic_results
        synthesis = state.synthesis

        context = ""

        if critic is not None:
            context += (
                f"\nAgreements across sources:\n{critic.agreements}\n"
                f"\nContradictions:\n{critic.contradictions}\n"
                f"\nResearch gaps identified:\n{critic.research_gaps}\n"
                f"\nEvidence confidence: {critic.confidence}\n"
            )

        if synthesis is not None:
            context += f"\nSynthesis summary:\n{synthesis.summary}\n"

        prompt = f"""
You are an academic writer helping a postgraduate student
draft the literature review chapter of a thesis.

RESEARCH QUESTION:
{state.question}

FOCUS AREAS INVESTIGATED:
{self._bullets(state.sub_questions)}

EVIDENCE (each line ends with its source key in brackets):
{evidence_text}

REVIEWER NOTES:
{context or "None"}

Write a literature review using ONLY the evidence above.

CITATION RULES (mandatory):
1. Support every factual sentence with one or more source
   keys copied exactly from the evidence, in square brackets,
   e.g. [chunk_p3_ab12cd34ef56] or [paper_2, paper_5].
2. Never invent a source key, author, year or paper.
3. Do not write author names or years yourself; the keys are
   converted into formal citations automatically.
4. Do not add a reference list.

WRITING RULES:
- Formal academic register, third person, past tense for
  reported findings.
- Organize the body by themes, not paper by paper. Compare
  and contrast sources within each theme.
- Say explicitly where evidence is limited, comes from a
  single source, or conflicts.
- Lines marked "(abstract only)" come from a paper's
  abstract, not its full text. Report them more cautiously
  (e.g. "the abstract reports...").
- Research gaps must follow from the evidence and reviewer
  notes, not outside knowledge.
- Do not claim more certainty than the evidence supports.

Return ONLY valid JSON with exactly this structure:

{{
    "title": "",
    "abstract": "",
    "introduction": "",
    "themes": [
        {{
            "title": "",
            "discussion": ""
        }}
    ],
    "research_gaps": [],
    "conclusion": ""
}}

Use 2 to 5 themes. Each theme discussion should be one or
more full paragraphs.
"""

        try:
            response = self.llm.generate(prompt)
        except Exception as error:
            print("[LIT REVIEW] LLM call failed:", error)
            return

        data = parse_llm_json(response)

        if data is None:
            print("[LIT REVIEW] Invalid JSON response.")
            print(response)
            return

        review = self._normalize(data, valid_keys, state.question)

        if not review["themes"]:
            print("[LIT REVIEW] No themes returned.")
            return

        state.literature_review = review

        print("[LIT REVIEW] Title:", review["title"])
        print("[LIT REVIEW] Themes:", [t["title"] for t in review["themes"]])

    # =====================================================
    # EVIDENCE FORMATTING
    # =====================================================

    def _format_evidence(self, state):
        lines = []
        valid_keys = set()

        papers = state.papers or []

        for evidence in state.evidence:
            abstract_only = getattr(
                evidence, "source_type", ""
            ).startswith("abstract")

            for finding in evidence.findings or []:
                keys = CITATION_KEY.findall(str(finding))

                if not keys:
                    continue

                valid_keys.update(keys)

                # Abstract claims are weaker evidence; the
                # writer should hedge them accordingly.
                prefix = "(abstract only) " if abstract_only else ""

                lines.append(f"- {prefix}{finding}")

        # Paper titles and years help the writer group themes.
        cited_papers = sorted(
            {
                int(key.split("_")[1])
                for key in valid_keys
                if key.startswith("paper_")
                and key.split("_")[1].isdigit()
            }
        )

        for number in cited_papers:
            if 1 <= number <= len(papers):
                paper = papers[number - 1]
                lines.append(
                    f"  (paper_{number} is: {paper.title}, {paper.year})"
                )

        return "\n".join(lines), valid_keys

    def _bullets(self, items):
        items = [str(item) for item in (items or []) if str(item).strip()]
        return "\n".join(f"- {item}" for item in items) or "- (none)"

    # =====================================================
    # NORMALIZATION
    # =====================================================

    def _normalize(self, data, valid_keys, question):
        sources = {key: True for key in valid_keys}

        def clean(text):
            if isinstance(text, (list, tuple)):
                text = "\n\n".join(ensure_str_list(text))
            return strip_unknown_citations(str(text or ""), sources)

        themes = []

        for theme in data.get("themes") or []:
            if isinstance(theme, dict):
                title = str(theme.get("title") or "").strip()
                discussion = clean(theme.get("discussion"))
            else:
                title = ""
                discussion = clean(theme)

            if discussion:
                themes.append(
                    {
                        "title": title or f"Theme {len(themes) + 1}",
                        "discussion": discussion,
                    }
                )

        return {
            "title": str(data.get("title") or "").strip()
            or f"Literature Review: {question}",
            "abstract": clean(data.get("abstract")),
            "introduction": clean(data.get("introduction")),
            "themes": themes,
            "research_gaps": [
                clean(gap)
                for gap in ensure_str_list(data.get("research_gaps"))
                if clean(gap)
            ],
            "conclusion": clean(data.get("conclusion")),
        }
