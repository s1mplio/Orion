"use client";

import {
    useEffect,
    useRef,
    useState,
} from "react";
import Link from "next/link";
import {
    CheckCircle2,
    Clock,
    Eye,
    EyeOff,
    Mic,
    MicOff,
    Pill,
    Send,
} from "lucide-react";

import {
    carePhotoUrl,
    greeting,
    reminderText,
    saysTookIt,
    type Dose,
    type TodayData,
} from "@/lib/care";
import { speak } from "@/lib/speech";
import { useCamera } from "@/lib/useCamera";
import { useVoiceInput } from "@/lib/useVoiceInput";
import api, { getErrorMessage } from "@/services/api";

const POLL_SECONDS = 15;
const ROOM_CHECK_SECONDS = 60;

export default function CareTodayPage() {
    const { videoRef, ready: cameraReady, error: cameraError, capture } = useCamera();

    const [started, setStarted] = useState(false);
    const [today, setToday] = useState<TodayData | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [question, setQuestion] = useState("");
    const [answer, setAnswer] = useState<{ text: string; photo?: string | null } | null>(null);
    const [busy, setBusy] = useState(false);
    // The question being answered right now, shown at once so
    // the person knows Orion heard them.
    const [asked, setAsked] = useState("");
    const [notice, setNotice] = useState("");

    // Mirrors busy for the room-camera loop (a callback).
    const busyRef = useRef(false);

    useEffect(() => {
        busyRef.current = busy;
    }, [busy]);

    const [roomWatch, setRoomWatch] = useState(true);

    const lastSpokenRef = useRef<Record<number, number>>({});

    /* ====================================================
       LOAD + POLL TODAY
    ==================================================== */

    async function refresh() {
        try {
            const response = await api.get("/care/today");
            setToday(response.data);
            setLoadError(null);
        } catch (err) {
            setLoadError(getErrorMessage(err, "Can't reach Orion."));
        }
    }

    useEffect(() => {
        let stopped = false;
        let timer: ReturnType<typeof setTimeout> | undefined;

        async function poll() {
            try {
                const response = await api.get("/care/today");
                if (stopped) return;
                setToday(response.data);
                setLoadError(null);
            } catch (err) {
                if (stopped) return;
                setLoadError(getErrorMessage(err, "Can't reach Orion."));
            }

            timer = setTimeout(poll, POLL_SECONDS * 1000);
        }

        poll();

        return () => {
            stopped = true;
            clearTimeout(timer);
        };
    }, []);

    /* ====================================================
       SPOKEN REMINDERS
       Repeat every repeat_minutes until the dose is taken.
    ==================================================== */

    useEffect(() => {
        if (!started || !today || today.due.length === 0) {
            return;
        }

        const now = Date.now();
        const repeatMs = today.repeat_minutes * 60 * 1000;

        const dueNow = today.due.filter((dose) => {
            const last = lastSpokenRef.current[dose.dose_id];
            return last === undefined || now - last >= repeatMs;
        });

        if (dueNow.length === 0) {
            return;
        }

        for (const dose of dueNow) {
            lastSpokenRef.current[dose.dose_id] = now;
        }

        speak(
            dueNow
                .map((dose) => reminderText(dose, today.person_name))
                .join(" ")
        );
    }, [today, started]);

    /* ====================================================
       CONFIRM A DOSE
    ==================================================== */

    async function confirmDose(dose: Dose, method: "tap" | "voice") {
        setBusy(true);

        try {
            const formData = new FormData();
            formData.append("method", method);

            // Photo as supporting evidence for family; the
            // confirmation itself is what counts.
            const photo = cameraReady ? await capture() : null;

            if (photo) {
                formData.append("image", photo, "dose.jpg");
            }

            await api.post(`/care/doses/${dose.dose_id}/confirm`, formData);

            const text = `Well done. I've noted your ${dose.name}.`;
            setAnswer({ text });
            speak(text);

            await refresh();
        } catch (err) {
            const text = getErrorMessage(err, "Sorry, I couldn't save that.");
            setAnswer({ text });
            speak(text);
        } finally {
            setBusy(false);
        }
    }

    /* ====================================================
       QUESTIONS (typed or spoken)
    ==================================================== */

    async function ask(text: string) {
        const trimmed = text.trim();

        if (!trimmed) return;

        if (busy) {
            // Previously ignored silently, which felt like Orion
            // was not listening.
            setNotice("Still answering your last question. One moment...");
            return;
        }

        setQuestion("");
        setNotice("");
        setAsked(trimmed);
        setAnswer(null);

        const due = today?.due || [];

        if (saysTookIt(trimmed) && due.length > 0) {
            if (due.length === 1) {
                await confirmDose(due[0], "voice");
            } else {
                const reply =
                    "You have more than one medicine due. Please tap the button for each one you took.";
                setAnswer({ text: reply });
                speak(reply);
            }
            return;
        }

        setBusy(true);

        // Spoken acknowledgement so voice users know they were
        // heard while the answer is prepared.
        speak("Let me check.");

        try {
            const formData = new FormData();
            formData.append("question", trimmed);

            // Lets Orion look for things right now ("where is my
            // trimmer?") instead of relying only on memory.
            const frame = cameraReady ? await capture() : null;

            if (frame) {
                formData.append("image", frame, "ask.jpg");
            }

            const response = await api.post("/care/ask", formData);
            setAnswer({ text: response.data.answer, photo: response.data.photo });
            speak(response.data.answer);
        } catch (err) {
            const reply = getErrorMessage(err, "Sorry, I couldn't answer that.");
            setAnswer({ text: reply });
            speak(reply);
        } finally {
            setBusy(false);
            setNotice("");
        }
    }

    // Voice: recorded and transcribed on the backend (local
    // Whisper), then asked like a typed question.
    const voice = useVoiceInput((text) => ask(text));

    function toggleListening() {
        if (voice.status === "listening") {
            voice.stop();
        } else if (voice.status === "idle") {
            // Don't record Orion's own voice.
            window.speechSynthesis?.cancel();
            voice.start();
        }
    }

    /* ====================================================
       ROOM CAMERA: remember where tracked things are
    ==================================================== */

    const captureRef = useRef(capture);

    useEffect(() => {
        captureRef.current = capture;
    });

    useEffect(() => {
        if (!started || !roomWatch || !cameraReady) {
            return;
        }

        let stopped = false;
        let timer: ReturnType<typeof setTimeout> | undefined;

        async function look() {
            const frame = await captureRef.current();

            // Don't compete with a question for the model.
            if (frame && !stopped && !busyRef.current) {
                const formData = new FormData();
                formData.append("image", frame, "room.jpg");

                try {
                    await api.post("/care/frames", formData);
                } catch (err) {
                    console.error("Room check failed:", err);
                }
            }

            if (!stopped) {
                timer = setTimeout(look, ROOM_CHECK_SECONDS * 1000);
            }
        }

        timer = setTimeout(look, 5000);

        return () => {
            stopped = true;
            clearTimeout(timer);
        };
    }, [started, roomWatch, cameraReady]);

    /* ====================================================
       RENDER
    ==================================================== */

    function start() {
        setStarted(true);

        // Speaking inside the click unlocks audio for the
        // reminders that follow.
        speak(
            `${greeting()}${today?.person_name ? `, ${today.person_name}` : ""}. I'm here to help.`
        );
    }

    if (!started) {
        return (
            <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-neutral-950 px-6 text-center text-white">
                <h1 className="text-5xl font-bold">Orion</h1>
                <p className="max-w-md text-2xl text-neutral-300">
                    Tap below so Orion can speak your reminders.
                </p>
                <button
                    onClick={start}
                    className="rounded-3xl bg-emerald-600 px-16 py-8 text-4xl font-bold text-white hover:bg-emerald-500"
                >
                    Start
                </button>
                {loadError && <p className="text-xl text-red-400">{loadError}</p>}
            </main>
        );
    }

    const due = today?.due || [];

    return (
        <main className="min-h-screen bg-neutral-950 px-6 py-8 text-white">
            <div className="mx-auto max-w-4xl space-y-8">

                {/* HEADER */}

                <header className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <p className="text-3xl text-neutral-300">
                            {greeting()}{today?.person_name ? `, ${today.person_name}` : ""}
                        </p>
                        <p className="mt-1 text-xl text-neutral-500">{today?.date}</p>
                    </div>
                    <p className="text-6xl font-bold tabular-nums">{today?.time}</p>
                </header>

                {loadError && (
                    <p className="rounded-2xl bg-red-500/10 p-4 text-xl text-red-300">
                        {loadError}
                    </p>
                )}

                {/* DUE NOW */}

                {due.map((dose) => (
                    <section
                        key={dose.dose_id}
                        className="rounded-3xl border-4 border-amber-400 bg-amber-400/10 p-8"
                    >
                        <div className="flex items-center gap-4">
                            <Pill className="h-12 w-12 text-amber-300" />
                            <div>
                                <p className="text-xl text-amber-200">Time for your medicine</p>
                                <p className="text-4xl font-bold">
                                    {dose.name} {dose.amount}
                                </p>
                                {dose.instructions && (
                                    <p className="mt-1 text-2xl text-neutral-300">
                                        {dose.instructions}
                                    </p>
                                )}
                                <p className="mt-1 text-xl text-neutral-400">Due at {dose.time}</p>
                            </div>
                        </div>

                        <button
                            onClick={() => confirmDose(dose, "tap")}
                            disabled={busy}
                            className="mt-6 flex w-full items-center justify-center gap-4 rounded-2xl bg-emerald-600 py-6 text-4xl font-bold hover:bg-emerald-500 disabled:opacity-50"
                        >
                            <CheckCircle2 className="h-10 w-10" />
                            I took it
                        </button>
                    </section>
                ))}

                {/* ASK */}

                <section className="rounded-3xl bg-neutral-900 p-6">
                    <div className="flex gap-3">
                        <button
                            onClick={toggleListening}
                            disabled={busy || voice.status === "transcribing"}
                            className={`flex items-center gap-3 rounded-2xl px-6 py-4 text-2xl font-semibold disabled:opacity-60 ${
                                voice.status === "listening"
                                    ? "animate-pulse bg-red-600 hover:bg-red-500"
                                    : "bg-blue-600 hover:bg-blue-500"
                            }`}
                        >
                            {voice.status === "listening" ? (
                                <MicOff className="h-8 w-8" />
                            ) : (
                                <Mic className="h-8 w-8" />
                            )}
                            {voice.status === "listening"
                                ? "Listening"
                                : voice.status === "transcribing"
                                  ? "One sec..."
                                  : "Ask"}
                        </button>

                        <input
                            value={question}
                            onChange={(event) => setQuestion(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter") ask(question);
                            }}
                            maxLength={500}
                            placeholder="Where are my glasses?"
                            className="min-w-0 flex-1 rounded-2xl border border-neutral-700 bg-neutral-950 px-5 text-2xl outline-none focus:border-blue-500"
                        />

                        <button
                            onClick={() => ask(question)}
                            disabled={busy || !question.trim()}
                            className="rounded-2xl bg-neutral-800 px-5 hover:bg-neutral-700 disabled:opacity-40"
                        >
                            <Send className="h-7 w-7" />
                        </button>
                    </div>

                    {voice.status === "listening" && (
                        <p className="mt-4 text-xl text-red-300">
                            Speak now. I&apos;ll stop when you pause.
                        </p>
                    )}

                    {voice.error && voice.status === "idle" && (
                        <p className="mt-4 text-xl text-amber-300">{voice.error}</p>
                    )}

                    {notice && (
                        <p className="mt-4 text-xl text-amber-300">{notice}</p>
                    )}

                    {asked && (busy || answer) && (
                        <p className="mt-5 text-xl text-neutral-400">
                            You asked: &ldquo;{asked}&rdquo;
                        </p>
                    )}

                    {busy && (
                        <div className="mt-3 flex items-center gap-4 text-3xl text-blue-300">
                            <span className="h-8 w-8 animate-spin rounded-full border-4 border-blue-300 border-t-transparent" />
                            Orion is thinking...
                        </div>
                    )}

                    {answer && !busy && (
                        <div className="mt-5 flex flex-col gap-4 sm:flex-row">
                            {answer.photo && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                    src={carePhotoUrl(answer.photo)}
                                    alt="Where it was last seen"
                                    className="w-full rounded-2xl sm:w-64"
                                />
                            )}
                            <p className="text-3xl leading-snug">{answer.text}</p>
                        </div>
                    )}
                </section>

                {/* REST OF TODAY */}

                <section className="grid gap-6 md:grid-cols-2">
                    <div className="rounded-3xl bg-neutral-900 p-6">
                        <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold">
                            <Clock className="h-7 w-7 text-blue-400" />
                            Later today
                        </h2>
                        {(today?.upcoming || []).length === 0 ? (
                            <p className="text-xl text-neutral-500">Nothing else today.</p>
                        ) : (
                            <ul className="space-y-3 text-2xl">
                                {today!.upcoming.map((dose) => (
                                    <li key={dose.dose_id}>
                                        <span className="font-semibold">{dose.time}</span>{" "}
                                        {dose.name}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>

                    <div className="rounded-3xl bg-neutral-900 p-6">
                        <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold">
                            <CheckCircle2 className="h-7 w-7 text-emerald-400" />
                            Done today
                        </h2>
                        {(today?.taken || []).length === 0 && (today?.missed || []).length === 0 ? (
                            <p className="text-xl text-neutral-500">Nothing yet.</p>
                        ) : (
                            <ul className="space-y-3 text-2xl">
                                {today!.taken.map((dose) => (
                                    <li key={dose.dose_id} className="text-emerald-300">
                                        ✓ {dose.name} at {dose.confirmed_time}
                                    </li>
                                ))}
                                {today!.missed.map((dose) => (
                                    <li key={dose.dose_id} className="text-neutral-400">
                                        {dose.time} {dose.name}: not confirmed
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </section>

                {/* CAMERA */}

                <section className="flex flex-wrap items-center gap-4 rounded-3xl bg-neutral-900 p-4">
                    <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        className="h-24 w-32 rounded-xl bg-black object-cover"
                    />

                    <div className="flex-1 text-lg text-neutral-400">
                        {cameraError ||
                            (roomWatch
                                ? "Orion is keeping an eye on where things are."
                                : "Room camera paused.")}
                    </div>

                    <button
                        onClick={() => setRoomWatch((value) => !value)}
                        className="flex items-center gap-2 rounded-xl border border-neutral-700 px-4 py-3 text-lg hover:bg-neutral-800"
                    >
                        {roomWatch ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        {roomWatch ? "Pause camera" : "Resume camera"}
                    </button>
                </section>

                <p className="text-center text-sm text-neutral-600">
                    Orion supports care and does not replace medical supervision.{" "}
                    <Link href="/care/setup" className="underline hover:text-neutral-400">
                        Caregiver setup
                    </Link>
                </p>
            </div>
        </main>
    );
}
