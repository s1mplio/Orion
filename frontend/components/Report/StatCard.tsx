import { ReactNode } from "react";

interface Props {

    icon: ReactNode;

    title: string;

    value: string;

}

export default function StatCard({

    icon,

    title,

    value

}: Props) {

    return (

        <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-6 shadow-lg">

            <div className="flex items-center gap-3">

                <div className="text-cyan-400">

                    {icon}

                </div>

                <p className="text-neutral-400">

                    {title}

                </p>

            </div>

            <h2 className="text-4xl font-bold mt-6">

                {value}

            </h2>

        </div>

    );

}