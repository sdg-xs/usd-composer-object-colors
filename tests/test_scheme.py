import unittest

from object_colors.scheme import ObjectRecord, Scheme, group_objects
from object_colors.presets import dumps, loads


class GroupingTests(unittest.TestCase):
    def test_equal_values_group_objects_and_missing_is_not_a_literal_label(self):
        records = [
            ObjectRecord('/A', {'bim:Level': '1'}),
            ObjectRecord('/B', {'bim:Level': '1'}),
            ObjectRecord('/C', {'bim:Level': 'Unassigned'}),
            ObjectRecord('/D', {}),
            ObjectRecord('/E', {'bim:Level': 1}),
        ]
        groups = group_objects(records, Scheme(property_key='bim:Level'))
        self.assertEqual(sorted(len(g.objects) for g in groups), [1, 1, 1, 2])
        self.assertEqual(next(g for g in groups if g.key == 'missing').objects, ('/D',))
        self.assertEqual(next(g for g in groups if g.key == 'str:"1"').objects, ('/A', '/B'))

    def test_assignments_survive_refresh_overflow_and_template_round_trip(self):
        scheme = Scheme(property_key='bim:Level', enabled=True)
        records = [ObjectRecord('/O' + str(i), {'bim:Level': f'L{i:03}'}) for i in range(105)]
        groups = group_objects(records, scheme)
        self.assertEqual(len(groups), 101)
        self.assertEqual(groups[-1].label, 'Unmapped')
        self.assertEqual(len(groups[-1].objects), 5)
        scheme.set_color('str:"L000"', None)
        name, restored = loads(dumps('Levels', scheme))
        self.assertEqual(name, 'Levels')
        self.assertTrue(restored.enabled)
        self.assertIsNone(group_objects(list(reversed(records)), restored)[0].color)
        self.assertEqual(restored.color('str:"L099"'), scheme.color('str:"L099"'))
        restored.set_color('str:"L099"', '#4E79A7')
        self.assertNotEqual(restored.palettes, scheme.palettes)


if __name__ == '__main__':
    unittest.main()
