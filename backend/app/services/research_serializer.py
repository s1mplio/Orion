from typing import Any

from app.services.citations import (
    apa_reference,
    build_sources,
    cited_keys,
)


# =========================================================
# COMPLETE RESEARCH RESULT
# =========================================================

def serialize_state(state) -> dict:
    """
    Convert a finished ResearchState into the JSON result
    returned by the API and saved in the job store.
    """

    papers = [
        serialize_paper(paper)
        for paper in (getattr(state, "papers", []) or [])
    ]

    evidence = [
        serialize_evidence(item)
        for item in (getattr(state, "evidence", []) or [])
    ]

    literature_review = make_json_safe(
        getattr(state, "literature_review", None)
    )

    result = {
        "question": getattr(state, "question", ""),
        "sub_questions": list(
            getattr(state, "sub_questions", []) or []
        ),
        "papers": papers,
        "evidence": evidence,
        "critic": serialize_object(
            getattr(state, "critic_results", None)
        ),
        "synthesis": serialize_object(
            getattr(state, "synthesis", None)
        ),
        "literature_review": literature_review,
        "hypothesis": serialize_object(
            getattr(state, "hypothesis", None)
        ),
        "hypothesis_review": serialize_object(
            getattr(state, "hypothesis_review", None)
        ),
        "experiment": serialize_object(
            getattr(state, "experiments", None)
        ),
        "final_report": make_json_safe(
            getattr(state, "final_report", None)
        ),
        "usage": make_json_safe(
            getattr(state, "usage", None)
        ),
    }

    result.update(
        build_citation_data(result)
    )

    return result


def build_citation_data(result: dict) -> dict:
    """
    Resolve every source key cited anywhere in the result
    to an APA in-text citation and a numbered reference.

    The reference list covers sources cited by the
    literature review, or by the evidence when no review
    was written.
    """

    sources = build_sources(
        result.get("papers") or [],
        result.get("evidence") or [],
    )

    review = result.get("literature_review") or {}

    review_texts = [
        review.get("abstract"),
        review.get("introduction"),
        review.get("conclusion"),
        *(theme.get("discussion") for theme in review.get("themes") or []),
        *(review.get("research_gaps") or []),
    ]

    evidence_texts = [
        finding
        for item in result.get("evidence") or []
        for finding in item.get("findings") or []
    ]

    other_texts = []

    for section in ("synthesis", "final_report", "hypothesis", "critic"):
        value = result.get(section)

        if isinstance(value, dict):
            for item in value.values():
                if isinstance(item, list):
                    other_texts.extend(str(x) for x in item)
                else:
                    other_texts.append(str(item))

    reference_keys = cited_keys(
        [text for text in review_texts if text]
        or evidence_texts,
        sources,
    )

    all_keys = cited_keys(
        review_texts + evidence_texts + other_texts,
        sources,
    )

    # One numbered reference per paper, alphabetical (APA).
    entries = {}

    for key in reference_keys:
        paper = sources[key]["paper"]
        entry = apa_reference(paper)
        entries.setdefault(entry, None)

    references = sorted(entries, key=str.lower)

    reference_index = {
        entry: index for index, entry in enumerate(references)
    }

    serialized_sources = {}

    for key in all_keys:
        source = sources[key]
        entry = apa_reference(source["paper"])

        serialized_sources[key] = {
            "in_text": source["in_text"],
            "paper_index": source["paper_index"],
            "page_start": source["page_start"],
            "page_end": source["page_end"],
            "section": source["section"],
            "title": source["paper"].get("title"),
            "reference_index": reference_index.get(entry),
        }

    return {
        "sources": serialized_sources,
        "references": references,
    }


# =========================================================
# PAPER SERIALIZER
# =========================================================

def serialize_paper(paper) -> dict:
    return {
        "title": getattr(paper, "title", ""),
        "authors": getattr(paper, "authors", []),
        "year": getattr(paper, "year", None),
        "url": getattr(paper, "url", None),
        "doi": getattr(paper, "doi", None),
        "citation_count": getattr(paper, "citation_count", 0),
        "landing_page_url": getattr(paper, "landing_page_url", None),
        "pdf_url": getattr(paper, "pdf_url", None),
        "is_open_access": getattr(paper, "is_open_access", False),
        "open_access_status": getattr(paper, "open_access_status", None),
        "source_name": getattr(paper, "source_name", None),
        "full_text_available": getattr(paper, "full_text_available", False),
    }


# =========================================================
# EVIDENCE SERIALIZER
# =========================================================

def serialize_evidence(evidence) -> dict:
    if hasattr(evidence, "to_dict"):
        try:
            return make_json_safe(evidence.to_dict())
        except Exception:
            pass

    return {
        "paper_title": getattr(evidence, "paper_title", ""),
        "findings": getattr(evidence, "findings", []),
        "methods": getattr(evidence, "methods", ""),
        "limitations": getattr(evidence, "limitations", ""),
        "relevance": getattr(evidence, "relevance", ""),
        "query": getattr(evidence, "query", None),
        "source_type": getattr(evidence, "source_type", "unknown"),
        "cited_chunk_ids": getattr(evidence, "cited_chunk_ids", []),
        "retrieved_chunks": getattr(evidence, "retrieved_chunks", []),
    }


# =========================================================
# GENERIC OBJECT SERIALIZER
# =========================================================

def serialize_object(obj):
    if obj is None:
        return None

    if isinstance(obj, dict):
        return make_json_safe(obj)

    if hasattr(obj, "__dict__"):
        return make_json_safe(vars(obj))

    return make_json_safe(obj)


# =========================================================
# JSON SAFE CONVERTER
# =========================================================

def make_json_safe(value: Any):
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    if hasattr(value, "__dict__"):
        return make_json_safe(vars(value))

    return str(value)
