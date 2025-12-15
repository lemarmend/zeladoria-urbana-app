from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from database import Base

class Problema(Base):
    __tablename__ = "problemas"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String)            # Ex: buraco, luz_queimada
    descricao = Column(Text)
    lat = Column(Float)
    lng = Column(Float)
    
    # Status: aberto, analise, resolvido, arquivado
    status = Column(String, default="aberto")
    
    # Contadores
    confirmacoes = Column(Integer, default=1)
    validacoes_cidadao = Column(Integer, default=0)
    
    # Notas
    nota_prefeitura = Column(Text, nullable=True)
    
    data_criacao = Column(DateTime, default=datetime.now)