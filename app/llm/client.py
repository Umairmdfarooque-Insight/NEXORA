
from openai import OpenAI

from app.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/",
)


def ask_rayfin(prompt: str) -> str:
    response = client.responses.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        instructions=(
        "You are Nexora, the AI engine behind the Rayfin user interface. "
        "You help users automate data engineering and analytics workflows "
        "for Microsoft Fabric. Be accurate, structured, and explicit "
        "about assumptions."
        ),
        input=prompt,
    )

    if not response.output_text:
        raise RuntimeError("The AI deployment returned an empty response.")

    return response.output_text
