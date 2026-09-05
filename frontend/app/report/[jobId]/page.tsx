"use client";

import Sidebar from "@/components/Report/Sidebar";
import SectionCard from "@/components/Report/SectionCard";
import StatCard from "@/components/Report/StatCard";
import PaperCard from "@/components/Report/PaperCard";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import api from "@/services/api";

import {
    FileText,
    FlaskConical,
    Brain,
    CheckCircle,
    BookOpen,
    Microscope,
    ArrowLeft,
    Database,
    Search,
    ExternalLink,
} from "lucide-react";


/* ========================================================
   TYPES
======================================================== */

interface Paper {
    title: string;
    authors: string[] | string;
    year: number | null;
    url: string | null;
    doi?: string | null;
    citation_count: number;
    landing_page_url?: string | null;
    pdf_url?: string | null;
    is_open_access?: boolean;
    open_access_status?: string | null;
    source_name?: string | null;
    full_text_available?: boolean;
}


interface RetrievedChunk {
    chunk_id?: string;
    paper_id?: string | null;
    paper_title?: string;
    doi?: string | null;
    section?: string;
    page_start?: number;
    page_end?: number;
    retrieval_score?: number;
}


interface Evidence {
    paper_title: string;
    findings: string[];
    methods: string;
    limitations: string;
    relevance: string;
    query?: string | null;
    source_type?: string;
    cited_chunk_ids?: string[];
    retrieved_chunks?: RetrievedChunk[];
}


interface Synthesis {
    summary?: string;
    key_findings?: string[];
    limitations?: string[];
    future_work?: string[];
}


interface Hypothesis {
    hypothesis?: string;
    reasoning?: string;
    assumptions?: string[];
}


interface HypothesisReview {
    strengths?: string[];
    weaknesses?: string[];
    supported_by_evidence?: boolean;
    confidence?: string;
    recommendation?: string;
}


interface Experiment {
    title?: string;
    objective?: string;
    methodology?: string[];
    required_data?: string[];
    expected_outcomes?: string[];
    evaluation_metrics?: string[];
    limitations?: string[];
}


interface FinalReport {
    research_question?: string;
    summary?: string;
    key_findings?: string[];

    hypothesis?: string;
    hypothesis_reasoning?: string;

    experiment_title?: string;
    experiment_objective?: string;
    experiment_methodology?: string[];

    expected_outcomes?: string[];

    limitations?: string[];

    future_work?: string[];
}


interface ResearchResult {
    question: string;
    sub_questions: string[];
    papers: Paper[];
    evidence: Evidence[];

    critic?: Record<string, unknown> | null;
    synthesis?: Synthesis | null;
    hypothesis?: Hypothesis | null;
    hypothesis_review?: HypothesisReview | null;
    experiment?: Experiment | null;
    final_report?: FinalReport | null;
}


interface ApiResponse {
    job_id: string;
    status: string;
    ready: boolean;
    result: ResearchResult;
}


interface CitationSource {
    number: number;
    chunkId: string;
    paperTitle: string;
    doi?: string | null;
    section?: string;
    pageStart?: number;
    pageEnd?: number;
    paperUrl?: string | null;
}


/* ========================================================
   CITATION HELPERS
======================================================== */

function normalizeDoiUrl(
    doi?: string | null
) {

    if (!doi) {
        return null;
    }

    if (
        doi.startsWith("http://") ||
        doi.startsWith("https://")
    ) {
        return doi;
    }

    return `https://doi.org/${doi}`;
}


