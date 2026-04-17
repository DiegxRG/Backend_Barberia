from uuid import UUID
from typing import List
from datetime import date
from app.database.queries import availability as queries
from app.models.availability import (
    AvailabilityRuleCreate, AvailabilityRuleResponse,
    BreakCreate, BreakResponse,
    DayOffCreate, DayOffResponse,
    FullAvailabilityResponse
)
from app.utils.errors import ValidationError

class AvailabilityService:
    # --- COMBINED ---
    def get_full_availability(self, barber_id: UUID) -> FullAvailabilityResponse:
        rules_data = queries.get_rules(barber_id)
        breaks_data = queries.get_breaks(barber_id)
        
        return FullAvailabilityResponse(
            barber_id=barber_id,
            rules=[AvailabilityRuleResponse(**r) for r in rules_data],
            breaks=[BreakResponse(**b) for b in breaks_data]
        )

    # --- RULES ---
    def set_availability_rules(self, barber_id: UUID, rules: List[AvailabilityRuleCreate]) -> List[AvailabilityRuleResponse]:
        # Validar rangos horarios localmente
        seen_days = set()
        for r in rules:
            if r.start_time >= r.end_time:
                raise ValidationError("start_time debe ser menor que end_time")
            if r.day_of_week in seen_days:
                raise ValidationError("No se permiten reglas duplicadas para el mismo day_of_week")
            seen_days.add(r.day_of_week)
                
        # Preparar data
        insert_data = []
        for r in rules:
            d = r.model_dump()
            d['barber_id'] = str(barber_id)
            d['start_time'] = d['start_time'].strftime("%H:%M:%S")
            d['end_time'] = d['end_time'].strftime("%H:%M:%S")
            insert_data.append(d)
            
        queries.delete_all_rules(barber_id)
        inserted = queries.bulk_insert_rules(insert_data)
        
        return [AvailabilityRuleResponse(**r) for r in inserted]

    # --- BREAKS ---
    def create_break(self, barber_id: UUID, break_data: BreakCreate) -> BreakResponse:
        if break_data.start_time >= break_data.end_time:
            raise ValidationError("start_time debe ser menor que end_time")
            
        d = break_data.model_dump()
        d['barber_id'] = str(barber_id)
        d['start_time'] = d['start_time'].strftime("%H:%M:%S")
        d['end_time'] = d['end_time'].strftime("%H:%M:%S")
        
        inserted = queries.create_break(d)
        return BreakResponse(**inserted)
        
    def delete_break(self, break_id: UUID) -> None:
        queries.delete_break(break_id)

    # --- DAYS OFF ---
    def get_days_off(self, barber_id: UUID, from_date: date = None) -> List[DayOffResponse]:
        data = queries.get_days_off(barber_id, from_date)
        return [DayOffResponse(**item) for item in data]
        
    def create_day_off(self, barber_id: UUID, data: DayOffCreate) -> DayOffResponse:
        d = data.model_dump()
        d['barber_id'] = str(barber_id)
        d['date'] = d['date'].isoformat()
        
        try:
            inserted = queries.create_day_off(d)
            return DayOffResponse(**inserted)
        except Exception:
            raise ValidationError("Puede que el día libre ya exista para esta fecha")
            
    def delete_day_off(self, barber_id: UUID, target_date: date) -> None:
        queries.delete_day_off(barber_id, target_date)

availability_service = AvailabilityService()
