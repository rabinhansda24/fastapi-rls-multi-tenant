import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant

def slugyfy(value: str) -> str:
    """
    Convert a string to a slug format. This is used to create URL-friendly identifiers for tenants.
    The function will convert the string to lowercase, replace spaces with hyphens, and remove any non-alphanumeric characters except for hyphens.
    """
    value = value.lower()
    value = re.sub(r'\s+', '-', value)
    value = re.sub(r'[^a-z0-9\-]', '', value)
    return value

def is_slug_unique(db: Session, slug: str) -> bool:
    """
    Check if a slug is unique across all tenants. This is important to prevent conflicts when creating new tenants.
    The function will query the database to see if any tenant already has the given slug.
    """
    stmt = select(Tenant).where(Tenant.slug == slug)
    result = db.execute(stmt).scalar_one_or_none()
    return result is None

def generate_unique_slug(db: Session, name: str) -> str:
    """
    Generate a unique slug for a tenant based on its name. The function will first create a slug from the name and then check if it is unique. If it is not unique, it will append a number to the slug until it finds a unique one.
    This ensures that even if multiple tenants have the same name, they will still have unique slugs.
    """
    base_slug = slugyfy(name)
    slug = base_slug
    counter = 1
    while not is_slug_unique(db, slug):
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

