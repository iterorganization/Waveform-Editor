import panel as pn
import pytest

from waveform_editor.settings import NiceSettings

SDCC = NiceSettings.CLUSTER_SDCC
ALTAIR = NiceSettings.CLUSTER_ALTAIR
ITER = NiceSettings.PRESET_ITER
WEST = NiceSettings.PRESET_WEST
CUSTOM = NiceSettings.PRESET_CUSTOM


@pytest.fixture
def available(monkeypatch):
    """The presets that can be loaded on each cluster, without reading any data."""
    available = {SDCC: [ITER, WEST], ALTAIR: [ITER, WEST]}

    def load(self):
        presets = self.CLUSTER_PRESET_URIS[self.cluster]
        return {name: presets[name] for name in available[self.cluster]}

    monkeypatch.setattr(NiceSettings, "_load_machine_description_presets", load)
    return available


@pytest.mark.parametrize(
    "hostname, cluster",
    [
        ("altair.partenaires.cea.fr", ALTAIR),
        ("sdcc-login01.iter.org", SDCC),
        ("my-laptop", SDCC),
    ],
)
def test_detect_cluster(monkeypatch, available, hostname, cluster):
    monkeypatch.setattr("socket.getfqdn", lambda: hostname)
    assert NiceSettings().cluster == cluster


def test_change_cluster(available):
    nice = NiceSettings(cluster=SDCC)
    nice.machine_preset = WEST
    assert "blokhus" in nice.md_wall.uri

    nice.cluster = ALTAIR
    assert nice.machine_preset == WEST
    assert nice.md_wall.uri == nice.CLUSTER_PRESET_URIS[ALTAIR][WEST]["wall"]


def test_change_cluster_without_preset(available):
    available[ALTAIR] = [ITER]
    nice = NiceSettings(cluster=SDCC)
    nice.machine_preset = WEST

    nice.cluster = ALTAIR
    assert nice.param.machine_preset.objects == [ITER, CUSTOM]
    assert nice.machine_preset == CUSTOM


def test_apply_settings_cluster_first(available):
    """The preset is only checked against the presets of the stored cluster."""
    available[SDCC] = []
    nice = NiceSettings(cluster=SDCC)

    nice.apply_settings({"cluster": ALTAIR, "machine_preset": WEST})
    assert nice.cluster == ALTAIR
    assert nice.machine_preset == WEST
    assert nice.md_wall.uri == nice.CLUSTER_PRESET_URIS[ALTAIR][WEST]["wall"]


def test_apply_settings_unavailable_preset(available):
    available[ALTAIR] = [ITER]
    nice = NiceSettings(cluster=ALTAIR)

    nice.apply_settings({"machine_preset": WEST, "cluster": "unknown cluster"})
    assert nice.cluster == ALTAIR
    assert nice.machine_preset == CUSTOM


def test_to_dict_stores_cluster(available):
    assert NiceSettings(cluster=ALTAIR).to_dict()["cluster"] == ALTAIR


def test_preset_selector_follows_cluster(available):
    available[ALTAIR] = [WEST]
    nice = NiceSettings(cluster=SDCC)
    selector = pn.widgets.Select.from_param(nice.param.machine_preset)

    nice.cluster = ALTAIR
    assert list(selector.options) == [WEST, CUSTOM]
