import json
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.schemas import BranchExport


def test_real_export_is_versioned_complete_and_truth_safe(tmp_path):
    with TestClient(create_app(tmp_path/'exports.sqlite')) as c:
        w=c.post('/v1/worlds',json={'backend':'cloth'}).json()
        e=c.post(f"/v1/worlds/{w['id']}/experiments",json={"search_candidates":50,"physics_budget":3}).json()
        c.app.state.runtime.wait(e['id'])
        b=c.get(f"/v1/experiments/{e['id']}/branches").json()[1]
        response=c.get(f"/v1/experiments/{e['id']}/branches/{b['id']}/export")
        assert response.status_code==200
        result=BranchExport.model_validate_json(response.text).model_dump()
        assert result['recorded_frames']==b['trace']
        assert result['initial_state']==b['initial_state']
        assert result['evaluation']==b['evaluation']
        assert result['action']==b['action']
        assert result['seed']==7 and len(result['configuration_sha256'])==64
        assert result['timestamps']['branch_completed_unix_s']>=result['timestamps']['submitted_unix_s']
        assert 'hidden_mass' not in response.text
        assert 'attachment;' in response.headers['content-disposition']
        e2=c.post(f"/v1/worlds/{w['id']}/experiments",json={"search_candidates":50,"physics_budget":3}).json()
        assert c.get(f"/v1/experiments/{e2['id']}/branches/{b['id']}/export").status_code==409
