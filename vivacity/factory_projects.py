"""Capability-owned project notebooks with append-only configuration versions."""
import json
import time
import uuid
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .workspace import owner
from .runtime import Conflict

class ProjectRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=80)
    team_label:str=Field(min_length=1,max_length=80)
    creator_label:str=Field(min_length=1,max_length=80)

class VersionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=1)
    cell_id:str=Field(min_length=1,max_length=80)
    creator_label:str=Field(min_length=1,max_length=80)
    note:str=Field('',max_length=300)

class AttachmentRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=1)
    kind:Literal['run','benchmark']
    record_id:str=Field(min_length=1,max_length=80)
    added_by_label:str=Field(min_length=1,max_length=80)

class FactoryProjects:
    def __init__(self,factory):self.factory=factory;self.workspace=factory.workspace
    def create(self,body,token):
        row={'id':str(uuid.uuid4()),'schema_version':'vivacity.factory-project/1.0',**body,
             'created_at':time.time(),'revision':1,'versions':[],'attachments':[],
             'identity_scope':'Creator and team labels are self-reported. Access uses this browser workspace capability; no authenticated team membership is claimed.'}
        self.workspace._put('factory_project',owner(token),row);return row
    def get(self,identifier,token):return self.workspace._get(identifier,token,'factory_project')
    def list(self,token):return self.workspace.list(token,'factory_project')
    def append(self,identifier,token,expected_revision,collection,item):
        with self.workspace.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            found=db.execute("SELECT payload FROM library_items WHERE id=? AND owner=? AND kind='factory_project'",(identifier,owner(token))).fetchone()
            if not found:raise KeyError(identifier)
            row=json.loads(found[0])
            if row['revision']!=expected_revision:raise Conflict('This project changed. Refresh it before adding another version; existing versions are unchanged.')
            if len(row[collection])>=50:raise ValueError('Project limit is 50 versions and 50 result attachments. Create another project.')
            if collection=='attachments' and any(x['record_id']==item['record_id'] and x['kind']==item['kind'] for x in row[collection]):
                raise Conflict('This result is already attached to the project.')
            item['number']=len(row[collection])+1;row[collection].append(item);row['revision']+=1
            self.workspace._put('factory_project',owner(token),row,db)
        return row
    def version(self,identifier,body,token):
        self.get(identifier,token)
        definition=self.factory.export_configuration(body['cell_id'],token)
        return self.append(identifier,token,body['expected_revision'],'versions',
                           {'created_at':time.time(),'creator_label':body['creator_label'],'note':body['note'],'definition':definition})
    def attach(self,identifier,body,token):
        self.get(identifier,token)
        record=self.factory.get(body['record_id'],token) if body['kind']=='run' else self.factory.benchmark(body['record_id'],token)
        if record['status'] in ('queued','running','paused'):raise Conflict('Finish or stop the experiment before attaching its result.')
        summary={'status':record['status'],'name':record.get('name',record.get('config',{}).get('name')),
                 'metrics':record.get('metrics'),'comparison':record.get('comparison'),
                 'created_at':record['created_at'],'creator_label':record.get('creator_label')}
        return self.append(identifier,token,body['expected_revision'],'attachments',
                           {'record_id':record['id'],'kind':body['kind'],'added_at':time.time(),'added_by_label':body['added_by_label'],'summary':summary})
