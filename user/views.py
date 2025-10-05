from django.shortcuts import render
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from user.serializers import UserLoginSerializer, UserRegisterSerializer, UserSerializer
from rest_framework.response import Response 
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from user.models import MyUser
from rest_framework.permissions import IsAuthenticated

def get_tokens_for_user(user):
    if not user.is_active:
      raise AuthenticationFailed("User is not active")
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class UserRegisterView(APIView):
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'Message': 'User created successfully'}, status=status.HTTP_201_CREATED)
        return Response({
            'Message': 'User not created',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
class UserLoginView(APIView):

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            token = get_tokens_for_user(user)
            return Response({"message": "Login successful", 'token': token,  "username": user.name, "email": user.email})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserView(APIView):  
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_code = request.query_params.get('user_code') or request.data.get('user_code')
        if user_code:
            user = get_object_or_404(MyUser, user_code=user_code)
            serializer = UserSerializer(user)
            return Response(serializer.data)
        users = MyUser.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def patch(self, request):
        user_code = request.query_params.get('user_code') or request.data.get('user_code')
        user = get_object_or_404(MyUser, user_code=user_code)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        user_code = request.query_params.get('user_code') or request.data.get('user_code')
        user = get_object_or_404(MyUser, user_code=user_code)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)