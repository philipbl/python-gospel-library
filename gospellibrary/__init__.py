import requests
import logging
from zipfile import ZipFile
from tempfile import mkdtemp
import os
import sqlite3
import shutil
from contextlib import contextmanager
from reprutils import GetattrRepr

try:
    from StringIO import StringIO
    Bytes = StringIO
except ImportError:
    from io import BytesIO
    Bytes = BytesIO


DEFAULT_BASE_URL = 'http://broadcast3.lds.org/crowdsource/mobile/gospelstudy/production'
SCHEMA_VERSION = '2.0.3'

logger = logging.getLogger('gospellibrary')


class Catalog:
    def __init__(self, base_url=DEFAULT_BASE_URL, session=None):
        self.base_url = base_url
        self.schema_version = SCHEMA_VERSION
        self.session = session if session else requests.session()

    __repr__ = GetattrRepr()

    def current_version(self):
        logger.info('Getting the current catalog version')

        index_url = '{base_url}/{schema_version}/index.json'.format(base_url=self.base_url,
                                                                    schema_version=self.schema_version)
        r = self.session.get(index_url)
        if r.status_code == 200:
            index = r.json()
            catalog_version = index.get('catalogVersion', 0)
            if catalog_version >= 1:
                return catalog_version

        raise ValueError('failed to get the current catalog version')

    def item(self, uri, lang):
        catalog_version = self.current_version()

        logger.info('Getting catalog {catalog_version}'.format(catalog_version=catalog_version))

        catalog_zip_url = '{base_url}/{schema_version}/catalogs/{catalog_version}.zip'.format(
            base_url=self.base_url,
            schema_version=self.schema_version,
            catalog_version=catalog_version)
        r = self.session.get(catalog_zip_url)
        if r.status_code == 200:
            catalog_path = os.path.join(mkdtemp(), 'Catalog.sqlite')
            try:
                try:
                    os.makedirs(os.path.dirname(catalog_path))
                except OSError:
                    pass

                with ZipFile(Bytes(r.content), 'r') as catalog_zip_file:
                    catalog_zip_file.extractall(os.path.dirname(catalog_path))

                with sqlite3.connect(catalog_path) as db:
                    c = db.cursor()
                    try:
                        c.execute('''
                                SELECT external_id, latest_version, title FROM item
                                    INNER JOIN language ON item.language_id=language._id
                                WHERE uri=? AND iso639_3=?''', (uri, lang))
                        item_external_id, item_version, item_title = c.fetchone()
                        return Item(base_url=self.base_url,
                                    session=self.session,
                                    item_external_id=item_external_id,
                                    version=item_version,
                                    title=item_title)
                    finally:
                        c.close()
            finally:
                shutil.rmtree(catalog_path, ignore_errors=True)

        raise ValueError('failed to get the item')

    def items(self):
        catalog_version = self.current_version()

        logger.info('Getting catalog {catalog_version}'.format(catalog_version=catalog_version))

        catalog_zip_url = '{base_url}/{schema_version}/catalogs/{catalog_version}.zip'.format(
            base_url=self.base_url,
            schema_version=self.schema_version,
            catalog_version=catalog_version)
        r = self.session.get(catalog_zip_url)
        if r.status_code == 200:
            catalog_path = os.path.join(mkdtemp(), 'Catalog.sqlite')
            try:
                try:
                    os.makedirs(os.path.dirname(catalog_path))
                except OSError:
                    pass

                with ZipFile(Bytes(r.content), 'r') as catalog_zip_file:
                    catalog_zip_file.extractall(os.path.dirname(catalog_path))

                items = []

                with sqlite3.connect(catalog_path) as db:
                    c = db.cursor()
                    try:
                        c.execute('''
                                SELECT uri, iso639_3, external_id, latest_version, title FROM item
                                    INNER JOIN language ON item.language_id=language._id''')
                        for uri, iso639_3, item_external_id, item_version, item_title in c.fetchall():
                            items.append((uri, iso639_3))
                    finally:
                        c.close()

                return items
            finally:
                shutil.rmtree(catalog_path, ignore_errors=True)

        raise ValueError('failed to get the items')


