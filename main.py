from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
import requests
import models
from database import engine, get_db

# --- CONFIGURAÇÕES ---
SECRET_KEY = "segredo-super-secreto"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 dia

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Zeladoria Urbana")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- SCHEMAS ---
class LoginData(BaseModel):
    email: str; senha: str

class FacebookLoginData(BaseModel):
    accessToken: str; userID: str

class UsuarioCreate(BaseModel):
    email: str; senha: str; perfil: str

class Token(BaseModel):
    access_token: str; token_type: str; perfil: str; user_id: int

class TipoProblemaCreate(BaseModel):
    chave: str; titulo: str; categoria: str; icone: str

class TipoProblemaResponse(TipoProblemaCreate):
    id: int
    class Config: from_attributes = True

class ProblemaCreate(BaseModel):
    tipo: str; descricao: str; lat: float; lng: float

class ProblemaResponse(ProblemaCreate):
    id: int; status: str; confirmacoes: int; validacoes_cidadao: int; nota_prefeitura: Optional[str] = None; data_criacao: datetime
    class Config: from_attributes = True

# --- SEGURANÇA ---
def verificar_senha(p, h): return pwd_context.verify(p, h)
def criar_hash(p): return pwd_context.hash(p)
def criar_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- ROTAS PRINCIPAIS ---

@app.get("/")
def home(): return FileResponse("app_cidade.html")

# --- ROTAS DE TIPOS (MENU DINÂMICO & ADMIN) ---

@app.get("/tipos", response_model=List[TipoProblemaResponse])
def listar_tipos(db: Session = Depends(get_db)):
    return db.query(models.TipoProblema).all()

@app.post("/admin/tipos", response_model=TipoProblemaResponse)
def criar_tipo_problema(tipo: TipoProblemaCreate, db: Session = Depends(get_db)):
    if db.query(models.TipoProblema).filter(models.TipoProblema.chave == tipo.chave).first():
        raise HTTPException(status_code=400, detail="Chave duplicada")
    novo = models.TipoProblema(**tipo.dict())
    db.add(novo); db.commit(); db.refresh(novo)
    return novo

@app.delete("/admin/tipos/{id}")
def deletar_tipo_problema(id: int, db: Session = Depends(get_db)):
    t = db.query(models.TipoProblema).filter(models.TipoProblema.id == id).first()
    if t: db.delete(t); db.commit()
    return {"msg": "Deletado"}

# --- ROTAS DE AUTENTICAÇÃO ---

@app.post("/auth/facebook", response_model=Token)
def facebook_login(dados: FacebookLoginData, db: Session = Depends(get_db)):
    # Validação REAL no Facebook
    url = f"https://graph.facebook.com/me?access_token={dados.accessToken}&fields=id,name,email"
    req = requests.get(url)
    if req.status_code != 200: raise HTTPException(400, "Token FB inválido")
    fb = req.json()
    email = fb.get("email") or f"{fb['id']}@facebook.com"
    
    user = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if not user:
        user = models.Usuario(email=email, senha_hash=criar_hash("fb"), perfil="cidadao", is_active=True)
        db.add(user); db.commit(); db.refresh(user)
    
    return {"access_token": criar_token({"sub": user.email, "role": user.perfil, "id": user.id}), "token_type": "bearer", "perfil": user.perfil, "user_id": user.id}