function buildCitationSources(
    data: ResearchResult
): CitationSource[] {

    const chunkMap =
        new Map<string, RetrievedChunk>();


    for (const evidence of data.evidence) {

        for (
            const chunk of
            evidence.retrieved_chunks || []
        ) {

            if (!chunk.chunk_id) {
                continue;
            }

            if (!chunkMap.has(chunk.chunk_id)) {

                chunkMap.set(
                    chunk.chunk_id,
                    chunk
                );

            }

        }

    }


    const citedChunkIds: string[] = [];

    const seen =
        new Set<string>();


    /*
     * First use explicit evidence citations.
     */

    for (const evidence of data.evidence) {

        for (
            const chunkId of
            evidence.cited_chunk_ids || []
        ) {

            if (!seen.has(chunkId)) {

                seen.add(chunkId);

                citedChunkIds.push(
                    chunkId
                );

            }

        }

    }


    /*
     * Generated synthesis/final-report text can contain
     * chunk IDs that are not present in cited_chunk_ids.
     *
     * Scan the generated text and include those as well.
     */

    const generatedTexts: string[] = [];


    if (data.synthesis?.summary) {
        generatedTexts.push(
            data.synthesis.summary
        );
    }


    generatedTexts.push(
        ...(data.synthesis?.key_findings || []),
        ...(data.synthesis?.limitations || []),
        ...(data.synthesis?.future_work || [])
    );


    if (data.final_report?.summary) {
        generatedTexts.push(
            data.final_report.summary
        );
    }


    generatedTexts.push(
        ...(data.final_report?.key_findings || []),
        ...(data.final_report?.limitations || []),
        ...(data.final_report?.future_work || [])
    );


    if (data.hypothesis?.hypothesis) {
        generatedTexts.push(
            data.hypothesis.hypothesis
        );
    }


    if (data.hypothesis?.reasoning) {
        generatedTexts.push(
            data.hypothesis.reasoning
        );
    }


    if (data.final_report?.hypothesis) {
        generatedTexts.push(
            data.final_report.hypothesis
        );
    }


    if (
        data.final_report
            ?.hypothesis_reasoning
    ) {

        generatedTexts.push(
            data.final_report
                .hypothesis_reasoning
        );

    }


    const chunkRegex =
        /chunk_[A-Za-z0-9_-]+/g;


    for (const text of generatedTexts) {

        const matches =
            text.match(chunkRegex) || [];


        for (const chunkId of matches) {

            if (!seen.has(chunkId)) {

                seen.add(chunkId);

                citedChunkIds.push(
                    chunkId
                );

            }

        }

    }


    return citedChunkIds.map(
        (
            chunkId,
            index
        ) => {

            const chunk =
                chunkMap.get(chunkId);


            const matchingPaper =
                data.papers.find(
                    (paper) => {

                        if (
                            chunk?.doi &&
                            paper.doi
                        ) {

                            return (
                                paper.doi ===
                                chunk.doi
                            );

                        }

                        return (
                            paper.title ===
                            chunk?.paper_title
                        );

                    }
                );


            return {
                number: index + 1,

                chunkId,

                paperTitle:
                    chunk?.paper_title ||
                    matchingPaper?.title ||
                    "Scientific source",

                doi:
                    chunk?.doi ||
                    matchingPaper?.doi,

                section:
                    chunk?.section,

                pageStart:
                    chunk?.page_start,

                pageEnd:
                    chunk?.page_end,

                paperUrl:
                    matchingPaper
                        ?.landing_page_url ||
                    matchingPaper
                        ?.doi ||
                    matchingPaper
                        ?.url ||
                    null,
            };

        }
    );

}


function getPageLabel(
    source: CitationSource
) {

    if (
        source.pageStart == null
    ) {
        return null;
    }


    if (
        source.pageEnd != null &&
        source.pageEnd !==
            source.pageStart
    ) {

        return (
            `Pages ${source.pageStart}–${source.pageEnd}`
        );

    }


    return `Page ${source.pageStart}`;
}


function getSourceMetadata(
    source: CitationSource
) {

    const parts: string[] = [];


    if (
        source.section &&
        source.section.toLowerCase() !==
            "unknown"
    ) {

        parts.push(
            source.section
        );

    }


    const page =
        getPageLabel(source);


    if (page) {

        parts.push(page);

    }


    return parts.join(" • ");
}


/* ========================================================
   CITATION TEXT RENDERER
======================================================== */

