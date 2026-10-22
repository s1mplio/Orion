"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
    ArrowLeft,
    Bell,
    Eye,
    Pencil,
    Pill,
    Plus,
    Send,
    Trash2,
    User,
    X,
} from "lucide-react";

import {
    WEEKDAYS,
    type CareSettings,
    type Contact,
    type Dose,
    type Medication,
    type TrackedObject,
} from "@/lib/care";
import api, { getErrorMessage } from "@/services/api";

interface TelegramStatus {
    configured: boolean;
    contacts: Contact[];
    recent_chats: { telegram_chat_id: string; name: string }[];
    error: string | null;
}

const EMPTY_MED = {
    name: "",
    dose: "",
    instructions: "",
    times: ["08:00"],
    days: [] as number[],
};

function Card({
    title,
    icon,
    children,
}: {
    title: string;
    icon: React.ReactNode;
    children: React.ReactNode;
}) {
    return (
        <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-6">
            <h2 className="mb-5 flex items-center gap-3 text-lg font-semibold">
                {icon}
                {title}
            </h2>
            {children}
        </section>
    );
}

const inputClass =
    "rounded-xl border border-neutral-700 bg-neutral-900 px-3 py-2 outline-none focus:border-emerald-500";

async function fetchAll() {
    const [settings, medications, objects, telegram, doses, summary] =
        await Promise.all([
            api.get("/care/settings"),
            api.get("/care/medications"),
            api.get("/care/objects"),
            api.get("/care/telegram"),
            api.get("/care/doses"),
            api.get("/care/summary"),
        ]);

    return {
        settings: settings.data as CareSettings,
        medications: medications.data.medications as Medication[],
        objects: objects.data.objects as TrackedObject[],
        telegram: telegram.data as TelegramStatus,
        doses: doses.data.doses as Dose[],
        summary: summary.data.text as string,
    };
}

