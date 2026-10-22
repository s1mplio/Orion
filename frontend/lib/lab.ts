export interface LabEntryDetails {
    materials?: string[];
    equipment?: string[];
    observation?: string;
    visible_text?: string[];
    safety_concern?: string | null;
}

export interface LabEntry {
    entry_id: number;
    kind: "observation" | "note";
    started_at: string;
    ended_at: string;
    activity: string;
    details: LabEntryDetails;
    has_image: boolean;
}

export interface LabNotebook {
    title: string;
    objective: string;
    materials: string[];
    equipment: string[];
    procedure: { time: string; step: string }[];
    observations: string[];
    deviations: string[];
    safety_notes: string[];
    summary: string;
    background?: {
        research_job_id: string;
        question?: string;
        text: string;
        references: string[];
    } | null;
    generated_at?: string;
}

export interface LabSession {
    session_id: string;
    title: string;
    protocol: string;
    research_job_id: string | null;
    status: "active" | "ended";
    created_at: string;
    ended_at: string | null;
    notebook: LabNotebook | null;
    entries?: LabEntry[];
}

export interface LabSessionSummary {
    session_id: string;
    title: string;
    status: "active" | "ended";
    created_at: string;
    ended_at: string | null;
    entry_count: number;
}

/** "14:05" from an ISO timestamp. */
export function clock(timestamp: string) {
    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }

    return date.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
    });
}

/** "14:05" or "14:05–14:09" for an entry. */
export function entryTime(entry: LabEntry) {
    const start = clock(entry.started_at);
    const end = clock(entry.ended_at);

    return start === end ? start : `${start}–${end}`;
}
