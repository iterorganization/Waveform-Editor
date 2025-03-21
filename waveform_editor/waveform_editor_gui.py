import panel as pn
import yaml

pn.extension()

yaml_file = "waveform_editor/test.yaml"

with open(yaml_file) as f:
    yaml_data = yaml.safe_load(f)


def create_ui(data):
    """Recursively create a Panel UI structure from the YAML"""
    categories = []
    options = []

    for key, value in data.items():
        if key == "globals":
            continue
        elif "/" in key:
            # If it contains '/', treat it as an option for selection
            options.append(key)
        else:
            categories.append((key, create_ui(value)))

    content = []
    if options:
        check_buttons = pn.widgets.CheckButtonGroup(
            value=[],
            options=options,
            button_style="outline",
            button_type="primary",
            sizing_mode="stretch_width",
            orientation="vertical",
            stylesheets=["button {text-align: left!important;}"],
        )
        content.append(check_buttons)

    if categories:
        accordion = pn.Accordion(*categories)
        content.append(accordion)

    return pn.Column(*content, sizing_mode="stretch_width")


yaml_ui = create_ui(yaml_data)

pn.template.MaterialTemplate(
    title="Waveform Editor (v0.0 ~ mockup)",
    sidebar=[yaml_ui],
    main=pn.Column(pn.pane.Markdown("## Dynamic YAML Viewer")),
).servable()
