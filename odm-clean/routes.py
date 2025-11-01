"""
API Routes
File: src/api/routes.py
"""

from fastapi import APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import shutil
import os
import uuid as uuid_lib
import time
from src.schemas import TaskResponse, TaskStatus
from src.utils import process_task, tasks

router = APIRouter()

UPLOAD_DIR = "uploads"

@router.post("/upload", response_model=TaskResponse)
async def upload_images(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload a ZIP or RAR file containing drone images"""
    # Check if file is ZIP or RAR
    if not file.filename.lower().endswith(('.zip', '.rar')):
        raise HTTPException(status_code=400, detail="Only ZIP and RAR files are supported")
    
    task_id = str(uuid_lib.uuid4())
    
    # Save with original extension
    file_extension = file.filename.lower().split('.')[-1]
    archive_path = os.path.join(UPLOAD_DIR, f"{task_id}.{file_extension}")
    
    with open(archive_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    tasks[task_id] = {
        'task_id': task_id,
        'status': 'queued',
        'progress': 0,
        'message': 'Task queued',
        'filename': file.filename,
        'created_at': time.time()
    }
    
    background_tasks.add_task(process_task, task_id, archive_path)
    
    return TaskResponse(
        task_id=task_id,
        status='queued',
        message='Task created. Check /status/{task_id}'
    )


@router.get("/status/{task_id}", response_model=TaskStatus)
def get_task_status(task_id: str):
    """Get the status of a processing task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    download_url = f"/download/{task_id}" if task['status'] == 'completed' else None
    
    return TaskStatus(
        task_id=task_id,
        status=task['status'],
        progress=task['progress'],
        message=task['message'],
        download_url=download_url
    )


@router.get("/download/{task_id}")
def download_result(task_id: str):
    """Download the processed orthomosaic"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail=f"Status: {task['status']}")
    
    output_file = task.get('output_file')
    
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        output_file,
        media_type='application/zip',
        filename=f"orthomosaic_{task_id}.zip"
    )


@router.get("/tasks")
def list_tasks():
    """List all tasks"""
    return {
        "total": len(tasks),
        "tasks": list(tasks.values())
    }


@router.delete("/task/{task_id}")
def delete_task(task_id: str):
    """Delete a task and its files"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if 'output_file' in task and os.path.exists(task['output_file']):
        os.remove(task['output_file'])
    
    # Delete both .zip and .rar possibilities
    for ext in ['zip', 'rar']:
        upload_file = os.path.join(UPLOAD_DIR, f"{task_id}.{ext}")
        if os.path.exists(upload_file):
            os.remove(upload_file)
    
    del tasks[task_id]
    
    return {"message": "Task deleted"}