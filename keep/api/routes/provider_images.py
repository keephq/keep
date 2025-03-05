import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlmodel import Session, select

from keep.api.core.db import get_session
from keep.api.models.db.provider_image import ProviderImage
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_IMAGE_PATH = os.environ.get(
    "DEFAULT_IMAGE_PATH",
    os.path.join(os.path.dirname(__file__), "../../../unknown-icon.png"),
)


@router.post("/upload/{image_name}")
async def upload_provider_image(
    image_name: str,
    file: UploadFile = File(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    """Upload a provider image"""
    tenant_id = authenticated_entity.tenant_id

    full_image_name = f"{image_name}-icon.png"
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    try:
        image_data = await file.read()

        # Check if image already exists
        existing_image = session.exec(
            select(ProviderImage)
            .where(ProviderImage.tenant_id == tenant_id)
            .where(ProviderImage.image_name == full_image_name)
        ).first()

        if existing_image:
            # Update existing image
            existing_image.image_blob = image_data
            session.add(existing_image)
        else:
            # Create new image
            provider_image = ProviderImage(
                id=f"{tenant_id}_{image_name}",
                tenant_id=tenant_id,
                image_name=full_image_name,
                image_blob=image_data,
                updated_by=authenticated_entity.email,
            )
            session.add(provider_image)

        session.commit()
        return {"message": "Image uploaded successfully"}

    except Exception:
        logger.exception("Failed to upload image")
        raise HTTPException(500, "Failed to upload image")


@router.get("/{image_name}")
async def get_provider_image(
    image_name: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
):
    """Get a provider image"""
    tenant_id = authenticated_entity.tenant_id

    full_image_name = f"{image_name}-icon.png"

    # Try to get custom image from DB
    provider_image = session.exec(
        select(ProviderImage)
        .where(ProviderImage.tenant_id == tenant_id)
        .where(ProviderImage.image_name == full_image_name)
    ).first()

    if provider_image:
        return Response(content=provider_image.image_blob, media_type="image/png")

    # Return default image if no custom image found
    try:
        path = DEFAULT_IMAGE_PATH
        if not os.path.exists(path):
            fallback_path = "/unknown-icon.png"
            logger.warning(
                f"Default image not found at {DEFAULT_IMAGE_PATH}, using fallback path: {fallback_path}"
            )
            path = fallback_path
        with open(DEFAULT_IMAGE_PATH, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    except FileNotFoundError:
        raise HTTPException(404, "Default image not found")


@router.get("")
async def list_provider_images(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
):
    """List all custom provider images for the tenant"""
    tenant_id = authenticated_entity.tenant_id

    # Query all provider images for this tenant
    provider_images = session.exec(
        select(ProviderImage).where(ProviderImage.tenant_id == tenant_id)
    ).all()

    # Return list of provider names that have custom images
    return [
        {
            "provider_name": img.image_name.replace("-icon.png", ""),
            "id": img.id,
            "updated_by": img.updated_by,
            "last_updated": img.last_updated,
        }
        for img in provider_images
    ]
