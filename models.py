from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    senha_hash = Column(String)
    perfil = Column(String) 
    is_active = Column(Boolean, default=True)

class TipoProblema(Base):
    __tablename__ = "tipos_problema"
    id = Column(Integer, primary_key=True, index=True)
    chave = Column(String, unique=True, index=True) # Ex: 'buraco'
    titulo = Column(String)                         # Ex: 'Buraco na Rua'
    categoria = Column(String)                      # Ex: 'Infraestrutura'
    icone = Column(String)                          # Ex: '🕳️'

class Problema(Base):
    __tablename__ = "problemas"
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String)
    descricao = Column(Text)
    lat = Column(Float)
    lng = Column(Float)
    status = Column(String, default="aberto")
    
    confirmacoes = Column(Integer, default=1)
    validacoes_cidadao = Column(Integer, default=0)
    nota_prefeitura = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.now)

    fotos = relationship("Foto", back_populates="problema", cascade="all, delete-orphan")

# NOVA CLASSE FOTO
class Foto(Base):
    __tablename__ = "fotos"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String) # Caminho do arquivo ou URL
    problema_id = Column(Integer, ForeignKey("problemas.id"))
    
    problema = relationship("Problema", back_populates="fotos")