"""Inspect upstream errors without losing status in adapter wrappers."""


def error_chain(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def http_status(exc):
    for cause in error_chain(exc):
        response = getattr(cause, 'response', None)
        status = getattr(cause, 'status_code', None)
        if status is None:
            status = getattr(response, 'status_code', None)
        if isinstance(status, int) and 100 <= status <= 599:
            return status
    return None


def rejects_output_contract(exc):
    # A contract on the request does not make every upstream failure a schema
    # rejection. In particular, outages, credentials and missing models keep
    # their own errors and HTTP status.
    status = http_status(exc)
    if status is not None and status not in {400, 404, 422}:
        return False
    text = str(exc).lower()
    return any(marker in text for marker in (
        'response_format', 'response format', 'json_schema', 'json schema',
        'structured output', 'tool_choice', 'tool choice', 'strict function',
    )) and any(marker in text for marker in (
        'unsupported', 'not support', 'invalid', 'unexpected keyword',
        'not allowed', 'not available', 'not permitted',
    ))
