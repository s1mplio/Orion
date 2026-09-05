import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

from faster_whisper import WhisperModel


class SpeechInputService:
    """
    Orion Voice Input V1.

    Push-to-talk speech recognition.

    Flow:
        Microphone
            ↓
        Record
            ↓
        Remove silence
            ↓
        Normalize speech only
            ↓
        Whisper
            ↓
        Text
    """

    def __init__(
        self,
        model_size: str = "small.en",
        sample_rate: int = 16000,
        record_seconds: float = 4.0,
        input_device: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.record_seconds = record_seconds
        self.input_device = input_device

        print(
            f"Loading speech model: {model_size}"
        )

        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )

        print(
            "Speech model loaded."
        )

    # =====================================================
    # LISTEN
    # =====================================================

    def listen(
        self,
    ) -> Optional[str]:

        print(
            "\n================================"
        )
        print(
            "ORION LISTENING"
        )
        print(
            "================================"
        )
        print(
            "Speak now..."
        )

        frame_count = int(
            self.record_seconds
            * self.sample_rate
        )

        try:

            audio = sd.rec(
                frame_count,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=self.input_device,
            )

            sd.wait()

        except Exception as exc:

            print(
                "MICROPHONE_ERROR:",
                repr(exc),
            )

            return None

        audio = np.asarray(
            audio,
            dtype=np.float32,
        ).reshape(-1)

        if audio.size == 0:

            print(
                "No audio recorded."
            )

            return None

        # =================================================
        # RAW AUDIO STATS
        # =================================================

        peak = float(
            np.max(
                np.abs(audio)
            )
        )

        rms = float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

        print(
            f"Microphone peak: {peak:.4f}"
        )

        print(
            f"Microphone RMS : {rms:.4f}"
        )

        if peak < 0.002:

            print(
                "Microphone signal too weak."
            )

            return None

        # =================================================
        # REMOVE DC OFFSET
        # =================================================

        audio = (
            audio
            - np.mean(audio)
        )

        # =================================================
        # TRIM SILENCE
        # =================================================

        audio = self._trim_silence(
            audio
        )

        if audio is None:

            print(
                "No usable speech region found."
            )

            return None

        # =================================================
        # NORMALIZE SPEECH REGION
        # =================================================

        peak = float(
            np.max(
                np.abs(audio)
            )
        )

        if peak > 0:

            gain = min(
                0.75 / peak,
                4.0,
            )

            audio = (
                audio
                * gain
            )

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        )

        final_peak = float(
            np.max(
                np.abs(audio)
            )
        )

        final_rms = float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

        print(
            f"Processed peak: {final_peak:.4f}"
        )

        print(
            f"Processed RMS : {final_rms:.4f}"
        )

        print(
            f"Processed duration: "
            f"{len(audio) / self.sample_rate:.2f}s"
        )

        return self._transcribe(
            audio
        )

    # =====================================================
    # TRIM SILENCE
    # =====================================================

    def _trim_silence(
        self,
        audio: np.ndarray,
    ) -> Optional[np.ndarray]:

        """
        Simple energy-based trimming.

        This is not full VAD.

        It only removes obvious silence from the beginning
        and end of a push-to-talk recording.
        """

        frame_ms = 30

        frame_size = int(
            self.sample_rate
            * frame_ms
            / 1000
        )

        if len(audio) < frame_size:

            return audio

        energies = []

        starts = range(
            0,
            len(audio) - frame_size + 1,
            frame_size,
        )

        for start in starts:

            frame = audio[
                start:
                start + frame_size
            ]

            rms = float(
                np.sqrt(
                    np.mean(
                        np.square(frame)
                    )
                )
            )

            energies.append(
                rms
            )

        energies = np.asarray(
            energies,
            dtype=np.float32,
        )

        if energies.size == 0:

            return None

        # Estimate background noise from quieter frames.

        noise_floor = float(
            np.percentile(
                energies,
                30,
            )
        )

        threshold = max(
            noise_floor * 2.5,
            0.004,
        )

        print(
            f"Noise floor: {noise_floor:.5f}"
        )

        print(
            f"Speech threshold: {threshold:.5f}"
        )

        speech_indices = np.where(
            energies > threshold
        )[0]

        if len(
            speech_indices
        ) == 0:

            return None

        first = int(
            speech_indices[0]
        )

        last = int(
            speech_indices[-1]
        )

        # Keep some context before/after speech.

        padding_frames = 5

        first = max(
            0,
            first - padding_frames,
        )

        last = min(
            len(energies) - 1,
            last + padding_frames,
        )

        start_sample = (
            first
            * frame_size
        )

        end_sample = min(
            len(audio),
            (
                last + 1
            )
            * frame_size,
        )

        trimmed = audio[
            start_sample:
            end_sample
        ]

        # Reject absurdly short clips.

        minimum_samples = int(
            0.35
            * self.sample_rate
        )

        if len(trimmed) < minimum_samples:

            return None

        return trimmed

    # =====================================================
    # TRANSCRIBE
    # =====================================================

    def _transcribe(
        self,
        audio: np.ndarray,
    ) -> Optional[str]:

        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temp_file:

                temp_path = Path(
                    temp_file.name
                )

            audio_int16 = (
                audio
                * 32767.0
            ).astype(
                np.int16
            )

            write(
                str(temp_path),
                self.sample_rate,
                audio_int16,
            )

            print(
                "Transcribing..."
            )

            segments, info = (
                self.model.transcribe(
                    str(temp_path),

                    language="en",

                    beam_size=5,

                    vad_filter=False,

                    condition_on_previous_text=False,

                    temperature=0.0,

                    # IMPORTANT:
                    # no initial_prompt here
                )
            )

            print(
                "Detected language:",
                info.language,
            )

            try:

                print(
                    "Language probability:",
                    f"{info.language_probability:.3f}",
                )

            except Exception:

                pass

            text_parts = []

            segment_count = 0

            for segment in segments:

                segment_count += 1

                text = (
                    segment.text
                    .strip()
                )

                print(
                    f"SEGMENT {segment_count}:",
                    repr(text),
                )

                try:

                    print(
                        "  no_speech_prob:",
                        f"{segment.no_speech_prob:.3f}",
                    )

                except Exception:

                    pass

                try:

                    print(
                        "  avg_logprob:",
                        f"{segment.avg_logprob:.3f}",
                    )

                except Exception:

                    pass

                if text:

                    text_parts.append(
                        text
                    )

            if segment_count == 0:

                print(
                    "Whisper returned zero segments."
                )

                return None

            result = (
                " ".join(
                    text_parts
                )
                .strip()
            )

            if not result:

                print(
                    "No usable transcription."
                )

                return None

            print(
                "\n================================"
            )
            print(
                "YOU SAID"
            )
            print(
                "================================"
            )
            print(
                result
            )
            print(
                "================================"
            )

            return result

        except Exception as exc:

            print(
                "TRANSCRIPTION_ERROR:",
                repr(exc),
            )

            return None

        finally:

            if temp_path is not None:

                try:

                    temp_path.unlink(
                        missing_ok=True
                    )

                except Exception:

                    pass


# =========================================================
# STANDALONE TEST
# =========================================================

if __name__ == "__main__":

    service = SpeechInputService(
        model_size="small.en",
        sample_rate=16000,
        record_seconds=4.0,
    )

    result = service.listen()

    print(
        "\nFINAL RESULT:",
        result,
    )