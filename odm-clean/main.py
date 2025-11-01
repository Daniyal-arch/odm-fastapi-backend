"""
FastAPI Backend for WebODM Lightning Orthomosaic Processing
File: src/main.py
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from routes import router

# Configuration
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
TEMP_DIR = "temp"

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Initialize FastAPI
app = FastAPI(
    title="WebODM Orthomosaic API",
    description="Upload drone images and generate orthomosaics",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)

@app.get("/")
def root():
    return {
        "name": "WebODM Orthomosaic API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)