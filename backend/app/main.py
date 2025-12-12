from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, date
import json
import uuid
import jwt
import os
import asyncio
import threading
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, Index, ForeignKey, or_
import logging
from app.database import get_db, create_tables, ClientDB, CaseDB, CompensationLetterDB, ExecutionDB
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="LexCloud API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.on_event("startup")
async def startup_event():
    print("Initializing database on startup...")
    
    database_url = os.getenv("DATABASE_URL", "NOT_SET")
    if database_url != "NOT_SET":
        try:
            from urllib.parse import urlparse
            parsed = urlparse(database_url)
            db_host = parsed.hostname
            db_name = parsed.path.lstrip('/')
            driver = "postgres"
            print(f"✅ Connected to DB: {db_host}/{db_name}")
            print(f"Database driver: {driver}")
            print(f"Database host: {db_host}")
            print(f"Database name: {db_name}")
        except Exception as e:
            print(f"⚠️ Could not parse DATABASE_URL: {e}")
    else:
        print("❌ DATABASE_URL not set!")
        raise ValueError("DATABASE_URL environment variable is required")
    
    try:
        create_tables()
        print("✅ Database tables created successfully")
    except Exception as table_error:
        print(f"⚠️ Table creation failed: {table_error}")
        print("✅ Backend starting without table creation - tables may already exist")
    
    try:
        from app.database import engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        with SessionLocal() as db:
            try:
                db.execute(text("SELECT custody_no FROM clients LIMIT 1"))
                print("✅ custody_no column already exists")
            except Exception:
                print("🔧 Adding custody_no column to clients table...")
                db.execute(text("ALTER TABLE clients ADD COLUMN custody_no VARCHAR"))
                db.commit()
                print("✅ Successfully added custody_no column")
    except Exception as migration_error:
        print(f"⚠️ Migration error: {migration_error}")
    
    print("✅ Backend startup completed - table creation and migration completed")


