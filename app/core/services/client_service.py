"""
app/core/services/client_service.py
────────────────────────────────────
All database operations for client/borrower profiles.
Every write operation is fully audit-logged.
"""

from app.database.connection import get_db
from app.core.models.client import Client
from app.core.services.audit_service import AuditService, Actions


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

        Args:
            data:           Dict of Client field values.
            created_by_id:  ID of the user performing this action (for audit log).
        """
        with get_db() as db:
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
            client = db.query(Client).filter_by(nin=nin, is_active=True).first()
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

        Args:
            client_id:      Primary key of the client to update.
            data:           Dict of fields to update.
            updated_by_id:  ID of the user performing this action (for audit log).
        """
        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if not client:
                raise ValueError(f"Client #{client_id} not found.")

            old_snapshot = _client_snapshot(client)

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
                client_name     = client.full_name
                client.is_active = False
                db.commit()

        AuditService.log(
            action      = Actions.CLIENT_DELETED,
            user_id     = deleted_by_id,
            entity_type = "Client",
            entity_id   = client_id,
            description = f"Client deactivated (soft-deleted): {client_name}",
        )