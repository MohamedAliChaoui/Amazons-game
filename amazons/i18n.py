"""Internationalization helpers for the Game of Amazons.

Detects the user's language from environment variables (``LC_ALL``,
``LANG``) or the operating system, then sets up GNU gettext so that
all user-facing strings can be translated.

Supported languages: English (``en``) and French (``fr``).
"""

import ctypes
import gettext
import locale
import os

LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locales")
SUPPORTED_LANGUAGES = {"en", "fr"}


def detect_system_language() -> str:
    """Detect the system UI language.

    On Windows this queries the Win32 API; on other platforms it falls
    back to :func:`locale.getdefaultlocale`.

    Returns:
        ``'fr'`` if French is detected, otherwise ``'en'``.
    """
    # Windows
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if (lang_id & 0xFF) == 0x0C:  # French
            return "fr"
        return "en"
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Linux / macOS
    sys_lang = locale.getdefaultlocale()[0]
    if sys_lang and sys_lang.startswith("fr"):
        return "fr"
    return "en"


def detect_language(lc_all=None, lang=None) -> str:
    """Determine the application language.

    Priority order:

    1. *lc_all* parameter (from ``LC_ALL`` env var).
    2. *lang* parameter (from ``LANG`` env var).
    3. System default via :func:`detect_system_language`.

    Args:
        lc_all: Value of the ``LC_ALL`` environment variable.
        lang: Value of the ``LANG`` environment variable.

    Returns:
        ``'en'`` or ``'fr'``.
    """
    # 1. LC_ALL has highest priority
    if lc_all:
        if lc_all.startswith("fr"):
            return "fr"
        if lc_all.startswith("en"):
            return "en"
        print(
            f"Warning: unsupported language '{lc_all}', "
            "falling back to English."
        )
        return "en"

    # 2. LANG
    if lang:
        if lang.startswith("fr"):
            return "fr"
        if lang.startswith("en"):
            return "en"
        print(
            f"Warning: unsupported language '{lang}', "
            "falling back to English."
        )
        return "en"

    # 3. System fallback
    return detect_system_language()


def setup_i18n(lc_all=None, lang=None) -> callable:
    """Configure gettext and return the translation function.

    Args:
        lc_all: Value of ``LC_ALL`` (overrides everything).
        lang: Value of ``LANG``.

    Returns:
        A callable ``_(msg)`` that translates *msg*.
    """
    detected = detect_language(lc_all=lc_all, lang=lang)
    try:
        translation = gettext.translation(
            domain="amazons",
            localedir=LOCALE_DIR,
            languages=[detected],
        )
        translation.install()
        return translation.gettext
    except FileNotFoundError:
        # Fallback if translation files are missing
        return lambda s: s
