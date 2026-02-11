from fastapi import FastAPI
from . import intelligence

app = FastAPI()
app.include_router(intelligence.router)
