from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Union
import json
import os
import datetime
from enum import Enum
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

# Prometheus 메트릭스 엔드포인트 (/metrics)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


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

# JSON 파일에 To-Do 항목 저장
def save_todos(todos):
    with open(TODO_FILE, "w") as file:
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
def get_todos(section: Union[str, None] = None, sort:Union[SortingType, None] = SortingType.fast, deadline: Union[DeadlineType, None] = None, isCompleted: bool = False):
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


@app.post("/todos/deadline", response_model=list[TodoItem], description="데드라인별 todo 조회")
def get_deadline_todos(year:Union[str, None] = None, month:Union[str, None] = None):
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
    todos = [todo for todo in todos if todo["id"] != todo_id]
    save_todos(todos)
    return {"message": "To-Do item deleted"}

@app.get("/sections", response_model=list[str])
def get_sections ():
    items = load_todos()
    sections = [item["section"] for item in items]
    unique_sections = list(set(sections))
    return unique_sections


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