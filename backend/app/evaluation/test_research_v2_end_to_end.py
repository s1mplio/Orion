from app.services.pipeline import run_pipeline


def print_section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def validate_pipeline(state):
    """
    Validate the important Research V2 stages.

    This does not judge scientific quality.
    It checks that the complete architecture successfully
    passes information from one stage to the next.
    """

    checks = []

    # -------------------------------------------------
    # Planner
    # -------------------------------------------------

    planner_passed = bool(
        getattr(
            state,
            "sub_questions",
            [],
        )
    )

    checks.append(
        (
            "Planner produced sub-questions",
            planner_passed,
        )
    )

    # -------------------------------------------------
    # Paper discovery
    # -------------------------------------------------

    papers = getattr(
        state,
        "papers",
        [],
    )

    papers_passed = bool(
        papers
    )

    checks.append(
        (
            "OpenAlex discovered papers",
            papers_passed,
        )
    )

    # -------------------------------------------------
    # Full-paper evidence
    # -------------------------------------------------

    evidence_objects = getattr(
        state,
        "evidence",
        [],
    )

    evidence_passed = bool(
        evidence_objects
    )

    checks.append(
        (
            "Evidence objects generated",
            evidence_passed,
        )
    )

    full_text_evidence = [
        evidence
        for evidence in evidence_objects
        if getattr(
            evidence,
            "source_type",
            "",
        ) == "full_text_rag"
    ]

    full_text_passed = bool(
        full_text_evidence
    )

    checks.append(
        (
            "Full-paper RAG used",
            full_text_passed,
        )
    )

    # -------------------------------------------------
    # Citations
    # -------------------------------------------------

    citation_objects = [
        evidence
        for evidence in full_text_evidence
        if getattr(
            evidence,
            "cited_chunk_ids",
            [],
        )
    ]

    citations_passed = bool(
        citation_objects
    )

    checks.append(
        (
            "Evidence contains chunk citations",
            citations_passed,
        )
    )

    # -------------------------------------------------
    # Provenance
    # -------------------------------------------------

    provenance_objects = [
        evidence
        for evidence in full_text_evidence
        if getattr(
            evidence,
            "retrieved_chunks",
            [],
        )
    ]

    provenance_passed = bool(
        provenance_objects
    )

    checks.append(
        (
            "Evidence contains provenance",
            provenance_passed,
        )
    )

    # -------------------------------------------------
    # Critic
    # -------------------------------------------------

    critic_passed = (
        getattr(
            state,
            "critic_results",
            None,
        )
        is not None
    )

    checks.append(
        (
            "Scientific critic completed",
            critic_passed,
        )
    )

    # -------------------------------------------------
    # Synthesis
    # -------------------------------------------------

    synthesis_passed = (
        getattr(
            state,
            "synthesis",
            None,
        )
        is not None
    )

    checks.append(
        (
            "Scientific synthesis completed",
            synthesis_passed,
        )
    )

    # -------------------------------------------------
    # Hypothesis
    # -------------------------------------------------

    hypothesis_passed = (
        getattr(
            state,
            "hypothesis",
            None,
        )
        is not None
    )

    checks.append(
        (
            "Hypothesis generated",
            hypothesis_passed,
        )
    )

    # -------------------------------------------------
    # Hypothesis review
    # -------------------------------------------------

    review_passed = (
        getattr(
            state,
            "hypothesis_review",
            None,
        )
        is not None
    )

    checks.append(
        (
            "Hypothesis critic completed",
            review_passed,
        )
    )

    # -------------------------------------------------
    # Experiments
    #
    # These only exist when hypothesis is accepted.
    # Therefore this is informational rather than a
    # mandatory pipeline PASS condition.
    # -------------------------------------------------

    experiments_available = (
        getattr(
            state,
            "experiments",
            None,
        )
        is not None
    )

    # -------------------------------------------------
    # Final report
    #
    # Same rule: pipeline intentionally skips this when
    # the hypothesis is not accepted.
    # -------------------------------------------------

    report_available = (
        getattr(
            state,
            "final_report",
            None,
        )
        is not None
    )

    return (
        checks,
        experiments_available,
        report_available,
    )


