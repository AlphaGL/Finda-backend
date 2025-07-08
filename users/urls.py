from django.urls import path,reverse_lazy
from .views import UserLoginView, RegisterView, logout_user,user_dashboard,UserUpdateView,UserDeleteView
from .forms import CustomPasswordResetForm

# reset password
from django.contrib.auth import views as auth_views
urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', logout_user, name='logout'),
    path('register/', RegisterView.as_view(), name='register'),

    # user dashboard
    path('dashboard/', user_dashboard, name='user_dashboard'),
    path('profile/edit/', UserUpdateView.as_view(), name='user-update'),
    path('profile/delete/', UserDeleteView.as_view(), name='user-delete'),


    # Password reset flow
    path('password_reset/', auth_views.PasswordResetView.as_view(
        form_class=CustomPasswordResetForm,
        template_name='users/password_reset.html',
        email_template_name='users/password_reset_email.html',
        subject_template_name='users/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done')
    ), name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete')
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html'
    ), name='password_reset_complete'),

]