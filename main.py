import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status, Request, File, UploadFile, Form
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from typing import Optional
from pydantic import BaseModel
import json
from datetime import timezone
import datetime
import requests
from dotenv import load_dotenv
from deta import Deta
import uuid
from air_telemetry import Endpoint
import base64


"""
--------------------------------------------------------------------------
SETUP
--------------------------------------------------------------------------
"""

load_dotenv()
DETA_TOKEN = os.getenv("DETA_TOKEN")
TELEMETRY_TOKEN = os.getenv("TELEMETRY_TOKEN")

app = FastAPI(title="berrysauce CDN", redoc_url=None)
security = HTTPBasic()
logger = Endpoint("https://telemetry.brry.cc", "brry-cdn", TELEMETRY_TOKEN)

deta = Deta(DETA_TOKEN)
drive = deta.Drive("cdn-files")
meta = deta.Base("cdn-meta")

app.mount("/assets", StaticFiles(directory="assets"), name="assets")

class Item(BaseModel):
    file: bytes

"""
--------------------------------------------------------------------------
FUNCTIONS
--------------------------------------------------------------------------
"""

def authenticate_post(credentials: HTTPBasicCredentials = Depends(security)):
    data = json.dumps({
        "userid": credentials.username,
        "token": credentials.password,
        "app_identifier": "cdn"
    })
    r = requests.post("https://auth.brry.cc/check", data=data)
    rdata = json.loads(r.text)
    if r.status_code == 200 and rdata["valid"] is True:
        logger.info(f"Authorized user: {credentials.username}")
        return credentials.username
    else:
        logger.warning(f"Failed to authorize user: {credentials.username}")
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized - wrong username or password",
                headers={"WWW-Authenticate": "Basic"},
        )
        
def authenticate_form(username, password):
    data = json.dumps({
        "userid": username,
        "token": password,
        "app_identifier": "cdn"
    })
    r = requests.post("https://auth.brry.cc/check", data=data)
    rdata = json.loads(r.text)
    if r.status_code == 200 and rdata["valid"] is True:
        logger.info(f"Authorized user: {username}")
        return True
    else:
        logger.warning(f"Failed to authorize user: {username}")
        return False
    
def uploader(file, username):
    id = str(uuid.uuid4())
    f = file.file
    res = drive.put(id, f)
    
    dt = datetime.datetime.now(timezone.utc)
    utc_time = dt.replace(tzinfo=timezone.utc)
    
    meta.insert({
        "file": res,
        "uploaded_by": username,
        "uploaded_on": str(utc_time.now())
    })
    logger.info(f"Uploaded files successfully by {username}")
    return res


"""
--------------------------------------------------------------------------
API ROUTES
--------------------------------------------------------------------------
"""
    
@app.get("/")
async def root():
    with open("assets/index.html", "r") as f:
        html = f.read()
    return HTMLResponse(html)

@app.get("/form", response_class=HTMLResponse)
def form():
    with open("assets/form.html", "r") as f:
        html = f.read()
    return HTMLResponse(html)

@app.post("/form/upload")
def upload_form(file: UploadFile = File(...), username: str = Form(...), password: str = Form(...)):
    if authenticate_form(username, password) is False:
        raise HTTPException(status_code=401, detail="Unauthorized - wrong username or password")
    id = str(uuid.uuid4())
    f = file.file
    res = drive.put(id, f)
    
    dt = datetime.datetime.now(timezone.utc)
    utc_time = dt.replace(tzinfo=timezone.utc)
    
    meta.insert({
        "file": res,
        "uploaded_by": username,
        "uploaded_on": str(utc_time.now())
    })
    logger.info(f"Uploaded files successfully by {username}")
    return RedirectResponse(f"/file/{res}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/upload")
def upload(item: Item, username: str = Depends(authenticate_post)):
    id = str(uuid.uuid4())
    res = drive.put(id, base64.b64decode(item.file))
    
    dt = datetime.datetime.now(timezone.utc)
    utc_time = dt.replace(tzinfo=timezone.utc)
    
    meta.insert({
        "file": res,
        "uploaded_by": username,
        "uploaded_on": str(utc_time.now())
    })
    logger.info(f"Uploaded files successfully by {username}")
    return {
        "detail": "File uploaded successfully!",
        "file": res,
        "uploaded_by": username
    }

@app.get("/file/{id}")
def get_file(id: str, show_meta: Optional[bool] = False):
    if show_meta:
        return meta.fetch({"file": id}).items[0]
    res = drive.get(id)
    # empty media type doesn't work on deta micro
    return StreamingResponse(res.iter_chunks(1024), media_type="image/png")

@app.get("/favicon.ico")
def redirect_favicon():
    return RedirectResponse(f"/assets/favicon.ico", status_code=status.HTTP_303_SEE_OTHER)


"""
--------------------------------------------------------------------------
UVICORN RUNNER
--------------------------------------------------------------------------
"""

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=80)