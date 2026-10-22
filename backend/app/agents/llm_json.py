import json


def parse_llm_json(response):
    """
    Parse a JSON object from an LLM response.

    Handles clean JSON, ```json fences and JSON wrapped
    in extra prose. Returns None when no object is found.
    """

    if response is None:
        return None

    cleaned = str(response).strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")

    if (
        first_brace != -1
        and last_brace > first_brace
    ):
        try:
            data = json.loads(
                cleaned[first_brace:last_brace + 1]
            )

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

    return None


def ensure_str_list(value):
    """
    Normalize an LLM field that should be a list of
    strings. The frontend iterates these fields, so a
    bare string or nested object must not leak through.
    """

    if value is None:
        return []

    if not isinstance(value, (list, tuple)):
        value = [value]

    items = []

    for item in value:
        if item is None:
            continue

        if isinstance(item, dict):
            item = (
                item.get("claim")
                or item.get("text")
                or item.get("finding")
                or json.dumps(item, ensure_ascii=False)
            )

        text = str(item).strip()

        if text:
            items.append(text)

    return items
