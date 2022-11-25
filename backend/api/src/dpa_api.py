import logging

from fastapi import FastAPI
from mangum import Mangum

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/pet/{pet_id}")
def read_item(pet_id: int):
    return {"pet_id": pet_id}


handler = Mangum(app, lifespan="off")
