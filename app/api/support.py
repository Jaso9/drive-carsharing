from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import admin_user, current_user, throttle
from app.models import AuditEvent, Rental, SupportTicket, User, utcnow

router = APIRouter(prefix="/api", tags=["Поддержка"])


class TicketInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=4000)
    rental_id: int | None = Field(default=None, gt=0)


class TicketOut(TicketInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    reply: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def utc(self, value):
        return value.isoformat() + "Z"


class TicketReply(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reply: str = Field(min_length=3, max_length=4000)
    status: Literal["answered", "closed"] = "answered"


@router.post("/support", response_model=TicketOut, status_code=201)
def create_ticket(
    data: TicketInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    throttle(db, f"support:{user.id}", limit=20)
    if data.rental_id is not None:
        rental = db.get(Rental, data.rental_id)
        if not rental or rental.user_id != user.id:
            raise HTTPException(404, "Поездка не найдена")
    ticket = SupportTicket(user_id=user.id, **data.model_dump())
    db.add(ticket)
    db.commit()
    return ticket


@router.get("/support", response_model=list[TicketOut])
def tickets(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return db.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/admin/support", response_model=list[TicketOut])
def inbox(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
    status: Literal["open", "answered", "closed"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(SupportTicket)
    if status:
        query = query.where(SupportTicket.status == status)
    return db.scalars(query.order_by(SupportTicket.id.desc()).offset(offset).limit(limit)).all()


@router.patch("/admin/support/{ticket_id}", response_model=TicketOut)
def reply(
    ticket_id: int,
    data: TicketReply,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Обращение не найдено")
    ticket.reply = data.reply
    ticket.status = data.status
    ticket.updated_at = utcnow()
    db.add(
        AuditEvent(actor_id=user.id, action="support." + data.status, target=f"ticket:{ticket_id}")
    )
    db.commit()
    return ticket
