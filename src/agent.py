def get_billing_status(account_id: str) -> str:
    """Gets the current status of a Google Cloud billing account.

    Args:
        account_id: The billing account identifier (e.g. 'A100', 'B200').

    Returns:
        The status string for the account.
    """
    statuses = {"A100": "Active", "B200": "Suspended", "C300": "Closed"}
    return statuses.get(account_id, f"Unknown account: {account_id}")


def get_billing_forecast(account_id: str, months: int = 3) -> str:
    """Gets a billing forecast for a Google Cloud account.

    Args:
        account_id: The billing account identifier.
        months: Number of months to forecast (default 3).

    Returns:
        A forecast summary string.
    """
    forecasts = {
        "A100": {"monthly_avg": 12500, "trend": "increasing 8% MoM"},
        "B200": {"monthly_avg": 0, "trend": "suspended"},
        "C300": {"monthly_avg": 0, "trend": "closed"},
    }
    info = forecasts.get(account_id)
    if not info:
        return f"No forecast data for account {account_id}"
    projected = info["monthly_avg"] * months
    return f"Account {account_id}: ${info['monthly_avg']}/mo avg, trend: {info['trend']}, {months}-month projection: ${projected}"
