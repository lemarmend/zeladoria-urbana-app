from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import models
from database import engine, get_db
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime  # <--- Certifique-se que essa linha existe

# Cria as tabelas no banco se não existirem
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Zeladoria Urbana API")

# Isso permite acessar o arquivo direto na raiz "/"
@app.get("/")
def read_root():
    return FileResponse('app_cidade.html')

# Configurar CORS (Para o HTML conseguir conversar com o Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite que seu arquivo HTML local acesse a API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCHEMAS (Modelos de Entrada/Saída de Dados) ---
class ProblemaCreate(BaseModel):
    tipo: str
    descricao: str
    lat: float
    lng: float

# --- MUDANÇA AQUI NO MAIN.PY ---

class ProblemaResponse(ProblemaCreate):
    id: int
    status: str
    confirmacoes: int
    validacoes_cidadao: int
    nota_prefeitura: Optional[str] = None    
    # MUDAMOS DE 'str' PARA 'datetime'
    data_criacao: datetime 

    class Config:
        from_attributes = True # Se sua versão do Pydantic for nova, use from_attributes. Se der erro, volte para orm_mode = True

# --- ROTAS (ENDPOINTS) ---

# 1. Listar todos os problemas (GET)
@app.get("/problemas", response_model=List[ProblemaResponse])
def listar_problemas(db: Session = Depends(get_db)):
    # Aqui poderíamos filtrar para não mostrar 'arquivados' se quiséssemos
    return db.query(models.Problema).all()

# 2. Criar novo problema (POST)
@app.post("/problemas", response_model=ProblemaResponse)
def criar_problema(problema: ProblemaCreate, db: Session = Depends(get_db)):
    novo_db = models.Problema(
        tipo=problema.tipo,
        descricao=problema.descricao,
        lat=problema.lat,
        lng=problema.lng
    )
    db.add(novo_db)
    db.commit()
    db.refresh(novo_db)
    return novo_db

# 3. Votar / Reforçar (POST)
@app.post("/problemas/{id}/votar")
def votar_problema(id: int, db: Session = Depends(get_db)):
    prob = db.query(models.Problema).filter(models.Problema.id == id).first()
    if not prob:
        raise HTTPException(status_code=404, detail="Problema não encontrado")
    
    prob.confirmacoes += 1
    db.commit()
    return {"msg": "Voto computado", "total": prob.confirmacoes}

# 4. Atualizar Status (Prefeitura) (PATCH)
@app.patch("/problemas/{id}/status")
def mudar_status(id: int, status: str, nota: Optional[str] = None, db: Session = Depends(get_db)):
    prob = db.query(models.Problema).filter(models.Problema.id == id).first()
    if not prob:
        raise HTTPException(status_code=404, detail="Problema não encontrado")
    
    prob.status = status
    if nota:
        prob.nota_prefeitura = nota
        
    db.commit()
    return {"msg": "Status atualizado"}

# 5. Validar Solução (Cidadão) (POST)
@app.post("/problemas/{id}/validar")
def validar_solucao(id: int, db: Session = Depends(get_db)):
    prob = db.query(models.Problema).filter(models.Problema.id == id).first()
    if not prob:
        raise HTTPException(status_code=404, detail="Erro")
    
    prob.validacoes_cidadao += 1
    
    # Regra de negócio: Se tiver 3 validações, arquiva
    if prob.validacoes_cidadao >= 3:
        prob.status = 'arquivado'
        
    db.commit()
    return {"msg": "Validado", "validacoes": prob.validacoes_cidadao, "status": prob.status}

# 6. Deletar (Admin) (DELETE)
@app.delete("/problemas/{id}")
def deletar_problema(id: int, db: Session = Depends(get_db)):
    prob = db.query(models.Problema).filter(models.Problema.id == id).first()
    if prob:
        db.delete(prob)
        db.commit()
    return {"msg": "Deletado"}