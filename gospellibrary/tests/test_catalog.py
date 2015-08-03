import unittest
from gospellibrary import Catalog, Subitem, RelatedAudioItem, RelatedVideoItem, RelatedContentItem
import logging
import bs4
import requests
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache


logger = logging.getLogger('gospellibrary')

session = CacheControl(requests.session(), cache=FileCache('.gospellibrarycache'))


class Test(unittest.TestCase):
    def test_current_version(self):
        self.assertGreaterEqual(Catalog(session=session).current_version(), 1)

    def test_item(self):
        item = Catalog(session=session).item(uri='/scriptures/bofm', lang='eng')
        self.assertEqual(item.item_external_id, '_scriptures_bofm_000')
        self.assertGreaterEqual(item.version, 1)

    def test_items(self):
        items = Catalog(session=session).items()
        self.assertTrue(('/scriptures/bofm', 'eng') in items)
        self.assertTrue(('/general-conference/2014/10', 'eng') in items)
        self.assertTrue(('/general-conference/2014/10', 'spa') in items)

    def test_package_html(self):
        with Catalog(session=session).item(uri='/scriptures/bofm', lang='eng').package() as package:
            p = bs4.BeautifulSoup(package.html(uri='/scriptures/bofm/1-ne/11.17')).p
            del p['pid']
            del p['hash']
            actual = str(p)

            expected = '<p class="verse" uri="/scriptures/bofm/1-ne/11.17"><span class="verseNumber">17</span>And I said unto him: I know that he loveth his children; nevertheless, I do not know the meaning of all things.</p>'

            self.assertEqual(actual, expected)

    def test_package_subitems(self):
        with Catalog(session=session).item(uri='/manual/all-is-safely-gathered-in-family-finances', lang='eng').package() as package:
            actual = package.subitems()

            expected = [
                Subitem(
                    id=1,
                    uri='/manual/all-is-safely-gathered-in-family-finances/all-is-safely-gathered-in-family-finances',
                    title='All Is Safely Gathered In: Family Finances',
                    short_title=None,
                    primary_title_component=None,
                    secondary_title_component=None,
                    web_url='http://www.lds.org/manual/all-is-safely-gathered-in-family-finances/all-is-safely-gathered-in-family-finances')
            ]

            self.assertEqual(expected, actual)

    def test_package_related_audio_items(self):
        with Catalog(session=session).item(uri='/manual/new-testament-stories', lang='eng').package() as package:
            subitem_id = 38

            actual = package.related_audio_items(subitem_id)

            expected = [
                RelatedAudioItem(
                    id=37,
                    subitem_id=subitem_id,
                    media_url='http://media2.ldscdn.org/assets/scripture-and-lesson-support/new-testament-stories/2010-11-370-chapter-36-jesus-tells-three-parables-complete-256k-eng.mp3',
                    file_size=9248128)
            ]

            self.assertEqual(expected, actual)

    def test_package_related_video_items(self):
        with Catalog(session=session).item(uri='/manual/new-testament-stories', lang='eng').package() as package:
            subitem_id = 38

            actual = [related_video_item for related_video_item in package.related_video_items(subitem_id) if related_video_item.container_type == 1]

            expected = [
                RelatedVideoItem(
                    id=469,
                    subitem_id=subitem_id,
                    media_url='http://c.brightcove.com/services/mobile/streaming/index/master.m3u8?videoId=1288200371001',
                    container_type=1)
            ]

            self.assertEqual(expected, actual)

    def test_package_related_content_items(self):
        with Catalog(session=session).item(uri='/scriptures/ot', lang='eng').package() as package:
            # Psalms 117
            subitem_id = 596

            actual = package.related_content_items(subitem_id)

            expected = [
                RelatedContentItem(
                    id=11429,
                    subitem_id=subitem_id,
                    position=0,
                    name='f_2a',
                    label='2a',
                    label_content='truth',
                    origin_uri='/scriptures/ot/ps/117.2',
                    content='<a href="/scriptures/dc-testament/dc/84.45" class="scriptureRef">D&amp;C 84:45</a>; <a href="/scriptures/dc-testament/dc/93.24" class="scriptureRef">93:24</a>.')
            ]

            self.assertEqual(expected, actual)
