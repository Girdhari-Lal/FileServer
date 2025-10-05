from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
import uuid

class MyUserManager(BaseUserManager):
    def create_user(self, email, date_of_birth, name, password=None):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(
            email=self.normalize_email(email),
            date_of_birth=date_of_birth,
             name = name,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, date_of_birth, name, password=None):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            email,
            password=password,
            date_of_birth=date_of_birth,
            name=name
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class MyUser(AbstractBaseUser):
    ADMIN = 'Admin'
    MANAGER = 'manager'
    USER = 'user'
    USER_TYPE_CHOICES = [
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (USER, 'User'),
    ]
    email = models.EmailField(
        verbose_name="email address",
        max_length=255,
        unique=True,
    )
    name = models.CharField(max_length=20)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default=USER)
    user_code = models.CharField(max_length=20, null=True)
    date_of_birth = models.DateField()
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["date_of_birth", "name"] 

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        # Simplest possible answer: All admins are staff
        return self.is_admin
    
    def save(self, *args, **kwargs):
        if not self.user_code:
            self.user_code = f"USR-{str(uuid.uuid4().int)[:8]}"  # Example: USR-12345678
        super().save(*args, **kwargs)

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(MyUser, related_name="%(class)s_created", on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(MyUser, related_name="%(class)s_updated", on_delete=models.SET_NULL, null=True, blank=True)
    class Meta:
        abstract = True