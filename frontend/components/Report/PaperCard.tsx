import { BookOpen } from "lucide-react";

interface Paper {

    title: string;

    authors: string[] | string;

    year: number;

    citation_count: number;

    url: string;

}

export default function PaperCard({

    paper

}: {

    paper: Paper;

}) {

    return (

        <div className="group rounded-3xl border border-neutral-800 bg-neutral-950 p-7 hover:border-cyan-500 hover:-translate-y-1 transition-all duration-300">

            <div className="flex justify-between items-start gap-5">

                <div className="flex gap-5">

                    <div className="h-14 w-14 rounded-2xl bg-cyan-500/10 flex items-center justify-center">

                        <BookOpen className="h-7 w-7 text-cyan-400"/>

                    </div>

                    <div>

                        <h3 className="text-xl font-semibold group-hover:text-cyan-300">

                            {paper.title}

                        </h3>

                        <p className="mt-2 text-neutral-400">

                            {Array.isArray(paper.authors)

                                ? paper.authors.join(", ")

                                : paper.authors}

                        </p>

                        <div className="flex gap-3 mt-5">

                            <span className="px-3 py-1 rounded-full bg-neutral-800 text-sm">

                                📅 {paper.year}

                            </span>

                            <span className="px-3 py-1 rounded-full bg-blue-900/30 text-blue-300 text-sm">

                                📖 {paper.citation_count} citations

                            </span>

                        </div>

                    </div>

                </div>

                <a

                    href={paper.url}

                    target="_blank"

                    rel="noopener noreferrer"

                    className="px-5 py-3 rounded-xl bg-cyan-500 text-black font-semibold hover:bg-cyan-400"

                >

                    Open →

                </a>

            </div>

        </div>

    );

}