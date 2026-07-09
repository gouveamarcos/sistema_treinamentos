from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="core/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "senha/esqueci/",
        auth_views.PasswordResetView.as_view(
            template_name="core/password_reset_form.html",
            email_template_name="core/emails/password_reset_email.txt",
            subject_template_name="core/emails/password_reset_subject.txt",
            success_url="/senha/email-enviado/",
        ),
        name="password_reset",
    ),
    path(
        "senha/email-enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="core/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "senha/redefinir/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="core/password_reset_confirm.html",
            success_url="/senha/concluida/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "senha/concluida/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="core/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("primeiro-acesso/", views.primeiro_acesso, name="primeiro_acesso"),
    path(
        "certificados/validar/",
        views.validar_certificado,
        name="validar_certificado",
    ),
    path(
        "certificados/<str:codigo>/",
        views.validar_certificado,
        name="validar_certificado_codigo",
    ),
    path(
        "produtos/<int:produto_id>/cursos/",
        views.cursos_por_produto,
        name="cursos_por_produto",
    ),
    path("cursos/<int:curso_id>/", views.curso_detalhe, name="curso_detalhe"),
    path(
        "cursos/<int:curso_id>/etapas/<int:etapa_id>/",
        views.curso_detalhe,
        name="curso_etapa",
    ),
]
