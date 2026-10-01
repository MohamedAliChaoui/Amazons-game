import gettext

from amazons import i18n


def test_setup_i18n_installs_detected_translation(monkeypatch):
    installed = []

    class DummyTranslation:
        def install(self):
            installed.append(True)

        def gettext(self, message):
            return f"xx:{message}"

    monkeypatch.setattr(i18n, "detect_language", lambda lc_all=None, lang=None: "fr")
    monkeypatch.setattr(
        i18n.gettext,
        "translation",
        lambda domain, localedir, languages: DummyTranslation(),
    )

    translator = i18n.setup_i18n()

    assert installed == [True]
    assert translator("hello") == "xx:hello"


def test_setup_i18n_falls_back_to_identity_when_catalog_missing(monkeypatch):
    monkeypatch.setattr(i18n, "detect_language", lambda lc_all=None, lang=None: "fr")
    monkeypatch.setattr(
        i18n.gettext,
        "translation",
        lambda domain, localedir, languages: (_ for _ in ()).throw(FileNotFoundError()),
    )

    translator = i18n.setup_i18n()

    assert translator("hello") == "hello"


def test_detect_system_language_returns_french_from_windows_api(monkeypatch):
    class Kernel32:
        @staticmethod
        def GetUserDefaultUILanguage():
            return 0x040C

    class Windll:
        kernel32 = Kernel32()

    monkeypatch.setattr(i18n.ctypes, "windll", Windll(), raising=False)

    assert i18n.detect_system_language() == "fr"


def test_detect_system_language_falls_back_to_locale_english(monkeypatch):
    monkeypatch.delattr(i18n.ctypes, "windll", raising=False)
    monkeypatch.setattr(i18n.locale, "getdefaultlocale", lambda: ("en_US", "UTF-8"))

    assert i18n.detect_system_language() == "en"
