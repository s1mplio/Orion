"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Opens the device camera and captures JPEG frames from it.
 *
 * Pass `videoRef` to a <video> element's ref. The stream is
 * attached whenever that element mounts, so pages may render
 * the video later (after a start screen or loading state).
 * Releases the camera on unmount, even if permission was
 * still pending.
 */
export function useCamera() {
    const videoElementRef = useRef<HTMLVideoElement | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    const [ready, setReady] = useState(false);
    const [error, setError] = useState("");

    // Callback ref: runs when the <video> mounts or unmounts.
    const videoRef = useCallback((element: HTMLVideoElement | null) => {
        videoElementRef.current = element;

        if (element && streamRef.current) {
            element.srcObject = streamRef.current;
        }
    }, []);

    useEffect(() => {
        let cancelled = false;

        async function start() {
            // Browsers expose the camera only on https:// pages or
            // localhost. Plain http:// on a LAN address hides it.
            if (!window.isSecureContext) {
                setError(
                    "The browser blocks the camera on insecure pages. " +
                        "Open Orion over https:// or on localhost."
                );
                return;
            }

            if (!navigator.mediaDevices?.getUserMedia) {
                setError("Camera access is not available in this browser.");
                return;
            }

            try {
                const mediaStream =
                    await navigator.mediaDevices.getUserMedia({
                        video: true,
                        audio: false,
                    });

                if (cancelled) {
                    mediaStream.getTracks().forEach((track) => track.stop());
                    return;
                }

                streamRef.current = mediaStream;

                if (videoElementRef.current) {
                    videoElementRef.current.srcObject = mediaStream;
                }

                setReady(true);
            } catch (err) {
                console.error("Camera error:", err);

                if (cancelled) {
                    return;
                }

                const name = err instanceof DOMException ? err.name : "";

                setError(
                    name === "NotReadableError"
                        ? "The camera is being used by another app or browser tab. Close it and reload."
                        : name === "NotFoundError"
                          ? "No camera was found."
                          : "Unable to access the camera. Check browser permissions."
                );
            }
        }

        start();

        return () => {
            cancelled = true;
            streamRef.current?.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        };
    }, []);

    /** Capture the current frame as a JPEG, or null if not ready. */
    async function capture(): Promise<Blob | null> {
        const video = videoElementRef.current;

        if (!video || !video.videoWidth || !video.videoHeight) {
            return null;
        }

        const canvas =
            canvasRef.current || document.createElement("canvas");
        canvasRef.current = canvas;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext("2d");

        if (!context) {
            return null;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        return new Promise((resolve) => {
            canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.8);
        });
    }

    return { videoRef, ready, error, capture };
}
