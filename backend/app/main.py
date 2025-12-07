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



@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/health/websocket")
async def websocket_health():
    connection_count = sum(len(connections) for connections in manager.active_connections.values())
    return {
        "status": "ok",
        "active_connections": connection_count,
        "total_users": len(manager.active_connections)
    }

@app.get("/health/api")
async def api_health():
    return {"status": "ok", "service": "api", "timestamp": datetime.now().isoformat()}

@app.get("/health/db")
async def db_health(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        from urllib.parse import urlparse
        
        db.execute(text("SELECT 1"))
        db.execute(text("CREATE TEMP TABLE health_test (id INTEGER)"))
        db.execute(text("INSERT INTO health_test (id) VALUES (1)"))
        db.execute(text("SELECT id FROM health_test WHERE id = 1"))
        db.execute(text("DROP TABLE health_test"))
        db.commit()
        
        database_url = os.getenv("DATABASE_URL", "")
        parsed = urlparse(database_url)
        
        return {
            "connected": True,
            "driver": "postgres",
            "host": parsed.hostname or "unknown",
            "db": parsed.path.lstrip('/') or "unknown",
            "status": "ok",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        db.rollback()
        return {
            "connected": False,
            "driver": "postgres",
            "host": "unknown",
            "db": "unknown", 
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/health/ws")
async def ws_health():
    connection_count = sum(len(connections) for connections in manager.active_connections.values())
    return {
        "status": "ok",
        "websocket": "active",
        "active_connections": connection_count,
        "total_users": len(manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/health/database")
async def database_health(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "error": str(e)}

@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if request.password == ADMIN_PASSWORD:
        token = jwt.encode(
            {"exp": datetime.utcnow().timestamp() + (JWT_EXPIRATION_HOURS * 3600)},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM
        )
        return LoginResponse(token=token)
    raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/api/logout")
async def logout():
    return {"message": "Logged out successfully"}

@app.post("/api/change-password")
async def change_password(request: PasswordChangeRequest, token: str = Depends(verify_token)):
    global ADMIN_PASSWORD
    ADMIN_PASSWORD = request.new_password
    return {"message": "Password changed successfully"}

@app.get("/api/backup")
async def backup_data(db: Session = Depends(get_db), token: str = Depends(verify_token)):
    db_clients = db.query(ClientDB).filter(ClientDB.is_deleted == False).all()
    db_cases = db.query(CaseDB).filter(CaseDB.is_deleted == False).all()
    db_letters = db.query(CompensationLetterDB).filter(CompensationLetterDB.is_deleted == False).all()
    db_executions = db.query(ExecutionDB).filter(ExecutionDB.is_deleted == False).all()
    
    backup_data = {
        "clients": {client.id: {
            **db_to_pydantic_client(client).dict(),
            "created_at": client.created_at.isoformat(),
            "updated_at": client.updated_at.isoformat()
        } for client in db_clients},
        "cases": {case.id: {
            **db_to_pydantic_case(case).dict(),
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "start_date": case.start_date.isoformat(),
            "next_hearing_date": case.next_hearing_date.isoformat() if case.next_hearing_date else None,
            "reminder_date": case.reminder_date.isoformat() if case.reminder_date else None
        } for case in db_cases},
        "compensation_letters": {letter.id: {
            **db_to_pydantic_compensation_letter(letter).dict(),
            "created_at": letter.created_at.isoformat(),
            "updated_at": letter.updated_at.isoformat()
        } for letter in db_letters},
        "executions": {execution.id: {
            **db_to_pydantic_execution(execution).dict(),
            "created_at": execution.created_at.isoformat(),
            "updated_at": execution.updated_at.isoformat(),
            "start_date": execution.start_date.isoformat(),
            "reminder_date": execution.reminder_date.isoformat() if execution.reminder_date else None
        } for execution in db_executions}
    }
    return backup_data

@app.post("/api/restore")
async def restore_data(backup: dict, db: Session = Depends(get_db), token: str = Depends(verify_token)):
    try:
        if not backup or not isinstance(backup, dict):
            raise HTTPException(status_code=400, detail="Invalid backup data format")
        
        required_sections = ['clients', 'cases', 'executions', 'compensation_letters']
        has_valid_sections = any(section in backup for section in required_sections)
        if not has_valid_sections:
            raise HTTPException(status_code=400, detail="Backup file does not contain valid data sections")
        
        db.query(ClientDB).filter(ClientDB.is_deleted == False).update({"is_deleted": True})
        db.query(CaseDB).filter(CaseDB.is_deleted == False).update({"is_deleted": True})
        db.query(CompensationLetterDB).filter(CompensationLetterDB.is_deleted == False).update({"is_deleted": True})
        db.query(ExecutionDB).filter(ExecutionDB.is_deleted == False).update({"is_deleted": True})
        
        if "clients" in backup:
            for client_id, client_data in backup["clients"].items():
                try:
                    client_data["created_at"] = datetime.fromisoformat(client_data["created_at"])
                    if "updated_at" in client_data:
                        client_data["updated_at"] = datetime.fromisoformat(client_data["updated_at"])
                    else:
                        client_data["updated_at"] = client_data["created_at"]
                    
                    db_client = ClientDB(**client_data)
                    db.add(db_client)
                except Exception as e:
                    print(f"Error processing client {client_id}: {e}")
                    continue
        
        if "cases" in backup:
            for case_id, case_data in backup["cases"].items():
                try:
                    case_data["created_at"] = datetime.fromisoformat(case_data["created_at"])
                    case_data["updated_at"] = datetime.fromisoformat(case_data["updated_at"])
                    case_data["start_date"] = date.fromisoformat(case_data["start_date"])
                    if case_data.get("next_hearing_date"):
                        case_data["next_hearing_date"] = date.fromisoformat(case_data["next_hearing_date"])
                    if case_data.get("reminder_date"):
                        case_data["reminder_date"] = date.fromisoformat(case_data["reminder_date"])
                    
                    db_case = CaseDB(**case_data)
                    db.add(db_case)
                except Exception as e:
                    print(f"Error processing case {case_id}: {e}")
                    continue
        
        if "compensation_letters" in backup:
            for letter_id, letter_data in backup["compensation_letters"].items():
                try:
                    letter_data["created_at"] = datetime.fromisoformat(letter_data["created_at"])
                    letter_data["updated_at"] = datetime.fromisoformat(letter_data["updated_at"])
                    if letter_data.get("reminder_date"):
                        letter_data["reminder_date"] = date.fromisoformat(letter_data["reminder_date"])
                    
                    db_letter = CompensationLetterDB(**letter_data)
                    db.add(db_letter)
                except Exception as e:
                    print(f"Error processing compensation letter {letter_id}: {e}")
                    continue
        
        if "executions" in backup:
            for execution_id, execution_data in backup["executions"].items():
                try:
                    execution_data["created_at"] = datetime.fromisoformat(execution_data["created_at"])
                    execution_data["updated_at"] = datetime.fromisoformat(execution_data["updated_at"])
                    execution_data["start_date"] = date.fromisoformat(execution_data["start_date"])
                    if execution_data.get("reminder_date"):
                        execution_data["reminder_date"] = date.fromisoformat(execution_data["reminder_date"])
                    
                    db_execution = ExecutionDB(**execution_data)
                    db.add(db_execution)
                except Exception as e:
                    print(f"Error processing execution {execution_id}: {e}")
                    continue
        
        db.commit()
        
        await manager.broadcast_data_change("restore", "all", "system", {"message": "Data restored successfully"})
        
        return {"message": "Data restored successfully"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error restoring data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore data: {str(e)}")

@app.get("/health/backup")
async def backup_health(db: Session = Depends(get_db)):
    import os
    import subprocess
    from datetime import datetime, timedelta
    
    try:
        backup_dir = "/app/backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        today = datetime.now().strftime("%Y%m%d")
        backup_file = f"{backup_dir}/lexcloud_backup_{today}.sql"
        
        last_backup_time = None
        backup_size = 0
        
        if os.path.exists(backup_file):
            stat = os.stat(backup_file)
            last_backup_time = datetime.fromtimestamp(stat.st_mtime)
            backup_size = stat.st_size
        
        restore_test_result = "PASS"
        try:
            test_query = db.execute(text("SELECT COUNT(*) FROM clients WHERE is_deleted = false")).scalar()
            if test_query is None:
                restore_test_result = "FAIL - Database connection issue"
        except Exception as e:
            restore_test_result = f"FAIL - {str(e)}"
        
        return {
            "status": "healthy" if last_backup_time and (datetime.now() - last_backup_time).days < 2 else "warning",
            "last_backup": last_backup_time.isoformat() if last_backup_time else None,
            "backup_size_bytes": backup_size,
            "last_restore_test": restore_test_result,
            "backup_retention_days": 7
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "last_backup": None,
            "backup_size_bytes": 0,
            "last_restore_test": "FAIL",
            "backup_retention_days": 7
        }
