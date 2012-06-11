from django.http import HttpResponse

class BAD_REQUEST(HttpResponse):
    """
    A class extending HttpResponse for creating user friendly error messages
    on HTTP 400 errors from the API.
    """
    def __init__(self, content='',status=400,content_type="text/plain"):
        super(BAD_REQUEST, self).__init__(content=content, status=status,
            content_type=content_type)

