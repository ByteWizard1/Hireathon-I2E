from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from retriever import NASAHandbookChat

# Initialize chatbot once
chat = NASAHandbookChat()

app = FastAPI(
    title="NASA Systems Engineering Handbook API",
    description="Ask questions about the NASA Systems Engineering Handbook",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production, but fine for hackathon dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the local images directory to be served as static files on /images route
app.mount("/images", StaticFiles(directory="images"), name="images")

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    citations: list


@app.get("/")
def root():
    return {"message": "NASA Handbook Chat API is running"}


@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    result = chat.ask(request.question)

    return {
        "answer": result["answer"],
        "citations": result["citations"]
    }