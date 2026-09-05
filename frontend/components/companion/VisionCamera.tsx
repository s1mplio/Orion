"use client";

import { useEffect, useRef, useState } from "react";

export default function VisionCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [cameraStarted, setCameraStarted] = useState(false);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    startCamera();

    return () => {
      stopCamera();
    };
  }, []);

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      setCameraStarted(true);
    } catch (error) {
      console.error("Camera error:", error);
    }
  }

  function stopCamera() {
    const video = videoRef.current;

    if (!video) {
      return;
    }

    const stream = video.srcObject as MediaStream | null;

    if (!stream) {
      return;
    }

    stream.getTracks().forEach((track) => {
      track.stop();
    });
  }

  async function analyzeFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas) {
      return;
    }

    setLoading(true);
    setAnswer("");

    try {
      const context = canvas.getContext("2d");

      if (!context) {
        throw new Error("Unable to access canvas.");
      }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
      );

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(
          (result) => resolve(result),
          "image/jpeg",
          0.8
        );
      });

      if (!blob) {
        throw new Error("Unable to capture frame.");
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

      const response = await fetch(
        "http://127.0.0.1:8000/companion/vision",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(
          `Vision request failed: ${response.status}`
        );
      }

      const data = await response.json();

      setAnswer(data.answer);
    } catch (error) {
      console.error("Vision request error:", error);
      setAnswer("I couldn't analyze the image.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-bold">
        Orion Vision
      </h1>

      <div className="relative overflow-hidden rounded-xl border">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full"
        />

        {!cameraStarted && (
          <div className="absolute inset-0 flex items-center justify-center">
            Starting camera...
          </div>
        )}
      </div>

      <canvas
        ref={canvasRef}
        className="hidden"
      />

      <button
        onClick={analyzeFrame}
        disabled={!cameraStarted || loading}
        className="rounded-lg bg-black px-4 py-3 text-white disabled:opacity-50"
      >
        {loading
          ? "Orion is looking..."
          : "Ask Orion"}
      </button>

      {answer && (
        <div className="rounded-xl border p-4">
          <h2 className="mb-2 font-semibold">
            Orion
          </h2>

          <p>{answer}</p>
        </div>
      )}
    </div>
  );
}