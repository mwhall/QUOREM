from django.core.management.base import BaseCommand, CommandError
from db.artifacts import mine_qiime2
class Command(BaseCommand):
    help = "Initialize an empty QUOREM database"

    def handle(self, *args, **options):
        print("Fetching Step objects from QIIME2 SDK")
        mine_qiime2()
