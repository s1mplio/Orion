"""
APA 7 citations built from paper metadata.

Every in-text citation and reference entry is produced here from
OpenAlex metadata, never by the LLM, so references cannot be
invented. Generated text cites sources with keys such as
[chunk_p3_ab12cd34ef56] (a full-text passage) or [paper_4]
(a paper abstract); this module resolves those keys.
"""

import re


CITATION_BLOCK = re.compile(
    r"\[((?:\s*(?:chunk|paper)_[A-Za-z0-9_-]+\s*,?)+)\]"
)

CITATION_KEY = re.compile(
    r"(?:chunk|paper)_[A-Za-z0-9_-]+"
)


# =========================================================
# AUTHOR NAMES
# =========================================================

def _surname(name):
    parts = str(name).replace(",", " ").split()
    return parts[-1] if parts else str(name)


def _initials(name):
    parts = str(name).replace(",", " ").split()[:-1]

    initials = []

    for part in parts:
        for piece in part.split("-"):
            if piece:
                initials.append(f"{piece[0].upper()}.")

    return " ".join(initials)


def _apa_author(name):
    initials = _initials(name)
    surname = _surname(name)
    return f"{surname}, {initials}" if initials else surname


def _authors_list(paper):
    authors = paper.get("authors") or []

    if isinstance(authors, str):
        authors = [authors]

    return [str(author).strip() for author in authors if str(author).strip()]


# =========================================================
# IN-TEXT CITATION
# =========================================================

def in_text_author_year(paper):
    authors = _authors_list(paper)
    year = paper.get("year") or "n.d."

    if not authors:
        title = str(paper.get("title") or "Untitled")
        short_title = " ".join(title.split()[:4])
        lead = f"“{short_title}”"
    elif len(authors) == 1:
        lead = _surname(authors[0])
    elif len(authors) == 2:
        lead = f"{_surname(authors[0])} & {_surname(authors[1])}"
    else:
        lead = f"{_surname(authors[0])} et al."

    return f"{lead}, {year}"


def _page_label(source):
    start = source.get("page_start")
    end = source.get("page_end")

    if start is None:
        return ""

    if end is not None and end != start:
        return f", pp. {start}–{end}"

    return f", p. {start}"


def in_text(source):
    """(Author, Year, p. N) without the surrounding parentheses."""
    return in_text_author_year(source["paper"]) + _page_label(source)


# =========================================================
# REFERENCE ENTRY
# =========================================================

def _doi_url(doi):
    if not doi:
        return ""

    doi = str(doi).strip()

    if doi.startswith("http"):
        return doi

    return f"https://doi.org/{doi}"


def apa_reference(paper):
    authors = _authors_list(paper)

    if len(authors) > 20:
        names = [_apa_author(a) for a in authors[:19]]
        author_text = ", ".join(names) + ", ... " + _apa_author(authors[-1])
    elif len(authors) > 1:
        names = [_apa_author(a) for a in authors]
        author_text = ", ".join(names[:-1]) + ", & " + names[-1]
    elif authors:
        author_text = _apa_author(authors[0])
    else:
        author_text = ""

    year = paper.get("year") or "n.d."
    title = str(paper.get("title") or "Untitled").strip().rstrip(".")
    source_name = paper.get("source_name")
    link = (
        _doi_url(paper.get("doi"))
        or paper.get("landing_page_url")
        or paper.get("url")
        or ""
    )

    if author_text:
        entry = f"{author_text} ({year}). {title}."
    else:
        entry = f"{title}. ({year})."

    if source_name:
        entry += f" {source_name}."

    if link:
        entry += f" {link}"

    return entry


# =========================================================
# SOURCE MAP
# =========================================================

def _normalize_title(title):
    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()


def _normalize_doi(doi):
    doi = str(doi or "").strip().lower()
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "")


def build_sources(papers, evidence):
    """
    Map every citable key to its paper and page range.

    papers and evidence are serialized dicts. Returns
    {key: {"key", "paper_index", "paper", "page_start",
    "page_end", "section", "in_text"}}.
    """

    by_doi = {}
    by_title = {}

    for index, paper in enumerate(papers):
        doi = _normalize_doi(paper.get("doi"))

        if doi:
            by_doi.setdefault(doi, index)

        by_title.setdefault(_normalize_title(paper.get("title")), index)

    sources = {}

    for index, paper in enumerate(papers, start=1):
        key = f"paper_{index}"
        sources[key] = {
            "key": key,
            "paper_index": index - 1,
            "paper": paper,
            "page_start": None,
            "page_end": None,
            "section": None,
        }

    for item in evidence:
        for chunk in item.get("retrieved_chunks") or []:
            chunk_id = chunk.get("chunk_id")

            if not chunk_id or chunk_id in sources:
                continue

            paper_index = by_doi.get(_normalize_doi(chunk.get("doi")))

            if paper_index is None:
                paper_index = by_title.get(
                    _normalize_title(chunk.get("paper_title"))
                )

            if paper_index is not None:
                paper = papers[paper_index]
            else:
                paper = {
                    "title": chunk.get("paper_title"),
                    "doi": chunk.get("doi"),
                    "authors": [],
                }

            sources[chunk_id] = {
                "key": chunk_id,
                "paper_index": paper_index,
                "paper": paper,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "section": chunk.get("section"),
            }

    for source in sources.values():
        source["in_text"] = in_text(source)

    return sources


# =========================================================
# TEXT RENDERING
# =========================================================

def cited_keys(texts, sources):
    """Valid source keys cited in the given texts, in order."""
    seen = []

    for text in texts:
        for key in CITATION_KEY.findall(str(text or "")):
            if key in sources and key not in seen:
                seen.append(key)

    return seen


def render_citations(text, sources):
    """
    Replace [key, key] blocks with APA parenthetical
    citations. Unknown keys are dropped rather than shown.
    """

    def replace(match):
        keys = [
            key.strip()
            for key in match.group(1).split(",")
            if key.strip() in sources
        ]

        if not keys:
            return ""

        parts = []

        for key in keys:
            label = sources[key]["in_text"]

            if label not in parts:
                parts.append(label)

        return f"({'; '.join(parts)})"

    rendered = CITATION_BLOCK.sub(replace, str(text or ""))

    # Tidy spacing left behind by removed citations.
    rendered = re.sub(r"\s+([.,;:])", r"\1", rendered)

    return re.sub(r"[ \t]{2,}", " ", rendered).strip()


def strip_unknown_citations(text, sources):
    """Remove citation keys that do not resolve to a source."""

    def replace(match):
        keys = [
            key.strip()
            for key in match.group(1).split(",")
            if key.strip() in sources
        ]

        return f"[{', '.join(keys)}]" if keys else ""

    cleaned = CITATION_BLOCK.sub(replace, str(text or ""))
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)

    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def reference_list(keys, sources):
    """APA reference entries for the papers behind the keys, sorted."""
    papers = {}

    for key in keys:
        source = sources.get(key)

        if not source:
            continue

        paper = source["paper"]
        identity = (
            _normalize_doi(paper.get("doi"))
            or _normalize_title(paper.get("title"))
        )

        papers.setdefault(identity, paper)

    entries = [apa_reference(paper) for paper in papers.values()]

    return sorted(entries, key=lambda entry: entry.lower())
