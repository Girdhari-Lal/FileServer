from user.models import MyUser
from rest_framework import serializers
from django.contrib.auth import authenticate

class UserRegisterSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={'input_type':'password'}, write_only = True)
    class Meta:
        model = MyUser
        fields =  ['email', 'name', 'password', 'password2', 'date_of_birth']
        extra_kwargs = {'password' : {'write_only' : True}}

    def validate(self, attrs):
        password = attrs.get('password')
        password2 = attrs.get('password2')
        if password != password2:
            raise serializers.ValidationError("Password & Confirm password doesn't match")
        return attrs    
    def create(self, validated_data):
        validated_data.pop("password2")  
        password = validated_data.pop("password")
        user = MyUser.objects.create_user(password=password, **validated_data)
        return user
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError({"error": "Email or password is not valid"})
        attrs["user"] = user
        return attrs
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        fields = ['email', 'name', 'user_type', 'user_code', 'is_active']
