from django.core.management.base import BaseCommand, CommandError
from db.models import File, Analysis, UserProfile
from db.tasks import react_to_file
from django.conf import settings
from django.core import files

class Command(BaseCommand):
    help = "Ingest an artifact through the shell, rather than the UI"

    def add_arguments(self, parser):
        parser.add_argument('--artifact', nargs=1, type=str, default=None, required=True)
        parser.add_argument('--analysispk', nargs=1, type=int, default=None, required=True)
        parser.add_argument('--register_provenance', nargs=1, type=bool, default=True, required=False)

    def handle(self, *args, **options):
        register_provenance = options['register_provenance']
        analysispk = options['analysispk'][0]
        artifact = options['artifact'][0]
        artifact = open(artifact, 'rb')
        analysis = Analysis.objects.get(pk=analysispk)
        upfile = File(upload_type="A", userprofile=UserProfile.objects.first())
        upfile.upload_file = files.File(artifact, name=artifact.name.split("/")[-1])
        upfile.save()
        react_to_file(upfile.pk, analysis_pk=analysis.pk, register_provenance=register_provenance)
        
