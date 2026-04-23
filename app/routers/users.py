from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.dependencies import require_role, invalidate_user_profile_cache
from app.models.user import UserListItemResponse, UserRoleUpdateRequest
from app.database.queries import profiles as profile_queries
from app.database.queries import barbers as barber_queries
from app.utils.errors import NotFoundError, ValidationError


router = APIRouter()


@router.get("", response_model=List[UserListItemResponse], summary="Listar usuarios (admin)")
def list_users(
    role: Optional[str] = Query(default=None, description="Filtrar por rol: admin|barbero|cliente"),
    only_active: bool = Query(default=True, description="Retornar solo usuarios activos"),
    page: int = Query(default=1, ge=1, description="Página actual (1-indexada)"),
    page_size: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Elementos por página"),
    available_for_barber: bool = Query(
        default=False,
        description="Si es true, retorna cuentas de barbero disponibles para vincular",
    ),
    _: dict = Depends(require_role("admin")),
):
    """
    Endpoint de soporte para flujos administrativos del frontend.
    """
    offset = (page - 1) * page_size
    effective_role = "barbero" if available_for_barber and role is None else role
    users = profile_queries.list_profiles(
        role=effective_role,
        active=only_active,
        offset=offset,
        limit=page_size,
    )
    barbers = barber_queries.list_barbers(include_inactive=True)

    linked_by_user_id = {
        str(item["user_id"]): str(item["id"])
        for item in barbers
        if item.get("user_id")
    }

    response = []
    for user in users:
        linked_barber_id = linked_by_user_id.get(str(user["id"]))
        if available_for_barber and linked_barber_id:
            continue

        response.append(
            {
                **user,
                "linked_barber_id": linked_barber_id,
            }
        )

    return response


@router.patch("/{user_id}/role", response_model=UserListItemResponse, summary="Actualizar rol de usuario (admin)")
def update_user_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
    _: dict = Depends(require_role("admin")),
):
    linked_barber = barber_queries.get_barber_by_user_id(user_id, include_inactive=True)
    if payload.role == "cliente" and linked_barber and linked_barber.get("active", True):
        raise ValidationError("No se puede cambiar a cliente mientras tenga barbero activo vinculado")

    updated = profile_queries.update_profile_role(user_id, payload.role)
    if not updated:
        raise NotFoundError(detail=f"Usuario con ID {user_id} no encontrado")

    invalidate_user_profile_cache(user_id)

    return {
        **updated,
        "linked_barber_id": str(linked_barber["id"]) if linked_barber else None,
    }
