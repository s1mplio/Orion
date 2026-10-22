import { API_BASE_URL } from "@/services/api";

export interface Dose {
    dose_id: number;
    med_id: number;
    name: string;
    amount: string;
    instructions: string;
    scheduled_for: string;
    time: string;
    status: "pending" | "taken" | "missed";
    confirmed_time: string | null;
    late: boolean;
    photo: string | null;
}

export interface TodayData {
    person_name: string;
    time: string;
    date: string;
    repeat_minutes: number;
    due: Dose[];
    upcoming: Dose[];
    taken: Dose[];
    missed: Dose[];
}

export interface Medication {
    med_id: number;
    name: string;
    dose: string;
    instructions: string;
    times: string[];
    days: number[];
    active: boolean;
}

export interface TrackedObject {
    object_id: number;
    name: string;
    last_seen_at: string | null;
    last_location: string | null;
    last_photo: string | null;
}

export interface CareSettings {
    person_name: string;
    grace_minutes: string;
    repeat_minutes: string;
    summary_time: string;
}

export interface Contact {
    contact_id: number;
    name: string;
    telegram_chat_id: string;
}

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function carePhotoUrl(name: string) {
    return `${API_BASE_URL}/care/photos/${encodeURIComponent(name)}`;
}

/** "Good morning" etc. for the person's local time. */
export function greeting() {
    const hour = new Date().getHours();

    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
}

/** Spoken reminder for a due dose. */
export function reminderText(dose: Dose, personName: string) {
    const who = personName ? `${personName}, it's` : "It's";
    const amount = dose.amount ? `, ${dose.amount}` : "";
    const how = dose.instructions ? `. ${dose.instructions}` : "";

    return `${who} time for your ${dose.name}${amount}${how}. Tap the button when you have taken it.`;
}

// "I took it", "I've taken my tablet", "done, took it" ...
const TOOK_IT_PATTERN =
    /\b(i\s*(have|'ve)?\s*(took|taken)|took it|taken it|i\s*had it)\b/i;

export function saysTookIt(text: string) {
    return TOOK_IT_PATTERN.test(text);
}
