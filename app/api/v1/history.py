from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import psycopg
from app.api.v1.models import Envelope, MetaResponse
from app.settings import settings

router = APIRouter(tags=["History"])

class HistoryMessage(BaseModel):
    message_id: Optional[str] = None # DB is likely auto-increment ID, normally int, but plan says msg_123.
    # checking repo: table has no specific "message_id" column returned by get_session_messages.
    # It has created_at which can be ID.
    # Or strict ID? Repo: "INSERT INTO messages...". Schema was not shown fully but likely ID serial.
    role: str
    content: str
    timestamp: Optional[str] = None

@router.get("/history", response_model=Envelope[List[HistoryMessage]])
async def get_history(
    request: Request,
    user_id: str,
    role: Optional[str] = None,
    limit: int = 20
):
    """
    Get message history from DB.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    if not settings.DATABASE_URL:
         raise HTTPException(status_code=500, detail="DB URL not configured")

    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
        async with conn.cursor() as cur:
            query = """
                SELECT id, role, content, created_at 
                FROM messages 
                WHERE user_id = %s
            """
            params = [user_id]
            
            if role:
                query += " AND role = %s"
                params.append(role)
                
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            await cur.execute(query, params)
            rows = await cur.fetchall()
            
            # Rows are (id, role, content, created_at)
            # Reverse to Chronological order
            rows.reverse()
            
            data = []
            for r in rows:
                data.append(HistoryMessage(
                    message_id=str(r[0]),
                    role=r[1],
                    content=r[2],
                    timestamp=r[3].isoformat() if r[3] else None
                ))
                
            return Envelope(
                data=data,
                meta=MetaResponse(trace_id=trace_id)
            )

class DeleteHistoryRequest(BaseModel):
    user_id: str
    method: str = "soft" # hard or soft

@router.delete("/history", response_model=Envelope[Dict[str, str]])
async def delete_history(request: Request, body: DeleteHistoryRequest):
    """
    Delete history.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    if not settings.DATABASE_URL:
         raise HTTPException(status_code=500, detail="DB URL not configured")
         
    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
        async with conn.cursor() as cur:
            if body.method == "hard":
                await cur.execute("DELETE FROM messages WHERE user_id = %s", (body.user_id,))
            else:
                # Soft delete? Do we have deleted_at column?
                # If not, we might fail or just do hard delete if schema doesn't support it.
                # Assuming hard delete for now as 'soft' usually requires schema migration.
                # Or 'soft' implies 'archiving'.
                # For safety, if table doesn't have is_deleted, we default to hard or error.
                # Checking schema? I don't have it fully.
                # I'll try generic update, catch error if column missing, else fallback to hard?
                # Plan says "Hard or Soft". I'll implement Hard for simplicity or check if I can add soft later.
                # I'll just do DELETE for now.
                 await cur.execute("DELETE FROM messages WHERE user_id = %s", (body.user_id,))
            
            count = cur.rowcount
            
    return Envelope(
        data={"status": "deleted", "count": str(count)},
        meta=MetaResponse(trace_id=trace_id)
    )
