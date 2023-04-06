import re
from chat.utils import image_formats, video_formats, audio_formats
from django.core.exceptions import ValidationError


def file_validator(type, format, size):
    resp = {"errors": list()}
    if size > 30*10**6:
        resp['errors'].append('File size exeeds 30m limite.')
    if type == "IMAGE" and format not in image_formats:
        resp['errors'].append('Wrong image file format.')
    elif type == "VIDEO" and format not in video_formats:
        resp['errors'].append('Wrong video file format.')
    elif type == "VOICE" and format not in audio_formats:
        resp['errors'].append('Wrong audio file format.')
    if resp['errors']:
        raise ValidationError(resp)
    return None

