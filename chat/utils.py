import io
import cv2
import imageio.v3 as iio
from PIL import Image, ImageOps
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import FileSystemStorage


IMAGE_FORMATS = ["jpg", "jpeg", "png", "gif", "tiff"]
VIDEO_FORMATS = ["mp4", "mkv", "avi", "flv", "f4v", "swf", "wmv", "mov"]
AUDIO_FORMATS = ["pcm", "wav", "aiff", "mp3",
                 "aac", "ogg", "wma", "flac", "alac"]
FILE_FORMATS = [".txt", ".xls", ".xlsx", ".ppt", ".pptx",
                ".doc", ".docx", ".pdf", ".odt", ".odp", ".ods"]
INVALID_FORMATS = [".php", ".php2", ".php3", ".php4", ".php5",
                   ".php6", ".php7", ".phps", ".phps", ".pht",
                   ".phtm", ".phtml", ".pgif", ".shtml", ".htaccess",
                   ".phar", ".inc", ".hphp", ".ctp", ".module",
                   ".asp", ".aspx", ".config", ".ashx", ".asmx",
                   ".aspq", ".axd", ".cshtm", ".cshtml", ".rem",
                   ".soap", ".vbhtm", ".vbhtml", ".asa", ".cer",
                   ".shtml", ".jsp", ".jspx", ".jsw", ".jsv",
                   ".jspf", ".wss", ".do", ".action", ".cfm",
                   ".cfml", ".cfc", '.dbm', ".swf", ".pl",
                   ".cgi", ".yaws", ".exe", ".bat", ".msi",
                   ".tar", ".zip", ".rar"]

ALL_ACCEPTABLE_FORMATS = IMAGE_FORMATS+VIDEO_FORMATS+AUDIO_FORMATS+FILE_FORMATS


def resize_image(image: Image) -> Image:
    """
    resize pillow image
    """
    height, width = image.size
    new_width = 50
    new_height = int(new_width * height / width)
    image = image.resize((new_width, new_height), Image.ANTIALIAS)
    wdif, hdif = 0, (new_height-new_width)//2
    border = wdif, hdif, wdif, hdif  # left, top, right, bottom
    image = ImageOps.crop(image, border)
    return image


def pillow_to_iobytes(image: Image) -> io.BytesIO:
    """
    convert pillow image to io bytes
    """
    output = io.BytesIO()
    image.save(output, format='PNG', quality=85)
    output.seek(0)
    return output


def iobytes_to_InMemoryUploadedFile(iobytes: io.BytesIO) -> InMemoryUploadedFile:
    """
    convert io bytes to django InMemoryUploadedFile
    """
    return InMemoryUploadedFile(file=iobytes,
                                name='_',
                                size=iobytes.getbuffer().nbytes,
                                content_type='image/png',
                                charset=None,
                                content_type_extra={},
                                field_name='file_pic')


def capture_video_inmemory(file: InMemoryUploadedFile) -> Image:
    """
    capture first frame of an in memory video 
    it takes too long time to convert video from bytes to numpy arrey 
    and then get first slice  
    """
    file_format = file.name.split(".")[-1]
    first_frame = iio.imread(file.file, format_hint='.'+file_format)[0]
    return Image.fromarray(first_frame)


def capture_video_temporary(file: InMemoryUploadedFile) -> Image:
    """
    save in-memory file on disk temporary storage
    capture first frame of the temporary file video 
    """
    FileSystemStorage(location="/tmp").save(file.name, file)
    vidcap = cv2.VideoCapture("/tmp/"+file.name)
    success, first_frame = vidcap.read()
    if success:
        image = Image.fromarray(first_frame)
        cv2.destroyAllWindows()
        vidcap.release()
        return image


def generate_file_pic(file: InMemoryUploadedFile) -> InMemoryUploadedFile:
    """
    to generate file_pic for file
    """
    file_format = file.name.split(".")[-1]
    try:
        if file_format in IMAGE_FORMATS:
            image = Image.open(file)
        elif file_format in VIDEO_FORMATS:
            # image = capture_video_inmemory(file)
            image = capture_video_temporary(file)
        image = resize_image(image)
        iobytes = pillow_to_iobytes(image)
        return iobytes_to_InMemoryUploadedFile(iobytes)
    except:
        return None
