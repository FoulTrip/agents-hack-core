def heading1(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_1",
        "heading_1": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }

def heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }

def paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }

def bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }

def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}

def blocks_to_markdown(blocks: list) -> str:
    """Convierte bloques de Notion a Markdown plano."""
    md = []
    for b in blocks:
        b_type = b.get("type")
        if b_type == "heading_1":
            text = b["heading_1"]["rich_text"][0]["text"]["content"]
            md.append(f"# {text}")
        elif b_type == "heading_2":
            text = b["heading_2"]["rich_text"][0]["text"]["content"]
            md.append(f"## {text}")
        elif b_type == "paragraph":
            rich_text = b["paragraph"]["rich_text"]
            text = "".join([t["text"]["content"] for t in rich_text]) if rich_text else ""
            md.append(text)
        elif b_type == "bulleted_list_item":
            text = b["bulleted_list_item"]["rich_text"][0]["text"]["content"]
            md.append(f"* {text}")
        elif b_type == "divider":
            md.append("---")
    return "\n\n".join(md)