from core.constants.events import EventType


# use existing domain event bus to define events such as ui theme changes, color changes and so on
class ThemeEvent(EventType):
    THEME_CHANGED = "app.theme.changed"  # Data : str(theme_name)
    THEME_ACCENT_CHANGED = "app.theme_accent.changed"  # Data: Kivy RGBA color
    THEME_FONT_STYLE = "app.theme.font_style"  # Data: Kivymd font theme style
    THEME_FONT_SIZE = "app.theme.font_size"  # Data : int
