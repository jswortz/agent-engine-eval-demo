"""In-memory mock user database for BYO MCP demo."""

USERS: dict[str, dict] = {
    "user-001": {
        "user_id": "user-001",
        "name": "Alice Chen",
        "email": "alice.chen@example.com",
        "role": "admin",
        "department": "Engineering",
        "created_at": "2024-01-15T09:00:00Z",
    },
    "user-002": {
        "user_id": "user-002",
        "name": "Bob Martinez",
        "email": "bob.martinez@example.com",
        "role": "developer",
        "department": "Engineering",
        "created_at": "2024-03-22T14:30:00Z",
    },
    "user-003": {
        "user_id": "user-003",
        "name": "Carol Nguyen",
        "email": "carol.nguyen@example.com",
        "role": "analyst",
        "department": "Data Science",
        "created_at": "2024-06-10T11:15:00Z",
    },
    "user-004": {
        "user_id": "user-004",
        "name": "David Kim",
        "email": "david.kim@example.com",
        "role": "manager",
        "department": "Product",
        "created_at": "2024-08-01T08:45:00Z",
    },
    "user-005": {
        "user_id": "user-005",
        "name": "Eva Rossi",
        "email": "eva.rossi@example.com",
        "role": "developer",
        "department": "Security",
        "created_at": "2025-01-05T16:20:00Z",
    },
}
