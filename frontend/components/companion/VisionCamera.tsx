"use client";

import { useState } from "react";

import { useCamera } from "@/lib/useCamera";
import api, { getErrorMessage } from "@/services/api";

export default function VisionCamera() {
  const { videoRef, ready, error, capture } = useCamera();

  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  async function analyzeFrame() {
    setLoading(true);
    setAnswer("");

    try {
      const blob = await capture();

      if (!blob) {
        setAnswer("The camera is not ready yet.");
        return;
      }

      const formData = new FormData();

      formData.append(
        "image",
        blob,
        "orion-frame.jpg"
      );

      formData.append(
        "prompt",
        "Describe what you see in this image. Focus on important objects, people, text, and anything relevant to the user."
      );

      const response = await api.post(
        "/companion/vision",
        formData
      );

      setAnswer(
        response.data.answer ||
          "I couldn't describe the image."
      );
    } catch (err) {
      console.error("Vision request error:", err);

      setAnswer(
        getErrorMessage(
          err,
          "I couldn't analyze the image."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="relative overflow-hidden rounded-xl border border-neutral-800 bg-black">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full"
        />

        {!ready && (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-neutral-400">
            {error || "Starting camera..."}
          </div>
        )}
      </div>

      <button
        onClick={analyzeFrame}
        disabled={!ready || loading}
        className="rounded-xl bg-blue-600 px-4 py-3 font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading
          ? "Orion is looking..."
          : "Ask Orion"}
      </button>

      {answer && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="mb-2 text-xs font-medium text-blue-400">
            Orion
          </h2>

          <p className="leading-relaxed text-neutral-200">
            {answer}
          </p>
        </div>
      )}
    </div>
  );
}
