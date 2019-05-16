#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another 
# process

from __future__ import absolute_import, unicode_literals
from celery import shared_task

@shared_task
def test_task(x):
    import os
    print(os.getppid())
    print("I'm a celery task!")
