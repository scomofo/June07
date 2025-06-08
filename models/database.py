# models/database.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Deal(Base):
    __tablename__ = "deals"
    
    id = Column(Integer, primary_key=True)
    customer_name = Column(String(255), nullable=False)
    deal_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    jd_quote_id = Column(String(100), unique=True)

class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True)
    quote_id = Column(String(100), unique=True)
    quote_data = Column(JSON)
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

# Repository pattern
class DealRepository:
    def __init__(self, session: Session):
        self.session = session
    
    async def create_deal(self, deal_data: Dict) -> Deal:
        deal = Deal(**deal_data)
        self.session.add(deal)
        await self.session.commit()
        return deal
    
    async def get_deal_by_id(self, deal_id: int) -> Optional[Deal]:
        return await self.session.get(Deal, deal_id)