import os

from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage


def travel_explanation(origin, destination, departure, travel_time):

    load_dotenv()

    if not os.environ.get("OPENAI_API_KEY"):
        return (
            "OpenAI API key is not set. "
            "Set OPENAI_API_KEY in your environment or .env and try again."
        )

    llm = ChatOpenAI(
        temperature=0.2,
        model="gpt-4o-mini"
    )

    prompt = f"""
You are a smart transport assistant.

User journey:
Origin: {origin}
Destination: {destination}

Recommended departure: {departure}
Estimated travel time: {travel_time} minutes

Explain the travel plan clearly.
"""

    response = llm([HumanMessage(content=prompt)])

    return response.content
