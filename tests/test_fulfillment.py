"""Order stages are derived from real saved MuJoCo sorting runs."""
import time

from fastapi.testclient import TestClient

from vivacity.api import create_app

OWNER = {'X-Workspace-Token':'fulfillment-owner-capability-123456789'}
OTHER = {'X-Workspace-Token':'fulfillment-other-capability-123456789'}


def _request(**settings):
    return {'order_label':'Physical trial order','item_ids':['item_1'],
            'settings':{'carton_count':1,'carton_start_y_m':-.4,'realtime_speed':8,
                        **settings}}


def _finish(client, identifier, deadline_s=120):
    deadline=time.monotonic()+deadline_s
    while time.monotonic()<deadline:
        order=client.get(f'/v1/fulfillment/orders/{identifier}',headers=OWNER).json()
        if order['status'] in ('sort_completed','failed'):
            return order
        time.sleep(.08)
    raise AssertionError(f'physical sorting did not finish: {order["tasks"][0]}')


def test_order_sort_is_measured_and_downstream_is_honestly_blocked(tmp_path):
    database=tmp_path/'fulfillment.sqlite3'
    with TestClient(create_app(database)) as client:
        invalid=_request();invalid['item_ids']=['a','b']
        assert client.post('/v1/fulfillment/orders',headers=OWNER,json=invalid).status_code==422
        created=client.post('/v1/fulfillment/orders',headers=OWNER,json=_request())
        assert created.status_code==201
        order=created.json();identifier=order['id']
        assert order['status']=='ready' and order['tasks'][0]['status']=='ready'
        assert order['sorted_count']==0
        assert client.get(f'/v1/fulfillment/orders/{identifier}',headers=OTHER).status_code==404
        assert client.post(f'/v1/fulfillment/orders/{identifier}/start',headers=OTHER).status_code==404
        started=client.post(f'/v1/fulfillment/orders/{identifier}/start',headers=OWNER)
        assert started.status_code==202 and started.json()['run_id']
        assert client.post(f'/v1/fulfillment/orders/{identifier}/start',headers=OWNER).status_code==409
        result=_finish(client,identifier)
        assert result['status']=='sort_completed',result
        assert result['sorted_count']==1 and result['tasks'][0]['status']=='completed'
        assert all(task['status']=='blocked' for task in result['tasks'][1:])
        assert result['items'][0]['status']=='sorted'
        assert result['items'][0]['verified_simulation_time_s']>0
        run=client.get(f'/v1/factory/runs/{result["run_id"]}',headers=OWNER).json()
        arrivals=[event for event in run['events'] if event['kind']=='destination_arrival']
        assert len(arrivals)==1 and arrivals[0]['lane']==result['items'][0]['lane']
        assert run['metrics']['cartons_sorted']==1 and run['metrics']['simulation_steps']>1000
        assert client.get('/v1/fulfillment/orders',headers=OWNER).json()[0]['id']==identifier
    with TestClient(create_app(database)) as client:
        persisted=client.get(f'/v1/fulfillment/orders/{identifier}',headers=OWNER).json()
        assert persisted['status']=='sort_completed' and persisted['items']==result['items']


def test_order_does_not_advance_on_physical_grasp_failure(tmp_path):
    with TestClient(create_app(tmp_path/'failed-order.sqlite3')) as client:
        created=client.post('/v1/fulfillment/orders',headers=OWNER,
                            json=_request(carton_mass_kg=.15,carton_friction=.05,gripper_force_scale=.005)).json()
        assert client.post(f'/v1/fulfillment/orders/{created["id"]}/start',headers=OWNER).status_code==202
        result=_finish(client,created['id'])
        assert result['status']=='failed'
        assert result['sorted_count']==0
        assert result['tasks'][0]['status']=='failed'
        assert all(item['status']=='pending' for item in result['items'])
        assert all(task['status']=='pending' for task in result['tasks'][1:])
