"use client";

import { CheckCircle2, Loader2, Circle } from "lucide-react";

interface Props {
    currentStep: string;
}

const STEPS = [
    "Planning Research",
    "Searching Scientific Papers",
    "Extracting Evidence",
    "Analyzing Evidence",
    "Generating Scientific Synthesis",
    "Generating Hypothesis",
    "Reviewing Hypothesis",
    "Designing Experiments",
    "Writing Final Report",
    "Research Complete"
];

export default function Timeline({ currentStep }: Props) {

    const safeStep = currentStep ?? "";

const currentIndex = STEPS.findIndex(step =>
    safeStep.startsWith(step)
);

    return (

        <div className="space-y-4">

            {STEPS.map((step, index) => {

                if (index < currentIndex) {

                    return (

                        <div
                            key={step}
                            className="flex items-center gap-3 text-green-400"
                        >

                            <CheckCircle2 size={20} />

                            <span>{step}</span>

                        </div>

                    );

                }

                if (index === currentIndex) {

                    return (

                        <div
                            key={step}
                            className="flex items-center gap-3 text-blue-400"
                        >

                            <Loader2
                                size={20}
                                className="animate-spin"
                            />

                            <span>{step}</span>

                        </div>

                    );

                }

                return (

                    <div
                        key={step}
                        className="flex items-center gap-3 text-neutral-500"
                    >

                        <Circle size={18} />

                        <span>{step}</span>

                    </div>

                );

            })}

        </div>

    );

}