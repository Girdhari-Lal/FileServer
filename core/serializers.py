from rest_framework import serializers
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from core.models import Script, TaskLog, AS2Partner, AS2Partner, AS2Agreement, PeriodicTaskMeta, Config
import json
from zoneinfo import ZoneInfo
import paramiko
from ftplib import FTP
from django.db import transaction

class ConfigSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Config
        fields = ['name', 'host', 'port', 'config_type', 'username', 'password', 'status']
        extra_kwargs = {
            'password': {'write_only': True},
            'host': {'write_only': True},  
        }

    def validate(self, attrs):
        host = attrs.get('host')
        port = int(attrs.get('port'))
        username = attrs.get('username')
        password = attrs.get('password')
        config_type = attrs.get('config_type')
        try:
            if config_type == 'FTP':
                ftp = FTP()
                ftp.connect(host, port, timeout=5)
                ftp.login(user=username, passwd=password)
                ftp.quit()
            elif config_type == 'SFTP':
                transport = paramiko.Transport((host, port))
                transport.connect(username=username, password=password)
                transport.close()
        except Exception:
            attrs['status'] = 'FAILED'
        else:
            attrs['status'] = 'ACTIVE'
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        raw_password = validated_data.pop('password')
        config = Config(**validated_data)
        config.set_password(raw_password)
        config.save()
        return config

    @transaction.atomic
    def update(self, instance, validated_data):
        raw_password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if raw_password:
            instance.set_password(raw_password)
        instance.save()
        return instance
    
class IntervalScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntervalSchedule
        fields = "__all__"

class CrontabScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrontabSchedule
        fields = "__all__"
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(instance, "timezone") and isinstance(instance.timezone, ZoneInfo):
            data["timezone"] = str(instance.timezone)
        return data

class PeriodicTaskSerializer(serializers.ModelSerializer):
    interval = IntervalScheduleSerializer(required=False, allow_null=True)
    crontab = CrontabScheduleSerializer(required=False, allow_null=True)
    kwargs = serializers.JSONField(required=False)
    last_run_at = serializers.SerializerMethodField()

    class Meta:
        model = PeriodicTask
        fields = "__all__"

    def get_last_run_at(self, obj):
        if obj.last_run_at:
            return obj.last_run_at.strftime("%Y-%m-%d %H:%M:%S")
        return None
        
    def validate(self, data):
        interval, crontab = data.get("interval"), data.get("crontab")
        if bool(interval) == bool(crontab):
            raise serializers.ValidationError("Provide either interval or crontab, but not both.")
        return data

    def create(self, validated_data):
        interval_data = validated_data.pop("interval", None)
        if interval_data:
            interval, _ = IntervalSchedule.objects.get_or_create(**interval_data)
            validated_data["interval"] = interval
        crontab_data = validated_data.pop("crontab", None)
        if crontab_data:
            crontab, _ = CrontabSchedule.objects.get_or_create(**crontab_data)
            validated_data["crontab"] = crontab
        kwargs_data = validated_data.get("kwargs", {})
        if not isinstance(kwargs_data, dict):
            try:
                kwargs_data = json.loads(kwargs_data)
            except Exception:
                kwargs_data = {}
        if "name" in validated_data:
            kwargs_data["periodic_name"] = validated_data["name"]
        validated_data["kwargs"] = json.dumps(kwargs_data)
        task = super().create(validated_data)
        user = self.context.get("request").user if self.context.get("request") else None
        if not user or not user.is_authenticated:
            raise serializers.ValidationError({"user": "Authenticated user required"})
        PeriodicTaskMeta.objects.create(task=task, created_by=user)
        return task

    def update(self, instance, validated_data):
        interval_data = validated_data.pop("interval", None)
        if interval_data:
            interval, _ = IntervalSchedule.objects.get_or_create(**interval_data)
            validated_data["interval"] = interval
        crontab_data = validated_data.pop("crontab", None)
        if crontab_data:
            crontab, _ = CrontabSchedule.objects.get_or_create(**crontab_data)
            validated_data["crontab"] = crontab
        if "kwargs" in validated_data and not isinstance(validated_data["kwargs"], str):
            validated_data["kwargs"] = json.dumps(validated_data["kwargs"])
        instance = super().update(instance, validated_data)
        user = self.context.get("request").user if self.context.get("request") else None
        if user and user.is_authenticated:
            PeriodicTaskMeta.objects.filter(task=instance).update(updated_by=user)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("kwargs"):
            try:
                data["kwargs"] = json.loads(data["kwargs"])
            except Exception:
                pass
        for field in ("timezone",):
            if field in data and isinstance(getattr(instance, field, None), ZoneInfo):
                data[field] = str(getattr(instance, field))
        
        return data

class ScriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Script
        fields = "__all__"

class TaskLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskLog
        fields = ['id', 'task_name', 'process_id', 'status', 'started_at', 'ended_at']

class TaskLogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskLog
        fields = ['message']
        
class AS2PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AS2Partner
        fields = ['id', 'name', 'as2_id', 'url', 'cert_file', 'private_key_file', 'created_at', 'updated_at']

class AS2AgreementSerializer(serializers.ModelSerializer):
    sender = AS2PartnerSerializer(read_only=True)
    receiver = AS2PartnerSerializer(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(queryset=AS2Partner.objects.all(), source='sender', write_only=True)
    receiver_id = serializers.PrimaryKeyRelatedField(queryset=AS2Partner.objects.all(), source='receiver', write_only=True)

    class Meta:
        model = AS2Agreement
        fields = ['id', 'sender', 'receiver', 'sender_id', 'receiver_id', 'encryption', 'signature', 'mic_algo', 'created_at']

    def validate(self, attrs):
        sender = attrs.get("sender")
        receiver = attrs.get("receiver")

        if sender and receiver and sender == receiver:
            raise serializers.ValidationError(
                {"receiver_id": "Sender and Receiver cannot be the same partner."}
            )
        return attrs
    
