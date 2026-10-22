"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    ArrowLeft,
    Download,
    Loader2,
    Printer,
    RefreshCw,
} from "lucide-react";

import { clock, entryTime, type LabSession } from "@/lib/lab";
import api, { API_BASE_URL, getErrorMessage } from "@/services/api";

function ListSection({
    title,
    items,
    ordered = false,
}: {
    title: string;
    items?: string[];
    ordered?: boolean;
}) {
    if (!items || items.length === 0) {
        return null;
    }

    const List = ordered ? "ol" : "ul";

    return (
        <section>
            <h2 className="mb-2 mt-8 text-lg font-bold">{title}</h2>
            <List className={`space-y-1 pl-6 ${ordered ? "list-decimal" : "list-disc"}`}>
                {items.map((item, index) => (
                    <li key={index} className="leading-7">
                        {item}
                    </li>
                ))}
            </List>
        </section>
    );
}

export default function LabNotebookPage() {
    const params = useParams();
    const router = useRouter();

    const sessionId = Array.isArray(params.sessionId)
        ? params.sessionId[0]
        : params.sessionId;

    const [session, setSession] = useState<LabSession | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [generating, setGenerating] = useState(false);

    useEffect(() => {
        if (!sessionId) {
            return;
        }

        api.get(`/lab/sessions/${sessionId}`)
            .then((response) => setSession(response.data))
            .catch((err) =>
                setError(getErrorMessage(err, "Failed to load the notebook."))
            );
    }, [sessionId]);

    async function regenerate() {
        setGenerating(true);

        try {
            const response = await api.post(`/lab/sessions/${sessionId}/notebook`);
            const entries = session?.entries;
            setSession({ ...response.data, entries });
        } catch (err) {
            alert(getErrorMessage(err, "Failed to write the notebook."));
        } finally {
            setGenerating(false);
        }
    }

    if (error) {
        return (
            <main className="min-h-screen bg-white p-12 text-center text-red-600">
                {error}
            </main>
        );
    }

    if (!session) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-white text-neutral-500">
                <Loader2 className="mr-3 h-5 w-5 animate-spin" />
                Loading notebook...
            </main>
        );
    }

    const notebook = session.notebook;
    const photos = (session.entries || []).filter((entry) => entry.has_image);

    return (
        <main className="min-h-screen bg-white text-black">

            <div className="sticky top-0 z-10 border-b border-neutral-200 bg-white/95 print:hidden">
                <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-8 py-4">
                    <button
                        onClick={() => router.push("/lab")}
                        className="flex items-center gap-2 text-sm text-neutral-600 hover:text-black"
                    >
                        <ArrowLeft size={16} />
                        Sessions
                    </button>

                    <div className="flex flex-wrap gap-2">
                        <button
                            onClick={regenerate}
                            disabled={generating}
                            className="inline-flex items-center gap-2 rounded-lg border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-100 disabled:opacity-50"
                        >
                            {generating ? (
                                <Loader2 size={16} className="animate-spin" />
                            ) : (
                                <RefreshCw size={16} />
                            )}
                            {notebook ? "Regenerate" : "Write Notebook"}
                        </button>

                        {notebook && (
                            <>
                                <a
                                    href={`${API_BASE_URL}/lab/sessions/${sessionId}/export/docx`}
                                    className="inline-flex items-center gap-2 rounded-lg border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-100"
                                >
                                    <Download size={16} />
                                    Word
                                </a>

                                <button
                                    onClick={() => window.print()}
                                    className="inline-flex items-center gap-2 rounded-lg bg-black px-3 py-2 text-sm text-white hover:bg-neutral-800"
                                >
                                    <Printer size={16} />
                                    Print / PDF
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>

            <article className="mx-auto max-w-3xl px-8 py-12 print:px-0 print:py-0">

                {!notebook ? (
                    <p className="text-center text-neutral-500">
                        No notebook has been written for this session yet.
                    </p>
                ) : (
                    <>
                        <h1 className="text-center text-3xl font-bold">
                            {notebook.title}
                        </h1>

                        <p className="mt-2 text-center text-sm italic text-neutral-600">
                            {new Date(session.created_at).toLocaleDateString()}{" "}
                            {clock(session.created_at)}
                            {session.ended_at && ` to ${clock(session.ended_at)}`}
                        </p>

                        {notebook.objective && (
                            <section>
                                <h2 className="mb-2 mt-8 text-lg font-bold">Objective</h2>
                                <p className="leading-7">{notebook.objective}</p>
                            </section>
                        )}

                        {notebook.background?.text && (
                            <section>
                                <h2 className="mb-2 mt-8 text-lg font-bold">Background</h2>
                                <p className="text-justify leading-7">
                                    {notebook.background.text}
                                </p>
                            </section>
                        )}

                        <ListSection title="Materials" items={notebook.materials} />
                        <ListSection title="Equipment" items={notebook.equipment} />

                        {notebook.procedure.length > 0 && (
                            <section>
                                <h2 className="mb-2 mt-8 text-lg font-bold">Procedure</h2>
                                <ol className="list-decimal space-y-1 pl-6">
                                    {notebook.procedure.map((item, index) => (
                                        <li key={index} className="leading-7">
                                            {item.time && (
                                                <span className="mr-2 font-semibold">
                                                    {item.time}
                                                </span>
                                            )}
                                            {item.step}
                                        </li>
                                    ))}
                                </ol>
                            </section>
                        )}

                        <ListSection title="Observations" items={notebook.observations} />
                        <ListSection title="Deviations from Protocol" items={notebook.deviations} />
                        <ListSection title="Safety Notes" items={notebook.safety_notes} />

                        {notebook.summary && (
                            <section>
                                <h2 className="mb-2 mt-8 text-lg font-bold">Summary</h2>
                                <p className="leading-7">{notebook.summary}</p>
                            </section>
                        )}

                        {(notebook.background?.references || []).length > 0 && (
                            <section>
                                <h2 className="mb-2 mt-8 text-lg font-bold">References</h2>
                                <ol className="space-y-2">
                                    {notebook.background!.references.map((entry, index) => (
                                        <li key={index} className="break-words pl-8 -indent-8 leading-7">
                                            {entry}
                                        </li>
                                    ))}
                                </ol>
                            </section>
                        )}
                    </>
                )}

                {photos.length > 0 && (
                    <section className="print:break-before-page">
                        <h2 className="mb-4 mt-10 text-lg font-bold">Photographic Record</h2>

                        <div className="grid grid-cols-2 gap-4">
                            {photos.map((entry) => (
                                <figure key={entry.entry_id} className="break-inside-avoid">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img
                                        src={`${API_BASE_URL}/lab/sessions/${sessionId}/entries/${entry.entry_id}/image`}
                                        alt={entry.activity}
                                        className="w-full rounded border border-neutral-200"
                                    />
                                    <figcaption className="mt-1 text-xs text-neutral-600">
                                        <span className="font-semibold">{entryTime(entry)}</span>{" "}
                                        {entry.activity}
                                    </figcaption>
                                </figure>
                            ))}
                        </div>
                    </section>
                )}

                <p className="mt-12 text-xs italic text-neutral-500">
                    Generated with Orion Lab Copilot from an automatic camera log.
                    Review and sign before filing.
                </p>
            </article>
        </main>
    );
}
