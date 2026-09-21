from app.store import Store, get_store


def store_dependency() -> Store:
    return get_store()
