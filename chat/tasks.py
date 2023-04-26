from celery import shared_task
from .utils import generate_file_pic


@shared_task
def generate_file_pic_task(file):
    """
    make a task qeueu for generating file picture
    """
    return generate_file_pic(file)