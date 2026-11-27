"""Python mirror of the banner check, so flag-cleanup's multi-language search has something to find."""


def show_banner(flagsmith):
    if flagsmith.has_feature('old_banner'):
        return 'Winter sale - 20% off!'
    return None
