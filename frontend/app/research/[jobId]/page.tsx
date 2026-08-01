"use client";

import Timeline from "@/components/Research/Timeline";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import api from "@/services/api";

interface Log {
    time: string;
    message: string;
}

export default function ResearchPage() {

    const { jobId } = useParams();
    const router = useRouter();

    const [status, setStatus] = useState("queued");
    const [progress, setProgress] = useState(0);
    const [currentStep, setCurrentStep] = useState("Waiting...");
    const [question, setQuestion] = useState("");
    const [logs, setLogs] = useState<Log[]>([]);

    useEffect(() => {

        if (!jobId) return;

        const interval = setInterval(async () => {

            try {

                const response = await api.get(`/research/${jobId}/status`);

                setStatus(response.data.status);
                setProgress(response.data.progress);
                setCurrentStep(response.data.current_step);

                if (response.data.question) {
                    setQuestion(response.data.question);
                }

                if (response.data.logs) {
                    setLogs(response.data.logs);
                }

                if (response.data.status === "completed") {

                    clearInterval(interval);

                    router.push(`/report/${jobId}`);

                }

            } catch (err) {

                console.error(err);

            }

        }, 1000);

        return () => clearInterval(interval);

    }, [jobId, router]);

    return (

        <div className="min-h-screen bg-gradient-to-b from-black via-neutral-950 to-black text-white">

            <div className="max-w-5xl mx-auto py-16 px-8">

                {/* Header */}

                <div className="text-center mb-14">

                    <h1 className="text-6xl font-bold tracking-tight">
                        Orion
                    </h1>

                    <p className="text-neutral-400 mt-4 text-xl">
                        Autonomous Scientific Research Platform
                    </p>

                </div>

                {/* Main Card */}

                <div className="rounded-3xl border border-neutral-800 bg-neutral-900/40 backdrop-blur-xl p-10 shadow-2xl">

                    <h2 className="text-3xl font-semibold mb-2">
                        Research In Progress
                    </h2>

                    <p className="text-neutral-400 mb-8">
                        Orion is autonomously reading scientific papers,
                        extracting evidence, evaluating research quality,
                        generating hypotheses and designing experiments.
                    </p>

                    {/* Progress */}

                    <div className="mb-10">

                        <div className="flex justify-between mb-3">

                            <span className="font-medium">
                                {currentStep}
                            </span>

                            <span className="text-cyan-400 font-semibold">
                                {progress}%
                            </span>

                        </div>

                        <div className="h-3 rounded-full bg-neutral-800 overflow-hidden">

                            <div
                                className="h-full bg-gradient-to-r from-cyan-500 to-blue-600 transition-all duration-700"
                                style={{
                                    width: `${progress}%`
                                }}
                            />

                        </div>

                    </div>

                    {/* Research Info */}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">

                        <div className="rounded-2xl border border-neutral-800 p-6 bg-neutral-900/40">

                            <h3 className="text-xl font-semibold mb-4">
                                Research Question
                            </h3>

                            <p className="text-neutral-300 leading-7">

                                {question || "Preparing research..."}

                            </p>

                        </div>

                        <div className="rounded-2xl border border-neutral-800 p-6 bg-neutral-900/40">

                            <h3 className="text-xl font-semibold mb-4">
                                Research Status
                            </h3>

                            <div className="space-y-3 text-neutral-300">

                                <div className="flex justify-between">

                                    <span>Status</span>

                                    <span className="text-cyan-400 capitalize">
                                        {status}
                                    </span>

                                </div>

                                <div className="flex justify-between">

                                    <span>Progress</span>

                                    <span>{progress}%</span>

                                </div>

                                <div className="flex justify-between">

                                    <span>Model</span>

                                    <span>Gemini-3-Flash-Preview</span>

                                </div>

                                <div className="flex justify-between">

                                    <span>Current Step</span>

                                    <span className="text-right ml-4">
                                        {currentStep}
                                    </span>

                                </div>

                            </div>

                        </div>

                    </div>

                    {/* Timeline */}

                    <Timeline currentStep={currentStep} />

                    {/* Live Activity */}

                    <div className="mt-10 rounded-2xl border border-neutral-800 bg-neutral-900/40 backdrop-blur-xl p-6">

                        <h2 className="text-2xl font-semibold mb-5">
                            Live Activity
                        </h2>

                        <div className="space-y-3 max-h-72 overflow-y-auto">

                            {logs.length === 0 ? (

                                <p className="text-neutral-500">
                                    Waiting for pipeline...
                                </p>

                            ) : (

                                logs.map((log, index) => (

                                    <div
                                        key={index}
                                        className="border-l-2 border-cyan-500 pl-4 text-sm"
                                    >

                                        <span className="text-neutral-500">
                                            {log.time}
                                        </span>

                                        <span className="ml-3 text-neutral-300">
                                            {log.message}
                                        </span>

                                    </div>

                                ))

                            )}

                        </div>

                    </div>

                </div>

            </div>

        </div>

    );

}