import collections
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from zmon_slr.plot import plot

SLO = collections.namedtuple('SLO', 'from_ to sli_values')


@pytest.fixture(params=[
    pytest.param(SLO(100, 100, [100 for _ in range(50)]), id='SLI values constant and equal to SLO target'),
])
def client_mock(request):
    mock = MagicMock()
    mock.slo_list = MagicMock(return_value=[{}])
    mock.target_list = MagicMock(return_value=[{'sli_name': 'sample-sli-1', 'from': request.param.from_, 'to': request.param.to}])
    mock.sli_list = MagicMock(return_value=[{'unit': '%'}])
    mock.sli_values = MagicMock(return_value=[
        {'value': value, 'timestamp': datetime.fromtimestamp(i).isoformat()}
        for i, value in enumerate(request.param.sli_values)
    ])

    return mock


def test_graph_is_not_corrupted(client_mock, tmpdir):
    graph_file = tmpdir / 'graph.png'
    plot(client_mock, {}, 0, str(graph_file))

    assert graph_file.size() > 0, 'Graph file size was zero'
