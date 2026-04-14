"""
Swagger UI HTML with explicit tag ordering.

OpenAPI's root ``tags`` array does not always control the sidebar: Swagger UI may
order tag groups by how operations first appear when it walks the spec. Injecting
``tagsSorter`` guarantees the sidebar matches our product flow.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.openapi.docs import swagger_ui_default_parameters
from starlette.responses import HTMLResponse


def get_swagger_ui_html_with_tag_order(
    *,
    openapi_url: str,
    title: str,
    tag_order: list[str],
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    oauth2_redirect_url: Optional[str] = None,
    init_oauth: Optional[dict[str, Any]] = None,
    swagger_ui_parameters: Optional[dict[str, Any]] = None,
) -> HTMLResponse:
    current = swagger_ui_default_parameters.copy()
    if swagger_ui_parameters:
        current.update(swagger_ui_parameters)
    # Our injected function replaces any JSON-only tagsSorter from parameters.
    current.pop("tagsSorter", None)

    order_json = json.dumps(tag_order)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link type="text/css" rel="stylesheet" href="{swagger_css_url}">
    <link rel="shortcut icon" href="{swagger_favicon_url}">
    <title>{title}</title>
    </head>
    <body>
    <div id="swagger-ui">
    </div>
    <script src="{swagger_js_url}"></script>
    <script>
    const ui = SwaggerUIBundle({{
        url: '{openapi_url}',
    """

    for key, value in current.items():
        html += f"{json.dumps(key)}: {json.dumps(jsonable_encoder(value))},\n"

    if oauth2_redirect_url:
        html += f"oauth2RedirectUrl: window.location.origin + '{oauth2_redirect_url}',"

    html += f"""
    tagsSorter: (a, b) => {{
      const order = {order_json};
      const ia = order.indexOf(a);
      const ib = order.indexOf(b);
      const fa = ia === -1 ? 10000 : ia;
      const fb = ib === -1 ? 10000 : ib;
      return fa - fb || String(a).localeCompare(String(b));
    }},
    """

    html += """
    presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
    })"""

    if init_oauth:
        html += f"""
        ui.initOAuth({json.dumps(jsonable_encoder(init_oauth))})
        """

    html += """
    </script>
    </body>
    </html>
    """
    return HTMLResponse(html)
