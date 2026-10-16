"""Policies propose bounded tool arguments; measured results remain authoritative."""
import os
import httpx
from .schemas import ExperimentRequest, HostedProposal


class DeterministicPolicy:
    name = 'deterministic_planning_policy'

    def propose(self, observation, action_schema, request):
        return request, {'policy': self.name, 'llm_used': False, 'steps': ['Inspect structured observation and valid action schema.', 'Generate candidate interventions through backend tools.', 'Fork the same persisted state for each candidate.', 'Rank measured outcomes; retain failures.']}

    def next_experiment(self, backend, observation, branches, settings):
        """One bounded planning retry, triggered by measured unsuccessful outcomes."""
        if backend != 'mujoco' or observation.get('contacts') or any(b['evaluation']['success'] for b in branches):
            return None
        retryable = any(b['evaluation']['status'] == 'planning_failure' and b['action']['ik']['converged'] for b in branches)
        if not retryable or settings['planner_iterations'] >= 4000:
            return None
        return settings | {'candidates': max(3, settings['candidates']), 'planner_iterations': min(4000, settings['planner_iterations']*2)}


class HostedPolicy:
    name = 'optional_hosted_proposal_policy'

    def propose(self, observation, action_schema, request):
        key, model = os.getenv('OPENAI_API_KEY'), os.getenv('OPENAI_MODEL')
        if not key or not model:
            raise ValueError('llm policy requires OPENAI_API_KEY and OPENAI_MODEL')
        # Allow only resource-bounded experiment settings, never simulation output.
        import json
        proposal_schema = {'type': 'object', 'properties': {'candidates': {'type': 'integer', 'minimum': 2, 'maximum': 5}, 'planner_iterations': {'type': 'integer', 'minimum': 100, 'maximum': 4000}}, 'required': ['candidates', 'planner_iterations'], 'additionalProperties': False}
        payload = {'model': model, 'input': [{'role': 'system', 'content': 'Propose bounded experiment settings using supplied observations and valid actions. You cannot supply or modify simulator outcomes.'}, {'role': 'user', 'content': json.dumps({'observation': observation, 'valid_actions': action_schema})}], 'text': {'format': {'type': 'json_schema', 'name': 'experiment_settings', 'strict': True, 'schema': proposal_schema}}}
        with httpx.Client(timeout=45) as client:
            response = client.post('https://api.openai.com/v1/responses', headers={'Authorization': f'Bearer {key}'}, json=payload)
        if response.status_code != 200:
            raise ValueError(f'hosted proposal failed with HTTP {response.status_code}')
        texts = [c['text'] for o in response.json().get('output', []) for c in o.get('content', []) if c.get('type') == 'output_text']
        proposal = HostedProposal.model_validate_json(''.join(texts)).model_dump()
        updated = ExperimentRequest.model_validate(request | proposal).model_dump()
        return updated, {'policy': self.name, 'llm_used': True, 'model': model, 'scope': 'Proposed bounded experiment settings only; all outcomes measured by adapters.'}
