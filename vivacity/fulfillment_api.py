"""Capability-owned order intake and measured sorting handoff."""
from fastapi import APIRouter, Request
from .fulfillment import OrderRequest, FulfillmentOrderResponse
from .workspace_api import Token

router = APIRouter(prefix='/v1/fulfillment', tags=['Fulfillment (sorting stage)'])

@router.post('/orders', status_code=201, response_model=FulfillmentOrderResponse)
def create_order(body:OrderRequest, request:Request, x_workspace_token:Token):
    return request.app.state.fulfillment.create(body, x_workspace_token)

@router.get('/orders', response_model=list[FulfillmentOrderResponse])
def orders(request:Request, x_workspace_token:Token):
    return request.app.state.fulfillment.list(x_workspace_token)

@router.get('/orders/{identifier}', response_model=FulfillmentOrderResponse)
def order(identifier:str, request:Request, x_workspace_token:Token):
    return request.app.state.fulfillment.get(identifier, x_workspace_token)

@router.post('/orders/{identifier}/start', status_code=202, response_model=FulfillmentOrderResponse)
def start_order(identifier:str, request:Request, x_workspace_token:Token):
    return request.app.state.fulfillment.start(identifier, x_workspace_token)
