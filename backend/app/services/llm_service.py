# import transformers
# from transformers import (
#     AutoTokenizer,
#     AutoModelForCausalLM,
#     BitsAndBytesConfig,
# )


# class LLMService:

#     def __init__(self):

#         self.model_name = "Qwen/Qwen-3-4B"

#         print("\nLoading Qwen model...")
#         print("This happens only once when the server starts.\n")

#         quantization_config = BitsAndBytesConfig(
#             load_in_4bit=True
#         )

#         self.tokenizer = AutoTokenizer.from_pretrained(
#             self.model_name
#         )

#         self.model = AutoModelForCausalLM.from_pretrained(
#             self.model_name,
#             quantization_config=quantization_config,
#             device_map="auto",
#         )

#         print(f"Loaded {self.model_name}")
#         print(f"Transformers {transformers.__version__}\n")

#     def generate(self, prompt: str) -> str:

#         messages = [
#             {
#                 "role": "system",
#                 "content": (
#                     "You are a helpful scientific assistant. "
#                     "Never reveal reasoning. "
#                     "Return only the final answer."
#                 ),
#             },
#             {
#                 "role": "user",
#                 "content": prompt,
#             },
#         ]

#         text = self.tokenizer.apply_chat_template(
#             messages,
#             tokenize=False,
#             add_generation_prompt=True,
#             enable_thinking=False,
#         )

#         inputs = self.tokenizer(
#             text,
#             return_tensors="pt",
#         ).to(self.model.device)

#         outputs = self.model.generate(
#             **inputs,
#             max_new_tokens=1024,
#             do_sample=False,
#             eos_token_id=self.tokenizer.eos_token_id,
#             pad_token_id=self.tokenizer.eos_token_id,
#         )

#         generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]

#         return self.tokenizer.decode(
#             generated_tokens,
#             skip_special_tokens=True,
#         )



#---------------------------------------------------------------------------------------------------local LLM 

# import os

# from dotenv import load_dotenv
# from google import genai

# load_dotenv()


# class LLMService:

#     def __init__(self):

#         api_key = os.getenv("GEMINI_API_KEY")

#         if api_key is None:
#             raise ValueError("GEMINI_API_KEY not found in .env")

#         self.client = genai.Client(api_key=api_key)

#         self.model = "OmniRoute"

#         print("\n===================================")
#         print("Gemini Loaded Successfully")
#         print(f"Model : {self.model}")
#         print("===================================\n")

#     def generate(self, prompt: str) -> str:

#         response = self.client.models.generate_content(
#             model=self.model,
#             contents=prompt,
#         )

#         return response.text.strip()



# llm = LLMService()

#---------------------------------------------------------------------------------------------------------gemini
import os
import threading

from openai import OpenAI


# OmniRoute connection. Override with environment
# variables when OmniRoute runs elsewhere or exposes a
# different model identifier.
OMNIROUTE_BASE_URL = os.getenv(
    "OMNIROUTE_BASE_URL",
    "http://localhost:20128/v1",
)

OMNIROUTE_API_KEY = os.getenv(
    "OMNIROUTE_API_KEY",
    "omniroute",  # any string works
)

OMNIROUTE_MODEL = os.getenv(
    "OMNIROUTE_MODEL",
    "auto",
)

# Model for interactive features (care questions, room checks).
# Point it at a fast, non-thinking model in OmniRoute to cut
# reply time; research keeps OMNIROUTE_MODEL.
OMNIROUTE_FAST_MODEL = os.getenv(
    "OMNIROUTE_FAST_MODEL",
    OMNIROUTE_MODEL,
)


# Per-thread usage counters. A research job runs in its own
# thread, so tracking there measures that job's model cost.
_usage = threading.local()


def start_usage_tracking():
    _usage.stats = {
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }


def stop_usage_tracking():
    stats = getattr(_usage, "stats", None)
    _usage.stats = None
    return stats


def _record_usage(response):
    stats = getattr(_usage, "stats", None)

    if stats is None:
        return

    stats["llm_calls"] += 1

    usage = getattr(response, "usage", None)

    if usage is not None:
        stats["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        stats["completion_tokens"] += (
            getattr(usage, "completion_tokens", 0) or 0
        )


class LLMService:

    def __init__(self, model=None):

        self.client = OpenAI(
            base_url=OMNIROUTE_BASE_URL,
            api_key=OMNIROUTE_API_KEY,
        )

        self.model = model or OMNIROUTE_MODEL

        print("Connected to OmniRoute")

    def generate(self, prompt: str):

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content":
                        "You are a scientific assistant. "
                        "Return only the final answer."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        _record_usage(response)

        if not response.choices:
            return None

        return response.choices[0].message.content


llm = LLMService()