from django.contrib.auth.views import LoginView
from django.views.generic import CreateView,DetailView,DeleteView,UpdateView
from django.urls import reverse_lazy
from django.contrib.auth import logout
from django.shortcuts import redirect,render
from .models import CustomUser
from .forms import CustomUserCreationForm
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from main.models import Products, Services
from cloudinary.exceptions import Error as CloudinaryError
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


# ===========================
#  USET LOGIN  VIEW
# ===========================
class UserLoginView(LoginView):
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('home')

    def form_invalid(self, form):
        messages.error(self.request, "Invalid email or password. Please try again.")
        return super().form_invalid(form)

# ===========================
#  USET LOGOUT  VIEW
# ===========================
def logout_user(request):
    logout(request)
    return redirect('login')


# ===========================
#  USET REGISTER  VIEW
# ===========================
class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Registration successful. Please log in.")
        return response


# ===========================
#  EDIT PRODUCT OR SERVICE  VIEW
# ===========================
@login_required
def user_dashboard(request):
    # Get all products (regular and promoted) posted by the logged-in user
    products = Products.objects.filter(user=request.user)
    promoted_products = Products.objects.filter(user=request.user, is_promoted=True)  # Assuming 'is_promoted' field

    # Get all services (regular and promoted) posted by the logged-in user
    services = Services.objects.filter(user=request.user)
    promoted_services = Services.objects.filter(user=request.user, is_promoted=True)  # Assuming 'is_promoted' field

    return render(request, 'users/dashboard.html', {
        'products': products,
        'promoted_products': promoted_products,
        'services': services,
        'promoted_services': promoted_services,
    })


# Update own profile
class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CustomUser
    fields = ['first_name', 'last_name', 'email', 'phone', 'profile']  # Assuming 'profile' is the image field
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_dashboard')

    def get_object(self):
        return self.request.user

    def test_func(self):
        return self.get_object() == self.request.user

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            messages.success(self.request, "Profile updated successfully!")
            return response
        except CloudinaryError as e:
            if "File size too large" in str(e):
                messages.error(self.request, "The uploaded file exceeds the maximum allowed size. Please upload a smaller image.")
            else:
                messages.error(self.request, f"An error occurred: {str(e)}")
            return self.form_invalid(form)
# Delete own profile
class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = CustomUser
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('home')  # Or redirect to homepage

    def get_object(self):
        return self.request.user

    def test_func(self):
        return self.get_object() == self.request.user