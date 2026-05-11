"""
app/core/services/client_service.py
────────────────────────────────────
All database operations for client/borrower profiles.
Every write operation is fully audit-logged.

Validation enforced at service level (applies to ALL callers —
UI form, chatbot, scripts, API):
  - NIN format:     C[MF] + 8 digits + 4 alphanumeric = 14 chars
  - NIN uniqueness: no two active clients may share a NIN
  - Phone uniqueness: no two active clients may share a phone number
"""

import re
from app.database.connection import get_db
from app.core.models.client import Client
from app.core.services.audit_service import AuditService, Actions


# ── Uganda NIN pattern ─────────────────────────────────────────────────────────
# Format: C[MF] + 8 digits + 4 alphanumeric = 14 characters total
# CM = male citizen, CF = female citizen
# Example: CM97012345ABCD  |  CF85123456X4CU
_NIN_PATTERN = re.compile(r'^C[MF]\d{8}[A-Z0-9]{4}$', re.IGNORECASE)


def _validate_nin_format(nin: str):
    """Raise ValueError if NIN does not match Uganda's 14-char format."""
    if not _NIN_PATTERN.match(nin):
        raise ValueError(
            f'Invalid NIN "{nin}". '
            f'Must be 14 characters starting with CM (male) or CF (female), '
            f'followed by 8 digits and 4 alphanumeric characters. '
            f'Example: CM97012345ABCD'
        )


def _check_nin_unique(db, nin: str, exclude_id: int = None):
    """Raise ValueError if another active client already has this NIN."""
    query = db.query(Client).filter(
        Client.nin       == nin.upper(),
        Client.is_active == True,
    )
    if exclude_id:
        query = query.filter(Client.id != exclude_id)
    if query.first():
        raise ValueError(
            f'NIN "{nin.upper()}" is already registered to another client.'
        )


def _check_phone_unique(db, phone: str, exclude_id: int = None):
    """Raise ValueError if another active client already has this phone number."""
    query = db.query(Client).filter(
        Client.phone_number == phone,
        Client.is_active    == True,
    )
    if exclude_id:
        query = query.filter(Client.id != exclude_id)
    if query.first():
        raise ValueError(
            f'Phone number "{phone}" is already registered to another client.'
        )


def _client_snapshot(client: Client) -> dict:
    """Return a JSON-serialisable dict snapshot of a client record."""
    return {
        "id":           client.id,
        "full_name":    client.full_name,
        "nin":          client.nin,
        "phone_number": client.phone_number,
        "email":        getattr(client, "email", None),
        "address":      getattr(client, "address", None),
        "is_active":    client.is_active,
    }