export default function CareSetupPage() {
    const [settings, setSettings] = useState<CareSettings | null>(null);
    const [medications, setMedications] = useState<Medication[]>([]);
    const [objects, setObjects] = useState<TrackedObject[]>([]);
    const [telegram, setTelegram] = useState<TelegramStatus | null>(null);
    const [doses, setDoses] = useState<Dose[]>([]);
    const [summary, setSummary] = useState("");
    const [error, setError] = useState<string | null>(null);

    const [medForm, setMedForm] = useState(EMPTY_MED);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [objectName, setObjectName] = useState("");
    const [saved, setSaved] = useState("");

    function apply(data: Awaited<ReturnType<typeof fetchAll>>) {
        setSettings(data.settings);
        setMedications(data.medications);
        setObjects(data.objects);
        setTelegram(data.telegram);
        setDoses(data.doses);
        setSummary(data.summary);
        setError(null);
    }

    async function loadAll() {
        try {
            apply(await fetchAll());
        } catch (err) {
            setError(getErrorMessage(err, "Failed to load care settings."));
        }
    }

    useEffect(() => {
        let cancelled = false;

        fetchAll()
            .then((data) => {
                if (!cancelled) apply(data);
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(getErrorMessage(err, "Failed to load care settings."));
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    async function run(action: () => Promise<unknown>, message: string) {
        try {
            await action();
            await loadAll();
            setSaved(message);
            setTimeout(() => setSaved(""), 2500);
        } catch (err) {
            alert(getErrorMessage(err, "Something went wrong."));
        }
    }

    /* ---------------- medicines ---------------- */

    function saveMedication() {
        const payload = {
            ...medForm,
            times: medForm.times.filter(Boolean),
        };

        run(async () => {
            if (editingId) {
                await api.put(`/care/medications/${editingId}`, payload);
            } else {
                await api.post("/care/medications", payload);
            }

            setMedForm(EMPTY_MED);
            setEditingId(null);
        }, "Medicine saved");
    }

    function editMedication(med: Medication) {
        setEditingId(med.med_id);
        setMedForm({
            name: med.name,
            dose: med.dose,
            instructions: med.instructions,
            times: med.times,
            days: med.days,
        });
    }

    function toggleDay(day: number) {
        setMedForm((form) => ({
            ...form,
            days: form.days.includes(day)
                ? form.days.filter((value) => value !== day)
                : [...form.days, day],
        }));
    }

    if (error) {
        return (
            <main className="min-h-screen bg-black p-10 text-red-400">{error}</main>
        );
    }

    if (!settings || !telegram) {
        return (
            <main className="min-h-screen bg-black p-10 text-neutral-400">Loading...</main>
        );
    }

    return (
        <div className="min-h-screen bg-black text-white">
            <header className="border-b border-neutral-800">
                <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
                    <div>
                        <h1 className="text-xl font-semibold">Caregiver Setup</h1>
                        <p className="text-sm text-neutral-500">
                            Medicines, reminders and family alerts
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        {saved && <span className="text-sm text-emerald-400">{saved}</span>}
                        <Link
                            href="/care"
                            className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Back
                        </Link>
                    </div>
                </div>
            </header>

            <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">

                {/* PERSON */}

                <Card title="Person & reminders" icon={<User className="h-5 w-5 text-emerald-400" />}>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <label className="text-sm text-neutral-400">
                            Name used in reminders
                            <input
                                value={settings.person_name}
                                onChange={(e) => setSettings({ ...settings, person_name: e.target.value })}
                                maxLength={60}
                                placeholder="e.g. Asha"
                                className={`mt-1 block w-full ${inputClass}`}
                            />
                        </label>

                        <label className="text-sm text-neutral-400">
                            Daily summary time
                            <input
                                type="time"
                                value={settings.summary_time}
                                onChange={(e) => setSettings({ ...settings, summary_time: e.target.value })}
                                className={`mt-1 block w-full ${inputClass}`}
                            />
                        </label>

                        <label className="text-sm text-neutral-400">
                            Alert family if not taken within (minutes)
                            <input
                                type="number"
                                min={10}
                                max={240}
                                value={settings.grace_minutes}
                                onChange={(e) => setSettings({ ...settings, grace_minutes: e.target.value })}
                                className={`mt-1 block w-full ${inputClass}`}
                            />
                        </label>

                        <label className="text-sm text-neutral-400">
                            Repeat spoken reminder every (minutes)
                            <input
                                type="number"
                                min={1}
                                max={60}
                                value={settings.repeat_minutes}
                                onChange={(e) => setSettings({ ...settings, repeat_minutes: e.target.value })}
                                className={`mt-1 block w-full ${inputClass}`}
                            />
                        </label>
                    </div>

                    <button
                        onClick={() =>
                            run(
                                () =>
                                    api.put("/care/settings", {
                                        person_name: settings.person_name,
                                        summary_time: settings.summary_time,
                                        grace_minutes: Number(settings.grace_minutes),
                                        repeat_minutes: Number(settings.repeat_minutes),
                                    }),
                                "Settings saved"
                            )
                        }
                        className="mt-5 rounded-xl bg-emerald-600 px-5 py-2 font-medium hover:bg-emerald-500"
                    >
                        Save
                    </button>
                </Card>

                {/* MEDICINES */}

                <Card title="Medicines" icon={<Pill className="h-5 w-5 text-emerald-400" />}>
                    <div className="space-y-3">
                        {medications.length === 0 && (
                            <p className="text-neutral-500">No medicines yet.</p>
                        )}

                        {medications.map((med) => (
                            <div
                                key={med.med_id}
                                className="flex items-center gap-3 rounded-xl border border-neutral-800 p-3"
                            >
                                <div className="flex-1">
                                    <p className="font-medium">
                                        {med.name} <span className="text-neutral-400">{med.dose}</span>
                                    </p>
                                    <p className="text-sm text-neutral-500">
                                        {med.times.join(", ")} ·{" "}
                                        {med.days.length === 0
                                            ? "every day"
                                            : med.days.map((d) => WEEKDAYS[d]).join(" ")}
                                        {med.instructions && ` · ${med.instructions}`}
                                    </p>
                                </div>

                                <button
                                    onClick={() => editMedication(med)}
                                    title="Edit"
                                    className="rounded-lg border border-neutral-700 p-2 text-neutral-400 hover:text-white"
                                >
                                    <Pencil className="h-4 w-4" />
                                </button>

                                <button
                                    onClick={() => {
                                        if (window.confirm(`Stop reminders for ${med.name}?`)) {
                                            run(() => api.delete(`/care/medications/${med.med_id}`), "Medicine removed");
                                        }
                                    }}
                                    title="Stop"
                                    className="rounded-lg border border-neutral-700 p-2 text-neutral-400 hover:text-red-400"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        ))}
                    </div>

                    <div className="mt-6 rounded-xl border border-neutral-800 p-4">
                        <p className="mb-3 text-sm font-medium text-neutral-300">
                            {editingId ? "Edit medicine" : "Add a medicine"}
                        </p>

                        <div className="grid gap-3 sm:grid-cols-3">
                            <input
                                value={medForm.name}
                                onChange={(e) => setMedForm({ ...medForm, name: e.target.value })}
                                placeholder="Name, e.g. Metformin"
                                maxLength={100}
                                className={inputClass}
                            />
                            <input
                                value={medForm.dose}
                                onChange={(e) => setMedForm({ ...medForm, dose: e.target.value })}
                                placeholder="Dose, e.g. 500 mg"
                                maxLength={100}
                                className={inputClass}
                            />
                            <input
                                value={medForm.instructions}
                                onChange={(e) => setMedForm({ ...medForm, instructions: e.target.value })}
                                placeholder="e.g. after food"
                                maxLength={500}
                                className={inputClass}
                            />
                        </div>

                        <div className="mt-4 flex flex-wrap items-center gap-2">
                            <span className="text-sm text-neutral-400">Times:</span>
                            {medForm.times.map((time, index) => (
                                <span key={index} className="flex items-center gap-1">
                                    <input
                                        type="time"
                                        value={time}
                                        onChange={(e) => {
                                            const times = [...medForm.times];
                                            times[index] = e.target.value;
                                            setMedForm({ ...medForm, times });
                                        }}
                                        className={inputClass}
                                    />
                                    {medForm.times.length > 1 && (
                                        <button
                                            onClick={() =>
                                                setMedForm({
                                                    ...medForm,
                                                    times: medForm.times.filter((_, i) => i !== index),
                                                })
                                            }
                                            className="text-neutral-500 hover:text-red-400"
                                            title="Remove time"
                                        >
                                            <X className="h-4 w-4" />
                                        </button>
                                    )}
                                </span>
                            ))}
                            <button
                                onClick={() => setMedForm({ ...medForm, times: [...medForm.times, "20:00"] })}
                                className="flex items-center gap-1 rounded-lg border border-neutral-700 px-2 py-1 text-sm text-neutral-300 hover:bg-neutral-900"
                            >
                                <Plus className="h-3 w-3" />
                                time
                            </button>
                        </div>

                        <div className="mt-4 flex flex-wrap items-center gap-2">
                            <span className="text-sm text-neutral-400">Days (none = every day):</span>
                            {WEEKDAYS.map((label, day) => (
                                <button
                                    key={label}
                                    onClick={() => toggleDay(day)}
                                    className={`rounded-lg px-3 py-1 text-sm ${
                                        medForm.days.includes(day)
                                            ? "bg-emerald-600 text-white"
                                            : "border border-neutral-700 text-neutral-400"
                                    }`}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>

                        <div className="mt-5 flex gap-3">
                            <button
                                onClick={saveMedication}
                                disabled={!medForm.name.trim() || medForm.times.filter(Boolean).length === 0}
                                className="rounded-xl bg-emerald-600 px-5 py-2 font-medium hover:bg-emerald-500 disabled:opacity-50"
                            >
                                {editingId ? "Save changes" : "Add medicine"}
                            </button>

                            {editingId && (
                                <button
                                    onClick={() => {
                                        setEditingId(null);
                                        setMedForm(EMPTY_MED);
                                    }}
                                    className="rounded-xl border border-neutral-700 px-5 py-2 text-neutral-300"
                                >
                                    Cancel
                                </button>
                            )}
                        </div>
                    </div>
                </Card>

                {/* OBJECTS */}

                <Card title="Things to keep track of" icon={<Eye className="h-5 w-5 text-emerald-400" />}>
                    <p className="mb-4 text-sm text-neutral-500">
                        The Today screen camera remembers where it last saw these.
                        Photos are deleted after 7 days.
                    </p>

                    <div className="mb-4 space-y-2">
                        {objects.map((obj) => (
                            <div key={obj.object_id} className="flex items-center gap-3 rounded-xl border border-neutral-800 p-3">
                                <div className="flex-1">
                                    <p className="font-medium capitalize">{obj.name}</p>
                                    <p className="text-sm text-neutral-500">
                                        {obj.last_seen_at
                                            ? `Last seen ${obj.last_location} · ${new Date(obj.last_seen_at).toLocaleString()}`
                                            : "Not seen yet"}
                                    </p>
                                </div>
                                <button
                                    onClick={() => run(() => api.delete(`/care/objects/${obj.object_id}`), "Removed")}
                                    className="rounded-lg border border-neutral-700 p-2 text-neutral-400 hover:text-red-400"
                                    title="Remove"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        ))}
                    </div>

                    <div className="flex gap-2">
                        <input
                            value={objectName}
                            onChange={(e) => setObjectName(e.target.value)}
                            placeholder="e.g. glasses, keys, phone, wallet"
                            maxLength={60}
                            className={`flex-1 ${inputClass}`}
                        />
                        <button
                            onClick={() =>
                                run(async () => {
                                    await api.post("/care/objects", { name: objectName });
                                    setObjectName("");
                                }, "Added")
                            }
                            disabled={!objectName.trim()}
                            className="rounded-xl bg-emerald-600 px-4 hover:bg-emerald-500 disabled:opacity-50"
                        >
                            Add
                        </button>
                    </div>
                </Card>

                {/* FAMILY ALERTS */}

                <Card title="Family alerts (Telegram)" icon={<Bell className="h-5 w-5 text-emerald-400" />}>
                    {!telegram.configured ? (
                        <ol className="list-decimal space-y-2 pl-5 text-sm text-neutral-300">
                            <li>
                                In Telegram, message <b>@BotFather</b>, send <code>/newbot</code>,
                                and follow the steps. Copy the bot token it gives you.
                            </li>
                            <li>
                                Set it before starting the backend:{" "}
                                <code className="rounded bg-neutral-800 px-1">
                                    $env:ORION_TELEGRAM_BOT_TOKEN = &quot;your-token&quot;
                                </code>
                            </li>
                            <li>Restart the backend and reopen this page.</li>
                        </ol>
                    ) : (
                        <>
                            {telegram.error && (
                                <p className="mb-3 text-sm text-red-400">{telegram.error}</p>
                            )}

                            <p className="mb-3 text-sm text-neutral-400">
                                Each family member opens your bot in Telegram and taps
                                <b> Start</b>, then appears below.
                            </p>

                            <div className="mb-4 space-y-2">
                                {telegram.contacts.map((contact) => (
                                    <div key={contact.contact_id} className="flex items-center gap-3 rounded-xl border border-neutral-800 p-3">
                                        <p className="flex-1">{contact.name}</p>
                                        <button
                                            onClick={() => run(() => api.delete(`/care/contacts/${contact.contact_id}`), "Removed")}
                                            className="rounded-lg border border-neutral-700 p-2 text-neutral-400 hover:text-red-400"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    </div>
                                ))}

                                {telegram.recent_chats.map((chat) => (
                                    <div key={chat.telegram_chat_id} className="flex items-center gap-3 rounded-xl border border-dashed border-emerald-700 p-3">
                                        <p className="flex-1 text-neutral-300">{chat.name} (new)</p>
                                        <button
                                            onClick={() => run(() => api.post("/care/contacts", chat), "Contact added")}
                                            className="rounded-lg bg-emerald-600 px-3 py-1 text-sm hover:bg-emerald-500"
                                        >
                                            Add
                                        </button>
                                    </div>
                                ))}
                            </div>

                            <div className="flex flex-wrap gap-3">
                                <button
                                    onClick={() => run(async () => undefined, "Refreshed")}
                                    className="rounded-xl border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900"
                                >
                                    Check for new contacts
                                </button>
                                <button
                                    onClick={() => run(() => api.post("/care/contacts/test"), "Test message sent")}
                                    disabled={telegram.contacts.length === 0}
                                    className="flex items-center gap-2 rounded-xl border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900 disabled:opacity-40"
                                >
                                    <Send className="h-4 w-4" />
                                    Send test message
                                </button>
                            </div>
                        </>
                    )}
                </Card>

                {/* TODAY + SUMMARY */}

                <Card title="Today's doses" icon={<Pill className="h-5 w-5 text-emerald-400" />}>
                    {doses.length === 0 ? (
                        <p className="text-neutral-500">No doses scheduled today.</p>
                    ) : (
                        <ul className="space-y-2">
                            {doses.map((dose) => (
                                <li key={dose.dose_id} className="flex flex-wrap gap-x-3 text-sm">
                                    <span className="w-20 font-medium">{dose.time}</span>
                                    <span className="flex-1">{dose.name} {dose.amount}</span>
                                    <span
                                        className={
                                            dose.status === "taken"
                                                ? dose.late ? "text-amber-400" : "text-emerald-400"
                                                : dose.status === "missed"
                                                ? "text-red-400"
                                                : "text-neutral-500"
                                        }
                                    >
                                        {dose.status === "taken"
                                            ? `taken ${dose.confirmed_time}${dose.late ? " (late)" : ""}`
                                            : dose.status === "missed"
                                            ? "not confirmed"
                                            : "pending"}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}

                    <h3 className="mb-2 mt-6 text-sm font-medium text-neutral-300">
                        Daily summary preview
                    </h3>
                    <pre className="whitespace-pre-wrap rounded-xl bg-neutral-900 p-4 font-sans text-sm text-neutral-300">
                        {summary}
                    </pre>
                    <button
                        onClick={() => run(() => api.post("/care/summary/send"), "Summary sent")}
                        disabled={!telegram.configured || telegram.contacts.length === 0}
                        className="mt-3 flex items-center gap-2 rounded-xl border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-900 disabled:opacity-40"
                    >
                        <Send className="h-4 w-4" />
                        Send summary now
                    </button>
                </Card>

                <p className="text-center text-xs text-neutral-600">
                    Orion supports care and does not replace medical supervision.
                    Only the person&apos;s own confirmation marks a dose as taken.
                </p>
            </main>
        </div>
    );
}
