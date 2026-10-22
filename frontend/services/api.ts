import axios from "axios";

// API calls go to this site's /api route, which Next.js forwards to
// the backend (see next.config.ts). Same-origin requests work from
// localhost, a LAN address or a phone, over HTTP or HTTPS.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "/api";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export function getErrorMessage(
  error: unknown,
  fallback: string
): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === "string" && detail) {
      return detail;
    }

    if (!error.response) {
      return "Couldn't reach the Orion backend. Check that it is running.";
    }
  }

  return fallback;
}

export default api;
