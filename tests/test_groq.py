import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import BaseModel
import config
from research_chunks import page_chunks, unique_items, select_chunks


class Answer(BaseModel):
    ready: bool


class NestedAnswer(BaseModel):
    answer: Answer


def response(status=200, content='{"ready": true}', finish='stop', error='', headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = ({'error': {'message': error}} if status >= 400 else {
        'choices': [{'finish_reason': finish, 'message': {'content': content}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
    })
    return result


real_reserve_capacity = config.reserve_capacity


class GroqTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        patches = [patch.object(config, 'CACHE_DIR', Path(self.temporary.name)),
                   patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}),
                   patch.object(config, 'reserve_capacity'),
                   patch.object(config.time, 'sleep')]
        self.mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

    def test_posts_groq_strict_schema_and_validates_response(self):
        with patch.object(config.requests, 'post', return_value=response()) as post:
            self.assertEqual(config.cache_and_retry('test-model', 'Return ready true', Answer), {'ready': True})
            kwargs = post.call_args.kwargs
            self.assertEqual(post.call_args.args[0], config.GROQ_URL)
            self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-key')
            self.assertTrue(kwargs['json']['response_format']['json_schema']['strict'])
            self.assertEqual(kwargs['json']['model'], 'test-model')

    def test_cache_hit_needs_no_key_or_network(self):
        with patch.object(config.requests, 'post', return_value=response()) as post:
            config.cache_and_retry('test-model', 'ready', Answer)
            with patch.dict('os.environ', {'GROQ_API_KEY': ''}):
                self.assertEqual(config.cache_and_retry('test-model', 'ready', Answer), {'ready': True})
            self.assertEqual(post.call_count, 1)

    def test_model_change_has_separate_cache(self):
        with patch.object(config.requests, 'post', return_value=response()) as post:
            for model in ('first', 'second'):
                config.cache_and_retry(model, 'ready', Answer)
            self.assertEqual(post.call_count, 2)

    def test_missing_key_does_not_call_api(self):
        with patch.dict('os.environ', {'GROQ_API_KEY': ''}), patch.object(config.requests, 'post') as post:
            with self.assertRaisesRegex(ValueError, 'GROQ_API_KEY'):
                config.cache_and_retry('test', 'ready', Answer)
            post.assert_not_called()

    def test_daily_quota_does_not_retry(self):
        with patch.object(config.requests, 'post', return_value=response(429, error='Tokens per day (TPD) limit exceeded')) as post:
            with self.assertRaises(config.ModelAPIError):
                config.cache_and_retry('test', 'ready', Answer)
            self.assertEqual(post.call_count, 1)

    def test_transient_rate_limit_honors_retry_after(self):
        with patch.object(config.requests, 'post', side_effect=[response(429, error='Tokens per minute exceeded', headers={'retry-after': '3'}), response()]):
            config.cache_and_retry('test', 'ready', Answer)
            config.time.sleep.assert_called_once_with(3.0)

    def test_invalid_json_is_not_cached(self):
        with patch.object(config.requests, 'post', return_value=response(content='broken')):
            with self.assertRaises(ValueError):
                config.cache_and_retry('test', 'ready', Answer)
        self.assertEqual(list(Path(self.temporary.name).glob('*.json')), [])

    def test_wrong_json_type_is_rejected(self):
        with patch.object(config.requests, 'post', return_value=response(content='{"ready": "true"}')):
            with self.assertRaises(ValueError):
                config.cache_and_retry('test', 'ready', Answer)

    def test_pipeline_uses_groq_key_to_enable_model_stages(self):
        import run_pull
        completed = Mock(returncode=0, stdout='', stderr='')
        with patch.object(run_pull.subprocess, 'run', return_value=completed) as run, patch.object(run_pull, 'publish_evidence') as fallback, patch.object(run_pull, 'set_progress'), patch('research_brief.publish_brief'):
            run_pull.run_pipeline('TEST')
            scripts = [call.args[0][1] for call in run.call_args_list]
            self.assertEqual(scripts, ['ingest_ticker.py', 'label_docs.py', 'snapshot.py', 'guidance_extract.py', 'promised_vs_delivered.py', 'ground.py'])
            fallback.assert_not_called()

    def test_pipeline_without_groq_key_uses_evidence(self):
        import run_pull
        with patch.dict('os.environ', {'GROQ_API_KEY': ''}), patch.object(run_pull.subprocess, 'run') as run, patch.object(run_pull, 'publish_evidence') as fallback, patch.object(run_pull, 'set_progress'):
            run_pull.run_pipeline('TEST')
            self.assertEqual(run.call_count, 1)
            fallback.assert_called_once_with('TEST')

    def test_truncated_response_is_not_cached(self):
        with patch.object(config.requests, 'post', return_value=response(finish='length')):
            with self.assertRaises(config.ModelAPIError):
                config.cache_and_retry('test', 'ready', Answer)
        self.assertEqual(list(Path(self.temporary.name).glob('*.json')), [])

    def test_oversized_input_rejected_before_network(self):
        with patch.object(config.requests, 'post') as post:
            with self.assertRaisesRegex(ValueError, 'token budget'):
                config.cache_and_retry('test', 'x' * 30000, Answer)
            post.assert_not_called()

    def test_nested_schema_forbids_extra_properties(self):
        schema = config.strict_schema(NestedAnswer)
        self.assertFalse(schema['additionalProperties'])
        self.assertFalse(schema['$defs']['Answer']['additionalProperties'])
        self.assertEqual(schema['$defs']['Answer']['required'], ['ready'])

    def test_chunking_preserves_page_markers_and_late_evidence(self):
        pages = [{'page': 7, 'text': 'word ' * 1500 + 'revenue growth was 5%.'},
                 {'page': 12, 'text': 'The cash flow guidance is 100 crore.'}]
        chunks = page_chunks(pages, max_chars=1000)
        self.assertTrue(all(len(chunk) <= 1000 for chunk in chunks))
        self.assertTrue(any('PAGE 7' in chunk and 'revenue growth was 5%.' in chunk for chunk in chunks))
        self.assertTrue(any('PAGE 12' in chunk for chunk in chunks))

    def test_overlapping_extractions_deduplicate(self):
        item = {'metric': 'Revenue', 'page': 1, 'quote': 'Revenue grew 5%.'}
        self.assertEqual(unique_items([item, item]), [item])

    def test_chunk_selection_finds_late_guidance(self):
        chunks = ['Historical revenue was 100.' for _ in range(10)]
        chunks[8] = 'Our full-year guidance is 20% to 22%.'
        chosen = select_chunks(chunks)
        self.assertEqual(len(chosen), 6)
        self.assertIn(chunks[8], chosen)

    def test_rate_budget_is_persisted_between_calls(self):
        with patch.object(config.time, 'time', return_value=1000):
            real_reserve_capacity('test', 2000)
            real_reserve_capacity('test', 2500)
        state = json.loads((Path(self.temporary.name) / 'groq-rate.json').read_text())
        self.assertEqual(sum(entry[1] for entry in state['test']), 4500)

    def test_rate_budget_waits_until_previous_window_expires(self):
        now = [1000.0]
        with patch.object(config.time, 'time', side_effect=lambda: now[0]), patch.object(config.time, 'sleep', side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)) as sleep:
            real_reserve_capacity('test', 5000)
            real_reserve_capacity('test', 3000)
            self.assertEqual(sleep.call_count, 1)
        state = json.loads((Path(self.temporary.name) / 'groq-rate.json').read_text())
        self.assertEqual(len(state['test']), 1)
        self.assertEqual(state['test'][0][1], 3000)

if __name__ == '__main__':
    unittest.main()
