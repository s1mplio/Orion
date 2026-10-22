"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    AlertTriangle,
    ArrowLeft,
    BookOpen,
    Circle,
    Loader2,
    Mic,
    MicOff,
    Pause,
    Play,
    Send,
} from "lucide-react";

import { entryTime, type LabEntry, type LabSession } from "@/lib/lab";
import { useCamera } from "@/lib/useCamera";
import { useVoiceInput } from "@/lib/useVoiceInput";
import api, { API_BASE_URL, getErrorMessage } from "@/services/api";

const INTERVALS = [10, 20, 30, 60];

const STATUS_TEXT: Record<string, string> = {
    logged: "New step logged",
    merged: "Same activity: extended the last step",
    idle: "No hands-on work seen: nothing logged",
};

export default function LabSessionPage() {
    const params = useParams();
    const router = useRouter();

    const sessionId = Array.isArray(params.sessionId)
        ? params.sessionId[0]
        : params.sessionId;

    const { videoRef, ready, error: cameraError, capture } = useCamera();

    const [session, setSession] = useState<LabSession | null>(null);
    const [entries, setEntries] = useState<LabEntry[]>([]);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [recording, setRecording] = useState(false);
    const [intervalSeconds, setIntervalSeconds] = useState(20);
    const [lastStatus, setLastStatus] = useState("");
    const [analyzing, setAnalyzing] = useState(false);

    const [note, setNote] = useState("");

    // Dictated notes are transcribed on the backend (local
    // Whisper) and appended to the note being typed.
    const voice = useVoiceInput((transcript) =>
        setNote((current) =>
            current.trim() ? `${current.trim()} ${transcript}` : transcript
        )
    );
    const listening = voice.status === "listening";

    const [finishing, setFinishing] = useState(false);

    // Latest capture function for the recording loop, without
    // restarting the loop on every render.
    const captureRef = useRef(capture);

    useEffect(() => {
        captureRef.current = capture;
    });

    /* ====================================================
       LOAD SESSION
    ==================================================== */

    useEffect(() => {
        if (!sessionId) {
            return;
        }

        api.get(`/lab/sessions/${sessionId}`)
            .then((response) => {
                if (response.data.status === "ended") {
                    router.replace(`/lab/${sessionId}/notebook`);
                    return;
                }

                setSession(response.data);
                setEntries(response.data.entries || []);
            })
            .catch((err) =>
                setLoadError(getErrorMessage(err, "Failed to load the session."))
            );
    }, [sessionId, router]);

    /* ====================================================
       RECORDING LOOP
       Sequential: the next capture waits for the previous
       analysis, so slow model replies never pile up.
    ==================================================== */

    useEffect(() => {
        if (!recording || !sessionId) {
            return;
        }

        let stopped = false;
        let timer: ReturnType<typeof setTimeout> | undefined;

        async function tick() {
            const blob = await captureRef.current();

            if (stopped) return;

            if (blob) {
                setAnalyzing(true);

                try {
                    const formData = new FormData();
                    formData.append("image", blob, "lab-frame.jpg");

                    const response = await api.post(
                        `/lab/sessions/${sessionId}/frames`,
                        formData
                    );

                    if (stopped) return;

                    const { status, entry } = response.data;
                    setLastStatus(STATUS_TEXT[status] || status);

                    if (entry) {
                        setEntries((current) => {
                            const others = current.filter(
                                (item) => item.entry_id !== entry.entry_id
                            );
                            return [...others, entry].sort(
                                (a, b) => a.entry_id - b.entry_id
                            );
                        });
                    }
                } catch (err) {
                    if (!stopped) {
                        setLastStatus(
                            getErrorMessage(err, "Frame analysis failed.")
                        );
                    }
                } finally {
                    if (!stopped) setAnalyzing(false);
                }
            }

            if (!stopped) {
                timer = setTimeout(tick, intervalSeconds * 1000);
            }
        }

        tick();

        return () => {
            stopped = true;
            clearTimeout(timer);
        };
    }, [recording, intervalSeconds, sessionId]);

    /* ====================================================
       VOICE DICTATION FOR NOTES
    ==================================================== */

    function toggleDictation() {
        if (listening) {
            voice.stop();
        } else {
            voice.start();
        }
    }

    /* ====================================================
       NOTES / FINISH
    ==================================================== */

    async function addNote() {
        const text = note.trim();

        if (!text) return;

        try {
            const response = await api.post(
                `/lab/sessions/${sessionId}/notes`,
                { text }
            );

            setEntries((current) => [...current, response.data]);
            setNote("");
        } catch (err) {
            alert(getErrorMessage(err, "Failed to save the note."));
        }
    }

    async function finishSession() {
        if (
            !window.confirm(
                "End this session and write the notebook? Recording will stop."
            )
        ) {
            return;
        }

        setRecording(false);
        setFinishing(true);

        try {
            await api.post(`/lab/sessions/${sessionId}/notebook`);
            router.push(`/lab/${sessionId}/notebook`);
        } catch (err) {
            alert(getErrorMessage(err, "Failed to write the notebook."));
            setFinishing(false);
        }
    }

    /* ====================================================
       RENDER
    ==================================================== */

    if (loadError) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-black px-6 text-red-400">
                {loadError}
            </div>
        );
    }

    if (!session) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-black text-neutral-400">
                <Loader2 className="mr-3 h-5 w-5 animate-spin" />
                Loading session...
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-black text-white">

            <header className="border-b border-neutral-800">
                <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-4">
                    <div>
                        <h1 className="text-xl font-semibold">{session.title}</h1>
                        <p className="text-sm text-neutral-500">
                            Lab Copilot session
                        </p>
                    </div>

                    <div className="flex gap-3">
                        <button
                            onClick={finishSession}
                            disabled={finishing || entries.length === 0}
                            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {finishing ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <BookOpen className="h-4 w-4" />
                            )}
                            {finishing ? "Writing notebook..." : "End & Write Notebook"}
                        </button>

                        <button
                            onClick={() => router.push("/lab")}
                            className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Sessions
                        </button>
                    </div>
                </div>
            </header>

            <main className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-2">

                {/* CAMERA + CONTROLS */}

                <section className="space-y-4">
                    <div className="relative overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950">
                        <video
                            ref={videoRef}
                            autoPlay
                            playsInline
                            muted
                            className="w-full"
                        />

                        {!ready && (
                            <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-neutral-400">
                                {cameraError || "Starting camera..."}
                            </div>
                        )}

                        {recording && (
                            <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full bg-black/70 px-3 py-1 text-xs text-red-400">
                                <Circle className="h-3 w-3 animate-pulse fill-red-500" />
                                Recording
                            </div>
                        )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <button
                            onClick={() => setRecording((value) => !value)}
                            disabled={!ready}
                            className={`flex items-center gap-2 rounded-xl px-5 py-3 font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
                                recording
                                    ? "bg-red-600 text-white hover:bg-red-500"
                                    : "bg-emerald-600 text-white hover:bg-emerald-500"
                            }`}
                        >
                            {recording ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                            {recording ? "Pause Recording" : "Start Recording"}
                        </button>

                        <label className="flex items-center gap-2 text-sm text-neutral-400">
                            Capture every
                            <select
                                value={intervalSeconds}
                                onChange={(event) =>
                                    setIntervalSeconds(Number(event.target.value))
                                }
                                className="rounded-lg border border-neutral-700 bg-neutral-900 px-2 py-1 text-white"
                            >
                                {INTERVALS.map((seconds) => (
                                    <option key={seconds} value={seconds}>
                                        {seconds}s
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>

                    <p className="min-h-5 text-sm text-neutral-500">
                        {analyzing ? "Analyzing frame..." : lastStatus}
                    </p>

                    {/* NOTES */}

                    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
                        {voice.error && (
                            <p className="mb-2 text-sm text-amber-300">{voice.error}</p>
                        )}

                        <p className="mb-3 text-sm text-neutral-400">
                            Add a note (quantities, readings, anything the camera
                            can&apos;t see)
                        </p>

                        <div className="flex gap-2">
                            <input
                                value={note}
                                onChange={(event) => setNote(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === "Enter") addNote();
                                }}
                                maxLength={5000}
                                placeholder={
                                    listening
                                        ? "Listening... pause to finish"
                                        : voice.status === "transcribing"
                                          ? "Writing it down..."
                                          : "e.g. Added 5 mL of 0.1 M NaOH"
                                }
                                className="flex-1 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 outline-none focus:border-emerald-500"
                            />

                            <button
                                onClick={toggleDictation}
                                disabled={voice.status === "transcribing"}
                                title={listening ? "Stop dictation" : "Dictate a note"}
                                className={`rounded-xl border px-3 ${
                                    listening
                                        ? "border-red-500/50 text-red-400"
                                        : "border-neutral-700 text-neutral-300 hover:text-emerald-400"
                                }`}
                            >
                                {listening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                            </button>

                            <button
                                onClick={addNote}
                                disabled={!note.trim()}
                                className="rounded-xl bg-neutral-800 px-4 text-neutral-200 hover:bg-neutral-700 disabled:opacity-40"
                            >
                                <Send className="h-4 w-4" />
                            </button>
                        </div>
                    </div>

                    {session.protocol && (
                        <details className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4 text-sm">
                            <summary className="cursor-pointer text-neutral-300">
                                Protocol
                            </summary>
                            <pre className="mt-3 whitespace-pre-wrap font-sans text-neutral-400">
                                {session.protocol}
                            </pre>
                        </details>
                    )}
                </section>

                {/* LIVE LOG */}

                <section className="rounded-2xl border border-neutral-800 bg-neutral-950">
                    <div className="border-b border-neutral-800 px-6 py-4">
                        <h2 className="font-semibold">Session Log</h2>
                        <p className="text-sm text-neutral-500">
                            {entries.length} entries · newest first
                        </p>
                    </div>

                    <div className="max-h-[75vh] space-y-4 overflow-y-auto p-6">
                        {entries.length === 0 && (
                            <p className="text-neutral-500">
                                Start recording or add a note. Steps appear here as
                                Orion sees them.
                            </p>
                        )}

                        {[...entries].reverse().map((entry) => (
                            <article
                                key={entry.entry_id}
                                className={`flex gap-4 rounded-xl border p-3 ${
                                    entry.details.safety_concern
                                        ? "border-red-500/40 bg-red-500/5"
                                        : "border-neutral-800"
                                }`}
                            >
                                {entry.has_image && (
                                    // Served by the backend through the /api proxy.
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={`${API_BASE_URL}/lab/sessions/${sessionId}/entries/${entry.entry_id}/image`}
                                        alt={entry.activity}
                                        className="h-20 w-28 shrink-0 rounded-lg object-cover"
                                    />
                                )}

                                <div className="min-w-0 text-sm">
                                    <p className="text-xs text-neutral-500">
                                        {entryTime(entry)}
                                        {entry.kind === "note" && (
                                            <span className="ml-2 rounded bg-blue-500/10 px-1.5 text-blue-400">
                                                Note
                                            </span>
                                        )}
                                    </p>

                                    <p className="mt-1 text-neutral-100">{entry.activity}</p>

                                    {entry.details.observation && (
                                        <p className="mt-1 text-neutral-400">
                                            Observed: {entry.details.observation}
                                        </p>
                                    )}

                                    {[
                                        ...(entry.details.materials || []),
                                        ...(entry.details.equipment || []),
                                    ].length > 0 && (
                                        <p className="mt-1 text-neutral-500">
                                            {[
                                                ...(entry.details.materials || []),
                                                ...(entry.details.equipment || []),
                                            ].join(" · ")}
                                        </p>
                                    )}

                                    {entry.details.safety_concern && (
                                        <p className="mt-1 flex items-center gap-1 text-red-400">
                                            <AlertTriangle className="h-4 w-4" />
                                            {entry.details.safety_concern}
                                        </p>
                                    )}
                                </div>
                            </article>
                        ))}
                    </div>
                </section>
            </main>
        </div>
    );
}
