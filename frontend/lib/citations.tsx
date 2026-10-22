import type { ReactNode } from "react";

/* ========================================================
   TYPES
======================================================== */

export interface CitationSource {
    in_text: string;
    paper_index: number | null;
    page_start: number | null;
    page_end: number | null;
    section: string | null;
    title: string | null;
    reference_index: number | null;
}

export type SourceMap = Record<string, CitationSource>;

export interface ReviewTheme {
    title: string;
    discussion: string;
}

export interface LiteratureReviewData {
    title: string;
    abstract: string;
    introduction: string;
    themes: ReviewTheme[];
    research_gaps: string[];
    conclusion: string;
}

/* ========================================================
   CITATION PATTERNS
   Generated text cites sources as [chunk_...] (full-text
   passage) or [paper_N] (abstract), possibly comma-separated.
======================================================== */

export const CITATION_BLOCK_PATTERN =
    /\[((?:\s*(?:chunk|paper)_[A-Za-z0-9_-]+\s*,?)+)\]/g;

export const CITATION_KEY_PATTERN =
    /(?:chunk|paper)_[A-Za-z0-9_-]+/g;

/* ========================================================
   APA TEXT
   Renders [key, key] as "(Smith et al., 2021, p. 3; ...)"
   linking to the reference list. Unknown keys are hidden.
======================================================== */

export function ApaText({
    text,
    sources,
    linkClassName = "text-cyan-400 hover:text-cyan-300",
}: {
    text: string;
    sources: SourceMap;
    linkClassName?: string;
}) {
    if (!text) {
        return null;
    }

    const output: ReactNode[] = [];
    const pattern = new RegExp(CITATION_BLOCK_PATTERN.source, "g");

    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
        let before = text.slice(lastIndex, match.index);

        const keys = match[1]
            .split(",")
            .map((key) => key.trim())
            .filter((key) => key && sources[key]);

        if (keys.length === 0) {
            // Drop the space that preceded a removed citation.
            before = before.replace(/\s+$/, "");
        }

        output.push(before);

        if (keys.length > 0) {
            const labels: { label: string; key: string }[] = [];

            for (const key of keys) {
                const label = sources[key].in_text;

                if (!labels.some((item) => item.label === label)) {
                    labels.push({ label, key });
                }
            }

            output.push(
                <span key={`cite-${match.index}`}>
                    (
                    {labels.map((item, index) => {
                        const source = sources[item.key];
                        const href =
                            source.reference_index != null
                                ? `#ref-${source.reference_index}`
                                : undefined;

                        return (
                            <span key={item.key}>
                                {index > 0 && "; "}
                                {href ? (
                                    <a
                                        href={href}
                                        title={source.title || undefined}
                                        className={linkClassName}
                                    >
                                        {item.label}
                                    </a>
                                ) : (
                                    item.label
                                )}
                            </span>
                        );
                    })}
                    )
                </span>
            );
        }

        lastIndex = pattern.lastIndex;
    }

    output.push(text.slice(lastIndex));

    return <>{output}</>;
}

/* ========================================================
   HELPERS
======================================================== */

export function paragraphs(text?: string | null): string[] {
    return (text || "")
        .split("\n")
        .map((part) => part.trim())
        .filter(Boolean);
}
