import fastapi
from main import app

a = app

b = fastapi.app()


for i in range(5):
    print(i)
