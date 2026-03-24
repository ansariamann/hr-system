from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ats_backend.core.database import get_db
from ats_backend.core.error_handling import with_error_handling
from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.activity_log import ActivityLog
from ats_backend.schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientProvisionResponse
from ats_backend.services.client_service import ClientService

router = APIRouter(
    prefix="/clients",
    tags=["clients"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[ClientResponse])
@with_error_handling(component="client_api")
def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all clients."""
    # TODO: Add specific permission check if needed (e.g. only superadmin can list all clients)
    return ClientService.list_clients(db, skip=skip, limit=limit)


@router.post("/", response_model=ClientProvisionResponse, status_code=status.HTTP_201_CREATED)
@with_error_handling(component="client_api")
def create_client(
    client_in: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new client."""
    # TODO: Add specific permission check
    
    # Check if client with same name exists
    existing_client = ClientService.get_client_by_name(db, client_in.name)
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this name already exists"
        )
        
    new_client, admin_user, admin_password = ClientService.provision_client_with_admin(
        db,
        name=client_in.name,
        email_domain=client_in.email_domain
    )
    db.commit()
    db.refresh(new_client)
    
    activity_log = ActivityLog(
        client_id=current_user.client_id,
        user_id=current_user.id,
        action_type="CLIENT_CREATED",
        entity_id=new_client.id,
        details={"name": new_client.name, "email_domain": new_client.email_domain}
    )
    db.add(activity_log)
    db.commit()
    
    return ClientProvisionResponse(
        id=new_client.id,
        name=new_client.name,
        email_domain=new_client.email_domain,
        created_at=new_client.created_at,
        updated_at=new_client.updated_at,
        credentials_generated=True,
        admin_email=admin_user.email,
        admin_password=admin_password,
        portal_login_url="http://localhost:8080/login",
    )


@router.get("/{client_id}", response_model=ClientResponse)
@with_error_handling(component="client_api")
def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get client details."""
    client = ClientService.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
@with_error_handling(component="client_api")
def update_client(
    client_id: UUID,
    client_in: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update client."""
    client = ClientService.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    previous_values = {
        "name": client.name,
        "email_domain": client.email_domain,
    }

    updated_client = ClientService.update_client(
        db, 
        client_id, 
        name=client_in.name, 
        email_domain=client_in.email_domain
    )
    updated_values = {
        "name": updated_client.name,
        "email_domain": updated_client.email_domain,
    }
    changed_fields = sorted(
        key for key, old_value in previous_values.items() if old_value != updated_values.get(key)
    )
    activity_log = ActivityLog(
        client_id=current_user.client_id,
        user_id=current_user.id,
        action_type="CLIENT_UPDATED",
        entity_id=updated_client.id,
        details={
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "updated_values": updated_values,
        }
    )
    db.add(activity_log)
    db.commit()
    db.refresh(updated_client)
    return updated_client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
@with_error_handling(component="client_api")
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete client."""
    # TODO: Add specific permission check
    success = ClientService.delete_client(db, client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    if current_user.client_id != client_id:
        activity_log = ActivityLog(
            client_id=current_user.client_id,
            user_id=current_user.id,
            action_type="CLIENT_DELETED",
            entity_id=client_id,
            details={"client_id": str(client_id)}
        )
        db.add(activity_log)
    db.commit()


@router.post("/{client_id}/invite")
@with_error_handling(component="client_api")
def invite_user(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate an invite link/token for a user to join this client.
    This is a placeholder implementation.
    """
    client = ClientService.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    # Mock response for now
    return {
        "token": "mock-invite-token",
        "link": f"http://localhost:5173/join?token=mock-invite-token&client={client_id}"
    }
