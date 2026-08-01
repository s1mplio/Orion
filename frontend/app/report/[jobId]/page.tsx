"use client"
import Sidebar from "@/components/Report/Sidebar";
import SectionCard from "@/components/Report/SectionCard";
import StatCard from "@/components/Report/StatCard";
import PaperCard from "@/components/Report/PaperCard";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import api from "@/services/api";
import {
    FileText,
    FlaskConical,
    Brain,
    CheckCircle,
    BookOpen,
    Microscope
} from "lucide-react";

interface ScientificReport {
    title: string;
    executive_summary: string;
    background: string;
    evidence_summary: string;
    hypothesis: string;
    experiment_plan: string;
    conclusion: string;
    future_work: string;
}

interface Paper {
    title: string;
    authors: string[] | string;
    year: number;
    url: string;
    citation_count: number;
}

interface ReportData {
    question: string;
    papers_found: number;
    papers: Paper[];
    hypothesis: string | null;
    report: ScientificReport;
}
export default function ReportPage() {

    const { jobId } = useParams();

    const [data, setData] = useState<ReportData | null>(null);

    const [loading, setLoading] = useState(true);

    useEffect(() => {

        async function loadReport() {

            try {

                const response = await api.get(
                    `/research/${jobId}/result`
                );

                setData(response.data);

            } catch (err) {

                console.error(err);

            } finally {

                setLoading(false);

            }

        }

        if (jobId) loadReport();

    }, [jobId]);
    if (loading) {

        return (

            <div className="min-h-screen bg-black flex items-center justify-center">

                <div className="text-center">

                    <Brain className="mx-auto mb-6 h-16 w-16 text-cyan-400 animate-pulse"/>

                    <h1 className="text-3xl text-white font-bold">

                        Orion

                    </h1>

                    <p className="text-neutral-400 mt-3">

                        Preparing Scientific Report...

                    </p>

                </div>

            </div>

        );

    }

    if (!data) {

        return (

            <div className="min-h-screen bg-black flex items-center justify-center text-red-500">

                Failed to load report.

            </div>

        );

    }

    return (

        <div className="min-h-screen bg-black text-white">

            <div className="max-w-7xl mx-auto py-12 px-8">

    <div className="grid lg:grid-cols-[320px_1fr] gap-10">
        <Sidebar
    question={data.question}
    papers={data.papers_found}
/>  
                <div className="space-y-8">

                <div className="text-center">

                    <h1 className="text-6xl font-bold">
                        Orion
                    </h1>

                    <p className="text-neutral-400 mt-3 text-xl">
                        Autonomous AI Research Scientist
                    </p>

                </div>

                <div className="rounded-3xl bg-neutral-900 border border-neutral-800 p-8">

                    <h2 className="text-4xl font-bold leading-tight">
                        {data.report.title}
                    </h2>

                    <p className="mt-5 text-neutral-300">
                        <span className="font-semibold">
                            Research Question:
                        </span>{" "}
                        {data.question}
                    </p>
                    <div className="flex flex-wrap gap-6 mt-6 text-sm text-neutral-400">

    <span>📚 {data.papers_found} Papers</span>

    <span>🧠 Gemini-3-Flash-Preview</span>

    <span>⚡ Autonomous Pipeline</span>

</div>

                </div>

                <div className="grid md:grid-cols-3 gap-6">

                    <StatCard
                        icon={<BookOpen size={24}/>}
                        title="Papers"
                        value={String(data.papers_found)}
                    />

                    <StatCard
                        icon={<Brain size={24}/>}
                        title="AI Model"
                        value="Gemini-3-Flash-Preview"
                    />

                    <StatCard
                        icon={<CheckCircle size={24}/>}
                        title="Pipeline"
                        value="Completed"
                    />

                </div>

                <SectionCard
                    id="summary"
                    title="Executive Summary"
                    icon={<FileText className="text-cyan-400"/>}>
                    {data.report.executive_summary}



                </SectionCard>
                    
                

               <SectionCard

id="background"

title="Background"

icon={<BookOpen className="text-cyan-400"/>}

>

{data.report.background}

</SectionCard>

                <SectionCard

id="evidence"

title="Evidence Summary"

icon={<Microscope className="text-cyan-400"/>}

>

{data.report.evidence_summary}

</SectionCard>

                <SectionCard

id="hypothesis"

title="Hypothesis"

blue

icon={<Brain className="text-cyan-400"/>}

>

{data.report.hypothesis}

</SectionCard>

                <SectionCard

id="experiment"

title="Experiment Plan"

icon={<FlaskConical className="text-cyan-400"/>}

>

{data.report.experiment_plan}

</SectionCard>

                <SectionCard

id="conclusion"

title="Conclusion"

icon={<CheckCircle className="text-cyan-400"/>}

>

{data.report.conclusion}

</SectionCard>

                <SectionCard

id="future"

title="Future Work"

icon={<Brain className="text-cyan-400"/>}

>

{data.report.future_work}

</SectionCard>

        <SectionCard
            id="references"
            title={`Scientific Sources (${data.papers_found} Papers)`}
            icon={<BookOpen className="text-cyan-400" />}
        >

            <div className="space-y-6">

                {data.papers.map((paper, index) => (

                    <PaperCard
                        key={index}
                        paper={paper}
                    />

                ))}

            </div>

        </SectionCard>


</div>

            

                </div>

            </div>
                <footer className="border-t border-neutral-800 mt-16 pt-8 text-center text-neutral-500">

    <p className="text-sm">
        Generated autonomously by Orion • Multi-Agent Scientific Research System
    </p>

</footer>

        </div>

    );

}



