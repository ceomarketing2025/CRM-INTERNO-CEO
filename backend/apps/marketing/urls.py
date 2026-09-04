from django.urls import path
from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.marketing_list, name="list"),
    path("tasks/", views.task_list, name="tasks"),
    path("task/new/", views.task_create, name="task_create"),
    path("task/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("task/<int:pk>/toggle/", views.task_toggle, name="task_toggle"),
    path("google-business/", views.google_business_list, name="google_business_list"),
    path("google-lsa/", views.google_lsa_list, name="google_lsa_list"),
    path("digital-ads/", views.digital_ads_list, name="digital_ads_list"),
    path("project/<int:project_pk>/brief/", views.brief_edit, name="brief_edit"),
    path("project/<int:project_pk>/workspace/", views.workspace, name="workspace"),
    path("project/<int:project_pk>/google-business/", views.google_business, name="google_business"),
    path("project/<int:project_pk>/google-lsa/", views.google_lsa, name="google_lsa"),
    path("project/<int:project_pk>/digital-ads/", views.digital_ads, name="digital_ads"),
    path("project/<int:project_pk>/documents/new/", views.document_add, name="document_add"),
    path("project/<int:project_pk>/review-qr/", views.review_qr, name="review_qr"),
    path("check/<int:pk>/", views.checklist_edit, name="checklist_edit"),
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/new/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/edit/", views.campaign_edit, name="campaign_edit"),
    path("campaigns/<int:pk>/review/", views.campaign_manager_review, name="campaign_manager_review"),
    path("campaigns/<int:pk>/weekly/new/", views.campaign_weekly_report, name="campaign_weekly_report"),
    path("audit/general/", views.social_tracking_list, name="general_audit"),
    path("audit/general/<int:pk>/check/", views.social_tracking_audit, name="general_audit_check"),
    path("social-tracking/", views.social_tracking_list, name="social_tracking"),  # compatibilidad histórica
    path("social-tracking/<int:pk>/audit/", views.social_tracking_audit, name="social_tracking_audit"),
    path("social-tracking/new/", views.social_tracking_create, name="social_tracking_create"),
    path("social-tracking/<int:pk>/edit/", views.social_tracking_edit, name="social_tracking_edit"),
    path("social-plans/", views.social_plan_list, name="social_plans"),
    path("social-plans/new/", views.social_plan_create, name="social_plan_create"),
    path("social-plans/<int:pk>/edit/", views.social_plan_edit, name="social_plan_edit"),
    path("social-plans/<int:plan_pk>/daily/new/", views.social_daily_add, name="social_daily_add"),
]
