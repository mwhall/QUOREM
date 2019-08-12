from django.core.management.base import BaseCommand, CommandError
from ...wiki_static import docs_wiki
class Command(BaseCommand):
    help = "Refresh a page's Automated Report"

#    def add_arguments(self, parser):
#        parser.add_argument('slug', nargs=1, type=str)
#        parser.add_argument('--pk', nargs=1, type=str, default=None, required=False)

    def handle(self, *args, **options):
#        slug = options['slug'][0]
#        pk = options['pk']
#        if pk is not None:
#            pk = int(pk[0])
        for wiki_report in docs_wiki:
            wiki_report.update_wiki()
#        refresh_automated_report(slug, pk=pk)
        
