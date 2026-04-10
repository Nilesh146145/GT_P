Vendored Swagger UI (swagger-ui-dist v5.11.0) for /docs — no CDN (Safari-friendly).
FastAPI’s ``get_swagger_ui_html`` only needs the bundle + CSS (BaseLayout preset is inside the bundle).

Required files: ``swagger-ui-bundle.js``, ``swagger-ui.css``, ``favicon-32x32.png``.

Refresh from jsDelivr:

  VER=5.11.0
  DIR=backend/app/static/swagger-ui
  curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist/${VER}/swagger-ui-bundle.js" -o "$DIR/swagger-ui-bundle.js"
  curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist/${VER}/swagger-ui.css" -o "$DIR/swagger-ui.css"
  curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist@${VER}/favicon-32x32.png" -o "$DIR/favicon-32x32.png"
