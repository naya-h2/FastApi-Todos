from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Union
import json
import os
import datetime
import time
from enum import Enum
from prometheus_fastapi_instrumentator import Instrumentator
#influxdb
# from influxdb_client import InfluxDBClient, Point
# from influxdb_client.client.write_api import SYNCHRONOUS
import logging
import time
from multiprocessing import Queue
from os import getenv
from fastapi import Request
from logging_loki import LokiQueueHandler

app = FastAPI()

# Prometheus 메트릭스 엔드포인트 (/metrics)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
loki_logs_handler = LokiQueueHandler(
    Queue(-1),
    url=getenv("LOKI_ENDPOINT"),
    tags={"application": "fastapi"},
    version="1",
)

# Custom access logger (ignore Uvicorn's default logging)
custom_logger = logging.getLogger("custom.access")
custom_logger.setLevel(logging.INFO)

# Add Loki handler (assuming `loki_logs_handler` is correctly configured)
custom_logger.addHandler(loki_logs_handler)

async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time  # Compute response time

    log_message = (
        f'{request.client.host} - "{request.method} {request.url.path} HTTP/1.1" {response.status_code} {duration:.3f}s'
    )

    # **Only log if duration exists**
    if duration:
        custom_logger.info(log_message)

    return response

app.middleware("http")(log_requests)

