from celery import shared_task
from django.core.management import call_command


@shared_task(ignore_result=True)
def deliver_email():
    call_command("deliver_email")


@shared_task(ignore_result=True)
def process_uploads():
    call_command("process_statements")
    call_command("scan_files")


@shared_task(ignore_result=True)
def send_reminders():
    call_command("send_reminders")


@shared_task(ignore_result=True)
def process_privacy():
    call_command("process_privacy_requests")


@shared_task(ignore_result=True)
def apply_retention():
    call_command("apply_retention")
