import {
    ApaText,
    paragraphs,
    type LiteratureReviewData,
    type SourceMap,
} from "@/lib/citations";

interface Props {
    review: LiteratureReviewData;
    sources: SourceMap;
    references: string[];
    variant?: "dark" | "print";
}

function Section({
    title,
    text,
    sources,
    headingClassName,
    bodyClassName,
    linkClassName,
}: {
    title: string;
    text?: string;
    sources: SourceMap;
    headingClassName: string;
    bodyClassName: string;
    linkClassName: string;
}) {
    const parts = paragraphs(text);

    if (parts.length === 0) {
        return null;
    }

    return (
        <section>
            <h3 className={headingClassName}>{title}</h3>

            {parts.map((part, index) => (
                <p key={index} className={bodyClassName}>
                    <ApaText
                        text={part}
                        sources={sources}
                        linkClassName={linkClassName}
                    />
                </p>
            ))}
        </section>
    );
}

export default function LiteratureReview({
    review,
    sources,
    references,
    variant = "dark",
}: Props) {
    const print = variant === "print";

    const heading = print
        ? "mt-8 mb-3 text-xl font-bold text-black"
        : "mt-10 mb-4 text-2xl font-semibold text-white";

    const body = print
        ? "mb-4 text-justify leading-7 text-neutral-900"
        : "mb-4 leading-8 text-neutral-300";

    const link = print
        ? "text-neutral-900 no-underline"
        : "text-cyan-400 hover:text-cyan-300";

    const sectionProps = {
        sources,
        headingClassName: heading,
        bodyClassName: body,
        linkClassName: link,
    };

    return (
        <article>
            <h2
                className={
                    print
                        ? "text-center text-2xl font-bold text-black"
                        : "text-3xl font-bold leading-tight text-white"
                }
            >
                {review.title}
            </h2>

            <Section {...sectionProps} title="Abstract" text={review.abstract} />
            <Section {...sectionProps} title="Introduction" text={review.introduction} />

            {review.themes.map((theme, index) => (
                <Section
                    {...sectionProps}
                    key={index}
                    title={theme.title}
                    text={theme.discussion}
                />
            ))}

            {review.research_gaps.length > 0 && (
                <section>
                    <h3 className={heading}>Research Gaps</h3>

                    <ul className="list-disc space-y-2 pl-6">
                        {review.research_gaps.map((gap, index) => (
                            <li key={index} className={body}>
                                <ApaText
                                    text={gap}
                                    sources={sources}
                                    linkClassName={link}
                                />
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <Section {...sectionProps} title="Conclusion" text={review.conclusion} />

            {references.length > 0 && (
                <section>
                    <h3 className={heading}>References</h3>

                    <ol className="space-y-3">
                        {references.map((entry, index) => (
                            <li
                                key={index}
                                id={`ref-${index}`}
                                // APA hanging indent
                                className={`pl-8 -indent-8 break-words ${
                                    print
                                        ? "leading-7 text-neutral-900"
                                        : "leading-7 text-neutral-300"
                                }`}
                            >
                                {entry}
                            </li>
                        ))}
                    </ol>
                </section>
            )}
        </article>
    );
}
