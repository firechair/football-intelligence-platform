from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.models.user import UserCreate, UserOut
from app.db import session as db_session, models
from app.services import auth
from app.services import user_service
from typing import List, Optional
from app.models.token import Token

router = APIRouter(prefix="/users", tags=["users"])

def get_db():
    db = db_session.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=UserOut)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter((models.User.username == user.username) | (models.User.email == user.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = auth.create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/profile", response_model=UserOut)
def get_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.patch("/profile", response_model=UserOut)
def update_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
    full_name: Optional[str] = Body(None),
    preferences: Optional[dict] = Body(None),
):
    return user_service.update_user_profile(
        db=db, user=current_user, full_name=full_name, preferences=preferences
    ) 