class Client(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    address: str
    tax_id: Optional[str] = None
    custody_no: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int

class ClientCreate(BaseModel):
    name: str
    email: str
    phone: str
    address: str
    tax_id: Optional[str] = None
    custody_no: Optional[str] = None

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    custody_no: Optional[str] = None
    version: int

class Case(BaseModel):
    id: str
    title: str
    case_name: Optional[str] = None
    description: Optional[str] = None
    client_id: str
    client_name: str
    case_type: str
    status: str
    court: str
    case_number: str
    defendant: str
    notes: Optional[str] = None
    start_date: date
    next_hearing_date: Optional[date] = None
    reminder_date: Optional[date] = None
    office_archive_no: str
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int

class CaseCreate(BaseModel):
    title: str
    case_name: Optional[str] = None
    description: Optional[str] = None
    client_id: str
    case_type: str
    status: str
    court: str
    case_number: str
    defendant: str
    notes: Optional[str] = None
    start_date: date
    next_hearing_date: Optional[date] = None
    reminder_date: Optional[date] = None
    office_archive_no: str
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    case_name: Optional[str] = None
    description: Optional[str] = None
    client_id: Optional[str] = None
    case_type: Optional[str] = None
    status: Optional[str] = None
    court: Optional[str] = None
    case_number: Optional[str] = None
    defendant: Optional[str] = None
    notes: Optional[str] = None
    start_date: Optional[date] = None
    next_hearing_date: Optional[date] = None
    reminder_date: Optional[date] = None
    office_archive_no: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None
    version: Optional[int] = None

class CompensationLetter(BaseModel):
    id: str
    title: str
    client_id: str
    client_name: str
    letter_number: str
    bank: str
    customer_number: str
    customer: str
    court: str
    case_number: str
    status: str
    description_text: Optional[str] = None
    reminder_date: Optional[date] = None
    reminder_text: Optional[str] = None
    responsible_person: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int

class CompensationLetterCreate(BaseModel):
    client_id: str
    letter_number: str
    bank: str
    customer_number: str
    customer: str
    court: str
    case_number: str
    status: str
    description_text: Optional[str] = None
    reminder_date: Optional[date] = None
    reminder_text: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None

class CompensationLetterUpdate(BaseModel):
    client_id: Optional[str] = None
    letter_number: Optional[str] = None
    bank: Optional[str] = None
    customer_number: Optional[str] = None
    customer: Optional[str] = None
    court: Optional[str] = None
    case_number: Optional[str] = None
    status: Optional[str] = None
    description_text: Optional[str] = None
    reminder_date: Optional[date] = None
    reminder_text: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None
    version: Optional[int] = None

class Execution(BaseModel):
    id: str
    client_id: str
    client_name: str
    defendant: str
    execution_office: str
    execution_number: str
    status: str
    execution_type: str
    start_date: date
    office_archive_no: str
    reminder_date: Optional[date] = None
    reminder_text: Optional[str] = None
    notes: Optional[str] = None
    haciz_durumu: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int

class ExecutionCreate(BaseModel):
    client_id: str
    defendant: str
    execution_office: str
    execution_number: str
    status: str
    execution_type: str
    start_date: date
    office_archive_no: str
    reminder_date: Optional[date] = None
    reminder_text: Optional[str] = None
    notes: Optional[str] = None
    haciz_durumu: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None

class ExecutionUpdate(BaseModel):
    client_id: Optional[str] = None
    defendant: Optional[str] = None
    execution_office: Optional[str] = None
    execution_number: Optional[str] = None
    status: Optional[str] = None
    execution_type: Optional[str] = None
    start_date: Optional[date] = None
    office_archive_no: Optional[str] = None
    reminder_date: Optional[date] = None
    reminder_text: Optional[str] = None
    notes: Optional[str] = None
    haciz_durumu: Optional[str] = None
    responsible_person: Optional[str] = None
    commisioner: Optional[str] = None
    version: Optional[int] = None

def db_to_pydantic_client(db_client: ClientDB) -> Client:
    return Client(
        id=db_client.id,
        name=db_client.name,
        email=db_client.email,
        phone=db_client.phone,
        address=db_client.address,
        tax_id=db_client.tax_id,
        custody_no=db_client.custody_no,
        created_at=db_client.created_at,
        updated_at=db_client.updated_at,
        version=db_client.version
    )

def db_to_pydantic_case(db_case: CaseDB) -> Case:
    return Case(
        id=db_case.id,
        title=db_case.title,
        case_name=db_case.case_name,
        description=db_case.description,
        client_id=db_case.client_id,
        client_name=db_case.client_name,
        case_type=db_case.case_type,
        status=db_case.status,
        court=db_case.court,
        case_number=db_case.case_number,
        defendant=db_case.defendant,
        notes=db_case.notes,
        start_date=db_case.start_date,
        next_hearing_date=db_case.next_hearing_date,
        reminder_date=db_case.reminder_date,
        office_archive_no=db_case.office_archive_no,
        responsible_person=db_case.responsible_person,
        commisioner=db_case.commisioner,
        created_at=db_case.created_at,
        updated_at=db_case.updated_at,
        version=db_case.version
    )

def db_to_pydantic_compensation_letter(db_letter: CompensationLetterDB) -> CompensationLetter:
    return CompensationLetter(
        id=db_letter.id,
        title=db_letter.title,
        client_id=db_letter.client_id,
        client_name=db_letter.client_name,
        letter_number=db_letter.letter_number,
        bank=db_letter.bank,
        customer_number=db_letter.customer_number,
        customer=db_letter.customer,
        court=db_letter.court,
        case_number=db_letter.case_number,
        status=db_letter.status,
        description_text=db_letter.description_text,
        reminder_date=db_letter.reminder_date,
        reminder_text=db_letter.reminder_text,
        responsible_person=db_letter.responsible_person,
        commisioner=db_letter.commisioner,
        created_at=db_letter.created_at,
        updated_at=db_letter.updated_at,
        version=db_letter.version
    )

def db_to_pydantic_execution(db_execution: ExecutionDB) -> Execution:
    return Execution(
        id=db_execution.id,
        client_id=db_execution.client_id,
        client_name=db_execution.client_name,
        defendant=db_execution.defendant,
        execution_office=db_execution.execution_office,
        execution_number=db_execution.execution_number,
        status=db_execution.status,
        execution_type=db_execution.execution_type,
        start_date=db_execution.start_date,
        office_archive_no=db_execution.office_archive_no,
        reminder_date=db_execution.reminder_date,
        reminder_text=db_execution.reminder_text,
        notes=db_execution.notes,
        haciz_durumu=db_execution.haciz_durumu,
        responsible_person=db_execution.responsible_person,
        commisioner=db_execution.commisioner,
        created_at=db_execution.created_at,
        updated_at=db_execution.updated_at,
        version=db_execution.version
    )
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
JWT_SECRET = os.getenv("JWT_SECRET")

if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD environment variable is required")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_lock = threading.Lock()

    def connect(self, websocket: WebSocket, user_token: str):
        with self.connection_lock:
            if user_token not in self.active_connections:
                self.active_connections[user_token] = set()
            self.active_connections[user_token].add(websocket)

    def disconnect(self, websocket: WebSocket, user_token: str):
        with self.connection_lock:
            if user_token in self.active_connections:
                self.active_connections[user_token].discard(websocket)
                if not self.active_connections[user_token]:
                    del self.active_connections[user_token]

    async def broadcast_data_change(self, change_type: str, entity_type: str, entity_id: str, data: dict):
        serializable_data = self._make_serializable(data)
        
        message = {
            "type": "data_change",
            "change_type": change_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "data": serializable_data,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected_connections = []
        with self.connection_lock:
            for user_token, connections in self.active_connections.items():
                for connection in connections.copy():
                    try:
                        await connection.send_text(json.dumps(message))
                    except Exception as e:
                        print(f"Error sending WebSocket message: {e}")
                        disconnected_connections.append((connection, user_token))
        
        for connection, user_token in disconnected_connections:
            self.disconnect(connection, user_token)
    
    def _make_serializable(self, obj):
        """Convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        else:
            return obj
manager = ConnectionManager()

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    token: str

class PasswordChangeRequest(BaseModel):
    new_password: str

def verify_token(token: str = Depends(HTTPBearer())):
    try:
        payload = jwt.decode(token.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        await websocket.accept()
        manager.connect(websocket, token)

        import asyncio
        async def ping_task():
            while True:
                try:
                    await asyncio.sleep(25)
                    if websocket.client_state == websocket.client_state.CONNECTED:
                        await websocket.ping()
                except Exception:
                    break

        ping_coroutine = asyncio.create_task(ping_task())

        try:
            while True:
                data = await websocket.receive_text()
                print(f"Received WebSocket message: {data}")
        except WebSocketDisconnect:
            ping_coroutine.cancel()
            manager.disconnect(websocket, token)
    except jwt.InvalidTokenError:
        await websocket.close(code=1008)


@app.post("/api/clients", response_model=Client)
async def create_client(client: ClientCreate, db: Session = Depends(get_db), token: str = Depends(verify_token)):
    client_id = str(uuid.uuid4())
    now = datetime.now()
    
    db_client = ClientDB(
        id=client_id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        address=client.address,
        tax_id=client.tax_id,
        vekalet_ofis_no=client.vekalet_ofis_no,
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False
    )
    
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    
    new_client = db_to_pydantic_client(db_client)
    await manager.broadcast_data_change("create", "client", client_id, new_client.dict())
    
    return new_client

@app.get("/api/clients", response_model=List[Client])
async def get_clients(
    page: int = Query(1, ge=1),
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db), 
    token: str = Depends(verify_token)
):
    offset = (page - 1) * limit
    db_clients = db.query(ClientDB).filter(ClientDB.is_deleted == False).order_by(ClientDB.updated_at.desc()).offset(offset).limit(limit).all()
    return [db_to_pydantic_client(client) for client in db_clients]

@app.get("/api/clients/{client_id}", response_model=Client)
async def get_client(client_id: str, db: Session = Depends(get_db), token: str = Depends(verify_token)):
    db_client = db.query(ClientDB).filter(ClientDB.id == client_id, ClientDB.is_deleted == False).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    return db_to_pydantic_client(db_client)

@app.put("/api/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_update: ClientUpdate, db: Session = Depends(get_db), token: str = Depends(verify_token)):
    db_client = db.query(ClientDB).filter(ClientDB.id == client_id, ClientDB.is_deleted == False).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if client_update.version is not None and db_client.version != client_update.version:
        raise HTTPException(status_code=409, detail="Version conflict. Please refresh and try again.")
    
    update_data = client_update.dict(exclude_unset=True, exclude={"version"})
    for field, value in update_data.items():
        setattr(db_client, field, value)
    
    db_client.updated_at = datetime.now()
    db_client.version += 1
    
    try:
        db.commit()
        db.refresh(db_client)
        
        client = db_to_pydantic_client(db_client)
        await manager.broadcast_data_change("update", "client", client_id, client.dict())
        
        print(f"Client updated successfully: {client_id}")
        return client
    except Exception as e:
        db.rollback()
        print(f"Error updating client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update client")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, db: Session = Depends(get_db), token: str = Depends(verify_token)):
    db_client = db.query(ClientDB).filter(ClientDB.id == client_id, ClientDB.is_deleted == False).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db_client.is_deleted = True
    db_client.updated_at = datetime.now()
    db.commit()
    
    await manager.broadcast_data_change("delete", "client", client_id, {})
    
    return {"message": "Client deleted successfully"} 


@app.get("/api/dashboard")
async def get_dashboard(db: Session = Depends(get_db), token: str = Depends(verify_token)):
    total_cases = db.query(CaseDB).filter(CaseDB.is_deleted == False).count()
    total_clients = db.query(ClientDB).filter(ClientDB.is_deleted == False).count()
    total_executions = db.query(ExecutionDB).filter(ExecutionDB.is_deleted == False).count()
    total_compensation_letters = db.query(CompensationLetterDB).filter(CompensationLetterDB.is_deleted == False).count()
    
    upcoming_reminders = []
    
    db_cases = db.query(CaseDB).filter(CaseDB.reminder_date.isnot(None), CaseDB.is_deleted == False).all()
    for case in db_cases:
        if case.reminder_date:
            reminder_date = case.reminder_date
            days_until = (reminder_date - date.today()).days
            
            if 0 <= days_until <= 7:
                upcoming_reminders.append({
                    "type": "case",
                    "case_id": case.id,
                    "case_number": case.case_number,
                    "case_name": case.case_name,
                    "court": case.court,
                    "client_name": case.client_name,
                    "defendant": case.defendant,
                    "reminder_date": reminder_date.isoformat(),
                    "description": case.description,
                    "responsible_person": case.responsible_person,
                    "görevlendiren": case.görevlendiren,
                    "days_until": days_until
                })
    
    db_executions = db.query(ExecutionDB).filter(ExecutionDB.reminder_date.isnot(None), ExecutionDB.is_deleted == False).all()
    for execution in db_executions:
        if execution.reminder_date:
            reminder_date = execution.reminder_date
            days_until = (reminder_date - date.today()).days
            
            if 0 <= days_until <= 7:
                upcoming_reminders.append({
                    "type": "execution",
                    "execution_id": execution.id,
                    "execution_number": execution.execution_number,
                    "execution_office": execution.execution_office,
                    "client_name": execution.client_name,
                    "defendant": execution.defendant,
                    "reminder_date": reminder_date.isoformat(),
                    "reminder_text": execution.reminder_text,
                    "responsible_person": execution.responsible_person,
                    "görevlendiren": execution.görevlendiren,
                    "days_until": days_until
                })
    
    db_compensation_letters = db.query(CompensationLetterDB).filter(CompensationLetterDB.reminder_date.isnot(None), CompensationLetterDB.is_deleted == False).all()
    for letter in db_compensation_letters:
        if letter.reminder_date:
            reminder_date = letter.reminder_date
            days_until = (reminder_date - date.today()).days
            
            if 0 <= days_until <= 7:
                upcoming_reminders.append({
                    "type": "compensation_letter",
                    "compensation_letter_id": letter.id,
                    "letter_number": letter.letter_number,
                    "court": letter.court,
                    "case_number": letter.case_number,
                    "customer": letter.customer,
                    "client_name": letter.client_name,
                    "reminder_date": reminder_date.isoformat(),
                    "reminder_text": letter.reminder_text,
                    "responsible_person": letter.responsible_person,
                    "görevlendiren": letter.görevlendiren,
                    "days_until": days_until
                })
    
    upcoming_reminders.sort(key=lambda x: x["days_until"])
    
    status_counts = {}
    db_cases = db.query(CaseDB).filter(CaseDB.is_deleted == False).all()
    for case in db_cases:
        status = case.status
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "total_cases": total_cases,
        "total_clients": total_clients,
        "total_executions": total_executions,
        "total_compensation_letters": total_compensation_letters,
        "status_counts": status_counts,
        "upcoming_reminders": upcoming_reminders
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Fly.io"""
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")