import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status, Request, File, UploadFile
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
from typing import Optional
import json
from PIL import Image
from datetime import date
import requests
from dotenv import load_dotenv
from deta import Deta
import uuid



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
    return {"msg": "Testing Deta Drive with a CDN"}


@app.get("/form", response_class=HTMLResponse)
@limiter.limit("100/minute")
def form(request: Request):
    return """
    <h1>Upload an image</h1>
    <p>You will need to authenticate yourself with a brry Auth account.</p>
    <form action="/upload" enctype="multipart/form-data" method="post">
        <input name="file" type="file">
        <input type="submit">
    </form>
    """
    
@app.post("/upload")
@limiter.limit("100/minute")
def upload_form(request: Request, file: UploadFile = File(...), username: str = Depends(get_current_username)):
    name = str(uuid.uuid4())
    f = file.file
    res = images.put(name, f)
    return RedirectResponse("https://cdn.labs.brry.cc/image/{res}")

@app.get("/image/{name}")
@limiter.limit("1000/minute")
def download_img(name: str, request: Request):
    res = images.get(name)
    return StreamingResponse(res.iter_chunks(1024), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=80)