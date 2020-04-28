import json
import logging
from collections import defaultdict

import elasticsearch
from elasticsearch_async.transport import AsyncTransport
from elasticsearch_dsl.connections import Connections
from tornado.ioloop import IOLoop

from biothings.utils.web.es import get_es_versions
from biothings.web.api.es.userquery import ESUserQuery
from biothings.web.settings import BiothingWebSettings


class BiothingESWebSettings(BiothingWebSettings):
    '''
    `BiothingWebSettings`_ subclass with functions specific to an elasticsearch backend.

    * Use the known live ES connection if more than one is specified.
    * Cache source metadata stored under the _meta field in es indices.

    '''

    def __init__(self, config=None, **kwargs):
        '''
        The ``config`` init parameter specifies a module that configures
        this biothing.  For more information see `config module`_ documentation.
        '''
        super(BiothingESWebSettings, self).__init__(config, **kwargs)

        # elasticsearch connections
        self._connections = Connections()

        connection_settings = {
            "hosts": self.ES_HOST,
            "timeout": self.ES_CLIENT_TIMEOUT,
            "max_retries": 1,  # maximum number of retries before an exception is propagated
            "timeout_cutoff": 1,  # timeout freezes after this number of consecutive failures
            "sniff_on_connection_fail": True,
            "sniffer_timeout": 60
        }
        self._connections.create_connection(alias='sync', **connection_settings)
        connection_settings.update(transport_class=AsyncTransport)
        self._connections.create_connection(alias='async', **connection_settings)

        # cached index mappings
        self.source_metadata = defaultdict(dict)
        self.source_properties = defaultdict(dict)

        # populate field notes if exist
        try:
            inf = open(self.AVAILABLE_FIELDS_NOTES_PATH, 'r')
            self._fields_notes = json.load(inf)
            inf.close()
        except Exception:
            self._fields_notes = {}

        # user query data
        self.userquery = ESUserQuery(self.USERQUERY_DIR)

        # query pipelines
        self.query_builder = self.load_class(self.ES_QUERY_BUILDER)(self)
        self.query_backend = self.load_class(self.ES_QUERY_BACKEND)(self)
        self.query_transform = self.load_class(self.ES_RESULT_TRANSFORM)(self)

        # initialize payload for standalone tracking batch
        self.tracking_payload = []

        self.ES_INDICES = dict(self.ES_INDICES)  # TODO
        self.ES_INDICES[self.ES_DOC_TYPE] = self.ES_INDEX
        self.BIOTHING_TYPES = list(self.ES_INDICES.keys())

        IOLoop.current().add_callback(self._initialize)

    async def _initialize(self):

        # failures will be logged concisely
        logging.getLogger('elasticsearch.trace').propagate = False

        versions = await get_es_versions(self.async_es_client)
        versions = iter(versions.values())
        self.logger.info("Python Elasticsearch Version: %s", next(versions))
        self.logger.info("Python Elasticsearch DSL Version: %s", next(versions))
        self.logger.info('Elasticsearch Version: %s', next(versions))
        self.logger.info('Elasticsearch Cluster: %s', next(versions))

        # populate source mappings
        for biothing_type in self.ES_INDICES:
            await self.read_index_mappings(biothing_type)

        # resume normal log flow
        logging.getLogger('elasticsearch.trace').propagate = True

    def validate(self):
        '''
        Additional ES settings to validate.
        '''
        super().validate()

        assert isinstance(self.ES_INDEX, str)
        assert isinstance(self.ES_DOC_TYPE, str)
        assert isinstance(self.ES_INDICES, dict)
        assert '*' not in self.ES_DOC_TYPE

    def get_es_client(self):
        '''
        Return the default blocking elasticsearch client.
        The connection is created upon first call.
        '''
        return self._connections.get_connection('sync')

    def get_async_es_client(self):
        '''
        Return the async elasitcsearch client.
        The connection is created upon first call.
        API calls return awaitable objects.
        '''
        return self._connections.get_connection('async')

    async def read_index_mappings(self, biothing_type=None):
        """
        Read ES index mappings for the corresponding biothing_type,
        Populate datasource info and field properties from mappings.
        Return ES raw response. This implementation combines indices.

        The ES response would look like: (for es7+)
        {
            'index_1': {
                'properties': { ... },  ---> source_properties
                '_meta': {
                    "src" : { ... }     ---> source_licenses
                    ...
                },              -----------> source_metadata
                ...
            },
            'index_2': {
                ...     ---------> Combine with results above
            }
        }
        """

        biothing_type = biothing_type or self.ES_DOC_TYPE
        try:
            mappings = await self.async_es_client.indices.get_mapping(
                index=self.ES_INDICES[biothing_type],
                allow_no_indices=True,
                ignore_unavailable=True,
                local=False)
        except elasticsearch.TransportError as exc:
            self.logger.error('Error loading index mapping for [%s].', biothing_type)
            self.logger.debug(exc)
            return None

        metadata = self.source_metadata[biothing_type]
        properties = self.source_properties[biothing_type]
        licenses = self.query_transform.source_licenses[biothing_type]

        metadata.clear()
        properties.clear()
        licenses.clear()

        for index in mappings:

            mapping = mappings[index]['mappings']

            if elasticsearch.__version__[0] < 7:
                # remove doc_type, support 1 type per index
                mapping = next(iter(mapping.values()))

            if '_meta' in mapping:
                for key, val in mapping['_meta'].items():
                    if key in metadata and isinstance(val, dict) \
                            and isinstance(metadata[key], dict):
                        metadata[key].update(val)
                    else:
                        metadata[key] = val
                metadata.update(mapping['_meta'])

                if 'src' in mapping['_meta']:
                    for src, info in mapping['_meta']['src'].items():
                        if 'license_url_short' in info:
                            licenses[src] = info['license_url_short']
                        elif 'license_url' in info:
                            licenses[src] = info['license_url']

            if 'properties' in mapping:
                properties.update(mapping['properties'])

        return mappings

    def get_field_notes(self):
        '''
        Return the cached field notes associated with this instance.
        '''
        return self._fields_notes

    @property
    def es_client(self):
        return self.get_es_client()

    @property
    def async_es_client(self):
        return self.get_async_es_client()