from django.core.management.base import BaseCommand, CommandError
from db.artifacts import mine_qiime2
from quorem.wiki_static import WikiStatic, docs_manifest, base_manifest
class Command(BaseCommand):
    help = "Initialize an empty QUOREM database"

    def handle(self, *args, **options):
        print("Fetching Step objects from QIIME2 SDK")
        mine_qiime2()
        print("Creating Base Wiki Articles")
        for doc in base_manifest:
            slug = doc.split(".md")[0]
            WikiStatic(slug=slug, template=doc).update_wiki()
        print("Creating Docs in Wiki")
        for doc in docs_manifest:
            slug = doc.split(".md")[0]
            WikiStatic(slug=slug, template=doc, prefix='docs').update_wiki()
