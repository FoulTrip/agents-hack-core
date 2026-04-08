from __future__ import annotations

import re
from typing import Any, Dict


def flatten_files_payload(files: Any) -> Dict[str, str]:
    """
    Aplana estructuras anidadas de archivos a un mapping plano {path: content}.

    Ejemplo:
    {
      "__tests__": {
        "api/products.test.ts": "...",
        "api/checkout.test.ts": "..."
      }
    }
    ->
    {
      "__tests__/api/products.test.ts": "...",
      "__tests__/api/checkout.test.ts": "..."
    }
    """
    if not isinstance(files, dict):
        return {}

    flattened: Dict[str, str] = {}

    def walk(prefix: str, node: Any) -> None:
        if isinstance(node, dict):
            for raw_key, value in node.items():
                key = str(raw_key or "").strip()
                if not key:
                    continue
                next_prefix = f"{prefix}/{key}" if prefix else key
                walk(next_prefix, value)
            return

        if node is None:
            return

        if not prefix:
            return

        flattened[prefix] = node if isinstance(node, str) else str(node)

    walk("", files)

    if not flattened:
        return flattened

    # 1) Si existe una ruta padre y también rutas hijas (p. ej. "__tests__" y
    # "__tests__/api/a.test.ts"), eliminamos la entrada padre para evitar crear
    # un archivo donde en realidad debe existir un directorio.
    keys_sorted = sorted(flattened.keys())
    drop: set[str] = set()
    for idx, key in enumerate(keys_sorted):
        prefix = f"{key}/"
        if idx + 1 < len(keys_sorted) and keys_sorted[idx + 1].startswith(prefix):
            drop.add(key)

    # 2) Ignorar placeholders de directorio comunes (ej. "__tests__") cuando
    # llegan como archivo suelto.
    for key in keys_sorted:
        leaf = key.rsplit("/", 1)[-1].strip()
        if "/" not in key and re.fullmatch(r"__[^/]+__", leaf or ""):
            drop.add(key)

    for key in drop:
        flattened.pop(key, None)

    return flattened
