from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_celery_beat.models import IntervalSchedule, CrontabSchedule, PeriodicTask
from core.serializers import PeriodicTaskSerializer, ScriptSerializer, TaskLogSerializer, AS2PartnerSerializer, AS2AgreementSerializer, ConfigSerializer, TaskLogDetailSerializer
from core.tasks import dynamic_task, run_script_task
from core.models import Script, TaskLog, AS2Partner, AS2Agreement, PeriodicTaskMeta, Config
import json, os
from rest_framework.permissions import IsAuthenticated
import shutil
from rest_framework.permissions import IsAuthenticated
from user.permission import IsAdminUser
from rest_framework.settings import api_settings
from django.db.models import Q

class ConfigCreateView(APIView):

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminUser()]
        elif self.request.method == 'GET':
            return [IsAuthenticated()]
        elif self.request.method == 'PATCH':
            return [IsAuthenticated(), IsAdminUser()]
        elif self.request.method == 'DELETE':
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

    def get(self, request):
        config_id = request.query_params.get('config_id') or request.data.get('config_id')
        if config_id:
            try:
                config = Config.objects.get(id=config_id)
                serializer = ConfigSerializer(config)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Config.DoesNotExist:
                return Response({"detail": "Config not found."}, status=status.HTTP_404_NOT_FOUND)
        configs = Config.objects.all()
        serializer = ConfigSerializer(configs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ConfigSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        config_id = request.query_params.get('config_id') or request.data.get('config_id')
        try:
            config = Config.objects.get(config_id=config_id)
        except Config.DoesNotExist:
            return Response({"detail": "Config not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ConfigSerializer(config).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        config_id = request.query_params.get('config_id') or request.data.get('config_id')
        try:
            config = Config.objects.get(config_id=config_id)
        except Config.DoesNotExist:
            return Response({"detail": "Config not found."}, status=status.HTTP_404_NOT_FOUND)
        config.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# class IntervalScheduleAPI(APIView):
#     def get(self, request):
#         schedules = IntervalSchedule.objects.all()
#         serializer = IntervalScheduleSerializer(schedules, many=True)
#         return Response(serializer.data)

#     def post(self, request):
#         serializer = IntervalScheduleSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def put(self, request):
#         id = request.query_params.get('id') or request.data.get('id')
#         if id:
#             try:
#                 task = IntervalSchedule.objects.get(pk=id)
#             except IntervalSchedule.DoesNotExist:
#                 return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
#         serializer = IntervalScheduleSerializer(task, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def delete(self, request):
#         id = request.query_params.get('id') or request.data.get('id')
#         if id:
#             try:
#                 task = IntervalSchedule.objects.get(pk=id)
#             except IntervalSchedule.DoesNotExist:
#                 return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
#             task.delete()
#             return Response(status=status.HTTP_204_NO_CONTENT)

# # ---- Crontab ----
# class CrontabScheduleAPI(APIView):
#     def get(self, request):
#         schedules = CrontabSchedule.objects.all()
#         serializer = CrontabScheduleSerializer(schedules, many=True)
#         return Response(serializer.data)

#     def post(self, request):
#         serializer = CrontabScheduleSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

PROCESS_TASK_MAP = {
    "file": "core.tasks.dynamic_task",
    "script": "core.tasks.run_script_task",
}

class PeriodicTaskAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        task_id = request.query_params.get("id") or request.data.get("id")
        if task_id:
            try:
                task = PeriodicTask.objects.get(pk=task_id)
                if request.user.user_type != "Admin" and not PeriodicTaskMeta.objects.filter(
                    task=task, created_by=request.user).exists():
                    return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
                serializer = PeriodicTaskSerializer(task)
                return Response(serializer.data)
            except PeriodicTask.DoesNotExist:
                return Response({"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND)
        elif request.user.user_type == "Admin":
            tasks = PeriodicTask.objects.all()
        else:
            tasks = PeriodicTask.objects.filter(meta__created_by=request.user)
        serializer = PeriodicTaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        process = data.get("process")
        if process:
            task_path = PROCESS_TASK_MAP.get(process)
            if not task_path:
                return Response({"error": f"Invalid process '{process}'"}, status=status.HTTP_400_BAD_REQUEST)
            data["task"] = task_path 
            data.pop("process", None)  
        serializer = PeriodicTaskSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def patch(self, request):
        id = request.query_params.get('id') or request.data.get('id')
        if not id:
            return Response({"error": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            task = PeriodicTask.objects.get(pk=id)
        except PeriodicTask.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        process = data.get("process")
        if process:
            task_path = PROCESS_TASK_MAP.get(process)
            if not task_path:
                return Response({"error": f"Invalid process '{process}'"}, status=status.HTTP_400_BAD_REQUEST)
            data["task"] = task_path
            data.pop("process", None)
        serializer = PeriodicTaskSerializer(task, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        id = request.query_params.get('id') or request.data.get('id')
        if id:
            try:
                task = PeriodicTask.objects.get(pk=id)
            except PeriodicTask.DoesNotExist:
                return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
            task.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class RunTaskByNameView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        task_name = request.data.get("name")
        if not task_name:
            return Response({"error": "Missing parameter: name"},status=status.HTTP_400_BAD_REQUEST,)
        try:
            task_obj = PeriodicTask.objects.get(name=task_name)
        except PeriodicTask.DoesNotExist:
            return Response(
                {"error": f"No periodic task found with name '{task_name}'"},
                status=status.HTTP_404_NOT_FOUND,
            )
        kwargs = json.loads(task_obj.kwargs or "{}")
        if task_obj.task == "core.tasks.dynamic_task":
            async_result = dynamic_task.apply_async(kwargs=kwargs)
        elif task_obj.task == "core.tasks.run_script_task":
            async_result = run_script_task.apply_async(kwargs=kwargs)
        else:
            return Response({"error": f"Unsupported task type '{task_obj.task}'"},status=status.HTTP_400_BAD_REQUEST,)
        result = async_result.get() 
        return Response(
            {"message": f"Task '{task_obj.name}' queued successfully", **result},
            status=status.HTTP_202_ACCEPTED,
        )

        
class ScriptCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        script_id = request.query_params.get("id") or request.data.get("id")
        if script_id:
            try:
                script = Script.objects.get(pk=script_id)
            except Script.DoesNotExist:
                return Response({"error": f"Script with id {script_id} not found"}, status=status.HTTP_404_NOT_FOUND)
            serializer = ScriptSerializer(script)
            return Response(serializer.data)
        else:
            scripts = Script.objects.all()
            serializer = ScriptSerializer(scripts, many=True)
            return Response(serializer.data)

    def post(self, request):
        serializer = ScriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        script_id = request.query_params.get("id") or request.data.get("id")
        if not script_id:
            return Response({"error": "id is required for update"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            script = Script.objects.get(pk=script_id)
        except Script.DoesNotExist:
            return Response({"error": f"Script with id {script_id} not found"}, status=status.HTTP_404_NOT_FOUND,)
        serializer = ScriptSerializer(script, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        script_id = request.query_params.get("id") or request.data.get("id")
        if not script_id:
            return Response({"error": "id is required for delete"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            script = Script.objects.get(pk=script_id)
        except Script.DoesNotExist:
            return Response({"error": f"Script with id {script_id} not found"}, status=status.HTTP_404_NOT_FOUND,)
        script.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class TaskLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        process_id = request.query_params.get("process_id") or request.data.get("process_id")
        status_value = request.query_params.get("status") or request.data.get("status")
        task_name = request.query_params.get("task_name") or request.data.get("task_name")
        search = request.query_params.get("search") or request.data.get("search")
        if search is not None:
            try:
                log = TaskLog.objects.filter(
                    Q(id__iexact=search) |            
                    Q(task_name__icontains=search) |    
                    Q(process_id__icontains=search)    
                )
            except TaskLog.DoesNotExist:
                return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
            serializer = TaskLogSerializer(log, many=True)
            return Response(serializer.data)
        if process_id is not None:
            try:
                log = TaskLog.objects.get(process_id=process_id)
            except TaskLog.DoesNotExist:
                return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
            serializer = TaskLogDetailSerializer(log)
            return Response(serializer.data)
        logs = TaskLog.objects.all().order_by('-started_at')
        if status_value is not None:
            logs = logs.filter(status=status_value)
        elif task_name is not None:
            logs = logs.filter(task_name=task_name)
        if not logs.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        paginator = api_settings.DEFAULT_PAGINATION_CLASS()
        result_page = paginator.paginate_queryset(logs, request)
        serializer = TaskLogSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    # def post(self, request):
    #     serializer = TaskLogSerializer(data=request.data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data, status=status.HTTP_201_CREATED)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # def patch(self, request):
    #     id = request.query_params.get("id") or request.data.get("id")
    #     if not id:
    #         return Response({"error": "id is required for update"}, status=status.HTTP_400_BAD_REQUEST,)
    #     try:
    #         log = TaskLog.objects.get(pk=id)
    #     except Script.DoesNotExist:
    #         return Response({"error": f"Script with id {id} not found"}, status=status.HTTP_404_NOT_FOUND,)
    #     serializer = TaskLogSerializer(log, data=request.data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        id = request.query_params.get("id") or request.data.get("id")
        if not id:
            return Response({"error": "id is required for delete"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            log = TaskLog.objects.get(pk=id)
        except Script.DoesNotExist:
            return Response({"error": f"Script with id {id} not found"}, status=status.HTTP_404_NOT_FOUND,)
        log.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# Partner API
class AS2PartnerView(APIView):

    def get(self, request):
        partner_id = request.query_params.get('partner_id') or request.data.get('partner_id')
        if partner_id:
            try:
                partner = AS2Partner.objects.get(id=partner_id)
            except AS2Partner.DoesNotExist:
                return Response({"error": "Partner not found"}, status=status.HTTP_404_NOT_FOUND)
            serializer = AS2PartnerSerializer(partner)
            return Response(serializer.data)
        partners = AS2Partner.objects.all()
        serializer = AS2PartnerSerializer(partners, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AS2PartnerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Agreement API
class AS2AgreementView(APIView):
    def get(self, request):
        agreement_id = request.query_params.get('agreement_id') or request.data.get('agreement_id')
        if agreement_id:
            try:
                agreement = AS2Agreement.objects.get(id=agreement_id)
            except AS2Agreement.DoesNotExist:
                return Response({"error": "Agreement not found"}, status=status.HTTP_404_NOT_FOUND)
            serializer = AS2AgreementSerializer(agreement)
            return Response(serializer.data)
        agreements = AS2Agreement.objects.all()
        serializer = AS2AgreementSerializer(agreements, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AS2AgreementSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

AS2_OUTBOX_DIR = r"E:\python\sftp_project\as2\outbox"
class AS2SendFileView(APIView):
    def post(self, request):
        agreement_id = request.data.get("agreement_id")
        file_path = request.data.get("file_path")  # Path on server

        if not agreement_id:
            return Response({"error": "agreement_id is required"}, status=400)
        if not file_path:
            return Response({"error": "file_path is required"}, status=400)
        if not os.path.exists(file_path):
            return Response({"error": f"File does not exist at {file_path}"}, status=400)

        try:
            agreement = AS2Agreement.objects.select_related("sender", "receiver").get(id=agreement_id)
        except AS2Agreement.DoesNotExist:
            return Response({"error": "Agreement not found"}, status=404)
        agreement.mdn_requested = True
        agreement.mdn_mode = 'sync' 
        agreement.save()
        # Save file to sender's outbound directory
        outbound_dir = os.path.join(AS2_OUTBOX_DIR, agreement.sender.as2_id)
        os.makedirs(outbound_dir, exist_ok=True)
        dest_path = os.path.join(outbound_dir, os.path.basename(file_path))

        shutil.copy(file_path, dest_path)

        return Response({
            "message": f"File queued for sending to {agreement.receiver.as2_id}",
            "path": dest_path
        }, status=202)
