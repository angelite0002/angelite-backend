from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run

from pymongo.mongo_client import MongoClient
from pymongo.collection import Collection
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

from pydantic import BaseModel
from pydantic.fields import Field

from typing import Union
from hashlib import sha512
from functools import lru_cache
from dotenv import load_dotenv
from random import randint
from os import environ

load_dotenv()

app = FastAPI()

db_pass = environ.get("DB_PASS")
frontend = environ.get("FRONTEND")

if frontend != None:
    CORSMiddleware(app=app, allow_origins=frontend)

uri = (
    "mongodb+srv://jaipalbhanwariya6:"
        + db_pass +
        "@cluster0.psnm55e.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

client: MongoClient = MongoClient(uri, server_api=ServerApi("1"))
angeliteDB = client["angelite"]


class userT(BaseModel):
    _id: ObjectId
    name: str
    email: str
    phone: str
    countryCode: int
    address: str
    date_of_birth: str = Field(alias="date-of-birth")


# Admin session web token generator by password
def gen_token(password: str) -> str:
    strlen = 128
    jwtUnhashed = ""
    num_range = range(0x30, 0x3A)
    upper_range = range(0x41, 0x5A)
    lower_range = range(0x61, 0x7A)
    jwtUnhashed = str(strlen)
    for i in range(128):
        char = password[i]
        if ord(char) in num_range:
            jwtUnhashed += chr(randint(0x61, 0x7A))
        elif ord(char) in upper_range:
            jwtUnhashed += chr(randint(0x31, 0x3A))
        elif ord(char) in lower_range:
            jwtUnhashed += chr(randint(0x21, 0x2F))
        else:
            jwtUnhashed += chr(randint(0x41, 0x5A))
    return sha512(jwtUnhashed.encode()).hexdigest()


class UserInSession:
    name: str
    token: str

    def __init__(self, name: str, password: str):
        self.name = name
        self.token = gen_token(password)


usersInSession: dict[str, UserInSession] = {}


@lru_cache(maxsize=None)
def getUsersCollection() -> Collection:
    return angeliteDB["users"]


@lru_cache(maxsize=None)
def getBlogCollection() -> Collection:
    return angeliteDB["blogs"]


@app.post("/sign-in")
def add_user(name: str, email, countryCode, phone, address, DoB):
    getUsersCollection().insert_one(
        {
            "name": name,
            "email": email,
            "phone": phone,
            "countryCode": countryCode,
            "address": address,
            "date-of-birth": DoB,
        }
    )


@app.post("/")
async def users(name: str, token: str):
    if name not in usersInSession.keys():
        return []
    elif usersInSession[name].token != token:
        return []
    out = getUsersCollection().find()
    return {"users": [userT(**user).model_dump() for user in out.to_list()]}


async def getAllBlog():
    blogs = getBlogCollection().find().to_list()
    blogs.reverse()
    return blogs


@app.get("/blogs")
async def returnBlogs(blogFrag: int):
    allBlogs = await getAllBlog()
    out = []
    if blogFrag * 5 > len(allBlogs):
        return []
    for i in range(blogFrag * 5, len(allBlogs)):
        blog = {
            "title": allBlogs[i]["title"],
            "id": str(allBlogs[i]["_id"]),
            "month": allBlogs[i]["month"],
            "year": allBlogs[i]["year"],
        }
        out.append(blog)
    return out


@app.post("/get-blog")
async def findBlog(id: str):
    blog: dict[str, Union[str, int]] | None = getBlogCollection().find_one(
        {"_id": ObjectId(id)}
    )
    if blog is None:
        return {"error": "Blog not found"}
    return {
        "title": blog["title"],
        "content": blog["content"],
        "month": blog["month"],
        "year": blog["year"],
    }


@app.post("/add-blog")
async def addBlog(data: dict[str, str], name: str, token: str):
    if name not in usersInSession.keys():
        return []
    elif usersInSession[name].token != token:
        return []
    parsedData = {
        "title": data["title"],
        "content": data["content"],
        "month": data["month"],
        "year": data["year"],
    }
    try:
        getBlogCollection().insert_one(parsedData)
        return {"status": 200, "error": ""}
    except Exception as e:
        print(e)
        return {"status": 500, "error": e.args[0]}


@app.post("/add-user")
async def addUsers(data: dict[str, str]):
    parsedData = {
        "name": data["name"],
        "email": data["email"],
        "phone": data["phone"],
        "countryCode": data["countryCode"],
        "address": data["address"],
        "date-of-birth": data["date-of-birth"],
    }
    try:
        getUsersCollection().insert_one(parsedData)
        return {"status": 200, "error": ""}
    except Exception as e:
        print(e)
        return {"status": 500, "error": "Internal server error"}


@app.post("/admins")
async def admins(adminHash: str):
    out = angeliteDB["admins"].find()
    admins = [
        {
            "name": str(admin["name"]).lower(),
            "pass": admin["pass"],
            "email": str(admin["email"]).lower(),
        }
        for admin in out.to_list()
    ]
    for admin in admins:
        adminStr = "{name: " + admin["name"]
        adminStr += f", email: {admin['email']}, pass: "
        adminStr += admin["pass"] + "}"
        hashed = sha512(adminStr.encode())
        hashHexDigest = hashed.hexdigest()
        if hashHexDigest == adminHash:
            if admin["name"] in usersInSession.keys():
                return {"token": usersInSession[admin["name"]].token}
            token = UserInSession(admin["name"], admin["pass"])
            usersInSession[admin["name"]] = token
            return {"token": token.token}
    return {"token": "failed"}


@app.post("/events")
async def events(name: str, token: str):
    if name not in usersInSession.keys():
        return []
    elif usersInSession[name].token != token:
        return []
    out = angeliteDB["events"].find()
    return [
        {
            "id": str(event["_id"]),
            "name": event["name"],
            "email": event["email"],
            "phone": event["phone"],
            "countryCode": event["countryCode"],
            "address": event["address"],
            "date-of-birth": event["date-of-birth"],
            "event-date": event["event-date"],
            "event-type": event["event-type"],
            "sub-event-type": event["sub-event-type"],
        }
        for event in out.to_list()
    ]


@app.post("/add-event")
async def addEvent(eventData: dict[str, str]):
    eventCollection = angeliteDB["events"]
    parsedData = {
        "name": eventData["name"],
        "email": eventData["email"],
        "phone": eventData["phone"],
        "countryCode": eventData["countryCode"],
        "address": eventData["address"],
        "date-of-birth": eventData["date-of-birth"],
        "event-date": eventData["event-date"],
        "event-type": eventData["event-type"],
        "sub-event-type": eventData["sub-event-type"],
    }
    try:
        eventCollection.insert_one(parsedData)
        return {"status": 200, "error": ""}
    except Exception:
        return {"status": 500, "error": "Internal server error"}

if __name__ == "__main__":
    run("app:app", host="127.0.0.1", port=8000, reload=True)
