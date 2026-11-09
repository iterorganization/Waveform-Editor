import pytest

from waveform_editor.settings import NiceSettings


@pytest.fixture
def unreadable(monkeypatch):
    """Make the presets whose URIs contain a given substring unreadable."""

    def make_unreadable(substring):
        def check_preset(self, preset):
            if any(substring in uri for uri in preset.values()):
                raise Exception("unreadable")

        monkeypatch.setattr(NiceSettings, "_check_preset", check_preset)

    return make_unreadable


def test_presets_default(unreadable):
    """Test that the default presets are used when they can be loaded."""
    unreadable("no uri contains this")
    settings = NiceSettings()
    assert settings._available_presets == NiceSettings.PRESET_URIS


def test_presets_fallback(unreadable):
    """Test that the fallback presets are used when the defaults cannot be loaded."""
    unreadable("blokhus")
    settings = NiceSettings()
    assert settings._available_presets == NiceSettings.FALLBACK_PRESET_URIS

    settings.machine_preset = NiceSettings.PRESET_WEST
    fallback_west = NiceSettings.FALLBACK_PRESET_URIS[NiceSettings.PRESET_WEST]
    assert settings.md_wall.uri == fallback_west["wall"]


def test_presets_unreadable(unreadable):
    """Test that only the custom preset remains when no preset can be loaded."""
    unreadable("imas:")
    settings = NiceSettings()
    assert settings._available_presets == {}
    assert settings.param.machine_preset.objects == [NiceSettings.PRESET_CUSTOM]
