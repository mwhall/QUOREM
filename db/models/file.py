import logging

from django.db import models
from django.core import files
from django.contrib.auth import get_user_model
from django.conf import settings

from django.utils.html import mark_safe, format_html
from django.forms.utils import flatatt
from django.urls import reverse

#for searching
from django.contrib.postgres.search import SearchVector

from django.apps import apps

# Note: This is called UploadFile because we have File as a Value which is a pointer to a broader set of things considered Files
class UploadFile(models.Model):
    base_name = "uploadfile"
    plural_name = "uploadfiles"
    STATUS_CHOICES = (
        ('P', "Processing"),
        ('S', "Success"),
        ('E', "Error")
    )
    TYPE_CHOICES = (
        ('S', 'Spreadsheet'),
        ('A', 'Artifact'))
    userprofile = models.ForeignKey("UserProfile", on_delete=models.CASCADE, verbose_name='Uploader')
    upload_file = models.FileField(upload_to="upload/")
    logfile = models.OneToOneField("LogFile", on_delete=models.CASCADE, related_name="file")
    upload_status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    upload_type = models.CharField(max_length=1, choices=TYPE_CHOICES)
    #Should upload files be indexed by the search??
    #search_vector = SearchVectorField(null=True)

    def __str__(self):
        return "UserProfile: {0}, UploadFile: {1}".format(self.userprofile, self.upload_file)

    def get_detail_link(self):
        kwargs = {}
        kwargs["uploadfile_id"] = self.pk
        return format_html('<a{}>{}</a>',
                         flatatt({'href': reverse("uploadfile_detail",
                                 kwargs=kwargs)}),
                                 str(self.upload_file).split("/")[-1])

    def save(self, *args, **kwargs):
        self.upload_status = 'P'
        lf = LogFile(type='F')
        lf.save()
        self.logfile = lf
        super().save(*args, **kwargs)

    def update(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
class LogFile(models.Model):
    base_name = "log"
    plural_name = "logs"

    # Define log types here
    TYPE_CHOICES = (
            ('U', 'Upload Log'),
            ('F', "Upload File Log"),
            ('A', "User Action Log")
    )

    DEFAULT_LOG_FILENAMES = {'U': "all_uploads.log",
                             'F': "upload_%d.log",
                             'A': "user_actions.log"}

    log = models.FileField(upload_to='logs', blank=True, null=True)
    # Text description of the log type
    type = models.CharField(max_length=1, choices=TYPE_CHOICES)
    # When the log was written
    date_created = models.DateTimeField(auto_now_add=True)
    # Last update to it
    last_updated = models.DateTimeField(auto_now=True)

    def get_log_path(self):
        if not self.pk:
            raise ValueError("LogFile instance must be saved before a log path can be retrieved")
        if self.type=='F':
            if not self.file:
                raise ValueError("Uninitialized Upload File Log. Must be set to\
                        a File object's logfile field and saved before a logger\
                        can be retrieved")
            # Should have a File pointed at it, so
            fileobj = self.file
            pk = fileobj.pk
            return settings.LOG_ROOT + "/uploads/" + self.DEFAULT_LOG_FILENAMES['F'] % (pk,)
        else:
            return settings.LOG_ROOT + "/" + self.DEFAULT_LOG_FILENAMES[self.type]

    def get_logger(self):
        # Return the Logger instance for this logfile, which will push updates
        # to the appropriate File
        #NOTE: Loggers are not garbage collected, so there's always a chance
        # that we'll stumble back on an old logger if we aren't careful with
        # the uniqueness of the names
        if not self.pk:
            raise ValueError("LogFile instance must be saved before a logger can be retrieved")

        # If this object doesn't have a log file created for it yet, do it now
        # This should be fine here since it is only needed once a logger is called
        # and begins pushing to it
        if not self.log:
            print("No log, making log file")
            path = self.get_log_path()
            logfile = files.File(open(path, 'w+b'), name=path.split("/")[-1])
            print("Opened logfile at that path and made it into a files.File")
            self.log = logfile
            self.save()

        if self.type == 'F':
            # Should have a File pointed at it, or get_log_path would've errored and we'd have no self.log
            fileobj = self.file
            pk = fileobj.pk
            lgr = logging.getLogger("quorem.uploads.%d" % (pk,))
            if not lgr.hasHandlers():
                lgr.addHandler(logging.StreamHandler(stream=self.log))
            #TODO: Add a formatter, set levels properly
            #TODO: Define quorem.uploads and its configuration
        elif self.type == 'U':
            lgr = logging.getLogger("quorem.uploads")
            if not lgr.hasHandlers():
                lgr.addHandler(logging.StreamHandler(stream=self.log))
        return lgr

    def tail(self, n=10):
        # Get the last n lines of this log
        # This function needs to open up and scrape self.log
        pass

