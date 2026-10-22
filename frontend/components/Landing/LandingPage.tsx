// frontend/components/Landing/LandingPage.tsx

"use client";

import { useRouter } from "next/navigation";
import {
  BrainCircuit,
  Camera,
  FileText,
  FlaskConical,
  HeartHandshake,
  Search,
} from "lucide-react";

export default function LandingPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-6">
      <div className="w-full max-w-5xl py-12">

        <div className="text-center mb-12">
          <div className="flex justify-center mb-6">
            <BrainCircuit className="w-16 h-16 text-blue-500" />
          </div>

          <h1 className="text-6xl font-bold">
            Orion
          </h1>

          <p className="text-gray-400 mt-4 text-xl">
            Context-Aware Multimodal AI Companion
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          <button
            onClick={() => router.push("/research")}
            className="group rounded-2xl border border-neutral-800 bg-neutral-950 p-8 text-left transition hover:border-blue-500 hover:bg-neutral-900"
          >
            <div className="flex items-center gap-4 mb-5">
              <div className="rounded-xl bg-blue-500/10 p-3">
                <Search className="w-8 h-8 text-blue-500" />
              </div>

              <h2 className="text-2xl font-semibold">
                Research
              </h2>
            </div>

            <p className="text-gray-400 leading-relaxed">
              Get a cited literature review in minutes. Orion reads real
              papers, organizes findings into themes and research gaps,
              and cites every claim in APA style down to the page.
            </p>

            <div className="mt-6 text-blue-400 font-medium">
              Open Research →
            </div>
          </button>

          <button
            onClick={() => router.push("/companion")}
            className="group rounded-2xl border border-neutral-800 bg-neutral-950 p-8 text-left transition hover:border-purple-500 hover:bg-neutral-900"
          >
            <div className="flex items-center gap-4 mb-5">
              <div className="rounded-xl bg-purple-500/10 p-3">
                <Camera className="w-8 h-8 text-purple-400" />
              </div>

              <h2 className="text-2xl font-semibold">
                Companion
              </h2>
            </div>

            <p className="text-gray-400 leading-relaxed">
              Give Orion access to your camera and interact with it using
              vision, contextual memory, conversation, goals, and eventually
              voice.
            </p>

            <div className="mt-6 text-purple-400 font-medium">
              Open Companion →
            </div>
          </button>

          <button
            onClick={() => router.push("/lab")}
            className="group rounded-2xl border border-neutral-800 bg-neutral-950 p-8 text-left transition hover:border-emerald-500 hover:bg-neutral-900"
          >
            <div className="flex items-center gap-4 mb-5">
              <div className="rounded-xl bg-emerald-500/10 p-3">
                <FlaskConical className="w-8 h-8 text-emerald-400" />
              </div>

              <h2 className="text-2xl font-semibold">
                Lab Copilot
              </h2>
            </div>

            <p className="text-gray-400 leading-relaxed">
              Point a camera at your bench. Orion logs each step with
              photos, then writes your lab notebook, including deviations
              from the protocol.
            </p>

            <div className="mt-6 text-emerald-400 font-medium">
              Open Lab Copilot →
            </div>
          </button>

          <button
            onClick={() => router.push("/care")}
            className="group rounded-2xl border border-neutral-800 bg-neutral-950 p-8 text-left transition hover:border-rose-400 hover:bg-neutral-900"
          >
            <div className="flex items-center gap-4 mb-5">
              <div className="rounded-xl bg-rose-500/10 p-3">
                <HeartHandshake className="w-8 h-8 text-rose-400" />
              </div>

              <h2 className="text-2xl font-semibold">
                Care
              </h2>
            </div>

            <p className="text-gray-400 leading-relaxed">
              Medicine reminders, &ldquo;where are my glasses?&rdquo;, and
              Telegram alerts to family when a dose is missed.
            </p>

            <div className="mt-6 text-rose-400 font-medium">
              Open Care →
            </div>
          </button>

        </div>

        <div className="mt-6 flex justify-center">
          <button
            onClick={() => router.push("/reports")}
            className="flex items-center gap-2 rounded-xl border border-neutral-800 px-5 py-3 text-sm text-gray-300 transition hover:border-blue-500 hover:bg-neutral-900"
          >
            <FileText className="w-4 h-4" />
            My Reports
          </button>
        </div>

        <div className="text-center mt-10 text-sm text-gray-600">
          Vision • Memory • Context • Research
        </div>

      </div>
    </div>
  );
}