"""Manual SOW platform type inference from document text."""

from app.services.manual_sow.platform_detection import infer_platform_type_from_text
from app.schemas.manual_sow.manual_sow_platform_type import ManualSowPlatformType


def test_web_only():
    assert infer_platform_type_from_text("We need a responsive website for customers.") == ManualSowPlatformType.WEB_APPLICATION.value


def test_ios_only():
    assert infer_platform_type_from_text("Native iPhone app for field agents.") == ManualSowPlatformType.MOBILE_IOS.value


def test_multiple_categories_becomes_full_stack():
    t = "iOS and Android mobile apps plus a web portal for admins."
    assert infer_platform_type_from_text(t) == ManualSowPlatformType.FULL_STACK.value


def test_ios_android_without_web_is_mobile_hybrid():
    t = "Food delivery mobile application for Android and iOS platforms with APIs."
    assert infer_platform_type_from_text(t) == ManualSowPlatformType.MOBILE_HYBRID.value


def test_react_native_hybrid():
    assert (
        infer_platform_type_from_text("Cross-platform React Native mobile application.")
        == ManualSowPlatformType.MOBILE_HYBRID.value
    )


def test_empty_other():
    assert infer_platform_type_from_text("") == ManualSowPlatformType.OTHER.value