@app.post("/auth/cadastro")
def cadastro(user: UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(models.Usuario).filter(models.Usuario.email == user.email).first(): raise HTTPException(400, "Email já existe")
    ativo = True if user.perfil == 'cidadao' else False
    novo = models.Usuario(email=user.email, senha_hash=criar_hash(user.senha), perfil=user.perfil, is_active=ativo)
    db.add(novo); db.commit(); db.refresh(novo)
    if user.perfil == 'prefeitura': print(f"\nLINK ATIVACAO: http://127.0.0.1:8000/auth/verificar/{novo.id}\n")
    return {"msg": "Criado! Verifique terminal se for prefeitura."}

@app.get("/auth/verificar/{uid}")
def verificar(uid: int, db: Session = Depends(get_db)):
    u = db.query(models.Usuario).filter(models.Usuario.id == uid).first()
    if u: u.is_active = True; db.commit(); return {"msg": "Conta Ativada!"}
    return {"msg": "Erro"}

@app.post("/auth/login", response_model=Token)
def login(form: LoginData, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.email == form.email).first()
    if not user or not verificar_senha(form.senha, user.senha_hash): raise HTTPException(401, "Login falhou")
    if not user.is_active: raise HTTPException(403, "Conta inativa")
    return {"access_token": criar_token({"sub": user.email, "role": user.perfil, "id": user.id}), "token_type": "bearer", "perfil": user.perfil, "user_id": user.id}

# --- ROTAS DE OCORRÊNCIAS ---

@app.get("/problemas", response_model=List[ProblemaResponse])
def listar_probs(db: Session = Depends(get_db)): return db.query(models.Problema).all()

@app.post("/problemas", response_model=ProblemaResponse)
def criar_prob(p: ProblemaCreate, db: Session = Depends(get_db)):
    novo = models.Problema(**p.dict())
    db.add(novo); db.commit(); db.refresh(novo); return novo

@app.post("/problemas/{id}/votar")
def votar(id: int, db: Session = Depends(get_db)):
    p = db.query(models.Problema).filter(models.Problema.id==id).first()
    if p: p.confirmacoes += 1; db.commit()
    return {"ok": True}

@app.post("/problemas/{id}/validar")
def validar(id: int, db: Session = Depends(get_db)):
    p = db.query(models.Problema).filter(models.Problema.id==id).first()
    if p:
        p.validacoes_cidadao += 1
        if p.validacoes_cidadao >= 3: p.status = 'arquivado'
        db.commit()
    return {"ok": True}

@app.patch("/problemas/{id}/status")
def status_prob(id: int, status: str, nota: Optional[str]=None, db: Session = Depends(get_db)):
    p = db.query(models.Problema).filter(models.Problema.id==id).first()
    if p: p.status = status; 
    if nota: p.nota_prefeitura = nota; 
    db.commit()
    return {"ok": True}

@app.delete("/problemas/{id}")
def deletar(id: int, db: Session = Depends(get_db)):
    db.query(models.Problema).filter(models.Problema.id==id).delete(); db.commit()
    return {"ok": True}

# --- INICIALIZAÇÃO (CRIA ADMIN E TIPOS) ---
@app.on_event("startup")
def startup_db():
    db = next(get_db())
    
    # 1. Cria Admin se não existir
    if not db.query(models.Usuario).filter(models.Usuario.email=="admin@city.com").first():
        print("--- CRIANDO ADMIN PADRÃO ---")
        db.add(models.Usuario(email="admin@city.com", senha_hash=criar_hash("admin"), perfil="admin", is_active=True))
        db.commit()
    
    # 2. Popula Tipos Padrão se estiver vazio
    if not db.query(models.TipoProblema).first():
        print("--- POPULANDO TIPOS DE OCORRÊNCIA ---")
        padrao = [
            {"k": "buraco", "t": "Buraco na Rua", "c": "Infraestrutura", "i": "🕳️"},
            {"k": "luz_queimada", "t": "Lâmpada Queimada", "c": "Iluminação", "i": "🌑"},
            {"k": "lixo_coleta", "t": "Lixo não Coletado", "c": "Limpeza", "i": "🚛"},
            {"k": "dengue", "t": "Foco de Dengue", "c": "Saúde", "i": "🦟"},
            {"k": "inseguranca", "t": "Local Inseguro", "c": "Segurança", "i": "⚠️"},
            {"k": "arvore", "t": "Árvore Caída", "c": "Natureza", "i": "🪵"}
        ]
        for item in padrao:
            db.add(models.TipoProblema(chave=item["k"], titulo=item["t"], categoria=item["c"], icone=item["i"]))
        db.commit()