// frontend/app/research/page.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BrainCircuit,
  FileText,
} from "lucide-react";

import api, { getErrorMessage } from "@/services/api";
import { Input } from "@/components/ui/input";

// Matches ORION_MAX_QUESTION_CHARS on the backend.
const MAX_QUESTION_CHARS = 500;

export default function ResearchPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const router = useRouter();

  const startResearch = async () => {
    if (loading) {
      return;
    }

    if (!question.trim()) {
      alert("Please enter a research question.");
      return;
    }

    try {
      setLoading(true);

      const response = await api.post("/research", {
        question: question.trim(),
      });

      const jobId = response.data.job_id;

      // Keep the button disabled while navigating.
      router.push(`/research/${jobId}`);
    } catch (error) {
      console.error(error);

      alert(
        getErrorMessage(
          error,
          "Failed to start research."
        )
      );

      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white">

      <header className="border-b border-neutral-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">

          <div>
            <h1 className="text-xl font-semibold">
              Orion Research
            </h1>

            <p className="text-sm text-gray-500">
              Evidence-grounded autonomous research
            </p>
          </div>

          <div className="flex gap-3">
          <button
            onClick={() => router.push("/reports")}
            className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-gray-300 hover:bg-neutral-900"
          >
            <FileText className="h-4 w-4" />
            My Reports
          </button>

          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-gray-300 hover:bg-neutral-900"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          </div>

        </div>
      </header>

      <main className="flex min-h-[calc(100vh-73px)] items-center justify-center px-6">

        <div className="w-full max-w-3xl space-y-8">

          <div className="flex justify-center">
            <BrainCircuit className="h-16 w-16 text-blue-500" />
          </div>

          <div className="text-center">
            <h2 className="text-5xl font-bold">
              Literature Review
            </h2>

            <p className="mt-4 text-lg text-gray-400">
              Ask a research question. Orion reads real papers and writes a
              cited review with an APA reference list.
            </p>
          </div>

          <Input
            placeholder="e.g. What is known about microplastics in drinking water?"
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                startResearch();
              }
            }}
            maxLength={MAX_QUESTION_CHARS}
            className="h-14 border-neutral-700 bg-neutral-900 text-lg"
          />

          <p className="-mt-6 text-right text-xs text-neutral-500">
            {question.length}/{MAX_QUESTION_CHARS}
          </p>

          <button
            onClick={startResearch}
            disabled={loading}
            className="h-14 w-full rounded-lg bg-blue-600 text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading
              ? "Starting Research..."
              : "Start Research"}
          </button>

        </div>

      </main>

    </div>
  );
}