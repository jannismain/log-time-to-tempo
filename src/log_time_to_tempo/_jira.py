"""Wrapper around [JIRA Python API](https://jira.readthedocs.io/)."""

from jira import JIRA

from . import caching as c
from ._time import modified_within


@c.cache('issues-$project')
def get_issues(client: JIRA, *, project='TSI', **kwargs):
    return {
        i.key: i.fields.summary
        for i in sorted(
            client.search_issues(f'project={project}', fields='summary'),
            key=lambda i: int(i.key.split('-')[1]),
        )
    }


@c.cache('issues')
def get_all_issues(client: JIRA, **kwargs):
    rv = {}
    for project in get_projects(client, **kwargs):
        rv.update(get_issues(client, project=project, **kwargs))
    return rv


@c.cache('projects')
def get_projects(client: JIRA, **kwargs):
    return {p.key: p.name for p in sorted(client.projects(), key=lambda p: p.key)}


@c.cache('myself')
def myself(client: JIRA, **kwargs):
    return client.myself()


def cache_is_warm():
    issue_list = c.cache_dir / 'issues'
    return (
        c.cache_dir.is_dir()
        and issue_list in c.cache_dir.iterdir()
        and modified_within(issue_list, weeks=1)
    )
