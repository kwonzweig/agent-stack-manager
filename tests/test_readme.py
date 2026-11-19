"""Public getting-started links resolve without duplicating the consumer matrix."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (ROOT / 'README.md', ROOT / 'docs/api-contract.md', ROOT / 'docs/paperclip.md')
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')


def anchors(text):
    result = set()
    in_code = False
    for line in text.splitlines():
        if line.startswith('```'):
            in_code = not in_code
        if not in_code and (heading := re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)):
            result.add(re.sub(r'[^\w -]', '', heading[1].lower()).replace(' ', '-'))
    return result


class ReadmeLinkTests(unittest.TestCase):
    def test_readme_links_to_consumer_support_owner(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('catalog/consumers.json', LINK.findall(text))
        self.assertTrue((ROOT / 'catalog/consumers.json').is_file())

    def test_public_documentation_relative_links_and_anchors_resolve(self):
        for source in DOCUMENTS:
            for value in LINK.findall(source.read_text(encoding='utf-8')):
                url = urlsplit(value)
                if url.scheme or url.netloc:
                    continue
                target = (source.parent / unquote(url.path)).resolve() if url.path else source
                with self.subTest(source=source.relative_to(ROOT), link=value):
                    self.assertTrue(target.exists(), str(target))
                    if url.fragment and target.suffix == '.md':
                        self.assertIn(unquote(url.fragment), anchors(target.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
