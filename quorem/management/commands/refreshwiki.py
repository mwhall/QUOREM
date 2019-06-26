from django.core.management.base import BaseCommand, CommandError
from ...wiki import refresh_automated_report
class Command(BaseCommand):
    help = "Refresh a page's Automated Report"

    def add_arguments(self, parser):
        parser.add_argument('slug', nargs=1, type=str)
        parser.add_argument('--pk', nargs=1, type=str, default=None, required=False)

    def handle(self, *args, **options):
        slug = options['slug'][0]
        pk = options['pk']
        if pk is not None:
            pk = int(pk[0])
        refresh_automated_report(slug, pk=pk)
        
