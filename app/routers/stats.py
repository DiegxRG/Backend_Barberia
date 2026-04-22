from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from typing import Dict, Any

from app.dependencies import require_role

router = APIRouter()

@router.get("/dashboard", summary="Obtener estadísticas del dashboard")
def get_dashboard_stats(current_user: dict = Depends(require_role("admin"))):
    # Mock data para que el frontend funcione correctamente hasta que se implemente
    # la lógica real de base de datos en fase 3.3.
    today = datetime.now()
    
    weekly_bookings = []
    for i in range(7):
        day = today - timedelta(days=6-i)
        weekly_bookings.append({
            "day": day.strftime("%Y-%m-%d"),
            "count": i * 2 + 1 
        })
        
    return {
        "todayBookings": 5,
        "todayIncome": 1500,
        "pendingBookings": 3,
        "noShowCount": 1,
        "weeklyBookings": weekly_bookings,
        "recentBookings": []
    }

@router.get("/upcoming", summary="Obtener citas próximas")
def get_upcoming_stats(current_user: dict = Depends(require_role("admin"))):
    return []
