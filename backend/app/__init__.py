from __future__ import annotations


def _patch_pydantic_import_email_validator() -> None:
    """
    Must run before `app.main` imports FastAPI (which loads OpenAPI models that use EmailStr).

    Pydantic's `import_email_validator()` calls `version("email-validator")`. Missing pip
    metadata yields `PackageNotFoundError` with `str(e) == "email-validator"` — the /openapi.json
    500 detail users were seeing. We replace the helper so only `email_validator.__version__` is used.
    """
    import pydantic.networks as _pn

    def _import_email_validator() -> None:
        if _pn.email_validator is not None:
            return
        try:
            import email_validator as _ev
        except ImportError as e:
            raise ImportError(
                "email-validator is not installed, run `pip install 'pydantic[email]'`"
            ) from e
        _ver = getattr(_ev, "__version__", None)
        _major = (str(_ver) if _ver else "2").partition(".")[0]
        if _major != "2":
            raise ImportError(
                "email-validator version >= 2.0 required, run pip install -U email-validator"
            )
        _pn.email_validator = _ev

    _pn.import_email_validator = _import_email_validator


_patch_pydantic_import_email_validator()
