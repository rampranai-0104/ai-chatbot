import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from llm import stream_groq_response
from memory import get_history, append_message

# Load environment variables from .env
load_dotenv()

app = FastAPI()

# Enable CORS for the Vite frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "https://ai-chatbot-ivory-beta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    web_search: bool = False

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    # Append the incoming user message to memory
    append_message(request.session_id, "user", request.message)
    
    # Retrieve the full conversation history for this session
    history = get_history(request.session_id)

    # ---------------------------------------------------------
    # STREAMING LOGIC - SSE GENERATOR
    # ---------------------------------------------------------
    # This async generator consumes the stream from llm.py, formats
    # each yielded dictionary into a Server-Sent Event (SSE) string,
    # and keeps track of the full text to save into memory at the end.
    async def event_generator():
        search_context = ""
        sources = []
        
        if request.web_search:
            from web_search import search_web
            from scraper import scrape_page
            
            yield f"data: {json.dumps({'type': 'status', 'value': 'Searching the web...'})}\n\n"
            search_results = await search_web(request.message)
            
            if search_results:
                yield f"data: {json.dumps({'type': 'status', 'value': 'Reading sources...'})}\n\n"
                
                context_parts = []
                for res in search_results:
                    scrape_res = await scrape_page(res["url"])
                    if scrape_res["success"] and scrape_res["content"]:
                        context_parts.append(f"SOURCE\nTitle: {res['title']}\nURL: {res['url']}\nContent:\n{scrape_res['content']}\n")
                        sources.append({"title": res["title"], "url": res["url"]})
                
                if sources:
                    search_context = "\n".join(context_parts)
                    yield f"data: {json.dumps({'type': 'sources', 'value': sources})}\n\n"
                    yield f"data: {json.dumps({'type': 'status', 'value': 'Generating answer...'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'status', 'value': 'No sources could be read. Generating normal answer...'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'value': 'Search returned no results. Generating normal answer...'})}\n\n"

        full_assistant_text = ""
        
        async for event in stream_groq_response(history, search_context):
            if event["type"] == "token":
                full_assistant_text += event["value"]
            
            # SSE format requires "data: " followed by the payload and two newlines.
            yield f"data: {json.dumps(event)}\n\n"
            
            if event["type"] == "error":
                # Stop processing if an error occurred during stream
                return
                
        # Send a final 'done' event to tell the frontend to stop the stream indicator
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        # Save the full assistant message so it remembers context for the next turn
        if full_assistant_text:
            append_message(request.session_id, "assistant", full_assistant_text)

    # Return as a streaming response with the correct SSE media type
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/scrape")
async def scrape_endpoint(url: str):
    from scraper import scrape_page
    result = await scrape_page(url)
    return {
        "url": url,
        **result
    }
