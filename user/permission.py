from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'Admin'

class IsManagerUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'manager'

class IsRegularUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'user'
    
class IsManagerOrRegularUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.user_type == 'manager' or request.user.user_type == 'user')
    
class IsAdminOrManagerUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.user_type == 'manager' or request.user.user_type == 'Admin')    