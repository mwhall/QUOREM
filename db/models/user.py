from django.db import models
from django.contrib.auth import get_user_model

from django.apps import apps

User = get_user_model()
#Needed for input
User.base_name = "user"
User.plural_name = "users"

def get_id_fields():
    return ["user_id", "user_pk", "user_name"]

def get_value_fields():
    return []

User.get_id_fields = get_id_fields
User.get_value_fields = get_value_fields

class UserProfile(models.Model):
    #userprofile doesnt have a search vector bc it shouldn tbe searched.
    user = models.ForeignKey(User, on_delete=models.CASCADE, unique=True)

    @classmethod
    def create(cls, user):
        userprofile = cls(user=user)
        return userprofile
    def __str__(self):
        return self.user.email

#a class for mail messages sent to users.
class UserMail(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now=False, auto_now_add=True)
    title = models.TextField()
    message = models.TextField()
    #mail is oviously not read when it's first created
    read = models.BooleanField(default = False)

class UploadMessage(models.Model):
    """
    Store messages for file uploads.
    """
    file = models.ForeignKey("UploadFile", on_delete=models.CASCADE, verbose_name='Uploaded File')
    error_message = models.CharField(max_length = 1000, null=True)

