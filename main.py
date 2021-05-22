import uvicorn
import secrets
from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, HTMLResponse
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


class Item(BaseModel):
    image: str
    file_type: str
    compress: Optional[bool] = True
    

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

@app.get("/image/{imgID}")
@limiter.limit("1000/minute")
async def get_image(imgID, request: Request, show_meta: Optional[bool] = False):
    if show_meta is True:
        try:
            return meta.get(imgID)
        except IOError:
            raise HTTPException(status_code=500, detail="There is no metadata saved with this image")
    try:
        return FileResponse(images.get(imgID))
    except IOError:
        raise HTTPException(status_code=404, detail="File not found")

@app.post("/upload")
@limiter.limit("30/minute")
async def upload(item: Item, request: Request, username: str = Depends(get_current_username)):
    try:
        #tempID = str(random.randint(1000000000,9999999999))
        
        #if item.file_type[:1] != ".":
        #    file_type = "."+item.file_type
        #else:
        #    file_type = item.file_type

        # Save Image
        #with open("/tmp/"+tempID+file_type, "wb") as img:
        #    img.write(base64.b64decode(item.image))
            
        # Compress Image
        #if item.compress is True and file_type in [".png", ".jpg", ".jpeg"]:
        #    img = Image.open("/tmp/"+tempID+file_type)
        #    img.save("/tmp/"+tempID+file_type, optimize=True,quality=80)
        #    compressed = True
        #else:
        #    compressed = False
        compressed = False
            
        # Save Image Metadata    
        metaResponse = meta.put({"compressed": compressed,
                        "uploaded_by": username,
                        "uploaded_on": str(date.today())
                        })
        imgID = str(metaResponse["key"])
        
        # Upload image and delete local copy
        images.put(imgID, data=item.image)
        #images.put(imgID+file_type, path="/tmp/"+tempID+file_type)
        #os.remove("/tmp/"+tempID+file_type)
            
        return {
            "detail": "Image uploaded",
            "img_id": imgID,
            "img_url": "cdn.lab.brry.cc"+"/image/"+imgID,
            "compressed": compressed
            }
    except Exception as exception:
        raise HTTPException(status_code=500, detail="Error - {0}".format(exception))
    
"""
@app.delete("/delete/{imgID}")
@limiter.limit("15/minute")
async def delete(imgID, request: Request, username: str = Depends(get_current_username)):
    try:
        with open(directory+"/image_data/"+imgID+".json", "r") as imgd:
            imgdata = imgd.read()
            imgdata = json.loads(imgdata)
        os.remove(directory+"/images/"+imgID+imgdata["file_type"])
        os.remove(directory+"/image_data/"+imgID+".json")
        raise HTTPException(status_code=200, detail="Image deleted successfully")
    except IOError:
        raise HTTPException(status_code=404, detail="File not found")
    
@app.get("/shields/{shield_type}")
@limiter.limit("100/minute")
def shields(shield_type: str, request: Request):
    if shield_type == "total": 
        DIR = directory+"/images"
        img_count = len([name for name in os.listdir(DIR) if os.path.isfile(os.path.join(DIR, name))])
        return {
            "schemaVersion": 1,
            "label": "total",
            "message": str(img_count) + " images",
            "color": "blue"
            }
    raise HTTPException(status_code=404, detail="Type not found")
"""


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=80)