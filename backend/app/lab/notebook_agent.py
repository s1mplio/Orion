from datetime import datetime

from app.agents.llm_json import ensure_str_list, parse_llm_json
from app.services.citations import render_citations
from app.services.job_manager import job_manager
from app.services.llm_service import llm


def _clock(timestamp):
    try:
        return datetime.fromisoformat(timestamp).strftime("%H:%M")
    except (TypeError, ValueError):
        return str(timestamp or "")


def _time_range(entry):
    start = _clock(entry["started_at"])
    end = _clock(entry["ended_at"])
    return start if start == end else f"{start}–{end}"


class NotebookAgent:
    """
    Writes a lab notebook entry from a session's log.

    The model only organizes and words what the log
    recorded. Timestamps come from the log, and background
    and references from a linked research report are added
    verbatim from that report.
    """

    def __init__(self, llm_service=None):
        self.llm = llm_service or llm

    def generate(self, session, entries):
        log_text = self._format_log(entries)

        if not log_text:
            raise ValueError(
                "This session has no log entries yet. Record "
                "some work or add a note first."
            )

        protocol = (session.get("protocol") or "").strip()

        prompt = f"""
You are writing a laboratory notebook entry from an
automatically recorded session log.

SESSION TITLE:
{session["title"]}

PLANNED PROTOCOL:
{protocol or "No protocol was provided."}

SESSION LOG (chronological; [time] activity, then details):
{log_text}

Write the notebook entry using ONLY the log and protocol.

RULES:
1. Never invent quantities, concentrations, durations,
   readings or results that are not in the log.
2. Keep the exact times from the log in the procedure.
3. Researcher notes (marked NOTE) are authoritative.
4. Camera observations can be imprecise; describe them
   neutrally ("appeared to", "was observed").
5. Deviations: compare the log with the protocol and list
   protocol steps that were skipped, reordered or done
   differently. If there is no protocol, return an empty
   list.
6. Only report safety notes that appear in the log.

Return ONLY valid JSON:

{{
    "title": "",
    "objective": "",
    "materials": [],
    "equipment": [],
    "procedure": [
        {{"time": "HH:MM", "step": ""}}
    ],
    "observations": [],
    "deviations": [],
    "safety_notes": [],
    "summary": ""
}}
"""

        data = parse_llm_json(self.llm.generate(prompt))

        if data is None:
            raise RuntimeError(
                "The model did not return a readable notebook."
            )

        notebook = self._normalize(data, session)
        notebook["background"] = self._research_background(
            session.get("research_job_id")
        )
        notebook["generated_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        return notebook

    # =====================================================
    # LOG FORMATTING
    # =====================================================

    def _format_log(self, entries):
        lines = []

        for entry in entries:
            when = _time_range(entry)

            if entry["kind"] == "note":
                lines.append(f"[{when}] NOTE: {entry['activity']}")
                continue

            details = entry["details"]
            lines.append(f"[{when}] {entry['activity']}")

            for label, key in (
                ("Materials", "materials"),
                ("Equipment", "equipment"),
                ("Visible text/readings", "visible_text"),
            ):
                if details.get(key):
                    lines.append(f"    {label}: {', '.join(details[key])}")

            if details.get("observation"):
                lines.append(f"    Observation: {details['observation']}")

            if details.get("safety_concern"):
                lines.append(
                    f"    SAFETY CONCERN: {details['safety_concern']}"
                )

        return "\n".join(lines)

    # =====================================================
    # NORMALIZATION
    # =====================================================

    def _normalize(self, data, session):
        procedure = []

        for item in data.get("procedure") or []:
            if isinstance(item, dict):
                step = str(item.get("step") or "").strip()
                time = str(item.get("time") or "").strip()
            else:
                step = str(item).strip()
                time = ""

            if step:
                procedure.append({"time": time, "step": step})

        return {
            "title": str(data.get("title") or "").strip()
            or session["title"],
            "objective": str(data.get("objective") or "").strip(),
            "materials": ensure_str_list(data.get("materials")),
            "equipment": ensure_str_list(data.get("equipment")),
            "procedure": procedure,
            "observations": ensure_str_list(data.get("observations")),
            "deviations": ensure_str_list(data.get("deviations")),
            "safety_notes": ensure_str_list(data.get("safety_notes")),
            "summary": str(data.get("summary") or "").strip(),
        }

    # =====================================================
    # LINKED RESEARCH
    # =====================================================

    def _research_background(self, research_job_id):
        """
        Background text and references from a linked
        literature review, with citations rendered.
        """

        if not research_job_id:
            return None

        job = job_manager.get_job(research_job_id)

        if not job or job.get("status") != "completed":
            return None

        result = job.get("result") or {}
        review = result.get("literature_review") or {}
        synthesis = result.get("synthesis") or {}
        sources = result.get("sources") or {}

        text = (
            review.get("abstract")
            or synthesis.get("summary")
            or ""
        )

        return {
            "research_job_id": research_job_id,
            "question": result.get("question"),
            "text": render_citations(text, sources),
            "references": result.get("references") or [],
        }


notebook_agent = NotebookAgent()
