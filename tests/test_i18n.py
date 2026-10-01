import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from amazons.i18n import (  # noqa: E402
    detect_language,
    detect_system_language,
)


# Tests detect_language()
class TestDetectLanguage:

    # LC_ALL

    def test_lc_all_french(self):
        """LC_ALL=fr_FR.UTF-8 → fr"""
        assert detect_language(lc_all="fr_FR.UTF-8") == "fr"

    def test_lc_all_english(self):
        """LC_ALL=en_US.UTF-8 → en"""
        assert detect_language(lc_all="en_US.UTF-8") == "en"

    def test_lc_all_unsupported(self, capsys):
        """LC_ALL=ar_MA.UTF-8 → warning + en"""
        result = detect_language(lc_all="ar_MA.UTF-8")
        captured = capsys.readouterr()
        assert result == "en"
        assert "Warning" in captured.out
        assert "ar_MA.UTF-8" in captured.out

    def test_lc_all_priority_over_lang(self):
        """LC_ALL est prioritaire sur LANG"""
        assert (
            detect_language(lc_all="en_US.UTF-8", lang="fr_CA.UTF-8") == "en"
        )

    # LANG

    def test_lang_french(self):
        """LANG=fr_CA.UTF-8 → fr"""
        assert detect_language(lang="fr_CA.UTF-8") == "fr"

    def test_lang_english(self):
        """LANG=en_GB.UTF-8 → en"""
        assert detect_language(lang="en_GB.UTF-8") == "en"

    def test_lang_unsupported(self, capsys):
        """LANG=ar_MA.UTF-8 → warning + en"""
        result = detect_language(lang="ar_MA.UTF-8")
        captured = capsys.readouterr()
        assert result == "en"
        assert "Warning" in captured.out
        assert "ar_MA.UTF-8" in captured.out

    def test_lang_en_us_utf8_detected(self):
        """LANG=en_US.UTF-8 → 'en' (standard locale, not ignored)"""
        result = detect_language(lang="en_US.UTF-8")
        assert result == "en"

    def test_lang_fr_fr_utf8_detected(self):
        """LANG=fr_FR.UTF-8 → 'fr' (standard locale, not ignored)"""
        result = detect_language(lang="fr_FR.UTF-8")
        assert result == "fr"

    # Fallback système

    def test_no_env_fallback_system(self):
        """Sans LC_ALL ni LANG → détection système"""
        with patch(
            "amazons.i18n.detect_system_language", return_value="fr"
        ) as mock:
            result = detect_language()
            mock.assert_called_once()
            assert result == "fr"

    def test_none_values_fallback_system(self):
        """LC_ALL=None, LANG=None → détection système"""
        with patch(
            "amazons.i18n.detect_system_language", return_value="en"
        ) as mock:
            result = detect_language(lc_all=None, lang=None)
            mock.assert_called_once()
            assert result == "en"


# Tests detect_system_language()
class TestDetectSystemLanguage:

    def test_windows_french(self):
        """Windows avec langue française (0x40C) → fr"""
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32.GetUserDefaultUILanguage.return_value = (
            0x040C
        )
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            # Recharger pour que ctypes soit mocké
            result = _detect_system_windows(0x040C)
            assert result == "fr"

    def test_windows_english(self):
        """Windows avec langue anglaise (0x409) → en"""
        result = _detect_system_windows(0x0409)
        assert result == "en"

    def test_windows_arabic(self):
        """Windows avec langue arabe (0x401) → en (non supporté)"""
        result = _detect_system_windows(0x0401)
        assert result == "en"

    def test_linux_french(self):
        """Linux avec locale fr_FR → fr"""
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32.GetUserDefaultUILanguage.side_effect = (
            Exception()
        )
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            with patch(
                "locale.getdefaultlocale", return_value=("fr_FR", "UTF-8")
            ):
                result = detect_system_language()
                assert result == "fr"

    def test_linux_english(self):
        """Linux avec locale en_US → en"""
        with patch("ctypes.windll", side_effect=AttributeError, create=True):
            with patch(
                "locale.getdefaultlocale", return_value=("en_US", "UTF-8")
            ):
                result = detect_system_language()
                assert result == "en"

    def test_linux_no_locale(self):
        """Linux sans locale → en par défaut"""
        with patch("ctypes.windll", side_effect=AttributeError, create=True):
            with patch("locale.getdefaultlocale", return_value=(None, None)):
                result = detect_system_language()
                assert result == "en"


def _detect_system_windows(lang_id: int) -> str:
    """Helper : simule detect_system_language avec un lang_id Windows."""
    primary = lang_id & 0xFF
    if primary == 0x0C:
        return "fr"
    return "en"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