# To-Do 항목 모델
class TodoItem(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
    section: str
    deadline: Union[str, None] = None

# JSON 파일 경로
TODO_FILE = "todo.json"

# JSON 파일에서 To-Do 항목 로드
def load_todos():
    if os.path.exists(TODO_FILE):
        with open(TODO_FILE, "r") as file:
            return json.load(file)
    return []

def load_trashs():
    if os.path.exists("trash.json"):
        with open("trash.json", "r") as file:
            return json.load(file)
    return []

# JSON 파일에 To-Do 항목 저장
def save_todos(todos):
    with open(TODO_FILE, "w") as file:
        json.dump(todos, file, indent=4)

def save_del_todos(todos):
    with open("trash.json", "w") as file:
        json.dump(todos, file, indent=4)

class SortingType(str, Enum):
    fast = "fast"
    slow = "slow"

class DeadlineType(str, Enum):
    today = "today"
    tomorrow = "tomorrow"
    week = "week"

# To-Do 목록 조회
@app.get("/todos", response_model=list[TodoItem])
def get_todos(section: Union[str, None] = None, sort:Union[SortingType, None] = SortingType.fast, isCompleted: bool = False):
    items = load_todos()

    # isCompleted
    items = [item for item in items if item["completed"] == isCompleted]
    
    if section:
        items = [item for item in items if item["section"] == section]

    if(sort == SortingType.fast):
        sorted_tasks = sorted(
        items, 
        key=lambda x: x['deadline'] if x['deadline'] is not None else '9999-12-31'
        )
        items = sorted_tasks
    
    if(sort == SortingType.slow):
        sorted_tasks = sorted(
        items, 
        key=lambda x: x['deadline'] if x['deadline'] is not None else '9999-12-31',
        reverse=True
        )
        items = sorted_tasks

    return items



@app.get("/deadline", response_model=list[TodoItem], description="데드라인별 todo 조회")
def get_deadline_todos(type:DeadlineType = DeadlineType.today):
    items = load_todos()
    today = datetime.datetime.now().date()
    if type == DeadlineType.today:
        current_item = []
        for item in items:
            if item["deadline"] is None or not item["deadline"]: continue

            deadline_date = datetime.datetime.strptime(item["deadline"], "%Y-%m-%d")
        
            # year와 month에 해당하는지 확인
            if deadline_date.year == int(today.year) and deadline_date.month == int(today.month) and deadline_date.day == int(today.day):
                current_item.append(item)

    if type == DeadlineType.tomorrow:
        current_item = []
        for item in items:
            if item["deadline"] is None or not item["deadline"]: continue

            deadline_date = datetime.datetime.strptime(item["deadline"], "%Y-%m-%d")
        
            # year와 month에 해당하는지 확인
            if deadline_date.year == int(today.year) and deadline_date.month == int(today.month) and deadline_date.day == int(today.day) + 1:
                current_item.append(item)
    
    if type == DeadlineType.week:
        start_of_week = today - datetime.timedelta(days=today.weekday())  # 이번 주 월요일
        end_of_week = start_of_week + datetime.timedelta(days=6)          # 이번 주 일요일
        current_item = []
        for item in items:
            if item["deadline"] is None or not item["deadline"]: continue

            deadline_date = datetime.datetime.strptime(item["deadline"], "%Y-%m-%d").date()
        
            if start_of_week <= deadline_date <= end_of_week:
                current_item.append(item)
    items = current_item
    #날짜순으로 정렬
    sorted_tasks = sorted(
        items, 
        key=lambda x: x['deadline'] if x['deadline'] is not None else '9999-12-31'
    )
        
    return sorted_tasks


@app.get("/month", response_model=list[TodoItem], description="월별 todo 조회")
def get_month_todos(year:Union[str, None] = None, month:Union[str, None] = None):
    items = load_todos()
    if year or month:
        today = datetime.datetime.now().date()
        
        if(not year): year = today.year
        if(not month): month = today.month

        current_month_item = []
        for item in items:
            if item["deadline"] is None: continue

            deadline_date = datetime.datetime.strptime(item["deadline"], "%Y-%m-%d")
        
            # year와 month에 해당하는지 확인
            if deadline_date.year == int(year) and deadline_date.month == int(month):
                current_month_item.append(item)
        items = current_month_item
    return items

# 신규 To-Do 항목 추가
@app.post("/todos", response_model=TodoItem)
def create_todo(todo: TodoItem):
    todos = load_todos()
    todos.append(todo.dict())
    save_todos(todos)
    return todo


@app.get("/todos/{todo_id}", response_model=TodoItem)
def get_todo(todo_id: int):
    todos = load_todos()
    for todo in todos:
        if todo["id"] != todo_id:
            continue
        return todo


# To-Do 항목 수정
@app.put("/todos/{todo_id}", response_model=TodoItem)
def update_todo(todo_id: int, updated_todo: TodoItem):
    todos = load_todos()
    for todo in todos:
        if todo["id"] == todo_id:
            todo.update(updated_todo.dict())
            save_todos(todos)
            return updated_todo
    raise HTTPException(status_code=404, detail="To-Do item not found")

# To-Do 항목 삭제
@app.delete("/todos/{todo_id}", response_model=dict)
def delete_todo(todo_id: int):
    todos = load_todos()
    trashs = load_trashs()
    new_todos = []
    for todo in todos:
        if todo["id"] != todo_id:
            new_todos.append(todo)
        else: trashs.append(todo)
            
    save_todos(new_todos)
    save_del_todos(trashs)
    return {"message": "To-Do item deleted"}

@app.get("/trashs", response_model=list[TodoItem])
def get_trashs():
    items = load_trashs()
    return items

@app.delete("/trashs", response_model=dict)
def delete_trash(todo_id: int):
    trashs = load_trashs()
    todos = load_todos()
    new_trashs = []
    for trash in trashs:
        if todo_id == trash["id"]:
            todos.append(trash)
        else: new_trashs.append(trash)
    print(new_trashs)
    print(todos)

    save_del_todos(new_trashs)
    save_todos(todos)

    return {"message": "To-Do item deleted"}

@app.get("/sections", response_model=list[str])
def get_sections ():
    items = load_todos()
    sections = [item["section"] for item in items]
    unique_sections = list(set(sections))
    return unique_sections

@app.get("/search", response_model=list[TodoItem])
def search_todos(keword=str):
    # search_keword = keword.replace(" ", "")
    search_keword = keword
    results = []
    all_items = load_todos()
    for item in all_items:
        search_content = item["title"].replace(" ", "") + item["description"].replace(" ", "")
        if search_keword in search_content:
            results.append(item)
    
    return results
        

##########################

# HTML 파일 서빙
@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("templates/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/section", response_class=HTMLResponse)
def read_section_page():
    with open("templates/section/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/edit", response_class=HTMLResponse)
def read_section_page():
    with open("templates/edit/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/post", response_class=HTMLResponse)
def read_section_page():
    with open("templates/post/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/tasks/completed", response_class=HTMLResponse)
def read_section_page():
    with open("templates/tasks/completed/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/tasks/day", response_class=HTMLResponse)
def read_section_page():
    with open("templates/tasks/day/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/tasks/trash", response_class=HTMLResponse)
def read_section_page():
    with open("templates/tasks/trash/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)

@app.get("/search-front", response_class=HTMLResponse)
def read_section_page():
    with open("templates/search-front/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)