"""Pipeline steps. Importing a module registers its Step."""


def load_all() -> None:
    from . import script, storyboard, assets, tts, align, timeline, render, qa  # noqa: F401
