"""Composer-native panel with a searchable property selector and fixed swatches."""
from pathlib import Path

import carb.settings
import omni.ui as ui

from . import presets
from .discovery import property_label
from .scheme import PALETTE


def swatch_color(color):
    if color is None:
        return 0xFF555555
    return 0xFF000000 | int(color[5:7], 16) << 16 | int(color[3:5], 16) << 8 | int(color[1:3], 16)


class ObjectColorsWindow:
    def __init__(self, controller):
        self.controller = controller
        self.window = ui.Window('Object Colors', width=440, height=690)
        self.search = ui.SimpleStringModel('')
        self.name = ui.SimpleStringModel('My colors')
        self.file_path = ui.SimpleStringModel('')
        self.template_index = 0
        self.palette_window = None
        self.templates = []
        self._load_templates()
        controller.listeners.append(self.update)
        self.window.frame.set_build_fn(self.build)
        self.search.add_value_changed_fn(lambda _: self.property_frame.rebuild())

    def _load_templates(self):
        directories = [Path(__file__).resolve().parent.parent / 'data/templates']
        configured = carb.settings.get_settings().get('/exts/object.color/templateDirectory')
        if configured:
            directories.append(Path(configured))
        for directory in directories:
            for path in sorted(directory.glob('*.json')):
                try:
                    name, _ = presets.read(path)
                    self.templates.append((name, path))
                except (ValueError, OSError) as exc:
                    self.controller.issues.append(f'{path.name}: {exc}')

    def update(self, rebuild=True):
        if rebuild:
            self.window.frame.rebuild()
        elif hasattr(self, 'status_label'):
            self.status_label.text = self.controller.status

    def show(self):
        self.window.visible = True

    def build(self):
        controller = self.controller
        with ui.VStack(spacing=8, margin=12):
            ui.Label('Object Colors', height=25, style={'font_size': 20})
            ui.Label('Whole stage', height=18, style={'color': 0xFFAAAAAA})
            with ui.VStack(spacing=8, height=0, enabled=not controller.busy and controller.stage is not None):
                with ui.HStack(height=24):
                    enabled = ui.CheckBox(width=22)
                    enabled.model.set_value(controller.scheme.enabled)
                    enabled.model.add_value_changed_fn(lambda m: controller.edit(enabled=m.as_bool))
                    ui.Label('Enable colors')
                    ui.Button('Refresh', width=85, clicked_fn=controller.refresh)
                with ui.HStack(height=24):
                    ui.Label('Color by', width=78)
                    modes = ('Property', 'File', 'Model')
                    combo = ui.ComboBox(modes.index(controller.scheme.mode), *modes)
                    combo.model.add_item_changed_fn(
                        lambda m, _: controller.edit(mode=modes[m.get_item_value_model().as_int]))
                reason = controller.scan.unavailable_reason(controller.scheme.mode)
                if reason:
                    ui.Label(reason, word_wrap=True, height=34, style={'color': 0xFF88BBFF})
                if controller.scheme.mode == 'Property':
                    ui.StringField(self.search, height=24, tooltip='Filter property names and categories')
                    self.property_frame = ui.Frame(height=26)
                    self.property_frame.set_build_fn(self._build_properties)
                with ui.CollapsableFrame('Shared templates', height=0, collapsed=False):
                    with ui.VStack(spacing=6, margin=6):
                        ui.Label('Load a copy. Your edits do not change the template.', height=20)
                        if self.templates:
                            with ui.HStack(height=25):
                                template = ui.ComboBox(self.template_index, *(n for n, _ in self.templates))
                                template.model.add_item_changed_fn(self._template_changed)
                                ui.Button('Load', width=60, clicked_fn=self._load_template)
                        with ui.HStack(height=24):
                            ui.Label('Preset name', width=85)
                            ui.StringField(self.name)
                        ui.StringField(self.file_path, height=24, tooltip='Full path to a JSON preset file')
                        with ui.HStack(height=24):
                            ui.Button('Import JSON', clicked_fn=self._import)
                            ui.Button('Export new JSON', clicked_fn=self._export)
            ui.Separator(height=2)
            with ui.HStack(height=22):
                ui.Label('Value')
                ui.Label('Objects', width=62, alignment=ui.Alignment.RIGHT_CENTER)
                ui.Label('Color', width=58, alignment=ui.Alignment.CENTER)
            with ui.ScrollingFrame():
                with ui.VStack(spacing=4, height=0, enabled=not controller.busy):
                    for group in controller.groups:
                        with ui.HStack(height=26, spacing=6):
                            ui.Label(group.label, tooltip=group.key, elided_text=True)
                            ui.Label(str(len(group.objects)), width=56, alignment=ui.Alignment.RIGHT_CENTER)
                            ui.Button('None' if group.color is None else '', width=52,
                                      style={'background_color': swatch_color(group.color)},
                                      tooltip='Change group color', clicked_fn=lambda g=group: self._palette(g))
            self.status_label = ui.Label(controller.status, height=36, word_wrap=True)
            if controller.issues:
                with ui.CollapsableFrame(f'{len(controller.issues)} notices', height=0, collapsed=True):
                    with ui.ScrollingFrame(height=110):
                        ui.Label('\n'.join(controller.issues), word_wrap=True, alignment=ui.Alignment.LEFT_TOP)
            ui.Label('Save the scene to retain its active scheme. Export JSON to reuse it.',
                     word_wrap=True, height=32, style={'color': 0xFFAAAAAA})

    def _build_properties(self):
        keys = [k for k in self.controller.scan.properties if self.search.as_string.casefold() in property_label(k).casefold()]
        active = self.controller.scheme.property_key
        if active and active not in keys:
            keys.insert(0, active)
        if not keys:
            ui.Label('No matching properties')
            return
        combo = ui.ComboBox(keys.index(active) if active in keys else 0, *(property_label(k) for k in keys))
        combo.model.add_item_changed_fn(lambda m, _: self.controller.edit(property_key=keys[m.get_item_value_model().as_int]))

    def _palette(self, group):
        if self.palette_window:
            self.palette_window.destroy()
        self.palette_window = ui.Window('Choose color', width=350, height=260)
        with self.palette_window.frame:
            with ui.VStack(spacing=6, margin=10):
                ui.Label(group.label, height=24, elided_text=True)
                for row in range(5):
                    with ui.HStack(spacing=4, height=28):
                        for color in PALETTE[row * 8:(row + 1) * 8]:
                            ui.Button('', style={'background_color': swatch_color(color)},
                                      clicked_fn=lambda c=color: self._choose(group.key, c))
                ui.Button('No color', height=26, clicked_fn=lambda: self._choose(group.key, None))

    def _choose(self, key, color):
        if self.palette_window:
            self.palette_window.visible = False
        self.controller.edit(color=(key, color))

    def _template_changed(self, model, _):
        self.template_index = model.get_item_value_model().as_int

    def _message(self, operation):
        try:
            operation()
        except (OSError, ValueError) as exc:
            self.controller.status = str(exc)
            self.update()

    def _load(self, path):
        name, scheme = presets.read(path)
        self.name.set_value(name)
        self.controller.change(scheme)

    def _load_template(self):
        self._message(lambda: self._load(self.templates[self.template_index][1]))

    def _import(self):
        self._message(lambda: self._load(self.file_path.as_string))

    def _export(self):
        def write():
            presets.export(self.file_path.as_string, self.name.as_string, self.controller.scheme)
            self.controller.status = 'Preset exported. Shared templates were not changed.'
            self.update()
        self._message(write)

    def close(self):
        self.controller.listeners.remove(self.update)
        if self.palette_window:
            self.palette_window.destroy()
        self.window.destroy()
