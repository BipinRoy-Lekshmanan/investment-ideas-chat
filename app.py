import os

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

from context import DOCUMENT_TITLE, SYSTEM_PROMPT

load_dotenv(override=True)

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.4-mini")

openai = OpenAI()

system = [{"role": "system", "content": SYSTEM_PROMPT}]


def chat(message, history):
    messages = system + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(model=MODEL_NAME, messages=messages)
    return response.choices[0].message.content


if __name__ == "__main__":
    gr.ChatInterface(
        chat,
        title=f"Chat with {DOCUMENT_TITLE}",
        description=(
            f"Ask questions about {DOCUMENT_TITLE}. Answers are based only on this "
            "document and are not financial advice."
        ),
        chatbot=gr.Chatbot(show_label=False),
    ).launch()
