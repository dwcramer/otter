"""
Twisted Application plugin for otter API nodes.
"""
import jsonfig
import warnings

from twisted.python import usage

from twisted.internet import reactor, task
from twisted.internet.endpoints import clientFromString

from twisted.application.strports import service
from twisted.application.service import MultiService

from twisted.web.server import Site
from twisted.python import log

try:
    from txairbrake.observers import AirbrakeLogObserver as _a
    AirbrakeLogObserver = _a   # to get around pyflakes
except ImportError:
    AirbrakeLogObserver = None

try:
    from otter.log.graylog import GraylogUDPPublisher as _g
    GraylogUDPPublisher = _g   # to get around pyflakes
except ImportError:
    GraylogUDPPublisher = None

from otter.rest.application import root, set_store
from otter.util.config import set_config_data, config_value
from otter.log.setup import make_observer_chain
from otter.models.cass import CassScalingGroupCollection
from silverberg.cluster import RoundRobinCassandraCluster

from otter.scheduler import check_for_events


class Options(usage.Options):
    """
    Options for the otter-api node.

    TODO: Force some common parameters in a base class.
    TODO: Tracing support.
    TODO: Debugging.
    TODO: Environments.
    TODO: Admin HTTP interface.
    TODO: Specify store
    """

    optParameters = [
        ["port", "p", "tcp:9000",
         "strports description of the port for API connections."],
        ["config", "c", "config.json",
         "path to JSON configuration file."]
    ]

    optFlags = [
        ["mock", "m", "whether to use a mock back end instead of cassandra"]
    ]

    def postOptions(self):
        """
        Merge our commandline arguments with our config file.
        """
        # Inject some default values into the config.  Right now this is
        # only used to support distinguishing between staging and production.
        self.update({
            'regionOverrides': {},
            'cloudServersOpenStack': 'cloudServersOpenStack',
            'cloudLoadBalancers': 'cloudLoadBalancers'
        })

        self.update(jsonfig.from_path(self['config']))

        # The staging service catalog has some unfortunate differences
        # from the production one, so these are here to hint at the
        # correct ocnfiguration for staging.
        if self.get('environment') == 'staging':
            self['cloudServersOpenStack'] = 'cloudServersPreprod'
            self['regionOverrides']['cloudLoadBalancers'] = 'STAGING'


def run_scheduler(batchsize):
    """
    Working guts of the scheduler service
    """
    def eat_errors(err):
        # Eat transient errors
        log.err(err)
        return None
    d = check_for_events(log, batchsize)
    d.addErrback(eat_errors)
    return d


def makeService(config):
    """
    Set up the otter-api service.
    """
    set_config_data(dict(config))

    # Try to configure graylog and airbrake.

    if config_value('graylog'):
        if GraylogUDPPublisher is not None:
            log.addObserver(
                make_observer_chain(
                    GraylogUDPPublisher(**config_value('graylog'))))
        else:
            warnings.warn("There is a configuration option for Graylog, but "
                          "txgraylog is not installed.")

    if config_value('airbrake'):
        if AirbrakeLogObserver is not None:
            airbrake = AirbrakeLogObserver(
                config_value('airbrake.api_key'),
                config_value('environment'),
                use_ssl=True
            )

            airbrake.start()
        else:
            warnings.warn("There is a configuration option for Airbrake, but "
                          "txairbrake is not installed.")

    if not config_value('mock'):
        seed_endpoints = [
            clientFromString(reactor, str(host))
            for host in config_value('cassandra.seed_hosts')]

        cassandra_cluster = RoundRobinCassandraCluster(
            seed_endpoints,
            config_value('cassandra.keyspace'))

        set_store(CassScalingGroupCollection(cassandra_cluster))

    if config_value('otterclock'):
        scheduler_task = task.LoopingCall(run_scheduler, int(config_value('otterclock.batchsize')))
        scheduler_task.start(int(config_value('otterclock.interval')))

    s = MultiService()

    site = Site(root)
    site.displayTracebacks = False

    api_service = service(str(config_value('port')), site)
    api_service.setServiceParent(s)

    return s
