from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.config import settings
from app.core.logging_config import get_logger
from app.schemas.auth import TokenClaims, TokenResponse

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
logger = get_logger(__name__)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hashed version.
    Returns True if the password is correct, False otherwise."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(token_claims: TokenClaims) -> TokenResponse:
    """
    Create a JWT access token with the given claims and expiration time.
    - **token_claims**: The claims to include in the token, such as user ID and tenant ID.
    Returns a TokenResponse containing the access token and its type.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = token_claims.model_dump(mode="json")
    payload.update({
        "exp": expire,
        "iat": now,
    })
    logger.debug("Creating access token tenant_id=%s user_id=%s", token_claims.tenant_id, token_claims.user_id)

    access_token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    return TokenResponse(access_token=access_token, token_type="bearer")


def decode_access_token(token: str) -> TokenClaims:
    """
    Decode a JWT access token and return its claims.
    - **token**: The JWT access token to decode.
    Returns the claims contained in the token if it is valid, or raises an error if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        claims = TokenClaims.model_validate(payload)
        logger.debug("Decoded access token tenant_id=%s user_id=%s", claims.tenant_id, claims.user_id)
        return claims

    except ExpiredSignatureError:
        logger.warning("Rejected expired access token")
        raise ValueError("Token expired")

    except JWTError:
        logger.warning("Rejected invalid access token")
        raise ValueError("Invalid token")
    

    
