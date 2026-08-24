import os
from groq import AsyncGroq

async def stream_groq_response(history: list[dict], search_context: str = ""):
    """
    Streams a response from Groq given a conversation history.
    """
    # Reads GROQ_API_KEY from the environment automatically.
    client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Convert simple dictionaries to the format expected by the SDK
    formatted_contents = []
    for msg in history:
        # Groq expects roles to be 'user' or 'assistant'
        role = "assistant" if msg["role"] == "assistant" else "user"
        formatted_contents.append(
            {"role": role, "content": msg["content"]}
        )

    if search_context:
        system_prompt = (
            "Answer the user's question using the provided sources.\n"
            "Do not invent facts.\n"
            "Prefer information supported by multiple sources.\n"
            "If the sources don't contain enough information, say so.\n"
            "Use the latest information available in the retrieved sources.\n"
            "Do not claim that you personally browsed the internet.\n"
            "Keep the answer clear and concise.\n\n"
            "FORMATTING INSTRUCTIONS:\n"
            "- Use Markdown headings when appropriate.\n"
            "- Use Markdown tables when comparing multiple items or presenting categorized information.\n"
            "- Use bullet points for short lists.\n"
            "- Do not output HTML such as <br>.\n"
            "- Do not manually escape Markdown.\n"
            "- Do not put unnecessary ** around table cell contents.\n"
            "- Keep tables readable and concise.\n\n"
            "WEB SOURCES:\n" + search_context
        )
        formatted_contents.insert(0, {"role": "system", "content": system_prompt})

    try:
        # ---------------------------------------------------------
        # STREAMING LOGIC - STATUS SIGNAL
        # ---------------------------------------------------------
        yield {"type": "status", "value": "thinking"}

        # Use the async client to get an async generator stream
        response_stream = await client.chat.completions.create(
            model='groq/compound-mini',
            messages=formatted_contents,
            stream=True
        )

        # ---------------------------------------------------------
        # STREAMING LOGIC - TEXT CHUNKS
        # ---------------------------------------------------------
        async for chunk in response_stream:
            if chunk.choices[0].delta.content is not None:
                yield {"type": "token", "value": chunk.choices[0].delta.content}

    except Exception as e:
        # Basic error handling: if the API call fails, send an error event
        # instead of crashing the server.
        yield {"type": "error", "value": f"LLM Error: {str(e)}"}