import Link from "next/link";
import { ArrowLeft, HeartHandshake, Settings, Sun } from "lucide-react";

export default function CareHomePage() {
    return (
        <main className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
            <div className="w-full max-w-3xl">
                <div className="mb-10 text-center">
                    <HeartHandshake className="mx-auto mb-4 h-14 w-14 text-rose-400" />
                    <h1 className="text-4xl font-bold">Orion Care</h1>
                    <p className="mt-3 text-neutral-400">
                        Medicine reminders, a memory for where things are, and
                        alerts for family.
                    </p>
                </div>

                <div className="grid gap-6 md:grid-cols-2">
                    <Link
                        href="/care/today"
                        className="rounded-2xl border border-neutral-800 bg-neutral-950 p-8 transition hover:border-rose-400 hover:bg-neutral-900"
                    >
                        <Sun className="mb-4 h-8 w-8 text-amber-300" />
                        <h2 className="text-2xl font-semibold">Today screen</h2>
                        <p className="mt-2 text-neutral-400">
                            For the person at home. Large text, spoken
                            reminders, and voice questions. Best on a tablet.
                        </p>
                    </Link>

                    <Link
                        href="/care/setup"
                        className="rounded-2xl border border-neutral-800 bg-neutral-950 p-8 transition hover:border-rose-400 hover:bg-neutral-900"
                    >
                        <Settings className="mb-4 h-8 w-8 text-rose-300" />
                        <h2 className="text-2xl font-semibold">Caregiver setup</h2>
                        <p className="mt-2 text-neutral-400">
                            For family. Add medicines and schedules, things to
                            track, and Telegram alerts.
                        </p>
                    </Link>
                </div>

                <p className="mt-8 text-center text-xs text-neutral-600">
                    Orion supports care and does not replace medical supervision.
                </p>

                <div className="mt-6 flex justify-center">
                    <Link
                        href="/"
                        className="flex items-center gap-2 text-sm text-neutral-400 hover:text-white"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Back
                    </Link>
                </div>
            </div>
        </main>
    );
}
