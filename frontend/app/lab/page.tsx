"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    FlaskConical,
    Loader2,
    Trash2,
} from "lucide-react";

import { clock, type LabSessionSummary } from "@/lib/lab";
import api, { getErrorMessage } from "@/services/api";

interface ResearchJob {
    job_id: string;
    question: string;
    status: string;
}

export default function LabPage() {
    const router = useRouter();

    const [sessions, setSessions] = useState<LabSessionSummary[] | null>(null);
    const [reports, setReports] = useState<ResearchJob[]>([]);
    const [error, setError] = useState<string | null>(null);

    const [title, setTitle] = useState("");
    const [protocol, setProtocol] = useState("");
    const [researchJobId, setResearchJobId] = useState("");
    const [creating, setCreating] = useState(false);

    useEffect(() => {
        api.get("/lab/sessions")
            .then((response) => setSessions(response.data.sessions))
            .catch((err) =>
                setError(getErrorMessage(err, "Failed to load sessions."))
            );

        api.get("/research")
            .then((response) =>
                setReports(
                    response.data.jobs.filter(
                        (job: ResearchJob) => job.status === "completed"
                    )
                )
            )
            .catch(() => setReports([]));
    }, []);

    async function startSession() {
        if (!title.trim() || creating) {
            return;
        }

        setCreating(true);

        try {
            const response = await api.post("/lab/sessions", {
                title: title.trim(),
                protocol,
                research_job_id: researchJobId || null,
            });

            router.push(`/lab/${response.data.session_id}`);
        } catch (err) {
            alert(getErrorMessage(err, "Failed to start the session."));
            setCreating(false);
        }
    }

    async function deleteSession(session: LabSessionSummary) {
        if (!window.confirm(`Delete "${session.title}" and its photos?`)) {
            return;
        }

        try {
            await api.delete(`/lab/sessions/${session.session_id}`);

            setSessions((current) =>
                (current || []).filter(
                    (item) => item.session_id !== session.session_id
                )
            );
        } catch (err) {
            alert(getErrorMessage(err, "Failed to delete the session."));
        }
    }

    return (
        <div className="min-h-screen bg-black text-white">

            <header className="border-b border-neutral-800">
                <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
                    <div>
                        <h1 className="text-xl font-semibold">Lab Copilot</h1>
                        <p className="text-sm text-neutral-500">
                            Automatic lab notebook from your camera
                        </p>
                    </div>

                    <button
                        onClick={() => router.push("/")}
                        className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Back
                    </button>
                </div>
            </header>

            <main className="mx-auto grid max-w-5xl gap-8 px-6 py-10 lg:grid-cols-[1fr_1fr]">

                <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-6">
                    <div className="mb-6 flex items-center gap-3">
                        <FlaskConical className="h-6 w-6 text-emerald-400" />
                        <h2 className="text-lg font-semibold">New Session</h2>
                    </div>

                    <label className="mb-2 block text-sm text-neutral-400">
                        Experiment title
                    </label>
                    <input
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                        maxLength={200}
                        placeholder="e.g. Titration of sample A"
                        className="mb-5 w-full rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 outline-none focus:border-emerald-500"
                    />

                    <label className="mb-2 block text-sm text-neutral-400">
                        Protocol (optional, used to spot deviations)
                    </label>
                    <textarea
                        value={protocol}
                        onChange={(event) => setProtocol(event.target.value)}
                        rows={6}
                        maxLength={20000}
                        placeholder={"1. Rinse burette\n2. Fill with NaOH\n3. ..."}
                        className="mb-5 w-full rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 outline-none focus:border-emerald-500"
                    />

                    <label className="mb-2 block text-sm text-neutral-400">
                        Link a literature review (optional)
                    </label>
                    <select
                        value={researchJobId}
                        onChange={(event) => setResearchJobId(event.target.value)}
                        className="mb-6 w-full rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 outline-none focus:border-emerald-500"
                    >
                        <option value="">None</option>
                        {reports.map((report) => (
                            <option key={report.job_id} value={report.job_id}>
                                {report.question.slice(0, 90)}
                            </option>
                        ))}
                    </select>

                    <button
                        onClick={startSession}
                        disabled={!title.trim() || creating}
                        className="w-full rounded-xl bg-emerald-600 py-3 font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {creating ? "Starting..." : "Start Session"}
                    </button>
                </section>

                <section>
                    <h2 className="mb-4 text-lg font-semibold">Past Sessions</h2>

                    {error && (
                        <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-300">
                            {error}
                        </p>
                    )}

                    {!sessions && !error && (
                        <div className="flex items-center gap-3 text-neutral-400">
                            <Loader2 className="h-5 w-5 animate-spin" />
                            Loading...
                        </div>
                    )}

                    {sessions && sessions.length === 0 && (
                        <p className="text-neutral-500">No sessions yet.</p>
                    )}

                    <div className="space-y-3">
                        {(sessions || []).map((session) => (
                            <div
                                key={session.session_id}
                                className="flex items-center gap-3 rounded-2xl border border-neutral-800 bg-neutral-950 p-4"
                            >
                                <button
                                    onClick={() =>
                                        router.push(
                                            session.status === "ended"
                                                ? `/lab/${session.session_id}/notebook`
                                                : `/lab/${session.session_id}`
                                        )
                                    }
                                    className="flex-1 text-left"
                                >
                                    <div className="flex items-center gap-2 text-xs">
                                        <span
                                            className={`rounded-full px-2 py-0.5 ${
                                                session.status === "active"
                                                    ? "bg-emerald-500/10 text-emerald-400"
                                                    : "bg-neutral-800 text-neutral-400"
                                            }`}
                                        >
                                            {session.status === "active"
                                                ? "Active"
                                                : "Ended"}
                                        </span>
                                        <span className="text-neutral-500">
                                            {new Date(session.created_at).toLocaleDateString()}{" "}
                                            {clock(session.created_at)} ·{" "}
                                            {session.entry_count} entries
                                        </span>
                                    </div>
                                    <p className="mt-1 font-medium hover:text-emerald-300">
                                        {session.title}
                                    </p>
                                </button>

                                <button
                                    onClick={() => deleteSession(session)}
                                    title="Delete"
                                    className="rounded-lg border border-neutral-700 p-2 text-neutral-400 hover:border-red-500/50 hover:text-red-400"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                </section>
            </main>
        </div>
    );
}
