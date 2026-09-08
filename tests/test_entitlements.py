from app.core.entitlements import effective_entitlements


def test_unconfigured_central_license_keeps_local_role_access():
    result = effective_entitlements(
        local_module_ids=["manim_transfer", "report_editing"],
        central_module_ids=None,
        central_license_usable=None,
    )
    assert result.allows("manim_transfer")


def test_usable_central_license_intersects_with_local_role_access():
    result = effective_entitlements(
        local_module_ids=["manim_transfer", "report_editing"],
        central_module_ids=["manim_transfer"],
        central_license_usable=True,
    )
    assert result.allows("manim_transfer")
    assert not result.allows("report_editing")


def test_explicitly_invalid_central_license_allows_no_module():
    result = effective_entitlements(
        local_module_ids=["manim_transfer"], central_module_ids=["manim_transfer"], central_license_usable=False
    )
    assert not result.allows("manim_transfer")
