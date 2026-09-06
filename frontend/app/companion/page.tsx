"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BrainCircuit,
  Mic,
  MicOff,
  Search,
  Send,
} from "lucide-react";

import VisionCamera from "@/components/companion/VisionCamera";
import api from "@/services/api";

interface Message {
  role: "user" | "orion";
  content: string;
}

interface BrowserSpeechRecognitionEvent {
  results: {
    [index: number]: {
      [index: number]: {
        transcript: string;
      };
    };
  };
}

interface BrowserSpeechRecognitionErrorEvent {
  error: string;
}

interface BrowserSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult:
    | ((
        event: BrowserSpeechRecognitionEvent
      ) => void)
    | null;
  onerror:
    | ((
        event: BrowserSpeechRecognitionErrorEvent
      ) => void)
    | null;
}

interface SpeechRecognitionConstructor {
  new (): BrowserSpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export default function CompanionPage() {
  const router = useRouter();

  const recognitionRef =
    useRef<BrowserSpeechRecognition | null>(null);

  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "orion",
      content:
        "Orion Companion online. What would you like to talk about?",
    },
  ]);

  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] =
    useState(false);

  // =====================================================
  // BROWSER VOICE INPUT
  // =====================================================

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setVoiceSupported(false);
      return;
    }

    setVoiceSupported(true);

    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-IN";

    recognition.onstart = () => {
      setListening(true);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognition.onerror = (event) => {
      console.error(
        "Speech recognition error:",
        event.error
      );

      setListening(false);
    };

    recognition.onresult = (event) => {
      const transcript =
        event.results?.[0]?.[0]?.transcript?.trim();

      if (!transcript) {
        return;
      }

      setMessage((currentMessage) => {
        if (!currentMessage.trim()) {
          return transcript;
        }

        return `${currentMessage.trim()} ${transcript}`;
      });
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
      recognitionRef.current = null;
    };
  }, []);

  function toggleVoiceInput() {
    if (!voiceSupported) {
      return;
    }

    const recognition =
      recognitionRef.current;

    if (!recognition) {
      return;
    }

    try {
      if (listening) {
        recognition.stop();
      } else {
        recognition.start();
      }
    } catch (error) {
      console.error(
        "Unable to toggle speech recognition:",
        error
      );

      setListening(false);
    }
  }

  // =====================================================
  // SEND COMPANION MESSAGE
  // =====================================================

  async function sendMessage() {
    const trimmedMessage = message.trim();

    if (!trimmedMessage || loading) {
      return;
    }

    setMessage("");

    setMessages((previousMessages) => [
      ...previousMessages,
      {
        role: "user",
        content: trimmedMessage,
      },
    ]);

    setLoading(true);

    try {
      const response = await api.post(
        "/companion/chat",
        {
          message: trimmedMessage,
        }
      );

      const data = response.data;

      console.log(
        "COMPANION_CHAT_RESPONSE:",
        data
      );

      const answer =
        data.answer ||
        "I received your message, but I couldn't generate a response.";

      setMessages((previousMessages) => [
        ...previousMessages,
        {
          role: "orion",
          content: answer,
        },
      ]);

      // -------------------------------------------------
      // Automatic Companion -> Research V2 handoff.
      // -------------------------------------------------

      if (
        data.intent === "research" &&
        data.job_id
      ) {
        const researchJobId =
          String(data.job_id);

        console.log(
          "RESEARCH_JOB_ID:",
          researchJobId
        );

        window.setTimeout(() => {
          router.push(
            `/research/${researchJobId}`
          );
        }, 900);

        return;
      }
    } catch (error) {
      console.error(
        "Companion chat error:",
        error
      );

      setMessages((previousMessages) => [
        ...previousMessages,
        {
          role: "orion",
          content:
            "I couldn't reach the Orion backend. Check that the backend is running.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // =====================================================
  // DIRECT RESEARCH MODE
  // =====================================================

  function openResearchMode() {
    router.push("/research");
  }

  return (
    <div className="min-h-screen bg-black text-white">

      {/* Header */}

      <header className="border-b border-neutral-800 bg-black">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">

          <div className="flex items-center gap-3">

            <div className="rounded-xl bg-blue-500/10 p-2">
              <BrainCircuit className="h-6 w-6 text-blue-500" />
            </div>

            <div>
              <h1 className="text-xl font-semibold">
                Orion Companion
              </h1>

              <p className="text-sm text-neutral-500">
                Vision • Context • Memory
              </p>
            </div>

          </div>

          <div className="flex items-center gap-3">

            <button
              onClick={openResearchMode}
              className="flex items-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm text-blue-300 transition hover:bg-blue-500/20"
            >
              <Search className="h-4 w-4" />
              Research
            </button>

            <button
              onClick={() => router.push("/")}
              className="flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 transition hover:bg-neutral-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>

          </div>

        </div>
      </header>

      {/* Workspace */}

      <main className="mx-auto max-w-7xl px-6 py-6">

        <div className="grid min-h-[calc(100vh-130px)] grid-cols-1 gap-6 lg:grid-cols-2">

          {/* Camera */}

          <section className="overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950">

            <div className="border-b border-neutral-800 px-6 py-4">

              <h2 className="font-semibold">
                Live Vision
              </h2>

              <p className="mt-1 text-sm text-neutral-500">
                Orion&apos;s visual perception
              </p>

            </div>

            <VisionCamera />

          </section>

          {/* Conversation */}

          <section className="flex min-h-[650px] flex-col overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950">

            {/* Conversation Header */}

            <div className="border-b border-neutral-800 px-6 py-4">

              <div className="flex items-center justify-between gap-4">

                <div>
                  <h2 className="font-semibold">
                    Conversation
                  </h2>

                  <p className="mt-1 text-sm text-neutral-500">
                    Talk with Orion using contextual memory
                  </p>
                </div>

                <button
                  onClick={openResearchMode}
                  className="hidden items-center gap-2 rounded-lg border border-neutral-700 px-3 py-2 text-xs text-neutral-300 transition hover:border-blue-500/50 hover:bg-blue-500/10 hover:text-blue-300 sm:flex"
                >
                  <Search className="h-4 w-4" />
                  Deep Research
                </button>

              </div>

            </div>

            {/* Messages */}

            <div className="flex-1 space-y-5 overflow-y-auto p-6">

              {messages.map((chatMessage, index) => {

                const isUser =
                  chatMessage.role === "user";

                return (
                  <div
                    key={index}
                    className={`flex ${
                      isUser
                        ? "justify-end"
                        : "justify-start"
                    }`}
                  >

                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                        isUser
                          ? "bg-blue-600 text-white"
                          : "border border-neutral-800 bg-neutral-900 text-neutral-200"
                      }`}
                    >

                      <div
                        className={`mb-1 text-xs font-medium ${
                          isUser
                            ? "text-blue-200"
                            : "text-blue-400"
                        }`}
                      >
                        {isUser
                          ? "You"
                          : "Orion"}
                      </div>

                      <p className="whitespace-pre-wrap leading-relaxed">
                        {chatMessage.content}
                      </p>

                    </div>

                  </div>
                );
              })}

              {loading && (
                <div className="flex justify-start">

                  <div className="rounded-2xl border border-neutral-800 bg-neutral-900 px-4 py-3">

                    <div className="mb-1 text-xs font-medium text-blue-400">
                      Orion
                    </div>

                    <p className="text-neutral-400">
                      Thinking...
                    </p>

                  </div>

                </div>
              )}

            </div>

            {/* Input */}

            <div className="border-t border-neutral-800 p-4">

              <div className="flex gap-3">

                <input
                  value={message}
                  onChange={(event) =>
                    setMessage(event.target.value)
                  }
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder={
                    listening
                      ? "Listening..."
                      : "Ask Orion..."
                  }
                  disabled={loading}
                  className="flex-1 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-white outline-none transition placeholder:text-neutral-600 focus:border-blue-500 disabled:opacity-50"
                />

                <button
                  onClick={toggleVoiceInput}
                  disabled={
                    loading ||
                    !voiceSupported
                  }
                  title={
                    voiceSupported
                      ? listening
                        ? "Stop listening"
                        : "Speak to Orion"
                      : "Voice input is not supported in this browser"
                  }
                  className={`flex items-center justify-center rounded-xl border px-4 py-3 transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    listening
                      ? "border-red-500/50 bg-red-500/10 text-red-400 hover:bg-red-500/20"
                      : "border-neutral-700 bg-neutral-900 text-neutral-300 hover:border-blue-500/50 hover:text-blue-400"
                  }`}
                >
                  {listening ? (
                    <MicOff className="h-5 w-5" />
                  ) : (
                    <Mic className="h-5 w-5" />
                  )}
                </button>

                <button
                  onClick={sendMessage}
                  disabled={
                    loading ||
                    !message.trim()
                  }
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Send className="h-4 w-4" />

                  <span className="hidden sm:inline">
                    Send
                  </span>
                </button>

              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 px-1">

                <p className="text-xs text-neutral-600">
                  {voiceSupported
                    ? "Press Enter to send • Use the microphone to dictate"
                    : "Press Enter to send • Browser voice input unavailable"}
                </p>

                <button
                  onClick={openResearchMode}
                  className="flex items-center gap-2 text-xs font-medium text-blue-400 transition hover:text-blue-300 sm:hidden"
                >
                  <Search className="h-3.5 w-3.5" />
                  Open Deep Research
                </button>

              </div>

            </div>

          </section>

        </div>

      </main>

    </div>
  );
}
