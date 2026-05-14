from rest_framework import serializers
from .models import RedItem

class RedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedItem
        fields = '__all__'
