import json
from pathlib import Path
import tempfile
import unittest
from pxr import Usd

from object_colors.presets import dumps, export, load_scene, loads, read, save_scene
from object_colors.scheme import Scheme


class PresetTests(unittest.TestCase):
    def test_save_reopen_restores_enabled_state_and_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'scene.usda')
            stage = Usd.Stage.CreateNew(path)
            scheme = Scheme(property_key='bim:Level', enabled=True)
            scheme.set_color('str:"Level 1"', '#E15759')
            scheme.set_color('missing', None)
            self.assertTrue(save_scene(stage, scheme))
            stage.GetRootLayer().Save()
            reopened = Usd.Stage.Open(path)
            self.assertEqual(load_scene(reopened), scheme)
            scheme.enabled = False
            save_scene(reopened, scheme)
            reopened.GetRootLayer().Save()
            self.assertFalse(load_scene(Usd.Stage.Open(path)).enabled)

    def test_exports_never_overwrite_shared_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'shared.json'
            export(path, 'Shared', Scheme())
            _, copy = read(path)
            copy.enabled = True
            with self.assertRaises(FileExistsError):
                export(path, 'Changed', copy)
            self.assertFalse(read(path)[1].enabled)

    def test_bad_imports_are_rejected(self):
        for key, value in [('version', 2), ('scope', 'selection'), ('enabled', 'false'),
                           ('palettes', {'Property:x': {'str:"y"': 'not a color'}})]:
            data = json.loads(dumps('Test', Scheme()))
            data[key] = value
            with self.assertRaises(ValueError):
                loads(json.dumps(data))


if __name__ == '__main__':
    unittest.main()
