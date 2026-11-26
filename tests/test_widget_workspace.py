import unittest
from ui.jarvis_widgets import backend
from ui.jarvis_widgets.view_schema import validate_view


class WorkspaceTests(unittest.TestCase):
    def test_workspace_compiles_distinct_actionable_panels(self):
        widget = backend.make_widget('workspace', 'Project', {
            'revision': 2, 'brief': 'A brief', 'files': [{'path': '/tmp/notes.md', 'detail': 'Notes'}],
            'ideas': ['One direction'], 'plan': ['First step'],
            'tasks': [{'id': 'first', 'label': 'Check result', 'done': False}]}, widget_id='project')
        self.assertEqual(widget['kind'], 'workspace')
        panels = widget['data']['panels']
        self.assertEqual([p['section'] for p in panels], ['brief', 'files', 'ideas', 'plan', 'tasks'])
        for panel in panels:
            validate_view(panel['view'])
        row = panels[1]['view']['layout']['children'][1]['children'][0]
        self.assertEqual(row['type'], 'entry')
        self.assertIn('/tmp/notes.md', row['prompt'])

    def test_rejects_invalid_snapshots(self):
        for data in ({'revision': -1, 'brief': 'x'}, {'revision': True, 'brief': 'x'},
                     {'reopen': 'yes', 'brief': 'x'}, {'files': ['a', 'a']}, {},
                     {'tasks': [{'id': str(i), 'label': str(i)} for i in range(31)]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                backend.make_widget('workspace', 'Bad', data)

    def test_stable_row_identity_survives_reordering(self):
        def rows(values):
            w = backend.make_widget('workspace', 'Files', {'files': values})
            return w['data']['panels'][0]['view']['layout']['children'][1]['children']
        first, second = rows(['a', 'b']), rows(['b', 'a'])
        self.assertEqual(first[0]['id'], second[1]['id'])
