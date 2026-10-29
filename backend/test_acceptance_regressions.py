from tests.fixtures import wire_payload
"""Offline regressions for the two observed live acceptance failures."""
import asyncio
import json
import os
import time
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types

import ai_service as service
import main
from request_control import RequestBudget
from tests.fixtures import SOURCE, payload


@pytest.mark.parametrize('failure', [TimeoutError(), asyncio.TimeoutError(), httpx.ReadTimeout('offline'),
    errors.ServerError(504, {'error': {'status': 'DEADLINE_EXCEEDED'}}),
    errors.ClientError(408, {'error': {'status': 'REQUEST_TIMEOUT'}}),
    errors.ServerError(500, {'error': {'status': 'DEADLINE_EXCEEDED'}})])
def test_real_api_review_timeout_retains_only_admitted_claims(failure):
    requests = []
    clock = [0.0]
    real_client = service.genai.Client
    def respond(request):
        requests.append(json.loads(request.content))
        if len(requests) == 2:
            raise failure
        return httpx.Response(200, json={'candidates': [{'content': {'role': 'model',
            'parts': [{'text': json.dumps(wire_payload(payload()))}]}, 'finishReason': 'STOP'}]})
    def client(**options):
        assert options['http_options'].retry_options.attempts == 1
        if len(requests):
            assert options['http_options'].timeout == 90_000
        return real_client(vertexai=False, api_key='offline', http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1), client_args={'transport': httpx.MockTransport(respond)}))
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'offline', 'GEMINI_MODEL': service.DEFAULT_MODEL}, clear=True), \
         patch.object(service, 'ANALYSIS_ENABLED', True), patch.object(service.genai, 'Client', side_effect=client), \
         patch.object(service, 'REQUEST_BUDGET', RequestBudget(clock=lambda: clock[0])), \
         patch.object(service, 'sleep', side_effect=lambda delay: clock.__setitem__(0, clock[0]+delay)), \
         TestClient(main.app) as api:
        headers = {'X-Session-Token': api.post('/api/session').json()['token']}
        job = api.post('/api/analysis', headers=headers, json={'text': SOURCE, 'reviewed': True,
            'kind': 'text', 'revision': 'review-deadline'}).json()['job_id']
        for _ in range(200):
            data = api.get('/api/jobs/'+job, headers=headers).json()
            if data['status'] in {'succeeded', 'failed'}:
                break
            time.sleep(.01)
        assert data['status'] == 'succeeded', data
        result = data['result']
        assert result['review_mode'] == 'deterministic_only'
        assert result['semantic_review_complete'] is False
        assert result['has_guidance']
        assert all(e['excerpt'] in SOURCE for e in result['evidence'])
        assert any(c['evidence_ids'] for items in result['sections'].values() for c in items)
        assert len(requests) == 2


@pytest.mark.parametrize('setting', ['false', '0', 'off', ' FALSE ', 'no'])
def test_explicit_fallback_opt_out(setting):
    from examples import load_example
    source, checked = load_example()
    with patch.dict(os.environ, {'DETERMINISTIC_REVIEW_FALLBACK': setting}):
        assert service.deterministic_review_fallback(checked, TimeoutError(),source_text=source.source_text) is None


@pytest.mark.parametrize('setting', ['', 'true', '1', 'on'])
def test_fallback_defaults_enabled_unless_explicitly_disabled(setting):
    from examples import load_example
    source, checked = load_example()
    with patch.dict(os.environ, {'DETERMINISTIC_REVIEW_FALLBACK': setting}):
        assert service.deterministic_review_fallback(checked, TimeoutError(),source_text=source.source_text).review_mode == 'deterministic_only'


def test_generation_deadline_does_not_invent_a_degraded_result():
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'offline'}, clear=True), \
         patch.object(service, 'ANALYSIS_ENABLED', True), patch.object(service, 'REQUEST_BUDGET', RequestBudget()), \
         patch.object(service.genai, 'Client') as provider:
        provider.return_value.__enter__.return_value.models.generate_content.side_effect = errors.ServerError(
            504, {'error': {'status': 'DEADLINE_EXCEEDED'}})
        with pytest.raises(service.AnalysisError) as caught:
            service.analyze_instructions(SOURCE)
        assert caught.value.code == 'timeout'
        assert provider.call_count == 1