class ClientService:

    # ── Create ─────────────────────────────────────────────────────────────────

    @staticmethod
    def create_client(data: dict, created_by_id: int = None) -> Client:
        """
        Create and return a new client.

        Validates:
          - NIN format (if provided)
          - NIN uniqueness (if provided)
          - Phone number uniqueness

        Args:
            data:           Dict of Client field values.
            created_by_id:  ID of the user performing this action (for audit log).

        Raises:
            ValueError: if NIN format is wrong, or NIN/phone already exists.
        """
        # ── Normalise NIN to uppercase ─────────────────────────────────────
        nin = (data.get("nin") or "").strip().upper()
        if nin:
            data["nin"] = nin

        phone = (data.get("phone_number") or "").strip()

        with get_db() as db:
            # ── Validate NIN format ────────────────────────────────────────
            if nin:
                _validate_nin_format(nin)

            # ── Check NIN uniqueness ───────────────────────────────────────
            if nin:
                _check_nin_unique(db, nin)

            # ── Check phone uniqueness ─────────────────────────────────────
            if phone:
                _check_phone_unique(db, phone)

            # ── Create client ──────────────────────────────────────────────
            client = Client(**data)
            db.add(client)
            db.commit()
            db.refresh(client)
            db.expunge(client)

        AuditService.log(
            action      = Actions.CLIENT_CREATED,
            user_id     = created_by_id,
            entity_type = "Client",
            entity_id   = client.id,
            description = (
                f"New client created: {client.full_name} "
                f"| NIN: {client.nin} "
                f"| Phone: {client.phone_number}"
            ),
            new_value   = _client_snapshot(client),
        )
        return client

    # ── Read ───────────────────────────────────────────────────────────────────

    @staticmethod
    def get_all_clients(search: str = None) -> list:
        """
        Return all active clients.
        If a search string is provided, filter by name, NIN, or phone.
        """
        with get_db() as db:
            query = db.query(Client).filter_by(is_active=True)

            if search:
                term  = f"%{search}%"
                query = query.filter(
                    Client.full_name.ilike(term)    |
                    Client.nin.ilike(term)           |
                    Client.phone_number.ilike(term)
                )

            clients = query.order_by(Client.full_name).all()
            for c in clients:
                db.expunge(c)

        return clients

    @staticmethod
    def get_client_by_id(client_id: int) -> Client | None:
        """Return a single client by primary key, or None if not found."""
        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if client:
                db.expunge(client)
        return client

    @staticmethod
    def get_client_by_nin(nin: str) -> Client | None:
        """Look up an active client by NIN — used to prevent duplicates."""
        with get_db() as db:
            client = db.query(Client).filter_by(
                nin=nin.upper(), is_active=True).first()
            if client:
                db.expunge(client)
        return client

    @staticmethod
    def count_clients() -> int:
        """Return total number of active clients."""
        with get_db() as db:
            return db.query(Client).filter_by(is_active=True).count()

    # ── Update ─────────────────────────────────────────────────────────────────

    @staticmethod
    def update_client(
        client_id: int,
        data: dict,
        updated_by_id: int = None,
    ) -> Client:
        """
        Update client fields from a dictionary.

        Validates:
          - NIN format (if NIN is being changed)
          - NIN uniqueness (excludes current client)
          - Phone uniqueness (excludes current client)

        Args:
            client_id:      Primary key of the client to update.
            data:           Dict of fields to update.
            updated_by_id:  ID of the user performing this action (for audit log).

        Raises:
            ValueError: if client not found, NIN format wrong, or
                        NIN/phone already belongs to another client.
        """
        # ── Normalise NIN to uppercase ─────────────────────────────────────
        nin = (data.get("nin") or "").strip().upper()
        if nin:
            data["nin"] = nin

        phone = (data.get("phone_number") or "").strip()

        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if not client:
                raise ValueError(f"Client #{client_id} not found.")

            old_snapshot = _client_snapshot(client)

            # ── Validate NIN format ────────────────────────────────────────
            if nin:
                _validate_nin_format(nin)

            # ── Check NIN uniqueness (exclude this client) ─────────────────
            if nin:
                _check_nin_unique(db, nin, exclude_id=client_id)

            # ── Check phone uniqueness (exclude this client) ───────────────
            if phone:
                _check_phone_unique(db, phone, exclude_id=client_id)

            # ── Apply updates ──────────────────────────────────────────────
            for key, value in data.items():
                if hasattr(client, key):
                    setattr(client, key, value)

            db.commit()
            db.refresh(client)
            new_snapshot = _client_snapshot(client)
            db.expunge(client)

        AuditService.log(
            action      = Actions.CLIENT_UPDATED,
            user_id     = updated_by_id,
            entity_type = "Client",
            entity_id   = client_id,
            description = f"Client profile updated: {client.full_name}",
            old_value   = old_snapshot,
            new_value   = new_snapshot,
        )
        return client

    # ── Delete (soft) ──────────────────────────────────────────────────────────

    @staticmethod
    def delete_client(client_id: int, deleted_by_id: int = None) -> None:
        """
        Soft-delete a client by setting is_active = False.

        Args:
            client_id:      Primary key of the client to deactivate.
            deleted_by_id:  ID of the user performing this action (for audit log).
        """
        client_name = "Unknown"

        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if client:
                client_name      = client.full_name
                client.is_active = False
                db.commit()

        AuditService.log(
            action      = Actions.CLIENT_DELETED,
            user_id     = deleted_by_id,
            entity_type = "Client",
            entity_id   = client_id,
            description = f"Client deactivated (soft-deleted): {client_name}",
        )