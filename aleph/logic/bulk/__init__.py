import logging
import os

from aleph.core import db
from aleph.util import dict_list
from aleph.model import Collection, Role, Permission
from aleph.index.entities import index_bulk
from aleph.index.collections import index_collection
from aleph.logic.bulk.query import DatabaseQuery, CSVQuery

PAGE = 1000
log = logging.getLogger(__name__)


def bulk_load(config):
    """Bulk load entities from a CSV file or SQL database.

    This is done by mapping the rows in the source data to entities and links
    which can be understood by the entity index.
    """
    if 'config' in config and 'slugs' in config.get('config', []):
        for slug in config['config']['slugs']:
            os.environ['OSANC_SLUG'] = slug
            config.pop('config', None) # Assume we're done with config for now
            load_one(config)
    else:
        load_one(config)


def load_one(config):
    for foreign_id, data in config.items():
        collection = Collection.by_foreign_id(foreign_id)
        if collection is None:
            collection = Collection.create({
                'foreign_id': foreign_id,
                'managed': True,
                'label': data.get('label') or foreign_id,
                'summary': data.get('summary'),
                'category': data.get('category'),
            })

        for role_fk in dict_list(data, 'roles', 'role'):
            role = Role.by_foreign_id(role_fk)
            if role is not None:
                Permission.grant(collection.id, role, True, False)
            else:
                log.warning("Could not find role: %s", role_fk)

        db.session.commit()

        for query in dict_list(data, 'queries', 'query'):
            load_query(collection, query)


def load_query(collection, query):
    if 'database' in query or 'databases' in query:
        query = DatabaseQuery(collection, query)
    else:
        query = CSVQuery(collection, query)

    rows = []
    for row_idx, row in enumerate(query.iterrows(), 1):
        rows.append(row)
        if len(rows) >= PAGE:
            load_rows(query, rows)
            rows = []
    if len(rows):
        load_rows(query, rows)

    index_collection(collection)


def load_rows(query, rows):
    """Load a single batch of QUEUE_PAGE rows from the given query."""
    entities = {}
    links = []
    for row in rows:
        entity_map = {}
        for entity in query.entities:
            data = entity.to_index(row)
            if data is not None:
                entity_map[entity.name] = data
                entities[data['id']] = data

        for link in query.links:
            for inverted in [False, True]:
                data = link.to_index(row, entity_map, inverted=inverted)
                if data is not None:
                    links.append(data)

    index_bulk(entities, links)
    log.info("[%s] Indexed %s rows as %s entities, %s links...",
             query.collection.foreign_id,
             len(rows),
             len(entities),
             len(links))
