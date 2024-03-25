from datetime import date, datetime

import requests
from pydantic import BaseModel

from log_time_to_tempo import cfg

from ._logging import log

tempo_rest_url = '/rest/tempo-timesheets/4/worklogs/'


class Issue(BaseModel):
    id: int
    key: str
    summary: str


class Worklog(BaseModel):
    billableSeconds: int
    comment: str
    issue: Issue
    started: datetime
    originTaskId: int
    timeSpent: str
    timeSpentSeconds: int
    dateUpdated: str
    dateCreated: str


def get_worklogs(worker_id: str, from_date: date, to_date: date):
    payload = {
        'worker': [worker_id],
        'from': from_date.isoformat(),
        'to': to_date.isoformat(),
    }
    response = _post('search', json=payload)
    log.debug(response.text)
    return [Worklog(**item) for item in response.json()]


def create_worklog(
    worker_id: str,
    task_id: str,
    started: str,
    time_spent_seconds: int | float,
    message: str = None,
):
    payload = {
        'worker': worker_id,
        'originTaskId': task_id,
        'started': started,
        'timeSpentSeconds': time_spent_seconds,
    }
    if message is not None:
        payload['comment'] = message
    log.info(payload)

    response = _post(json=payload)
    log.debug(response.text)


def _post(endpoint: str = '', **kwargs):
    default_headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg.token}',
    }
    headers = {
        **default_headers,
        **kwargs.pop('headers', {}),
    }
    log.debug(f'> POST {cfg.instance}{tempo_rest_url}{endpoint} {kwargs}')
    response = requests.post(
        f'{cfg.instance}{tempo_rest_url}{endpoint}',
        headers=headers,
        **kwargs,
    )
    log.debug('< %s', response.text)
    return response
