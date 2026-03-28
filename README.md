# Hireathon-I2E: NASA Systems Engineering Handbook Research Assistant

This project is an AI-powered research assistant designed to answer questions based on the NASA Systems Engineering Handbook. It features a Retrieval-Augmented Generation (RAG) backend utilizing FastAPI and a modern frontend interface built with React and Vite. 

## Features
- **AI-Powered Search**: Ask questions specifically about the NASA Systems Engineering Handbook.
- **Citations**: The assistant provides document chunks and images retrieved as context for its answers.
- **Dynamic Frontend**: A beautiful and highly responsive chat UI with markdown support and modal-based image viewing.
- **Fast Backend**: Leveraging FastAPI for quick inference, chunk retrieval, and static file serving.

---

## Architecture & Tech Stack Details

The system is broken into three main tasks: **Document Ingestion**, **Backend API**, and **Frontend UI**.

### 1. Document Ingestion (Offline Process)
The ingestion pipeline processes the NASA handbook to extract context, including images and tables, to populate the vector database with rich semantic chunks.
- **PDF Parse & Chunking**: `PyMuPDF (fitz)` is used for visual layout, pulling raster/vector images, extracting cropped bounding boxes around complex diagrams, and maintaining semantic document structure.
- **Vision Recognition**: `OpenAI gpt-4o` (Vision model) describes diagrams step-by-step to be embedded.
- **Vector Database**: **Pinecone** is the chosen vector database. It stores the resulting text, table, and image chunks alongside their embeddings and metadata (chapter, section ID, paths, parent topics, etc.).
- **Embedding Model**: `text-embedding-3-small` from OpenAI.

### 2. Backend API
The FastAPI backend acts as the bridge that manages incoming chat requests, performs semantic searches, cross-reference resolutions, and context assembly.
- **Web Framework**: **FastAPI** paired with **Uvicorn** for lightning-fast performance.
- **Data Validation**: **Pydantic** to enforce strictly-typed request and response structures.
- **Retrieval Engine**: Uses the **Pinecone Python SDK** to query top chunks and retrieve related cross-reference chunks as required. 
- **LLM Engine**: **OpenAI `gpt-4o`** to synthesize answers accurately while restricting it to the retrieved NASA context.

### 3. Frontend UI
The custom frontend UI creates a fluid and premium chat experience with the assistant, showing answers smoothly and providing viewable citations dynamically.
- **Framework**: **React** built and served using **Vite**.
- **Styling**: **Tailwind CSS** for rapid and fully responsive styling.
- **Animations**: **Framer Motion** for premium chat transitions, staggered list appearances, and smooth modal pops.
- **Utility Libraries**: **Axios** (API requests), **Lucide React** (iconography), **React Markdown** (rendering formatted AI answers and code correctly).

---

## Environment Setup (.env)

Before running the backend, you must configure your API keys. In the `backend/` directory, create a `.env` file referencing the following keys:

```env
# OpenAI Key used for 'text-embedding-3-small' and 'gpt-4o'
OPENAI_API_KEY="your-openai-api-key"

# Pinecone Key used to access the 'nasa-handbook' vector index
PINECONE_API_KEY="your-pinecone-api-key"
```

---

## Prerequisites
- Node.js (v18 or higher recommended)
- Python (3.9 or higher recommended)

---

## How to Run the Project

You will need two terminal windows to run both the backend and the frontend simultaneously.

### 1. Running the Backend
The backend serves the API and the static images used by the assistant.

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install the required Python dependencies:
   ```bash
   pip install -r requirement.txt
   ```
   *(Note: ensure you are using a virtual environment if you prefer)*

3. Start the FastAPI development server:
   ```bash
   uvicorn server:app --reload --port 8000
   ```
The backend API will be available at `http://localhost:8000`.

### 2. Running the Frontend
The frontend is the main user interface where you can chat with the assistant.

1. Navigate to the `web` directory:
   ```bash
   cd web
   ```
2. Install the Node.js dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```
The frontend application will be accessible at the Local URL provided in your terminal (usually `http://localhost:5173`).
