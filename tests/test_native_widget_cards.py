import asyncio
import json
import unittest
from unittest.mock import patch
from skills.domains.widgets import WidgetsDomain
from ui.jarvis_widgets import backend
from ui.jarvis_widgets.view_schema import describe, validate_view


class NativeCardTests(unittest.TestCase):
    def test_all_native_examples_use_existing_renderer(self):
        for kind, data in describe()['native_cards'].items():
            with self.subTest(kind=kind):
                widget = backend.make_widget(kind, 'Example', data, widget_id='existing')
                self.assertEqual(widget['id'], 'existing')
                self.assertEqual(widget['kind'], 'view')
                validate_view(widget['data'])

    def test_existing_agent_tool_delivers_native_form(self):
        async def inline(function, *args):
            return function(*args)
        with patch('skills.domains.widgets.asyncio.to_thread', side_effect=inline), \
                patch.object(backend, 'shell_call', return_value={'ok': True}) as call:
            result = asyncio.run(WidgetsDomain()._adapter_show_widget(
                'form', 'Research', json.dumps(describe()['native_cards']['form']), widget_id='research'))
        self.assertTrue(result['ok'])
        method, widget = call.call_args.args
        self.assertEqual(method, 'present')
        self.assertEqual(widget['kind'], 'view')
        self.assertEqual(widget['id'], 'research')

    def test_invalid_cards_fail_before_delivery(self):
        cases = [('metric', {'value': float('nan')}), ('list', {'items': [{'label': 'X', 'done': 'yes'}]}),
                 ('actions', {'buttons': [{'id': 'a', 'label': 'A'}, {'id': 'a', 'label': 'B'}]}),
                 ('form', {'fields': [{'id': '__proto__', 'label': 'X'}]}),
                 ('form', {'fields': [{'id': 'x', 'label': 'X', 'required': 'true'}]}),
                 ('chart', {'mode': 'line', 'points': [{'label': 'X', 'value': float('inf')}]}),
                 ('chart', {'mode': 'pie', 'labels': ['x'], 'values': [2]})]
        for kind, data in cases:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                backend.make_widget(kind, 'Bad', data)

    def test_legacy_bar_chart_and_single_point_line(self):
        widget = backend.make_widget('chart', 'Old', {'labels': ['A'], 'values': [4]})
        self.assertEqual(widget['kind'], 'chart')
        line = backend.make_widget('chart', 'New', {'mode': 'line', 'points': [{'label': 'A', 'value': -4}]})
        shapes = line['data']['layout']['children'][0]['shapes']
        self.assertTrue(any(shape['type'] == 'circle' for shape in shapes))

    def test_checklist_bindings_follow_identity_when_rows_reorder(self):
        a = {"id": "a", "label": "First", "done": False}
        b = {"id": "b", "label": "Second", "done": False}
        first = backend.make_widget("list", "Tasks", {"items": [a, b]})
        second = backend.make_widget("list", "Tasks", {"items": [b, a]})
        self.assertEqual(first["data"]["layout"]["children"][0]["bind"], second["data"]["layout"]["children"][1]["bind"])
        with self.assertRaises(ValueError):
            backend.make_widget("list", "Tasks", {"items": [a, a]})

    def test_form_retains_required_and_placeholder(self):
        widget = backend.make_widget('form', 'Form', describe()['native_cards']['form'])
        field = widget['data']['layout']['children'][0]
        self.assertTrue(field['required'])
        self.assertEqual(field['placeholder'], 'Research topic')
