"""
Utility Functions
File: src/utils/__init__.py
"""

import requests
import os
import time
import shutil
import zipfile
import subprocess
import mimetypes

# Configuration
WEBODM_HOST = os.getenv("WEBODM_HOST", "https://spark1.webodm.net")
WEBODM_TOKEN = os.getenv("WEBODM_TOKEN", "")
OUTPUT_DIR = "outputs"
TEMP_DIR = "temp"

# Task storage (in production, use a database)
tasks = {}


def upload_images_to_webodm(image_folder: str, task_name: str = "API Upload"):
    """Upload images to WebODM Lightning"""
    files_list = []
    image_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')
    
    for filename in os.listdir(image_folder):
        if filename.lower().endswith(image_extensions):
            filepath = os.path.join(image_folder, filename)
            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type is None:
                if filename.lower().endswith(('.jpg', '.jpeg')):
                    mime_type = 'image/jpeg'
                elif filename.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif filename.lower().endswith(('.tif', '.tiff')):
                    mime_type = 'image/tiff'
                else:
                    mime_type = 'application/octet-stream'
            
            files_list.append(('images', (filename, open(filepath, 'rb'), mime_type)))
    
    if not files_list:
        return None, "No images found"
    
    url = f"{WEBODM_HOST}/task/new"
    data = {
        'name': task_name,
        'options': '{"orthophoto-resolution": 5, "dsm": true, "dtm": true}',
    }
    params = {'token': WEBODM_TOKEN}
    
    try:
        response = requests.post(url, files=files_list, data=data, params=params, timeout=300)
        
        for _, file_tuple in files_list:
            file_tuple[1].close()
        
        if response.status_code == 200:
            task_data = response.json()
            webodm_task_id = task_data.get('uuid')
            return webodm_task_id, None
        else:
            return None, f"Error: {response.status_code}"
            
    except Exception as e:
        return None, str(e)


def check_webodm_task_status(webodm_task_id: str):
    """Check WebODM task status"""
    url = f"{WEBODM_HOST}/task/{webodm_task_id}/info"
    params = {'token': WEBODM_TOKEN}
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return {
                'status_code': data['status']['code'],
                'progress': data.get('progress', 0)
            }
        return None
    except:
        return None


def download_from_webodm(webodm_task_id: str, output_path: str):
    """Download results from WebODM"""
    url = f"{WEBODM_HOST}/task/{webodm_task_id}/download/all.zip"
    params = {'token': WEBODM_TOKEN}
    
    try:
        response = requests.get(url, params=params, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        return False
    except:
        return False


def extract_archive(archive_path: str, extract_dir: str):
    """Extract ZIP or RAR archive"""
    file_extension = archive_path.lower().split('.')[-1]
    
    try:
        if file_extension == 'zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            return True
            
        elif file_extension == 'rar':
            # Check if unrar is available
            result = subprocess.run(['unrar', 'x', '-y', archive_path, extract_dir], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return True
            else:
                raise Exception(f"RAR extraction failed: {result.stderr}")
        else:
            raise Exception(f"Unsupported archive format: {file_extension}")
            
    except FileNotFoundError:
        raise Exception("unrar is not installed. Please install: apt-get install unrar or brew install unrar")
    except Exception as e:
        raise Exception(f"Extraction failed: {str(e)}")


def process_task(task_id: str, archive_path: str):
    """Background task processor"""
    try:
        tasks[task_id]['status'] = 'extracting'
        tasks[task_id]['message'] = 'Extracting images...'
        
        extract_dir = os.path.join(TEMP_DIR, task_id)
        os.makedirs(extract_dir, exist_ok=True)
        
        # Extract archive (ZIP or RAR)
        extract_archive(archive_path, extract_dir)
        
        # Find image folder
        image_folder = extract_dir
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
                    image_folder = root
                    break
            break
        
        image_count = len([f for f in os.listdir(image_folder) 
                          if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff'))])
        
        tasks[task_id]['status'] = 'uploading'
        tasks[task_id]['message'] = f'Uploading {image_count} images...'
        
        webodm_task_id, error = upload_images_to_webodm(image_folder, f"Task-{task_id}")
        
        if error:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['message'] = error
            return
        
        tasks[task_id]['webodm_task_id'] = webodm_task_id
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['message'] = 'Processing orthomosaic...'
        
        while True:
            status_data = check_webodm_task_status(webodm_task_id)
            
            if not status_data:
                time.sleep(10)
                continue
            
            status_code = status_data['status_code']
            progress = status_data['progress']
            
            tasks[task_id]['progress'] = progress
            
            if status_code == 40:  # COMPLETED
                tasks[task_id]['status'] = 'downloading'
                tasks[task_id]['message'] = 'Downloading results...'
                
                output_file = os.path.join(OUTPUT_DIR, f"{task_id}.zip")
                success = download_from_webodm(webodm_task_id, output_file)
                
                if success:
                    tasks[task_id]['status'] = 'completed'
                    tasks[task_id]['message'] = 'Complete!'
                    tasks[task_id]['output_file'] = output_file
                    tasks[task_id]['progress'] = 100
                else:
                    tasks[task_id]['status'] = 'failed'
                    tasks[task_id]['message'] = 'Download failed'
                break
                
            elif status_code == 30:  # FAILED
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['message'] = 'Processing failed'
                break
                
            elif status_code == 50:  # CANCELED
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['message'] = 'Task canceled'
                break
            
            time.sleep(10)
        
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.remove(archive_path)
        
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['message'] = str(e)