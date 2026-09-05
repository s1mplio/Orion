from typing import List, Optional, Dict, Any


class Evidence:
    """
    Scientific evidence extracted by Orion.

    The original fields are preserved for compatibility
    with existing Critic, Synthesis and Final Report agents.

    Research V2 adds provenance fields so evidence can be
    traced back to retrieved full-paper chunks.
    """

    def __init__(
        self,
        paper_title: str,
        findings: List[str],
        methods: str,
        limitations: str,
        relevance: str,
        query: Optional[str] = None,
        source_type: str = "unknown",
        cited_chunk_ids: Optional[List[str]] = None,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    ):
        # -------------------------------------------------
        # Existing Research V1 fields
        # -------------------------------------------------

        self.paper_title = paper_title
        self.findings = findings
        self.methods = methods
        self.limitations = limitations
        self.relevance = relevance

        # -------------------------------------------------
        # Research V2 provenance
        # -------------------------------------------------

        self.query = query

        self.source_type = source_type

        self.cited_chunk_ids = (
            cited_chunk_ids
            if cited_chunk_ids is not None
            else []
        )

        self.retrieved_chunks = (
            retrieved_chunks
            if retrieved_chunks is not None
            else []
        )

    def to_dict(self):
        """
        Convert evidence into a serializable dictionary.
        """

        return {
            "paper_title": self.paper_title,
            "findings": self.findings,
            "methods": self.methods,
            "limitations": self.limitations,
            "relevance": self.relevance,
            "query": self.query,
            "source_type": self.source_type,
            "cited_chunk_ids": self.cited_chunk_ids,
            "retrieved_chunks": self.retrieved_chunks,
        }