class Item:
    def __init__(self, base_url, session, item_external_id, version, title):
        self.base_url = base_url
        self.schema_version = SCHEMA_VERSION
        self.item_external_id = item_external_id
        self.version = version
        self.title = title
        self.session = session

    __repr__ = GetattrRepr(item_external_id='item_external_id', version='version', title='title')

    @contextmanager
    def package(self):
        logger.info('Getting version {item_version} of {item_external_id}'.format(
            item_version=self.version,
            item_external_id=self.item_external_id))

        item_package_zip_url = '{base_url}/{schema_version}/item-packages/{item_external_id}/{item_version}.zip'.format(
            base_url=self.base_url,
            schema_version=self.schema_version,
            item_external_id=self.item_external_id,
            item_version=self.version)
        r = self.session.get(item_package_zip_url)
        if r.status_code == 200:
            item_package_path = os.path.join(mkdtemp(), 'package.sqlite')

            try:
                os.makedirs(os.path.dirname(item_package_path))
            except OSError:
                pass

            with ZipFile(Bytes(r.content), 'r') as catalog_zip_file:
                catalog_zip_file.extractall(os.path.dirname(item_package_path))

            package = ItemPackage(path=item_package_path)
            try:
                yield package
            finally:
                package.close()
            return

        raise ValueError('failed to get the item package')


class ItemPackage:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.text_factory = str

    def close(self):
        self.db.close()

    def html(self, uri):
        c = self.db.cursor()
        try:
            c.execute('''
                    SELECT content, start_index, end_index FROM subitem_content_range
                        INNER JOIN subitem_content ON subitem_content_range.subitem_id=subitem_content.subitem_id
                    WHERE uri=?''', [uri])
            (html, start_index, end_index) = c.fetchone()

            return html[start_index:end_index].decode('utf-8')
        finally:
            c.close()

    def subitems(self):
        c = self.db.cursor()
        try:
            return [Subitem(
                id=row[0],
                uri=row[1],
                title=row[2],
                short_title=row[3],
                primary_title_component=row[4],
                secondary_title_component=row[5],
                web_url=row[6]) for row in
                    c.execute('''SELECT _id, uri, title, short_title, primary_title_component, secondary_title_component, web_url FROM subitem ORDER BY position''')]
        finally:
            c.close()

    def related_audio_items(self, subitem_id):
        c = self.db.cursor()
        try:
            return [RelatedAudioItem(
                id=row[0],
                subitem_id=row[1],
                media_url=row[2],
                file_size=row[3]) for row in
                    c.execute('''SELECT _id, subitem_id, media_url, file_size FROM related_audio_item WHERE subitem_id=?''', [subitem_id])]
        finally:
            c.close()

    def related_video_items(self, subitem_id):
        c = self.db.cursor()
        try:
            return [RelatedVideoItem(
                id=row[0],
                subitem_id=row[1],
                media_url=row[2],
                container_type=row[3]) for row in
                    c.execute('''SELECT _id, subitem_id, media_url, container_type FROM related_video_item WHERE subitem_id=?''', [subitem_id])]
        finally:
            c.close()

    def related_content_items(self, subitem_id):
        c = self.db.cursor()
        try:
            return [RelatedContentItem(
                id=row[0],
                subitem_id=row[1],
                position=row[2],
                name=row[3],
                label=row[4],
                label_content=row[5],
                origin_uri=row[6],
                content=row[7]) for row in
                    c.execute('''SELECT _id, subitem_id, position, name, label, label_content, origin_uri, content FROM related_content_item WHERE subitem_id=?''', [subitem_id])]
        finally:
            c.close()


class Subitem:
    def __init__(self, id, uri, title, short_title, primary_title_component,
                secondary_title_component, web_url):
        self.id = id
        self.uri = uri
        self.title = title
        self.short_title = short_title
        self.primary_title_component = primary_title_component
        self.secondary_title_component = secondary_title_component
        self.web_url = web_url

    __repr__ = GetattrRepr('id',
                           uri='uri',
                           title='title',
                           short_title='short_title',
                           primary_title_component='primary_title_component',
                           secondary_title_component='secondary_title_component',
                           web_url='web_url')

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))


class RelatedAudioItem:
    def __init__(self, id, subitem_id, media_url, file_size):
        self.id = id
        self.subitem_id = subitem_id
        self.media_url = media_url
        self.file_size = file_size

    __repr__ = GetattrRepr('id', subitem_id='subitem_id', media_url='media_url',
                           file_size='file_size')

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))


class RelatedVideoItem:
    def __init__(self, id, subitem_id, media_url, container_type):
        self.id = id
        self.subitem_id = subitem_id
        self.media_url = media_url
        self.container_type = container_type

    __repr__ = GetattrRepr('id', subitem_id='subitem_id', media_url='media_url', container_type='container_type')

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))

class RelatedContentItem:
    def __init__(self, id, subitem_id, position, name, label, label_content, origin_uri, content):
        self.id = id
        self.subitem_id = subitem_id
        self.position = position
        self.name = name
        self.label = label
        self.label_content = label_content
        self.origin_uri = origin_uri
        self.content = content

    __repr__ = GetattrRepr('id',
                           subitem_id='subitem_id',
                           position='position',
                           name='name',
                           label='label',
                           label_content='label_content',
                           origin_uri='origin_uri',
                           content='content')

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))
