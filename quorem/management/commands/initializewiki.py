from django.core.management.base import BaseCommand, CommandError
from ...wiki import initialize_wiki
class Command(BaseCommand):
    help = "Initialize the base pages for a new QUOR'EM deployment"

    def handle(self, *args, **options):
        initialize_wiki()
