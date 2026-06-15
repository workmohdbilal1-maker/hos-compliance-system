from rest_framework import serializers
from .models import Driver


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'license_number', 'carrier_name', 'carrier_address',
            'home_terminal_address', 'home_terminal_timezone',
            'cycle_type', 'truck_number', 'trailer_number', 'co_driver_name',
        ]
        read_only_fields = ['id']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Driver
        fields = [
            'username', 'password', 'first_name', 'last_name', 'email',
            'license_number', 'carrier_name', 'carrier_address',
            'home_terminal_address', 'home_terminal_timezone',
            'cycle_type', 'truck_number', 'trailer_number',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        driver = Driver(**validated_data)
        driver.set_password(password)
        driver.save()
        return driver
