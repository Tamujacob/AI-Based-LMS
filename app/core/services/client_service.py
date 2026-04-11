"""
app/core/services/client_service.py
─────────────────────────────────────────────
All database operations for client/borrower profiles.
"""

from app.database.connection import get_db
from app.core.models.client import Client


class ClientService:

    @staticmethod
    def create_client(data: dict) -> Client:
        """Create and return a new client."""
        with get_db() as db:
            client = Client(**data)
            db.add(client)
            db.commit()
            db.refresh(client)
            db.expunge(client)
            return client

    @staticmethod
    def get_all_clients(search: str = None) -> list:
        """
        Return all active clients.
        If search string provided, filter by name, NIN, or phone.
        """
        with get_db() as db:
            query = db.query(Client).filter_by(is_active=True)
            if search:
                term = f"%{search}%"
                query = query.filter(
                    Client.full_name.ilike(term) |
                    Client.nin.ilike(term) |
                    Client.phone_number.ilike(term)
                )
            clients = query.order_by(Client.full_name).all()
            for c in clients:
                db.expunge(c)
            return clients

    @staticmethod
    def get_client_by_id(client_id: int) -> Client:
        """Return a single client by ID."""
        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if client:
                db.expunge(client)
            return client

    @staticmethod
    def get_client_by_nin(nin: str) -> Client:
        """Look up a client by NIN — used to prevent duplicates."""
        with get_db() as db:
            client = db.query(Client).filter_by(nin=nin, is_active=True).first()
            if client:
                db.expunge(client)
            return client

    @staticmethod
    def update_client(client_id: int, data: dict) -> Client:
        """Update client fields from a dictionary."""
        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if not client:
                raise ValueError(f"Client #{client_id} not found.")
            for key, value in data.items():
                if hasattr(client, key):
                    setattr(client, key, value)
            db.commit()
            db.refresh(client)
            db.expunge(client)
            return client

    @staticmethod
    def delete_client(client_id: int):
        """Soft-delete a client (set is_active = False)."""
        with get_db() as db:
            client = db.query(Client).filter_by(id=client_id).first()
            if client:
                client.is_active = False
                db.commit()

    @staticmethod
    def count_clients() -> int:
        with get_db() as db:
            return db.query(Client).filter_by(is_active=True).count()