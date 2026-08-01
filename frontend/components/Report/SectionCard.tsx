import { ReactNode } from "react";

interface Props {
    id?: string;
    title: string;
    children: ReactNode;
    icon?: ReactNode;
    blue?: boolean;
}

export default function SectionCard({
    id,
    title,
    children,
    icon,
    blue = false
}: Props) {

    return (

        <section
            id={id}
            className={`rounded-3xl border p-8 shadow-xl ${
                blue
                    ? "border-cyan-500/30 bg-cyan-950/10"
                    : "border-neutral-800 bg-neutral-900"
            }`}
        >

            <div className="flex items-center gap-3 mb-6">

                {icon}

                <h2 className="text-3xl font-bold">
                    {title}
                </h2>

            </div>

            <div className="leading-8 text-neutral-300 whitespace-pre-wrap">

                {children}

            </div>

        </section>

    );

}