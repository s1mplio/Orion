// frontend/components/Landing/LandingPage.tsx

"use client";

import { useRouter } from "next/navigation";
import {
  BrainCircuit,
  Camera,
  Search,
} from "lucide-react";

export default function LandingPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-6">
      <div className="w-full max-w-5xl">

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
              Ask a scientific question and let Orion search papers,
              retrieve evidence, generate hypotheses, critique findings,
              design experiments, and build a final research report.
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

        </div>

        <div className="text-center mt-10 text-sm text-gray-600">
          Vision • Memory • Context • Research
        </div>

      </div>
    </div>
  );
}