from app.services.fare_service import promote_due_returns
from app.store import Store, get_store


def store_dependency() -> Store:
    store = get_store()
    promote_due_returns(store)
    return store
