# Tareas operativas se coordinan desde apps.reminders.tasks.
from celery import shared_task
from django.core.mail import send_mail


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_development_task_email(
    subject,
    message,
    recipient_email,
):
    if not recipient_email:
        return False

    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[recipient_email],
        fail_silently=False,
    )

    return True