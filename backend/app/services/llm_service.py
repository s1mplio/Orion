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





import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


class LLMService:

    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        if api_key is None:
            raise ValueError("GEMINI_API_KEY not found in .env")

        self.client = genai.Client(api_key=api_key)

        self.model = "gemini-3-flash-preview"

        print("\n===================================")
        print("Gemini Loaded Successfully")
        print(f"Model : {self.model}")
        print("===================================\n")

    def generate(self, prompt: str) -> str:

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        return response.text.strip()



llm = LLMService()