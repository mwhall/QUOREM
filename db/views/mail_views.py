from django.shortcuts import render, redirect
from django.views import View
from django.utils.html import format_html, mark_safe

from ..models import UserProfile, UserMail

class MailBoxView(View):
    template_name="mail/mailbox.htm"
    def get(self, request):
        if request.user.is_authenticated:
            userProfile = UserProfile.objects.get(user=request.user)
            mailBox = UserMail.objects.filter(user=userProfile).order_by('-date_created')
            unread = mailBox.filter(read=False).count()
            return render(request, self.template_name, {'user':userProfile,
                                                        'mail': mailBox,
                                                        'unread': unread,
                                                        'active_page': 'mail',})

class MailOpen(View):
    template_name="mail/mailbox.htm"
    def get(self, request, mail_id):
        mail_pk = self.kwargs['mail_id']
        if request.user.is_authenticated:
            mail = UserMail.objects.get(pk=mail_pk)
            userProfile = UserProfile.objects.get(user=request.user)
            if mail.user != userProfile:
                print("nah")
                return
            mail.read = True
            mail.save()
            mailBox = UserMail.objects.filter(user=userProfile).order_by('-date_created')
            unread = mailBox.filter(read=False).count()
            return render(request, "mail/mailbox.htm", {'user':userProfile,
                                                        'mail': mailBox,
                                                        'unread': unread,
                                                        'active_page': 'mail',
                                                        'selected': mail,})


