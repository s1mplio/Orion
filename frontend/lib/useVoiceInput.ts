"use client";

import { useEffect, useRef, useState } from "react";

import api, { getErrorMessage } from "@/services/api";

export type VoiceStatus = "idle" | "listening" | "transcribing";

// Loudness (RMS, 0-1) treated as speech.
const SPEECH_LEVEL = 0.02;
// Stop this long after the person stops talking.
const SILENCE_MS = 1300;
// Give up if nobody speaks within this time.
const NO_SPEECH_MS = 7000;
// Never record longer than this.
const MAX_MS = 20000;

/**
 * Push-to-talk voice input that works in every browser.
 *
 * Records the microphone, stops automatically after a pause,
 * and transcribes on the Orion backend with local Whisper
 * (the browser Web Speech API silently fails in several
 * browsers). Calls onText with the recognized words.
 */
export function useVoiceInput(onText: (text: string) => void) {
    const [status, setStatus] = useState<VoiceStatus>("idle");
    const [error, setError] = useState("");

    const onTextRef = useRef(onText);
    const stopRef = useRef<(() => void) | null>(null);
    const cancelledRef = useRef(false);

    useEffect(() => {
        onTextRef.current = onText;
    });

    // Release the microphone if the page closes mid-recording.
    useEffect(() => {
        return () => {
            cancelledRef.current = true;
            stopRef.current?.();
        };
    }, []);

    async function start() {
        if (status !== "idle") {
            return;
        }

        setError("");

        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
            setError("Voice input is not supported in this browser.");
            return;
        }

        let stream: MediaStream;

        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (err) {
            const name = err instanceof DOMException ? err.name : "";

            setError(
                name === "NotAllowedError"
                    ? "Microphone access is blocked. Allow it in the browser's address bar."
                    : name === "NotFoundError"
                      ? "No microphone was found."
                      : "Couldn't open the microphone."
            );
            return;
        }

        cancelledRef.current = false;

        const recorder = new MediaRecorder(stream);
        const chunks: Blob[] = [];

        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 1024;
        audioContext.createMediaStreamSource(stream).connect(analyser);

        const samples = new Float32Array(analyser.fftSize);
        const startedAt = Date.now();
        let heardSpeech = false;
        let lastSoundAt = startedAt;

        // Watch the volume to stop after the person finishes.
        const monitor = setInterval(() => {
            analyser.getFloatTimeDomainData(samples);

            let sum = 0;
            for (const value of samples) sum += value * value;
            const level = Math.sqrt(sum / samples.length);

            const now = Date.now();

            if (level > SPEECH_LEVEL) {
                heardSpeech = true;
                lastSoundAt = now;
            }

            if (
                (heardSpeech && now - lastSoundAt > SILENCE_MS) ||
                (!heardSpeech && now - startedAt > NO_SPEECH_MS) ||
                now - startedAt > MAX_MS
            ) {
                stop();
            }
        }, 100);

        function stop() {
            clearInterval(monitor);

            if (recorder.state !== "inactive") {
                recorder.stop();
            }
        }

        stopRef.current = stop;

        recorder.ondataavailable = (event) => {
            if (event.data.size > 0) chunks.push(event.data);
        };

        recorder.onstop = async () => {
            stopRef.current = null;
            stream.getTracks().forEach((track) => track.stop());
            audioContext.close();

            if (cancelledRef.current) {
                setStatus("idle");
                return;
            }

            if (!heardSpeech) {
                setStatus("idle");
                setError("I didn't hear anything. Tap the button and speak.");
                return;
            }

            setStatus("transcribing");

            try {
                const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
                const formData = new FormData();
                formData.append("audio", blob, "speech.webm");

                const response = await api.post("/speech/transcribe", formData);
                const text = String(response.data.text || "").trim();

                if (text) {
                    onTextRef.current(text);
                } else {
                    setError("I couldn't make out the words. Please try again.");
                }
            } catch (err) {
                setError(getErrorMessage(err, "Couldn't understand the recording."));
            } finally {
                setStatus("idle");
            }
        };

        recorder.start();
        setStatus("listening");
    }

    /** Stop now (e.g. the person tapped the button again). */
    function stop() {
        stopRef.current?.();
    }

    return { status, error, start, stop };
}