function CitationText({
    text,
    citations,
}: {
    text: string;
    citations: CitationSource[];
}) {

    if (!text) {
        return null;
    }


    const citationMap =
        new Map<string, CitationSource>();


    citations.forEach(
        (citation) => {

            citationMap.set(
                citation.chunkId,
                citation
            );

        }
    );


    /*
     * Match citation blocks such as:
     *
     * [chunk_x]
     *
     * [chunk_x, chunk_y, chunk_z]
     */

    const citationBlockRegex =
        /\[((?:\s*chunk_[A-Za-z0-9_-]+\s*,?)+)\]/g;


    const output: React.ReactNode[] = [];

    let lastIndex = 0;

    let match:
        RegExpExecArray | null;


    while (
        (
            match =
                citationBlockRegex.exec(text)
        ) !== null
    ) {

        if (
            match.index >
            lastIndex
        ) {

            output.push(
                text.slice(
                    lastIndex,
                    match.index
                )
            );

        }


        const ids =
            match[1]
                .split(",")
                .map(
                    (value) =>
                        value.trim()
                )
                .filter(Boolean);


        const validSources =
            ids
                .map(
                    (id) =>
                        citationMap.get(id)
                )
                .filter(
                    (
                        source
                    ): source is CitationSource =>
                        Boolean(source)
                );


        if (
            validSources.length > 0
        ) {

            output.push(

                <span
                    key={
                        `citation-${match.index}`
                    }
                    className="inline-flex flex-wrap gap-1 ml-1 align-baseline"
                >

                    {validSources.map(
                        (source) => (

                            <a
                                key={
                                    source.chunkId
                                }
                                href={
                                    `#source-${source.number}`
                                }
                                title={
                                    `${source.paperTitle}${
                                        getSourceMetadata(
                                            source
                                        )
                                            ? ` — ${getSourceMetadata(
                                                  source
                                              )}`
                                            : ""
                                    }`
                                }
                                className="
                                text-cyan-400
                                hover:text-cyan-300
                                font-medium
                                no-underline
                                "
                            >

                                [{source.number}]

                            </a>

                        )
                    )}

                </span>

            );

        }

        /*
         * If metadata cannot be resolved, hide the raw
         * internal chunk identifier instead of exposing it.
         */

        lastIndex =
            citationBlockRegex.lastIndex;

    }


    if (
        lastIndex <
        text.length
    ) {

        output.push(
            text.slice(
                lastIndex
            )
        );

    }


    return <>{output}</>;

}


/* ========================================================
   STRING LIST
======================================================== */

function StringList({
    items,
    citations,
}: {
    items?: string[];
    citations?: CitationSource[];
}) {

    if (
        !items ||
        items.length === 0
    ) {

        return (

            <p className="text-neutral-500">

                No information available.

            </p>

        );

    }


    return (

        <ul className="space-y-3">

            {items.map(
                (
                    item,
                    index
                ) => (

                    <li
                        key={index}
                        className="flex gap-3 text-neutral-300 leading-7"
                    >

                        <span className="text-cyan-400 mt-1">

                            •

                        </span>


                        <span>

                            {citations ? (

                                <CitationText
                                    text={item}
                                    citations={
                                        citations
                                    }
                                />

                            ) : (

                                item

                            )}

                        </span>

                    </li>

                )
            )}

        </ul>

    );

}


/* ========================================================
   PAGE
======================================================== */

