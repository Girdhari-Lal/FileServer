from django.urls import path
from core.views import PeriodicTaskAPI, RunTaskByNameView, ScriptCreateView, TaskLogView, AS2AgreementView, AS2PartnerView, AS2SendFileView, ConfigCreateView

urlpatterns = [
    path("schedules/", PeriodicTaskAPI.as_view()),
    path("run-task-by-name/", RunTaskByNameView.as_view()),
    path("scripts/", ScriptCreateView.as_view()),
    path("tasklogs/", TaskLogView.as_view()),
    path("as2/partners/", AS2PartnerView.as_view()),
    path("as2/agreements/", AS2AgreementView.as_view()),
    path("as2/send-file/", AS2SendFileView.as_view()),
    path('configs/', ConfigCreateView.as_view())
]