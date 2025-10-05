from django.db import models
from user.models import TimeStampedModel
from django_celery_beat.models import PeriodicTask
from django.contrib.auth.hashers import make_password
import uuid

class Config(TimeStampedModel):
    CONFIG_TYPE = [
        ('SFTP', 'sftp'),
        ('FTP', 'ftp'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'active'),
        ('INACTIVE', 'inactive'),
        ('FAILED', 'failed'),
    ]
    id = models.AutoField(primary_key=True)
    config_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(unique=True, max_length=255)
    host = models.CharField(max_length=30)
    port = models.IntegerField()  
    config_type = models.CharField(max_length=30, choices=CONFIG_TYPE)
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=128) 
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='INACTIVE')

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
    
    def save(self, *args, **kwargs):
        if not self.config_id:
            self.config_id = f"CFG-{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

class PeriodicTaskMeta(TimeStampedModel):
    task = models.OneToOneField(PeriodicTask, on_delete=models.CASCADE, related_name="meta")
    
class AS2Partner(TimeStampedModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    as2_id = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    cert_file = models.CharField(max_length=500)  # path to public cert
    private_key_file = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class AS2Agreement(TimeStampedModel):
    id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(AS2Partner, related_name='sent_agreements', on_delete=models.CASCADE)
    receiver = models.ForeignKey(AS2Partner, related_name='received_agreements', on_delete=models.CASCADE)
    encryption = models.CharField(max_length=50, choices=[('AES128', 'AES128'), ('AES256', 'AES256')])
    signature = models.CharField(max_length=50, choices=[('SHA1', 'SHA1'), ('SHA256', 'SHA256')])
    mic_algo = models.CharField(max_length=50, default='SHA256')
    created_at = models.DateTimeField(auto_now_add=True)

class TaskLog(models.Model):
    id = models.AutoField(primary_key=True)
    process_id = models.CharField(max_length=255) 
    task_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50)                  
    message = models.TextField(blank=True, null=True)       
    started_at = models.DateTimeField()      
    ended_at = models.DateTimeField()      
    
    def __str__(self):
        return f"{self.task_name} ({self.status})"
    
class Script(TimeStampedModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    file_path = models.CharField(max_length=500)  
    required_libraries = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name