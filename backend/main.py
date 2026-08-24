import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from llm import stream_groq_response
from memory import get_history, append_message


# Load environment variables
load_dotenv()

app = FastAPI()


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ai-chatbot-ivory-beta.vercel.app",
         "https://ai-chatbot-git-main-ram-s-projects-8e6c9989.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODEL
# =========================================================

class ChatRequest(BaseModel):
    session_id: str
    message: str
    web_search: bool = False


# =========================================================
# CHAT ENDPOINT
# =========================================================

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):

    # Save user message
    append_message(
        request.session_id,
        "user",
        request.message
    )

    # Get conversation history
    history = get_history(request.session_id)

    # =====================================================
    # SSE EVENT GENERATOR
    # =====================================================

    async def event_generator():

        search_context = ""
        sources = []

        # =================================================
        # WEB SEARCH
        # =================================================

        if request.web_search:

            from web_search import search_web
            from scraper import scrape_page

            # Tell frontend that web search started
            yield (
                f"data: {json.dumps({
                    'type': 'status',
                    'value': 'Searching the web...'
                })}\n\n"
            )

            # Perform web search
            search_results = await search_web(request.message)

            # =================================================
            # SEARCH RESULTS FOUND
            # =================================================

            if search_results:

                yield (
                    f"data: {json.dumps({
                        'type': 'status',
                        'value': 'Reading sources...'
                    })}\n\n"
                )

                # ---------------------------------------------
                # SCRAPE SOURCES IN PARALLEL
                # ---------------------------------------------

                async def scrape_result(res):

                    try:

                        scrape_res = await scrape_page(
                            res["url"]
                        )

                        if (
                            scrape_res.get("success")
                            and scrape_res.get("content")
                        ):

                            return {
                                "context": (
                                    "SOURCE\n"
                                    f"Title: {res['title']}\n"
                                    f"URL: {res['url']}\n"
                                    "Content:\n"
                                    f"{scrape_res['content']}\n"
                                ),
                                "source": {
                                    "title": res["title"],
                                    "url": res["url"]
                                }
                            }

                    except Exception:
                        # Ignore individual failed sources
                        return None

                    return None

                # Run all scraping tasks concurrently
                scraped_results = await asyncio.gather(
                    *[
                        scrape_result(res)
                        for res in search_results
                    ]
                )

                # ---------------------------------------------
                # COLLECT SUCCESSFUL RESULTS
                # ---------------------------------------------

                context_parts = []

                for result in scraped_results:

                    if result:

                        context_parts.append(
                            result["context"]
                        )

                        sources.append(
                            result["source"]
                        )

                # ---------------------------------------------
                # BUILD SEARCH CONTEXT
                # ---------------------------------------------

                if sources:

                    search_context = "\n".join(
                        context_parts
                    )

                    # Send sources to frontend
                    yield (
                        f"data: {json.dumps({
                            'type': 'sources',
                            'value': sources
                        })}\n\n"
                    )

                    # Tell frontend LLM generation started
                    yield (
                        f"data: {json.dumps({
                            'type': 'status',
                            'value': 'Generating answer...'
                        })}\n\n"
                    )

                else:

                    yield (
                        f"data: {json.dumps({
                            'type': 'status',
                            'value': (
                                'No sources could be read. '
                                'Generating normal answer...'
                            )
                        })}\n\n"
                    )


            else:

                yield (
                    f"data: {json.dumps({
                        'type': 'status',
                        'value': (
                            'Search returned no results. '
                            'Generating normal answer...'
                        )
                    })}\n\n"
                )

        full_assistant_text = ""

        try:

            async for event in stream_groq_response(
                history,
                search_context
            ):

                # Save generated tokens
                if event.get("type") == "token":

                    full_assistant_text += (
                        event.get("value", "")
                    )

                # Send event to frontend
                yield (
                    f"data: {json.dumps(event)}\n\n"
                )

                # Stop if LLM returned an error
                if event.get("type") == "error":
                    return

        except Exception as e:

            # Send error to frontend
            yield (
                f"data: {json.dumps({
                    'type': 'error',
                    'value': str(e)
                })}\n\n"
            )

            return


        yield (
            f"data: {json.dumps({
                'type': 'done'
            })}\n\n"
        )

        if full_assistant_text:

            append_message(
                request.session_id,
                "assistant",
                full_assistant_text
            )


    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



@app.get("/scrape")
async def scrape_endpoint(url: str):

    from scraper import scrape_page

    result = await scrape_page(url)

    return {
        "url": url,
        **result
    }


@app.get("/healthz")
async def health_check():

    return {
        "status": "healthy"
    }
