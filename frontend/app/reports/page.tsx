"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    Download,
    FileText,
    Loader2,
    Plus,
    Trash2,
} from "lucide-react";

import api, { API_BASE_URL, getErrorMessage } from "@/services/api";

interface JobSummary {
    job_id: string;
    question: string;
    status: string;
    progress: number;
    error: string | null;
    created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
    completed: "bg-green-500/10 text-green-400",
    running: "bg-blue-500/10 text-blue-400",
    queued: "bg-yellow-500/10 text-yellow-400",
    failed: "bg-red-500/10 text-red-400",
};

function formatDate(value: string) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    });
}

export default function ReportsPage() {
    const router = useRouter();

    const [jobs, setJobs] = useState<JobSummary[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api.get("/research")
            .then((response) => setJobs(response.data.jobs))
            .catch((err) =>
                setError(
                    getErrorMessage(err, "Failed to load your reports.")
                )
            );
    }, []);

    function openJob(job: JobSummary) {
        router.push(
            job.status === "completed"
                ? `/report/${job.job_id}`
                : `/research/${job.job_id}`
        );
    }

    async function deleteJob(job: JobSummary) {
        if (!window.confirm(`Delete "${job.question}"?`)) {
            return;
        }

        try {
            await api.delete(`/research/${job.job_id}`);

            setJobs((current) =>
                (current || []).filter(
                    (item) => item.job_id !== job.job_id
                )
            );
        } catch (err) {
            alert(getErrorMessage(err, "Failed to delete the report."));
        }
    }

    return (
        <div className="min-h-screen bg-black text-white">

            <header className="border-b border-neutral-800">
                <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
                    <div>
                        <h1 className="text-xl font-semibold">
                            My Reports
                        </h1>
                        <p className="text-sm text-neutral-500">
                            Your saved literature reviews
                        </p>
                    </div>

                    <div className="flex gap-3">
                        <button
                            onClick={() => router.push("/research")}
                            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
                        >
                            <Plus className="h-4 w-4" />
                            New Review
                        </button>

                        <button
                            onClick={() => router.push("/")}
                            className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Back
                        </button>
                    </div>
                </div>
            </header>

            <main className="mx-auto max-w-5xl px-6 py-10">

                {error && (
                    <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-300">
                        {error}
                    </p>
                )}

                {!jobs && !error && (
                    <div className="flex items-center gap-3 text-neutral-400">
                        <Loader2 className="h-5 w-5 animate-spin" />
                        Loading reports...
                    </div>
                )}

                {jobs && jobs.length === 0 && (
                    <div className="rounded-2xl border border-neutral-800 p-10 text-center">
                        <FileText className="mx-auto h-10 w-10 text-neutral-600" />
                        <p className="mt-4 text-neutral-400">
                            No reports yet. Start your first literature review.
                        </p>
                    </div>
                )}

                <div className="space-y-4">
                    {(jobs || []).map((job) => (
                        <div
                            key={job.job_id}
                            className="flex flex-col gap-4 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 sm:flex-row sm:items-center"
                        >
                            <button
                                onClick={() => openJob(job)}
                                className="flex-1 text-left"
                            >
                                <div className="flex flex-wrap items-center gap-3">
                                    <span
                                        className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${
                                            STATUS_STYLES[job.status] ||
                                            "bg-neutral-800 text-neutral-300"
                                        }`}
                                    >
                                        {job.status === "running"
                                            ? `Running ${job.progress}%`
                                            : job.status}
                                    </span>

                                    <span className="text-xs text-neutral-500">
                                        {formatDate(job.created_at)}
                                    </span>
                                </div>

                                <p className="mt-2 font-medium text-neutral-100 hover:text-blue-300">
                                    {job.question}
                                </p>

                                {job.status === "failed" && job.error && (
                                    <p className="mt-1 text-sm text-red-400">
                                        {job.error}
                                    </p>
                                )}
                            </button>

                            <div className="flex gap-2">
                                {job.status === "completed" && (
                                    <a
                                        href={`${API_BASE_URL}/research/${job.job_id}/export/docx`}
                                        title="Download Word"
                                        className="rounded-lg border border-neutral-700 p-2 text-neutral-300 hover:bg-neutral-900"
                                    >
                                        <Download className="h-4 w-4" />
                                    </a>
                                )}

                                {job.status !== "running" &&
                                    job.status !== "queued" && (
                                    <button
                                        onClick={() => deleteJob(job)}
                                        title="Delete"
                                        className="rounded-lg border border-neutral-700 p-2 text-neutral-400 hover:border-red-500/50 hover:text-red-400"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </main>
        </div>
    );
}
