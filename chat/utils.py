import os
import io
import cv2
from PIL import Image, ImageOps
from django.core.files.uploadedfile import InMemoryUploadedFile


image_formats = ["jpg", "jpeg", "png", "gif", "tiff"]
video_formats = ["mp4", "mkv", "avi", "flv", "f4v", "swf", "wmv", "mov"]
audio_formats = ["pcm", "wav", "aiff", "mp3",
                 "aac", "ogg", "wma", "flac", "alac"]

IMAGE_FORMATS = list()
for format in image_formats:
    IMAGE_FORMATS.extend([format, format.upper()])

VIDEO_FORMAT = list()
for format in video_formats:
    VIDEO_FORMAT.extend([format, format.upper()])

AUDIO_FORMAT = list()
for format in audio_formats:
    AUDIO_FORMAT.extend([format, format.upper()])


def blur_image(file: InMemoryUploadedFile) -> InMemoryUploadedFile:
    """
    blur image and resize
    https://www.tutorialspoint.com/python_pillow/python_pillow_blur_an_image.htm
    https://stackoverflow.com/questions/273946/how-do-i-resize-an-image-using-pil-and-maintain-its-aspect-ratio
    https://stackoverflow.com/questions/46944107/how-to-crop-an-image-from-the-center-with-certain-dimensions
    """
    image = Image.open(file)
    # resize image
    height, width = image.size
    new_width = 50
    new_height = int(new_width * height / width)
    image = image.resize((new_width, new_height), Image.ANTIALIAS)
    wdif, hdif = 0, (new_height-new_width)//2
    border = wdif, hdif, wdif, hdif  # left, top, right, bottom
    image = ImageOps.crop(image, border)
    # convert to django image field
    output = io.BytesIO()
    image.save(output, format='PNG', quality=85)
    output.seek(0)
    return InMemoryUploadedFile(file=output,
                                name=file.name,
                                size=output.getbuffer().nbytes,
                                content_type='image/png',
                                charset=None,
                                content_type_extra={},
                                field_name='file_pic')


def capture_video(vid_path: str) -> str():
    """
    take a capture from video and blur it
    https://stackoverflow.com/questions/30136257/how-to-get-image-from-video-using-opencv-python
    """
    dir_name, base_name = os.path.split(vid_path)
    filename, file_format = os.path.splitext(vid_path)
    img_name = base_name.replace(file_format, ".png")
    img_path = os.path.join(dir_name, img_name)
    vidcap = cv2.VideoCapture(vid_path)
    success, image = vidcap.read()
    if success:
        cv2.imwrite(img_path, image)
    cv2.destroyAllWindows()
    vidcap.release()
    return blur_image(img_path)
