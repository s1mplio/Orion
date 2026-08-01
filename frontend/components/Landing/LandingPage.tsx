"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import api from "@/services/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { BrainCircuit } from "lucide-react";

export default function LandingPage() {

    const [question, setQuestion] = useState("");

    const router = useRouter();

    const startResearch = async () => {

        if (!question.trim()) {
            alert("Please enter a research question.");
            return;
        }

        try {

            console.log("Sending request...");

            const response = await api.post("/research", {
                question: question
            });

            console.log(response.data);

            const jobId = response.data.job_id;

            router.push(`/research/${jobId}`);

        } catch (error) {

            console.error(error);

            alert("Failed to start research. Check browser console.");

        }

    };

    return (

        <div className="min-h-screen bg-black text-white flex items-center justify-center px-6">

            <div className="w-full max-w-3xl space-y-8">

                <div className="flex justify-center">

                    <BrainCircuit
                        className="w-16 h-16 text-blue-500"
                    />

                </div>

                <div className="text-center">

                    <h1 className="text-6xl font-bold">
                        Orion
                    </h1>

                    <p className="text-gray-400 mt-4 text-xl">
                        Autonomous AI Research Scientist
                    </p>

                </div>

                <Input
                    placeholder="Ask a scientific research question..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    className="h-14 text-lg bg-neutral-900 border-neutral-700"
                />

        <button onClick={startResearch}  className="w-full h-14 bg-blue-600 rounded text-white">
  Start Research
</button>
            </div>

        </div>

    );

}