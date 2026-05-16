from rest_framework import serializers
from .models import Squad, SquadMembership
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer

class SquadMembershipSerializer(serializers.ModelSerializer):
    athlete = UserSerializer(read_only=True)
    
    class Meta:
        model = SquadMembership
        fields = ['athlete', 'joined_at']

class SquadSerializer(serializers.ModelSerializer):
    athletes = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=User.objects.all(),
        required=False
    )
    memberships = SquadMembershipSerializer(source='squadmembership_set', many=True, read_only=True)
    
    class Meta:
        model = Squad
        fields = ['id', 'name', 'coach', 'athletes', 'memberships', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'coach', 'created_at', 'updated_at']

    def create(self, validated_data):
        athletes = validated_data.pop('athletes', [])
        squad = Squad.objects.create(**validated_data)
        for athlete in athletes:
            SquadMembership.objects.create(squad=squad, athlete=athlete)
        return squad

    def update(self, instance, validated_data):
        athletes = validated_data.pop('athletes', None)
        instance = super().update(instance, validated_data)
        
        if athletes is not None:
            # Algo: Sync memberships without deleting and recreating everything
            # This preserves the 'joined_at' date for existing members
            current_athletes = set(instance.athletes.all())
            new_athletes = set(athletes)
            
            # Remove those no longer in the list
            SquadMembership.objects.filter(squad=instance, athlete__in=current_athletes - new_athletes).delete()
            
            # Add new ones
            for athlete in new_athletes - current_athletes:
                SquadMembership.objects.create(squad=instance, athlete=athlete)
                
        return instance