def print_research_summary(state):
    print_section(
        "RESEARCH V2 SUMMARY"
    )

    print(
        "Research Question:"
    )

    print(
        state.question
    )

    print()
    print(
        "Sub-questions:",
        len(
            getattr(
                state,
                "sub_questions",
                [],
            )
        ),
    )

    print(
        "Discovered papers:",
        len(
            getattr(
                state,
                "papers",
                [],
            )
        ),
    )

    print(
        "Evidence objects:",
        len(
            getattr(
                state,
                "evidence",
                [],
            )
        ),
    )

    full_text_count = sum(
        1
        for evidence in getattr(
            state,
            "evidence",
            [],
        )
        if getattr(
            evidence,
            "source_type",
            "",
        ) == "full_text_rag"
    )

    print(
        "Full-text RAG evidence:",
        full_text_count,
    )

    cited_chunks = set()

    source_papers = set()

    for evidence in getattr(
        state,
        "evidence",
        [],
    ):
        for chunk_id in getattr(
            evidence,
            "cited_chunk_ids",
            [],
        ):
            cited_chunks.add(
                chunk_id
            )

        for metadata in getattr(
            evidence,
            "retrieved_chunks",
            [],
        ):
            paper_title = metadata.get(
                "paper_title"
            )

            if paper_title:
                source_papers.add(
                    paper_title
                )

    print(
        "Unique cited chunks:",
        len(
            cited_chunks
        ),
    )

    print(
        "Retrieved source papers:",
        len(
            source_papers
        ),
    )

    print()
    print(
        "Critic:",
        (
            "AVAILABLE"
            if getattr(
                state,
                "critic_results",
                None,
            )
            else "MISSING"
        ),
    )

    print(
        "Synthesis:",
        (
            "AVAILABLE"
            if getattr(
                state,
                "synthesis",
                None,
            )
            else "MISSING"
        ),
    )

    print(
        "Hypothesis:",
        (
            "AVAILABLE"
            if getattr(
                state,
                "hypothesis",
                None,
            )
            else "MISSING"
        ),
    )

    print(
        "Hypothesis Review:",
        (
            "AVAILABLE"
            if getattr(
                state,
                "hypothesis_review",
                None,
            )
            else "MISSING"
        ),
    )

    print(
        "Experiments:",
        (
            "AVAILABLE"
            if getattr(
                state,
                "experiments",
                None,
            )
            else "NOT GENERATED"
        ),
    )

    print(
        "Final Report:",
        (
            "AVAILABLE"
            if getattr(
                state,
                "final_report",
                None,
            )
            else "NOT GENERATED"
        ),
    )


def print_validation(
    checks,
    experiments_available,
    report_available,
):
    print_section(
        "END-TO-END VALIDATION"
    )

    for name, passed in checks:
        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{name:<45}"
            f"{status}"
        )

    print()
    print(
        f"{'Experiments generated':<45}"
        f"{'YES' if experiments_available else 'NO'}"
    )

    print(
        f"{'Final report generated':<45}"
        f"{'YES' if report_available else 'NO'}"
    )

    mandatory_passed = all(
        passed
        for _, passed in checks
    )

    print()
    print("-" * 80)

    if mandatory_passed:
        print(
            "RESEARCH V2 CORE PIPELINE: PASS"
        )

        if (
            experiments_available
            and report_available
        ):
            print(
                "Hypothesis was accepted and the "
                "complete report path also executed."
            )

        else:
            print(
                "Core pipeline succeeded. Experiment/"
                "report generation may have been "
                "intentionally skipped if the "
                "hypothesis critic did not ACCEPT."
            )

    else:
        print(
            "RESEARCH V2 CORE PIPELINE: FAIL"
        )

        print(
            "At least one mandatory stage did not "
            "produce its expected output."
        )

    print("-" * 80)

    return mandatory_passed


def main():
    print_section(
        "ORION RESEARCH V2 END-TO-END TEST"
    )

    question = (
        "Can life survive beneath Europa's ice?"
    )

    print(
        "Question:",
        question,
    )

    print()
    print(
        "Starting complete Research V2 pipeline..."
    )

    state = run_pipeline(
        question
    )

    print_research_summary(
        state
    )

    (
        checks,
        experiments_available,
        report_available,
    ) = validate_pipeline(
        state
    )

    print_validation(
        checks=checks,
        experiments_available=(
            experiments_available
        ),
        report_available=(
            report_available
        ),
    )


if __name__ == "__main__":
    main()