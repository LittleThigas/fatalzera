from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv
import uuid
import shutil
from pathlib import Path
import aiofiles

load_dotenv()

# Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fatalzera")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# FastAPI app
app = FastAPI(title="Fatalzera API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# MongoDB client
client = AsyncIOMotorClient(MONGO_URL)
database = client[DATABASE_NAME]

# Collections
users_collection = database.users
projects_collection = database.projects
images_collection = database.images
logs_collection = database.logs

# Create uploads directory
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Pydantic models
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    role: str
    verified_email: bool
    created_at: datetime

class UserInDB(UserBase):
    id: str
    hashed_password: str
    role: str
    verified_email: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    email: Optional[str] = None

class ProjectBase(BaseModel):
    title: str
    description: str
    tags: List[str]
    cover_image: Optional[str] = None
    external_link: Optional[str] = None
    published: bool = True

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: str
    images: List[str]
    created_at: datetime
    updated_at: datetime

class ImageResponse(BaseModel):
    id: str
    filename: str
    url: str
    alt_text: Optional[str] = None
    size: int
    uploaded_at: datetime

class LogEntry(BaseModel):
    action: str
    user_id: str
    details: dict
    timestamp: datetime

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user_by_email(email: str):
    user = await users_collection.find_one({"email": email})
    if user:
        user["id"] = str(user["_id"])
        return UserInDB(**user)
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = await get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

async def get_admin_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

async def log_action(action: str, user_id: str, details: dict = {}):
    log_entry = {
        "action": action,
        "user_id": user_id,
        "details": details,
        "timestamp": datetime.utcnow()
    }
    await logs_collection.insert_one(log_entry)

# API Routes

@app.get("/")
async def root():
    return {"message": "Fatalzera API is running!"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Authentication endpoints
@app.post("/api/auth/register", response_model=UserResponse)
async def register(user: UserCreate):
    # Check if user already exists
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_password = get_password_hash(user.password)
    
    # Determine role (first user becomes admin)
    user_count = await users_collection.count_documents({})
    role = "admin" if user_count == 0 else "user"
    
    # Create user
    user_dict = {
        "email": user.email,
        "name": user.name,
        "hashed_password": hashed_password,
        "role": role,
        "verified_email": False,  # In production, implement email verification
        "created_at": datetime.utcnow()
    }
    
    result = await users_collection.insert_one(user_dict)
    user_dict["id"] = str(result.inserted_id)
    
    await log_action("user_registered", user_dict["id"], {"email": user.email, "role": role})
    
    return UserResponse(**user_dict)

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_email(form_data.username)  # username is email
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    await log_action("user_login", user.id)
    
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        verified_email=user.verified_email,
        created_at=user.created_at
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        verified_email=current_user.verified_email,
        created_at=current_user.created_at
    )

# Public project endpoints
@app.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects(published_only: bool = True):
    query = {"published": True} if published_only else {}
    cursor = projects_collection.find(query).sort("created_at", -1)
    projects = []
    
    async for project in cursor:
        project["id"] = str(project["_id"])
        projects.append(ProjectResponse(**project))
    
    return projects

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    project = await projects_collection.find_one({"_id": project_id, "published": True})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project["id"] = str(project["_id"])
    return ProjectResponse(**project)

# Admin project endpoints
@app.post("/api/admin/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    current_user: UserInDB = Depends(get_admin_user)
):
    project_dict = project.dict()
    project_dict["images"] = []
    project_dict["created_at"] = datetime.utcnow()
    project_dict["updated_at"] = datetime.utcnow()
    
    result = await projects_collection.insert_one(project_dict)
    project_dict["id"] = str(result.inserted_id)
    
    await log_action("project_created", current_user.id, {"project_id": project_dict["id"], "title": project.title})
    
    return ProjectResponse(**project_dict)

@app.put("/api/admin/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project: ProjectUpdate,
    current_user: UserInDB = Depends(get_admin_user)
):
    project_dict = project.dict()
    project_dict["updated_at"] = datetime.utcnow()
    
    result = await projects_collection.update_one(
        {"_id": project_id},
        {"$set": project_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    
    updated_project = await projects_collection.find_one({"_id": project_id})
    updated_project["id"] = str(updated_project["_id"])
    
    await log_action("project_updated", current_user.id, {"project_id": project_id, "title": project.title})
    
    return ProjectResponse(**updated_project)

@app.delete("/api/admin/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: UserInDB = Depends(get_admin_user)
):
    result = await projects_collection.delete_one({"_id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await log_action("project_deleted", current_user.id, {"project_id": project_id})
    
    return {"message": "Project deleted successfully"}

# Image upload endpoints
@app.post("/api/admin/upload-image", response_model=ImageResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_admin_user)
):
    # Generate unique filename
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = uploads_dir / unique_filename
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Get file size
    file_size = len(content)
    
    # Create image record
    image_dict = {
        "filename": unique_filename,
        "original_filename": file.filename,
        "url": f"/uploads/{unique_filename}",
        "alt_text": "",
        "size": file_size,
        "uploaded_at": datetime.utcnow(),
        "owner_id": current_user.id
    }
    
    result = await images_collection.insert_one(image_dict)
    image_dict["id"] = str(result.inserted_id)
    
    await log_action("image_uploaded", current_user.id, {"filename": unique_filename, "size": file_size})
    
    return ImageResponse(**image_dict)

@app.get("/api/admin/images", response_model=List[ImageResponse])
async def get_images(current_user: UserInDB = Depends(get_admin_user)):
    cursor = images_collection.find({}).sort("uploaded_at", -1)
    images = []
    
    async for image in cursor:
        image["id"] = str(image["_id"])
        images.append(ImageResponse(**image))
    
    return images

# Logs endpoint
@app.get("/api/admin/logs")
async def get_logs(
    limit: int = 50,
    current_user: UserInDB = Depends(get_admin_user)
):
    cursor = logs_collection.find({}).sort("timestamp", -1).limit(limit)
    logs = []
    
    async for log in cursor:
        log["_id"] = str(log["_id"])
        logs.append(log)
    
    return logs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)