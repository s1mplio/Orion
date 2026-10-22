"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Printer } from "lucide-react";

import LiteratureReview from "@/components/Report/LiteratureReview";
import {
    ApaText,
    paragraphs,
    type LiteratureReviewData,
    type SourceMap,
} from "@/lib/citations";
import api, { getErrorMessage } from "@/services/api";

interface PrintableResult {
    question: string;
    literature_review?: LiteratureReviewData | null;
    synthesis?: {
        summary?: string;
        key_findings?: string[];
    } | null;
    sources?: SourceMap;
    references?: string[];
}

export default function PrintReportPage() {
    const params = useParams();

    const jobId = Array.isArray(params.jobId)
        ? params.jobId[0]
        : params.jobId;

    const [data, setData] = useState<PrintableResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!jobId) {
            return;
        }

        api.get(`/research/${jobId}/result`)
            .then((response) => {
                if (!response.data.ready) {
                    setError("This research is still running.");
                    return;
                }

                setData(response.data.result);
            })
            .catch((err) => {
                setError(
                    getErrorMessage(err, "Failed to load the report.")
                );
            });
    }, [jobId]);

    if (error) {
        return (
            <main className="min-h-screen bg-white p-12 text-center text-red-600">
                {error}
            </main>
        );
    }

    if (!data) {
        return (
            <main className="min-h-screen bg-white p-12 text-center text-neutral-500">
                Preparing printable report...
            </main>
        );
    }

    const sources = data.sources || {};
    const references = data.references || [];

    return (
        <main className="min-h-screen bg-white font-serif text-black">

            <div className="sticky top-0 border-b border-neutral-200 bg-white/95 print:hidden">
                <div className="mx-auto flex max-w-3xl items-center justify-between px-8 py-4">
                    <p className="text-sm text-neutral-600">
                        In the print dialog, choose &ldquo;Save as PDF&rdquo;.
                    </p>

                    <button
                        onClick={() => window.print()}
                        className="inline-flex items-center gap-2 rounded-lg bg-black px-4 py-2 font-sans text-sm text-white hover:bg-neutral-800"
                    >
                        <Printer size={16} />
                        Print / Save as PDF
                    </button>
                </div>
            </div>

            <div className="mx-auto max-w-3xl px-8 py-12 print:px-0 print:py-0">

                <p className="mb-6 text-center text-sm italic text-neutral-600">
                    Research question: {data.question}
                </p>

                {data.literature_review ? (
                    <LiteratureReview
                        review={data.literature_review}
                        sources={sources}
                        references={references}
                        variant="print"
                    />
                ) : (
                    <article>
                        <h2 className="text-center text-2xl font-bold">
                            Research Summary
                        </h2>

                        {paragraphs(data.synthesis?.summary).map(
                            (part, index) => (
                                <p
                                    key={index}
                                    className="mt-4 text-justify leading-7"
                                >
                                    <ApaText
                                        text={part}
                                        sources={sources}
                                        linkClassName="text-black no-underline"
                                    />
                                </p>
                            )
                        )}

                        {(data.synthesis?.key_findings || []).length > 0 && (
                            <>
                                <h3 className="mt-8 mb-3 text-xl font-bold">
                                    Key Findings
                                </h3>

                                <ul className="list-disc space-y-2 pl-6">
                                    {(data.synthesis?.key_findings || []).map(
                                        (finding, index) => (
                                            <li key={index} className="leading-7">
                                                <ApaText
                                                    text={finding}
                                                    sources={sources}
                                                    linkClassName="text-black no-underline"
                                                />
                                            </li>
                                        )
                                    )}
                                </ul>
                            </>
                        )}

                        {references.length > 0 && (
                            <>
                                <h3 className="mt-8 mb-3 text-xl font-bold">
                                    References
                                </h3>

                                <ol className="space-y-3">
                                    {references.map((entry, index) => (
                                        <li
                                            key={index}
                                            className="break-words pl-8 -indent-8 leading-7"
                                        >
                                            {entry}
                                        </li>
                                    ))}
                                </ol>
                            </>
                        )}
                    </article>
                )}

                <p className="mt-12 text-xs italic text-neutral-500">
                    Generated with Orion Research. Verify every citation
                    against the original source before submission.
                </p>
            </div>
        </main>
    );
}