export default function ReportPage() {

    const params =
        useParams();

    const router =
        useRouter();


    const jobId =
        Array.isArray(
            params.jobId
        )
            ? params.jobId[0]
            : params.jobId;


    const [
        data,
        setData
    ] =
        useState<ResearchResult | null>(
            null
        );


    const [
        loading,
        setLoading
    ] =
        useState(true);


    const [
        error,
        setError
    ] =
        useState<string | null>(
            null
        );


    /* ====================================================
       LOAD REPORT
    ==================================================== */

    useEffect(() => {

        async function loadReport() {

            try {

                const response =
                    await api.get<ApiResponse>(
                        `/research/${jobId}/result`
                    );


                if (
                    !response.data.ready ||
                    !response.data.result
                ) {

                    setError(
                        "Research report is not ready yet."
                    );

                    return;

                }


                setData(
                    response.data.result
                );

            } catch (err) {

                console.error(
                    "Failed to load report:",
                    err
                );


                setError(
                    "Failed to load the research report."
                );

            } finally {

                setLoading(false);

            }

        }


        if (jobId) {
            loadReport();
        }

    }, [jobId]);


    /* ====================================================
       CITATIONS
    ==================================================== */

    const citations =
        useMemo(
            () =>
                data
                    ? buildCitationSources(
                          data
                      )
                    : [],
            [data]
        );


    /* ====================================================
       LOADING
    ==================================================== */

    if (loading) {

        return (

            <div className="min-h-screen bg-black flex items-center justify-center">

                <div className="text-center">

                    <Brain
                        className="
                        mx-auto
                        mb-6
                        h-16
                        w-16
                        text-cyan-400
                        animate-pulse
                        "
                    />

                    <h1 className="text-3xl text-white font-bold">

                        Orion

                    </h1>

                    <p className="text-neutral-400 mt-3">

                        Preparing Scientific Report...

                    </p>

                </div>

            </div>

        );

    }


    /* ====================================================
       ERROR
    ==================================================== */

    if (
        error ||
        !data
    ) {

        return (

            <div className="min-h-screen bg-black flex items-center justify-center px-6">

                <div className="text-center">

                    <h1 className="text-2xl text-red-400 font-semibold">

                        {error ||
                            "Failed to load report."}

                    </h1>


                    <button
                        onClick={
                            () =>
                                router.push(
                                    "/"
                                )
                        }
                        className="
                        mt-6
                        rounded-xl
                        bg-cyan-600
                        px-6
                        py-3
                        text-white
                        hover:bg-cyan-500
                        "
                    >

                        Return Home

                    </button>

                </div>

            </div>

        );

    }


    /* ====================================================
       REPORT DATA
    ==================================================== */

    const report =
        data.final_report;

    const hypothesis =
        data.hypothesis;

    const experiment =
        data.experiment;

    const review =
        data.hypothesis_review;

    const synthesis =
        data.synthesis;


    const summary =
        report?.summary ||
        synthesis?.summary ||
        "No summary generated.";


    const keyFindings =
        report?.key_findings ||
        synthesis?.key_findings ||
        [];


    const hypothesisText =
        report?.hypothesis ||
        hypothesis?.hypothesis ||
        "No hypothesis generated.";


    const hypothesisReasoning =
        report?.hypothesis_reasoning ||
        hypothesis?.reasoning ||
        "";


    const experimentTitle =
        report?.experiment_title ||
        experiment?.title ||
        "Proposed Experiment";


    const experimentObjective =
        report?.experiment_objective ||
        experiment?.objective ||
        "";


    const experimentMethodology =
        report?.experiment_methodology ||
        experiment?.methodology ||
        [];


    const expectedOutcomes =
        report?.expected_outcomes ||
        experiment?.expected_outcomes ||
        [];


    const limitations =
        report?.limitations ||
        synthesis?.limitations ||
        [];


    const futureWork =
        report?.future_work ||
        synthesis?.future_work ||
        [];


    /* ====================================================
       UI
    ==================================================== */

    return (

        <div className="min-h-screen bg-black text-white">


            {/* TOP BAR */}

            <div className="border-b border-neutral-900">

                <div className="max-w-7xl mx-auto px-8 py-5 flex items-center justify-between">

                    <button
                        onClick={
                            () =>
                                router.push(
                                    "/"
                                )
                        }
                        className="
                        flex
                        items-center
                        gap-2
                        text-neutral-400
                        hover:text-white
                        transition
                        "
                    >

                        <ArrowLeft
                            size={18}
                        />

                        New Research

                    </button>


                    <div className="text-sm text-neutral-500">

                        Research V2

                    </div>

                </div>

            </div>


            {/* MAIN */}

            <div className="max-w-7xl mx-auto py-12 px-8">

                <div className="grid lg:grid-cols-[320px_1fr] gap-10">


                    <Sidebar
                        question={
                            data.question
                        }
                        papers={
                            data.papers.length
                        }
                    />


                    <div className="space-y-8">


                        {/* HEADER */}

                        <div className="text-center">

                            <h1 className="text-6xl font-bold">

                                Orion

                            </h1>

                            <p className="text-neutral-400 mt-3 text-xl">

                                Autonomous AI Research Scientist

                            </p>

                        </div>


                        {/* REPORT HEADER */}

                        <div className="rounded-3xl bg-neutral-900 border border-neutral-800 p-8">

                            <div className="text-sm uppercase tracking-wider text-cyan-400 font-medium">

                                Research Complete

                            </div>


                            <h2 className="text-4xl font-bold leading-tight mt-3">

                                {data.question}

                            </h2>


                            <div className="flex flex-wrap gap-6 mt-6 text-sm text-neutral-400">

                                <span>
                                    📚{" "}
                                    {data.papers.length}{" "}
                                    Papers
                                </span>

                                <span>
                                    🔎{" "}
                                    {data.evidence.length}{" "}
                                    Evidence Sets
                                </span>

                                <span>
                                    🧠 Research V2
                                </span>

                                <span>
                                    ⚡ Autonomous Pipeline
                                </span>

                            </div>

                        </div>


                        {/* STATS */}

                        <div className="grid md:grid-cols-3 gap-6">

                            <StatCard
                                icon={
                                    <BookOpen
                                        size={24}
                                    />
                                }
                                title="Papers"
                                value={String(
                                    data.papers.length
                                )}
                            />


                            <StatCard
                                icon={
                                    <Database
                                        size={24}
                                    />
                                }
                                title="Evidence Sets"
                                value={String(
                                    data.evidence.length
                                )}
                            />


                            <StatCard
                                icon={
                                    <CheckCircle
                                        size={24}
                                    />
                                }
                                title="Pipeline"
                                value="Completed"
                            />

                        </div>


                        {/* RESEARCH PLAN */}

                        <SectionCard
                            id="research-plan"
                            title="Research Plan"
                            icon={
                                <Search className="text-cyan-400" />
                            }
                        >

                            <StringList
                                items={
                                    data.sub_questions
                                }
                            />

                        </SectionCard>


                        {/* SUMMARY */}

                        <SectionCard
                            id="summary"
                            title="Executive Summary"
                            icon={
                                <FileText className="text-cyan-400" />
                            }
                        >

                            <p className="leading-8 text-neutral-300">

                                <CitationText
                                    text={summary}
                                    citations={
                                        citations
                                    }
                                />

                            </p>

                        </SectionCard>


                        {/* KEY FINDINGS */}

                        <SectionCard
                            id="findings"
                            title="Key Scientific Findings"
                            icon={
                                <Microscope className="text-cyan-400" />
                            }
                        >

                            <StringList
                                items={
                                    keyFindings
                                }
                                citations={
                                    citations
                                }
                            />

                        </SectionCard>


                        {/* EVIDENCE */}

                        <SectionCard
                            id="evidence"
                            title={`Evidence Analysis (${data.evidence.length})`}
                            icon={
                                <Microscope className="text-cyan-400" />
                            }
                        >

                            <div className="space-y-8">

                                {data.evidence.length ===
                                    0 && (

                                    <p className="text-neutral-500">

                                        No evidence available.

                                    </p>

                                )}


                                {data.evidence.map(
                                    (
                                        evidence,
                                        index
                                    ) => {

                                        const evidenceSources =
                                            citations.filter(
                                                (
                                                    source
                                                ) =>
                                                    (
                                                        evidence.cited_chunk_ids ||
                                                        []
                                                    ).includes(
                                                        source.chunkId
                                                    )
                                            );


                                        return (

                                            <div
                                                key={
                                                    index
                                                }
                                                className="
                                                rounded-2xl
                                                border
                                                border-neutral-800
                                                bg-neutral-950
                                                p-6
                                                "
                                            >

                                                <div className="flex flex-wrap items-center gap-3 mb-4">

                                                    <span className="text-sm text-cyan-400 font-semibold">

                                                        Evidence{" "}
                                                        {index +
                                                            1}

                                                    </span>


                                                    {evidence.source_type && (

                                                        <span className="
                                                        rounded-full
                                                        border
                                                        border-neutral-700
                                                        px-3
                                                        py-1
                                                        text-xs
                                                        text-neutral-400
                                                        ">

                                                            {evidence.source_type ===
                                                            "full_text_rag"
                                                                ? "Full-Paper Evidence"
                                                                : evidence.source_type}

                                                        </span>

                                                    )}

                                                </div>


                                                {evidence.query && (

                                                    <div className="mb-5">

                                                        <p className="text-sm text-neutral-500 mb-1">

                                                            Research Sub-question

                                                        </p>

                                                        <p className="font-medium">

                                                            {evidence.query}

                                                        </p>

                                                    </div>

                                                )}


                                                <div className="space-y-3">

                                                    {evidence.findings.map(
                                                        (
                                                            finding,
                                                            findingIndex
                                                        ) => (

                                                            <div
                                                                key={
                                                                    findingIndex
                                                                }
                                                                className="
                                                                border-l-2
                                                                border-cyan-500
                                                                pl-4
                                                                text-neutral-300
                                                                leading-7
                                                                "
                                                            >

                                                                <CitationText
                                                                    text={
                                                                        finding
                                                                    }
                                                                    citations={
                                                                        citations
                                                                    }
                                                                />

                                                            </div>

                                                        )
                                                    )}

                                                </div>


                                                {evidenceSources.length >
                                                    0 && (

                                                    <div className="mt-6 pt-5 border-t border-neutral-800">

                                                        <p className="text-xs uppercase tracking-wide text-neutral-500 mb-3">

                                                            Sources

                                                        </p>


                                                        <div className="space-y-3">

                                                            {evidenceSources.map(
                                                                (
                                                                    source
                                                                ) => (

                                                                    <a
                                                                        key={
                                                                            source.chunkId
                                                                        }
                                                                        href={
                                                                            `#source-${source.number}`
                                                                        }
                                                                        className="
                                                                        flex
                                                                        items-start
                                                                        gap-3
                                                                        rounded-xl
                                                                        border
                                                                        border-neutral-800
                                                                        bg-neutral-900/60
                                                                        p-3
                                                                        hover:border-cyan-800
                                                                        transition
                                                                        "
                                                                    >

                                                                        <span className="text-cyan-400 font-semibold">

                                                                            [{source.number}]

                                                                        </span>


                                                                        <div>

                                                                            <p className="text-sm text-neutral-200">

                                                                                {source.paperTitle}

                                                                            </p>


                                                                            {getSourceMetadata(
                                                                                source
                                                                            ) && (

                                                                                <p className="text-xs text-neutral-500 mt-1 capitalize">

                                                                                    {getSourceMetadata(
                                                                                        source
                                                                                    )}

                                                                                </p>

                                                                            )}

                                                                        </div>

                                                                    </a>

                                                                )
                                                            )}

                                                        </div>

                                                    </div>

                                                )}

                                            </div>

                                        );

                                    }
                                )}

                            </div>

                        </SectionCard>


                        {/* HYPOTHESIS */}

                        <SectionCard
                            id="hypothesis"
                            title="Scientific Hypothesis"
                            blue
                            icon={
                                <Brain className="text-cyan-400" />
                            }
                        >

                            <div className="space-y-5">

                                <p className="text-xl leading-8 font-medium">

                                    <CitationText
                                        text={
                                            hypothesisText
                                        }
                                        citations={
                                            citations
                                        }
                                    />

                                </p>


                                {hypothesisReasoning && (

                                    <div>

                                        <p className="text-sm text-neutral-500 mb-2">

                                            Reasoning

                                        </p>

                                        <p className="text-neutral-300 leading-7">

                                            <CitationText
                                                text={
                                                    hypothesisReasoning
                                                }
                                                citations={
                                                    citations
                                                }
                                            />

                                        </p>

                                    </div>

                                )}


                                {hypothesis?.assumptions &&
                                    hypothesis.assumptions
                                        .length >
                                        0 && (

                                    <div>

                                        <p className="text-sm text-neutral-500 mb-3">

                                            Assumptions

                                        </p>

                                        <StringList
                                            items={
                                                hypothesis.assumptions
                                            }
                                            citations={
                                                citations
                                            }
                                        />

                                    </div>

                                )}

                            </div>

                        </SectionCard>


                        {/* REVIEW */}

                        {review && (

                            <SectionCard
                                id="review"
                                title="Hypothesis Review"
                                icon={
                                    <CheckCircle className="text-cyan-400" />
                                }
                            >

                                <div className="space-y-6">

                                    <div className="grid md:grid-cols-3 gap-4">

                                        <div className="rounded-xl border border-neutral-800 p-4">

                                            <p className="text-neutral-500 text-sm">
                                                Recommendation
                                            </p>

                                            <p className="font-semibold mt-1">
                                                {review.recommendation ||
                                                    "N/A"}
                                            </p>

                                        </div>


                                        <div className="rounded-xl border border-neutral-800 p-4">

                                            <p className="text-neutral-500 text-sm">
                                                Confidence
                                            </p>

                                            <p className="font-semibold mt-1">
                                                {review.confidence ||
                                                    "N/A"}
                                            </p>

                                        </div>


                                        <div className="rounded-xl border border-neutral-800 p-4">

                                            <p className="text-neutral-500 text-sm">
                                                Evidence Supported
                                            </p>

                                            <p className="font-semibold mt-1">
                                                {review.supported_by_evidence
                                                    ? "Yes"
                                                    : "No"}
                                            </p>

                                        </div>

                                    </div>


                                    {review.strengths &&
                                        review.strengths
                                            .length >
                                            0 && (

                                        <div>

                                            <p className="font-semibold mb-3">
                                                Strengths
                                            </p>

                                            <StringList
                                                items={
                                                    review.strengths
                                                }
                                                citations={
                                                    citations
                                                }
                                            />

                                        </div>

                                    )}


                                    {review.weaknesses &&
                                        review.weaknesses
                                            .length >
                                            0 && (

                                        <div>

                                            <p className="font-semibold mb-3">
                                                Weaknesses
                                            </p>

                                            <StringList
                                                items={
                                                    review.weaknesses
                                                }
                                                citations={
                                                    citations
                                                }
                                            />

                                        </div>

                                    )}

                                </div>

                            </SectionCard>

                        )}


                        {/* EXPERIMENT */}

                        <SectionCard
                            id="experiment"
                            title="Experiment Plan"
                            icon={
                                <FlaskConical className="text-cyan-400" />
                            }
                        >

                            <div className="space-y-7">

                                <div>

                                    <h3 className="text-xl font-semibold">

                                        {experimentTitle}

                                    </h3>


                                    {experimentObjective && (

                                        <p className="text-neutral-300 mt-3 leading-7">

                                            <CitationText
                                                text={
                                                    experimentObjective
                                                }
                                                citations={
                                                    citations
                                                }
                                            />

                                        </p>

                                    )}

                                </div>


                                <div>

                                    <p className="font-semibold mb-3">
                                        Methodology
                                    </p>

                                    <StringList
                                        items={
                                            experimentMethodology
                                        }
                                        citations={
                                            citations
                                        }
                                    />

                                </div>


                                {experiment?.required_data &&
                                    experiment.required_data
                                        .length >
                                        0 && (

                                    <div>

                                        <p className="font-semibold mb-3">
                                            Required Data
                                        </p>

                                        <StringList
                                            items={
                                                experiment.required_data
                                            }
                                            citations={
                                                citations
                                            }
                                        />

                                    </div>

                                )}


                                <div>

                                    <p className="font-semibold mb-3">
                                        Expected Outcomes
                                    </p>

                                    <StringList
                                        items={
                                            expectedOutcomes
                                        }
                                        citations={
                                            citations
                                        }
                                    />

                                </div>


                                {experiment?.evaluation_metrics &&
                                    experiment.evaluation_metrics
                                        .length >
                                        0 && (

                                    <div>

                                        <p className="font-semibold mb-3">
                                            Evaluation Metrics
                                        </p>

                                        <StringList
                                            items={
                                                experiment.evaluation_metrics
                                            }
                                        />

                                    </div>

                                )}

                            </div>

                        </SectionCard>


                        {/* LIMITATIONS */}

                        <SectionCard
                            id="limitations"
                            title="Limitations"
                            icon={
                                <FileText className="text-cyan-400" />
                            }
                        >

                            <StringList
                                items={
                                    limitations
                                }
                                citations={
                                    citations
                                }
                            />

                        </SectionCard>


                        {/* FUTURE WORK */}

                        <SectionCard
                            id="future"
                            title="Future Work"
                            icon={
                                <Brain className="text-cyan-400" />
                            }
                        >

                            <StringList
                                items={
                                    futureWork
                                }
                                citations={
                                    citations
                                }
                            />

                        </SectionCard>


                        {/* CITED EVIDENCE SOURCES */}

                        {citations.length >
                            0 && (

                            <SectionCard
                                id="citations"
                                title={`Cited Evidence (${citations.length})`}
                                icon={
                                    <BookOpen className="text-cyan-400" />
                                }
                            >

                                <div className="space-y-4">

                                    {citations.map(
                                        (
                                            source
                                        ) => {

                                            const sourceUrl =
                                                normalizeDoiUrl(
                                                    source.doi
                                                ) ||
                                                source.paperUrl;


                                            return (

                                                <div
                                                    key={
                                                        source.chunkId
                                                    }
                                                    id={
                                                        `source-${source.number}`
                                                    }
                                                    className="
                                                    scroll-mt-8
                                                    rounded-2xl
                                                    border
                                                    border-neutral-800
                                                    bg-neutral-950
                                                    p-5
                                                    "
                                                >

                                                    <div className="flex items-start gap-4">

                                                        <span className="text-cyan-400 text-lg font-bold">

                                                            [{source.number}]

                                                        </span>


                                                        <div className="flex-1">

                                                            <p className="font-semibold leading-6">

                                                                {source.paperTitle}

                                                            </p>


                                                            {getSourceMetadata(
                                                                source
                                                            ) && (

                                                                <p className="text-sm text-neutral-500 mt-2 capitalize">

                                                                    {getSourceMetadata(
                                                                        source
                                                                    )}

                                                                </p>

                                                            )}


                                                            {sourceUrl && (

                                                                <a
                                                                    href={
                                                                        sourceUrl
                                                                    }
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="
                                                                    inline-flex
                                                                    items-center
                                                                    gap-2
                                                                    mt-3
                                                                    text-sm
                                                                    text-cyan-400
                                                                    hover:text-cyan-300
                                                                    "
                                                                >

                                                                    View source

                                                                    <ExternalLink
                                                                        size={
                                                                            14
                                                                        }
                                                                    />

                                                                </a>

                                                            )}

                                                        </div>

                                                    </div>

                                                </div>

                                            );

                                        }
                                    )}

                                </div>

                            </SectionCard>

                        )}


                        {/* ALL DISCOVERED PAPERS */}

                        <SectionCard
                            id="references"
                            title={`Scientific Papers (${data.papers.length})`}
                            icon={
                                <BookOpen className="text-cyan-400" />
                            }
                        >

                            <div className="space-y-6">

                                {data.papers.length ===
                                    0 && (

                                    <p className="text-neutral-500">

                                        No papers available.

                                    </p>

                                )}


                                {data.papers.map(
                                    (
                                        paper,
                                        index
                                    ) => (

                                        <PaperCard
                                            key={
                                                index
                                            }
                                            paper={{
                                                title:
                                                    paper.title,

                                                authors:
                                                    paper.authors,

                                                year:
                                                    paper.year ??
                                                    0,

                                                url:
                                                    paper.landing_page_url ||
                                                    paper.doi ||
                                                    paper.url ||
                                                    "#",

                                                citation_count:
                                                    paper.citation_count,
                                            }}
                                        />

                                    )
                                )}

                            </div>

                        </SectionCard>

                    </div>

                </div>

            </div>


            <footer className="border-t border-neutral-800 mt-16 py-8 text-center text-neutral-500">

                <p className="text-sm">

                    Generated autonomously by Orion • Full-Paper RAG • Multi-Agent Scientific Research System

                </p>

            </footer>

        </div>

    );

}