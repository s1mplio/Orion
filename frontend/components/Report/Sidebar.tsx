interface Props {

    question: string;

    papers: number;

}

export default function Sidebar({

    question,

    papers

}: Props) {

    return (

        <aside className="sticky top-8 space-y-6">

            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-6">

                <h2 className="text-2xl font-bold">

                    Orion

                </h2>

                <p className="text-neutral-400 mt-2">

                    Autonomous Research Agent

                </p>

            </div>

            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-6">

                <h3 className="font-semibold">

                    Research Question

                </h3>

                <p className="mt-3 text-neutral-400">

                    {question}

                </p>

            </div>

            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-6">

                <h3 className="font-semibold mb-3">

                    Overview

                </h3>

                <div className="space-y-2 text-neutral-400">

                    <div>Papers : {papers}</div>

                    <div>Status : Completed</div>

                    <div>Model : OmniRoute</div>

                </div>

            </div>

        </aside>

    );

}