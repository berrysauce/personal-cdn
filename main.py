import uvicorn
import secrets
from fastapi import Depends, FastAPI, HTTPException, status, Request, File, UploadFile
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sys
import os
from pydantic import BaseModel
from typing import Optional
import base64
import random
import json
from PIL import Image
from datetime import date
from mimetypes import guess_extension
import requests
from dotenv import load_dotenv
from deta import Deta



'''
        brry CDN
-----------------------------
Self-hosted, easy to use CDN
made in Python 3.9.
License: General Copyright
Author: berrysauce
'''

load_dotenv()
DETA_TOKEN = os.getenv("DETA_TOKEN")

app = FastAPI()
security = HTTPBasic()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

deta = Deta(DETA_TOKEN)
images = deta.Drive("cdn-images")
meta = deta.Base("cdn-meta")
    

def generate_html_response():
    with open("assets/index.html", "r") as html:
        html_content = html.read()
    return HTMLResponse(content=html_content, status_code=200)


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    data = json.dumps({
        "userid": credentials.username,
        "token": credentials.password
    })
    r = requests.post("https://auth.brry.cc/check", data=data)
    rdata = json.loads(r.text)
    if r.status_code == 200 and rdata["valid"] is True:
           return credentials.username
    else:
        print(r.status_code, rdata)
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"},
        )
    
    
@app.get("/")
@limiter.limit("1000/minute")
async def root(request: Request):
    return generate_html_response()


@app.get("/upload", response_class=HTMLResponse)
def form():
    return """
    <h1>Upload an image<h1>
    <p>You need a brry Auth account to do this.<p>
    <form action="/upload" enctype="multipart/form-data" method="post">
        <input name="username" type="text">
        <input name="password" type="password">
        <input name="file" type="file">
        <input type="submit">
    </form>
    """
    
@app.post("/upload")
def upload_form(file: UploadFile = File(...), username: str = Depends(get_current_username)):
    name = file.filename
    f = file.file
    res = images.put(name, f)
    return {"img_name": res,
            "uploaded_by": username
    }

@app.get("/image/{name}")
def download_img(name: str):
    res = images.get(name)
    return StreamingResponse(res.iter_chunks(1024), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=80)