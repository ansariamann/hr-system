from datetime import datetime, timedelta
import hashlib
import secrets
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ats_backend.auth.models import PasswordResetToken
from ats_backend.core.database import get_db
from ats_backend.core.error_handling import with_error_handling
from ats_backend.core.config import settings
from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.activity_log import ActivityLog
from ats_backend.email.send import save_email_as_text, send_email
from ats_backend.email.templates import (
    render_client_invite_email,
    render_client_invite_email_text,
    render_client_welcome_email_text,
)
from ats_backend.schemas.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientProvisionResponse,
    ClientInviteResponse,
)
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
        email_domain=client_in.email_domain,
        industry=client_in.industry,
        contact_name=client_in.contact_name,
        contact_email=client_in.contact_email,
        contact_phone=client_in.contact_phone,
        address=client_in.address,
        website=client_in.website,
        is_active=client_in.is_active,
    )
    db.commit()
    db.refresh(new_client)

    portal_login_url = f"{settings.frontend_client_url.rstrip('/')}/login"
    forgot_password_url = f"{settings.frontend_client_url.rstrip('/')}/forgot-password"
    credentials_emailed = False
    generated_email_path = None
    if new_client.contact_email:
        text_body = render_client_welcome_email_text(
            client_name=new_client.name,
            contact_name=new_client.contact_name or new_client.name,
            admin_email=admin_user.email,
            admin_password=admin_password,
            login_url=portal_login_url,
            forgot_password_url=forgot_password_url,
        )
        generated_email_path = save_email_as_text(
            to=new_client.contact_email,
            subject=f"Your {new_client.name} Client Portal Account",
            text_body=text_body,
        )
    
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
        industry=new_client.industry,
        contact_name=new_client.contact_name,
        contact_email=new_client.contact_email,
        contact_phone=new_client.contact_phone,
        address=new_client.address,
        website=new_client.website,
        email_domain=new_client.email_domain,
        is_active=new_client.is_active,
        created_at=new_client.created_at,
        updated_at=new_client.updated_at,
        credentials_generated=True,
        credentials_emailed=credentials_emailed,
        generated_email_path=generated_email_path,
        admin_email=admin_user.email,
        admin_password=admin_password,
        portal_login_url=portal_login_url,
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
        "industry": client.industry,
        "contact_name": client.contact_name,
        "contact_email": client.contact_email,
        "contact_phone": client.contact_phone,
        "address": client.address,
        "website": client.website,
        "email_domain": client.email_domain,
        "is_active": client.is_active,
    }

    updated_client = ClientService.update_client(
        db, 
        client_id, 
        name=client_in.name, 
        email_domain=client_in.email_domain,
        industry=client_in.industry,
        contact_name=client_in.contact_name,
        contact_email=client_in.contact_email,
        contact_phone=client_in.contact_phone,
        address=client_in.address,
        website=client_in.website,
        is_active=client_in.is_active,
    )
    updated_values = {
        "name": updated_client.name,
        "industry": updated_client.industry,
        "contact_name": updated_client.contact_name,
        "contact_email": updated_client.contact_email,
        "contact_phone": updated_client.contact_phone,
        "address": updated_client.address,
        "website": updated_client.website,
        "email_domain": updated_client.email_domain,
        "is_active": updated_client.is_active,
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


@router.post("/{client_id}/invite", response_model=ClientInviteResponse)
@with_error_handling(component="client_api")
def invite_user(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a real one-time password setup link for the client's admin user.
    """
    client = ClientService.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    current_role = (current_user.role or "").lower()
    if current_role != "hr_admin" and current_user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to invite users for this client")

    admin_user = (
        db.query(User)
        .filter(
            User.client_id == client_id,
            User.role == "client_admin",
            User.is_active == True,
        )
        .order_by(User.created_at.asc())
        .first()
    )
    if not admin_user:
        raise HTTPException(status_code=404, detail="No active client admin user found for this client")

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.password_reset_token_minutes)

    reset_entry = PasswordResetToken(
        user_id=admin_user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_entry)

    setup_link = f"{settings.frontend_client_url.rstrip('/')}/reset-password?token={token}"
    html_body = render_client_invite_email(
        user_name=admin_user.full_name or admin_user.email,
        client_name=client.name,
        setup_link=setup_link,
        expiry_minutes=settings.password_reset_token_minutes,
    )
    text_body = render_client_invite_email_text(
        user_name=admin_user.full_name or admin_user.email,
        client_name=client.name,
        setup_link=setup_link,
        expiry_minutes=settings.password_reset_token_minutes,
    )

    generated_email_path = save_email_as_text(
        to=admin_user.email,
        subject=f"Set up your {client.name} Client Portal access",
        text_body=text_body,
    )
    invite_emailed = send_email(
        to=admin_user.email,
        subject=f"Set up your {client.name} Client Portal access",
        html_body=html_body,
    )

    activity_log = ActivityLog(
        client_id=current_user.client_id,
        user_id=current_user.id,
        action_type="CLIENT_INVITE_GENERATED",
        entity_id=client_id,
        details={
            "target_client_id": str(client_id),
            "invited_user_email": admin_user.email,
            "invite_emailed": invite_emailed,
            "expires_in_minutes": settings.password_reset_token_minutes,
        },
    )
    db.add(activity_log)
    db.commit()

    response = ClientInviteResponse(
        client_id=client_id,
        invited_user_email=admin_user.email,
        invite_link=setup_link,
        expires_in=settings.password_reset_token_minutes * 60,
        invite_emailed=invite_emailed,
        generated_email_path=generated_email_path,
        token=token if settings.environment != "production" else None,
    )
    return response
