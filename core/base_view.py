from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet


class CustomModelViewSet(ModelViewSet):
    """
    custom viewset for soft delete
    """
    def destroy(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super().destroy(request, *args, **kwargs)
        else:
            instance = self.get_object()
            instance.is_deleted = True
            instance.save()
            return Response(status=status.HTTP_204_NO_CONTENT)