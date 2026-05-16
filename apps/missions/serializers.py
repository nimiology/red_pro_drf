from rest_framework import serializers
from .models import Mission

class MissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mission
        fields = '__all__'
        read_only_fields = ['id', 'coach', 'created_at', 'updated_at']

    def validate(self, attrs):
        satisfying_activity = attrs.get('satisfying_activity')
        athlete = attrs.get('athlete')

        if satisfying_activity and athlete:
            if satisfying_activity.athlete != athlete:
                raise serializers.ValidationError({"satisfying_activity": "The activity must belong to the assigned athlete."})
        
        # If updating an existing instance
        if self.instance and satisfying_activity and not athlete:
            if satisfying_activity.athlete != self.instance.athlete:
                raise serializers.ValidationError({"satisfying_activity": "The activity must belong to the assigned athlete."})

        return attrs
