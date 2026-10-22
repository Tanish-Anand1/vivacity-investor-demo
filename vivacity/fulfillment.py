"""Order ledger around the existing physical sorting cell.

Only SORT has a validated controller. Later stages remain blocked until a
shared-world humanoid collection/packing/sealing/labeling controller exists.
Every sorted-item claim is reconstructed from persisted MuJoCo run events.
"""
from copy import deepcopy
import json
import time
import uuid

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .factory import FactorySettings
from .runtime import Conflict
from .storage import encode
from .workspace import owner


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    order_label: str = Field(min_length=1, max_length=80)
    item_ids: list[str] = Field(min_length=1, max_length=3)
    settings: FactorySettings

    @model_validator(mode='after')
    def valid_items(self):
        if len(self.item_ids) != self.settings.carton_count:
            raise ValueError('item count must match the physical carton count')
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError('item IDs must be unique')
        if any(not value or len(value) > 60 or not all(c.isalnum() or c in '-_' for c in value)
               for value in self.item_ids):
            raise ValueError('item IDs must be 1..60 letters, digits, hyphens or underscores')
        return self


class OrderItem(BaseModel):
    item_id: str
    carton_id: str
    status: str
    lane: str | None
    mass_kg: float | None
    verified_simulation_time_s: float | None


class TaskState(BaseModel):
    stage: str
    status: str
    reason: str | None


class FulfillmentOrderResponse(BaseModel):
    schema_version: str
    id: str
    order_label: str
    created_unix_s: float
    cell_id: str
    run_id: str | None
    attempts: list[str]
    settings: FactorySettings
    initial_state_hash: str
    status: str
    items: list[OrderItem]
    tasks: list[TaskState]
    sorted_count: int
    metrics: dict[str, JsonValue]
    events: list[dict[str, JsonValue]]
    scope: str


class FulfillmentService:
    stages = ('sort','collect','pack','seal','label','dispatch')

    def __init__(self, factory):
        self.factory = factory
        self.store = factory.workspace.store
        with self.store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS fulfillment_orders(
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS fulfillment_order_owner ON fulfillment_orders(owner)')

    def _record(self, identifier, token):
        with self.store.connect() as db:
            row = db.execute('SELECT payload FROM fulfillment_orders WHERE id=? AND owner=?',
                             (identifier, owner(token))).fetchone()
        if row is None:
            raise KeyError(identifier)
        return json.loads(row[0])

    def _save(self, record, token):
        with self.store.connect() as db:
            db.execute('INSERT INTO fulfillment_orders(id,owner,payload) VALUES(?,?,?) '
                       'ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                       (record['id'], owner(token), encode(record)))

    def create(self, request, token):
        cell = self.factory.create(request.settings.model_dump(), token)
        record = {'schema_version':'vivacity.fulfillment-order/1.0',
                  'id':str(uuid.uuid4()),'order_label':request.order_label,
                  'created_unix_s':time.time(),'item_ids':request.item_ids,
                  'cell_id':cell['id'],'settings':cell['config'],
                  'initial_state_hash':cell['initial_state']['model_hash'],
                  'run_id':None,'attempts':[]}
        self._save(record, token)
        return self._view(record, token)

    def start(self, identifier, token):
        record = self._record(identifier, token)
        if record['run_id'] is not None:
            previous = self.factory.get(record['run_id'], token)
            if previous['status'] in ('queued','running','paused'):
                raise Conflict('this order already has an active physical sorting run')
        run = self.factory.start(record['cell_id'], token, mode='production',
                                 creator_label=record['order_label'])
        record['run_id'] = run['id']
        record['attempts'].append(run['id'])
        self._save(record, token)
        return self._view(record, token)

    def get(self, identifier, token):
        return self._view(self._record(identifier, token), token)

    def list(self, token):
        with self.store.connect() as db:
            rows = db.execute('SELECT payload FROM fulfillment_orders WHERE owner=? ORDER BY rowid DESC LIMIT 30',
                              (owner(token),)).fetchall()
        return [self._view(json.loads(row[0]), token) for row in rows]

    def _view(self, record, token):
        run = self.factory.get(record['run_id'], token) if record['run_id'] else None
        events = run['events'] if run else []
        arrivals = {event['carton_id']:event for event in events if event['kind']=='destination_arrival'}
        routes = {event['carton_id']:event for event in events if event['kind']=='route_selected'}
        items = []
        for index, item_id in enumerate(record['item_ids']):
            carton_id = 'target' if index == 0 else f'carton_{index}'
            arrival = arrivals.get(carton_id)
            route = routes.get(carton_id)
            items.append({'item_id':item_id,'carton_id':carton_id,
                          'status':'sorted' if arrival else 'pending',
                          'lane':arrival['lane'] if arrival else None,
                          'mass_kg':route['mass_kg'] if route else None,
                          'verified_simulation_time_s':arrival['time_s'] if arrival else None})
        count = len(arrivals)
        run_status = run['status'] if run else None
        sorted_ok = bool(run_status == 'completed' and count == len(items)
                         and run['metrics'].get('cartons_sorted') == len(items))
        sort_status = ('completed' if sorted_ok else
                       'failed' if run_status == 'completed' else
                       'failed' if run_status in ('failed','interrupted') else
                       'blocked' if run_status in ('stopped','emergency_stopped') else
                       'assigned' if run_status == 'queued' else
                       'executing' if run_status in ('running','paused') else 'ready')
        tasks = []
        for index, stage in enumerate(self.stages):
            if index == 0:
                status = sort_status
                reason = (run.get('error') or 'Physical run ended without all destination contacts verified') if run and sort_status in ('failed','blocked') else None
            elif index == 1:
                status = 'blocked' if sorted_ok else 'pending'
                reason = ('No validated humanoid carry-and-deliver controller shares this factory state.'
                          if sorted_ok else 'Requires every item to reach its physical destination bin.')
            else:
                status = 'blocked' if sorted_ok else 'pending'
                reason = f'Requires a verified {self.stages[index-1]} stage in the same physical world.'
            tasks.append({'stage':stage,'status':status,'reason':reason})
        return {'schema_version':'vivacity.fulfillment-order/1.0',
                'id':record['id'],'order_label':record['order_label'],
                'created_unix_s':record['created_unix_s'],
                'cell_id':record['cell_id'],'run_id':record['run_id'],
                'attempts':deepcopy(record['attempts']),
                'settings':deepcopy(record['settings']),
                'initial_state_hash':record['initial_state_hash'],
                'status':'sort_completed' if sorted_ok else
                         'failed' if sort_status in ('failed','blocked') else
                         'sorting' if run else 'ready',
                'items':items,'tasks':tasks,'sorted_count':count,
                'metrics':deepcopy(run['metrics']) if run else {},
                'events':deepcopy(events),
                'scope':'Only physically verified sorting can complete. Collect, pack, seal, label and dispatch are blocked; no humanoid controller is claimed.'}
