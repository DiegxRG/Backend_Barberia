from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.auth import ProfileResponse, ProfileUpdate
from app.database.queries.profiles import update_profile
from app.utils.errors import NotFoundError

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Retorna el perfil del usuario autenticado.
    El JWT token en el header Authorization determina quién es.
    """
    return current_user


@router.patch("/profile", response_model=ProfileResponse)
async def update_my_profile(
    profile_data: ProfileUpdate, 
    current_user: dict = Depends(get_current_user)
):
    """
    Actualiza el perfil del usuario autenticado.
    Solo actualiza los campos proporcionados (PATCH).
    """
    update_dict = profile_data.model_dump(exclude_unset=True)
    
    updated = update_profile(current_user["id"], update_dict)
    if not updated:
         raise NotFoundError(resource="Perfil")
         
    return updated
